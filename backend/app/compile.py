"""Sandboxed LaTeX compilation.

Two backends, chosen with ``COMPILE_BACKEND``:

``subprocess`` (default)
    Runs the local TeX engine directly. Intended for the container image in
    ``backend/Dockerfile``, which *is* the sandbox: the whole service runs
    unprivileged with no outbound network.

``docker``
    Spawns a throwaway, network-isolated container per compile. Use this when
    the API itself runs somewhere less locked down.

Either way the same hard limits apply: shell-escape off, a wall-clock timeout,
and CPU/memory/file-size caps.

Windows note: the OS has no `RLIMIT_*` equivalent, so on Windows the engine
runs with shell-escape off and a wall-clock timeout, but WITHOUT the memory,
CPU and file-size caps. That is fine for local development and NOT acceptable
for a public deployment — ship the container, or set COMPILE_BACKEND=docker.
`sandbox_status()` reports which limits are actually in force.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

IS_WINDOWS = sys.platform == "win32"

if not IS_WINDOWS:
    import resource  # POSIX only; guarded so the app imports on Windows

log = logging.getLogger(__name__)

COMPILE_BACKEND = os.getenv("COMPILE_BACKEND", "subprocess")
LATEX_ENGINE = os.getenv("LATEX_ENGINE", "pdflatex")
DOCKER_IMAGE = os.getenv("COMPILE_DOCKER_IMAGE", "resume-maker-latex")

TIMEOUT_SECONDS = int(os.getenv("COMPILE_TIMEOUT", "20"))
MEMORY_LIMIT_BYTES = int(os.getenv("COMPILE_MEMORY_MB", "512")) * 1024 * 1024
OUTPUT_LIMIT_BYTES = int(os.getenv("COMPILE_OUTPUT_MB", "20")) * 1024 * 1024
# pdflatex resolves cross-references (and our tabularx widths) on a second
# pass. Two runs is enough for this template family.
PASSES = 2


class CompileError(Exception):
    """Compilation failed. ``log_excerpt`` is for our logs, never the user."""

    def __init__(self, message: str, log_excerpt: str = ""):
        super().__init__(message)
        self.log_excerpt = log_excerpt


@dataclass
class CompileResult:
    pdf_bytes: bytes
    passes: int


def compile_pdf(tex_source: str) -> CompileResult:
    """Compile LaTeX source to PDF bytes, or raise :class:`CompileError`."""
    workdir = Path(tempfile.mkdtemp(prefix="resume-compile-"))
    try:
        tex_path = workdir / "resume.tex"
        tex_path.write_text(tex_source, encoding="utf-8")

        last_log = ""
        for _ in range(PASSES):
            if COMPILE_BACKEND == "docker":
                code, output = _run_docker(workdir)
            else:
                code, output = _run_subprocess(workdir)
            last_log = output
            if code != 0:
                break

        pdf_path = workdir / "resume.pdf"
        if not pdf_path.exists() or pdf_path.stat().st_size == 0:
            raise CompileError("PDF generation failed", _log_excerpt(workdir, last_log))

        size = pdf_path.stat().st_size
        if size > OUTPUT_LIMIT_BYTES:
            raise CompileError(f"Generated PDF too large ({size} bytes)")

        return CompileResult(pdf_bytes=pdf_path.read_bytes(), passes=PASSES)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def _engine_argv(workdir: Path) -> list[str]:
    """Argv for one engine pass.

    The input is named relatively: the process runs with ``cwd=workdir`` and
    ``openin_any=p``, which refuses absolute paths.
    """
    if LATEX_ENGINE == "tectonic":
        return [
            "tectonic", "-X", "compile",
            "--outdir", ".",
            "--keep-logs",
            "--untrusted",  # refuses shell-escape and other unsafe features
            "resume.tex",
        ]
    return [
        LATEX_ENGINE,
        "-no-shell-escape",
        "-interaction=nonstopmode",
        "-halt-on-error",
        "-file-line-error",
        "-output-directory=.",
        "resume.tex",
    ]


def _limits() -> None:
    """Applied in the child process between fork and exec (POSIX only)."""
    resource.setrlimit(resource.RLIMIT_AS, (MEMORY_LIMIT_BYTES, MEMORY_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_CPU, (TIMEOUT_SECONDS, TIMEOUT_SECONDS))
    resource.setrlimit(resource.RLIMIT_FSIZE, (OUTPUT_LIMIT_BYTES, OUTPUT_LIMIT_BYTES))
    resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
    os.setsid()  # so a timeout kill takes any children with it


def sandbox_status() -> dict:
    """What protections are actually active, for /api/health and the logs."""
    return {
        "platform": sys.platform,
        "shell_escape_disabled": True,
        "timeout_seconds": TIMEOUT_SECONDS,
        # The only difference between platforms, stated rather than implied.
        "resource_limits": not IS_WINDOWS,
    }


def _run_subprocess(workdir: Path) -> tuple[int, str]:
    env = {
        "PATH": os.getenv("PATH", "/usr/bin:/bin"),
        "HOME": str(workdir),
        "TEXMFVAR": str(workdir / ".texmf-var"),
        "TEXMFHOME": str(workdir / ".texmf-home"),
        "SOURCE_DATE_EPOCH": "0",  # reproducible output, no clock leakage
        "openout_any": "p",        # no writing outside the working directory
        "openin_any": "p",
        "shell_escape": "f",
    }
    if IS_WINDOWS:
        # MiKTeX and TeX Live for Windows resolve their installation through
        # these; a stripped environment leaves the engine unable to find its
        # own files.
        for name in ("SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE",
                     "APPDATA", "LOCALAPPDATA", "PATHEXT", "COMSPEC"):
            value = os.getenv(name)
            if value:
                env[name] = value

    extra: dict = {}
    if IS_WINDOWS:
        # No fork, so no preexec_fn. A separate process group at least lets the
        # timeout kill signal reach the engine cleanly.
        extra["creationflags"] = getattr(
            subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        extra["preexec_fn"] = _limits

    try:
        proc = subprocess.run(
            _engine_argv(workdir),
            cwd=workdir,
            env=env,
            capture_output=True,
            timeout=TIMEOUT_SECONDS,
            check=False,
            **extra,
        )
    except subprocess.TimeoutExpired:
        raise CompileError("Compilation timed out") from None
    except FileNotFoundError:
        raise CompileError(f"LaTeX engine '{LATEX_ENGINE}' is not installed") from None
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def _run_docker(workdir: Path) -> tuple[int, str]:
    argv = [
        "docker", "run", "--rm",
        "--network=none",
        "--read-only",
        f"--memory={MEMORY_LIMIT_BYTES}",
        "--cpus=1",
        "--pids-limit=64",
        "--cap-drop=ALL",
        "--security-opt=no-new-privileges",
    ]
    if not IS_WINDOWS:
        # Keeps the output PDF owned by the calling user. Windows has no uid,
        # and Docker Desktop maps ownership for us anyway.
        argv += ["--user", f"{os.getuid()}:{os.getgid()}"]
    argv += [
        "-v", f"{workdir}:/work",
        "-w", "/work",
        DOCKER_IMAGE,
        LATEX_ENGINE, "-no-shell-escape", "-interaction=nonstopmode",
        "-halt-on-error", "-file-line-error", "resume.tex",
    ]
    try:
        proc = subprocess.run(
            argv, capture_output=True, timeout=TIMEOUT_SECONDS + 10, check=False
        )
    except subprocess.TimeoutExpired:
        raise CompileError("Compilation timed out") from None
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


def _log_excerpt(workdir: Path, stdout: str, max_chars: int = 4000) -> str:
    """Collect the tail of the TeX log for *our* logs.

    Resume content leaks into TeX logs, so callers must keep this out of user
    responses and out of any log sink that retains PII.
    """
    log_file = workdir / "resume.log"
    text = log_file.read_text(encoding="utf-8", errors="replace") if log_file.exists() else stdout
    lines = [ln for ln in text.splitlines() if ln.startswith("!") or "Error" in ln]
    excerpt = "\n".join(lines[-40:]) or text[-max_chars:]
    return excerpt[-max_chars:]


def engine_available() -> bool:
    """Whether the configured engine can actually be invoked (for /health)."""
    if COMPILE_BACKEND == "docker":
        return shutil.which("docker") is not None
    return shutil.which(LATEX_ENGINE) is not None


def render_first_page_png(pdf_bytes: bytes, dpi: int = 110) -> bytes | None:
    """Rasterise page 1 of a PDF, for template thumbnails.

    Returns ``None`` when poppler isn't installed, so the API can degrade to
    the PDF preview rather than failing the whole gallery.
    """
    if shutil.which("pdftoppm") is None:
        return None
    workdir = Path(tempfile.mkdtemp(prefix="resume-thumb-"))
    try:
        src = workdir / "in.pdf"
        src.write_bytes(pdf_bytes)
        proc = subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), "-f", "1", "-l", "1",
             "-singlefile", "in.pdf", "out"],
            cwd=workdir, capture_output=True, timeout=30, check=False,
        )
        out = workdir / "out.png"
        if proc.returncode != 0 or not out.exists():
            log.warning("thumbnail rendering failed: %s",
                        proc.stderr.decode("utf-8", "replace")[:500])
            return None
        return out.read_bytes()
    except subprocess.TimeoutExpired:
        return None
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
