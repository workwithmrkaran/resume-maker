import { Suspense, lazy, useEffect, useRef, useState } from 'react';
import { ResumePreview } from '../components/ResumePreview';
// pdf.js is ~400kB and is only needed once a PDF actually exists, so it is
// split out of the initial bundle rather than taxing every first visit.
const PdfViewer = lazy(() =>
  import('../components/PdfViewer').then((m) => ({ default: m.PdfViewer })),
);
import { absoluteUrl, fetchJob, startCompile } from '../api';
import type { JobStatus, Resume } from '../types';
import { validateAll } from '../validation';

const POLL_INTERVAL_MS = 800;
const POLL_TIMEOUT_MS = 90_000;

interface Props {
  resume: Resume;
  templateId: string;
  onEdit: () => void;
}

export function ReviewAndDownload({ resume, templateId, onEdit }: Props) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const cancelled = useRef(false);

  // Stop polling once this screen goes away. The flag is reset on mount
  // because StrictMode mounts, unmounts and remounts in development — without
  // the reset the cleanup would leave polling permanently disabled.
  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const problems = Object.entries(validateAll(resume));

  const generate = async () => {
    setBusy(true);
    setError(null);
    setJob(null);
    try {
      const started = await startCompile(resume, templateId);
      setJob(started);
      await poll(started.job_id);
    } catch (e) {
      setError((e as Error).message);
      setBusy(false);
    }
  };

  const poll = async (jobId: string) => {
    const deadline = Date.now() + POLL_TIMEOUT_MS;
    while (!cancelled.current && Date.now() < deadline) {
      await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));
      let status: JobStatus;
      try {
        status = await fetchJob(jobId);
      } catch (e) {
        setError((e as Error).message);
        setBusy(false);
        return;
      }
      if (cancelled.current) return;
      setJob(status);
      if (status.status === 'done') {
        setBusy(false);
        return;
      }
      if (status.status === 'error') {
        setError(status.message);
        setBusy(false);
        return;
      }
    }
    if (!cancelled.current) {
      setError("This is taking longer than expected. Please try generating again.");
      setBusy(false);
    }
  };

  return (
    <div className="screen review">
      <header className="screen__header">
        <h2>Review your resume</h2>
        <p className="muted">
          This is a close approximation of the final layout. Generate the PDF when it looks right.
        </p>
      </header>

      {problems.length > 0 && (
        <div className="notice notice--error">
          <p>A few fields still need attention before we can generate the PDF:</p>
          <ul>
            {problems.map(([field, message]) => (
              <li key={field}>{message}</li>
            ))}
          </ul>
          <button className="btn btn--secondary" onClick={onEdit}>
            Go back to the form
          </button>
        </div>
      )}

      <div className="review__actions">
        <button className="btn btn--ghost" onClick={onEdit}>
          ← Edit details
        </button>
        <button
          className="btn btn--primary btn--large"
          onClick={generate}
          disabled={busy || problems.length > 0}
        >
          {busy ? 'Generating…' : 'Generate PDF'}
        </button>
      </div>

      {/* Honest status text, not a bare spinner — compiles take a few seconds. */}
      {busy && job && (
        <p className="notice notice--status" role="status">
          <span className="spinner" aria-hidden="true" />
          {job.message}
        </p>
      )}

      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
          <button className="btn btn--secondary" onClick={generate}>
            Try again
          </button>
        </div>
      )}

      {job?.status === 'done' && job.download_url && (
        <div className="notice notice--success">
          <p>Your resume is ready.</p>
          <div className="review__downloads">
            <a
              className="btn btn--primary btn--large"
              href={absoluteUrl(job.download_url)}
              download
            >
              Download PDF
            </a>
            <a
              className="btn btn--ghost"
              href={`${absoluteUrl(job.download_url)}?inline=true`}
              target="_blank"
              rel="noreferrer"
            >
              Open in a new tab
            </a>
          </div>
          <p className="muted">
            The link works for the next hour, after which we delete the file from our servers. Your
            details stay saved in this browser so you can come back and regenerate.
          </p>
        </div>
      )}

      {/* Once a PDF exists, show the real thing rather than the approximation —
          no more guessing whether the typeset output matches the preview. */}
      {job?.status === 'done' && job.download_url ? (
        <div className="review__pdf">
          <p className="review__pdf-label">Your compiled PDF</p>
          <Suspense fallback={<p className="muted">Loading the preview…</p>}>
            <PdfViewer
              url={`${absoluteUrl(job.download_url)}?inline=true`}
              fallbackHref={`${absoluteUrl(job.download_url)}?inline=true`}
            />
          </Suspense>
        </div>
      ) : (
        <div className="review__preview">
          <ResumePreview resume={resume} />
        </div>
      )}
    </div>
  );
}
