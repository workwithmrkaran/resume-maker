# The API and the TeX engine ship in one image, and the image itself is the
# sandbox: unprivileged user, read-only root filesystem (see compose), and no
# outbound network needed at runtime.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DEBIAN_FRONTEND=noninteractive

# texlive-latex-extra supplies titlesec/enumitem; lmodern supplies the Type1
# fonts the template needs (without it pdflatex falls back to slow bitmap
# fonts); poppler-utils rasterises template thumbnails.
# --no-install-recommends keeps the image from pulling all of TeX Live.
RUN apt-get update && apt-get install -y --no-install-recommends \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        lmodern \
        poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p /var/tmp/resume-pdfs \
    && chown appuser:appuser /var/tmp/resume-pdfs
USER appuser

ENV PDF_STORE_DIR=/var/tmp/resume-pdfs \
    COMPILE_BACKEND=subprocess \
    LATEX_ENGINE=pdflatex

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
