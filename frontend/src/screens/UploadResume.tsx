import { useEffect, useRef, useState } from 'react';
import { fetchJob, startExtraction } from '../api';
import type { JobStatus, Resume } from '../types';

const POLL_INTERVAL_MS = 900;
const POLL_TIMEOUT_MS = 120_000;
const MAX_BYTES = 5 * 1024 * 1024;

interface Props {
  onExtracted: (resume: Resume, job: JobStatus) => void;
  onManual: () => void;
  onBack: () => void;
}

export function UploadResume({ onExtracted, onManual, onBack }: Props) {
  const [job, setJob] = useState<JobStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [dragging, setDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const cancelled = useRef(false);

  useEffect(() => {
    cancelled.current = false;
    return () => {
      cancelled.current = true;
    };
  }, []);

  const upload = async (file: File) => {
    setError(null);
    if (file.size > MAX_BYTES) {
      setError('That file is larger than 5 MB. Try exporting a smaller PDF.');
      return;
    }
    setBusy(true);
    try {
      const started = await startExtraction(file);
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
      if (status.status === 'done' && status.resume) {
        setBusy(false);
        onExtracted(status.resume, status);
        return;
      }
      if (status.status === 'error') {
        // The API's message is already plain language written for the user.
        setError(status.message);
        setBusy(false);
        return;
      }
    }
    if (!cancelled.current) {
      setError('This is taking longer than expected. Please try again.');
      setBusy(false);
    }
  };

  const onDrop = (event: React.DragEvent) => {
    event.preventDefault();
    setDragging(false);
    const file = event.dataTransfer.files?.[0];
    if (file) void upload(file);
  };

  return (
    <div className="screen">
      <header className="screen__header">
        <h2>Upload your resume</h2>
        <p className="muted">
          We'll read it into the form so you can check and edit it, then generate a fresh PDF.
        </p>
      </header>

      <div
        className={`dropzone${dragging ? ' dropzone--active' : ''}`}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
          className="dropzone__input"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) void upload(file);
            e.target.value = ''; // let the same file be picked again after an error
          }}
        />
        <p className="dropzone__title">Drag a file here</p>
        <p className="muted">PDF or Word (.docx), up to 5 MB</p>
        <button
          className="btn btn--primary"
          disabled={busy}
          onClick={() => inputRef.current?.click()}
        >
          {busy ? 'Reading…' : 'Choose a file'}
        </button>
      </div>

      {/* The plan requires saying plainly what happens to an uploaded resume,
          on the screen where it's uploaded — not buried in a policy page. */}
      <p className="muted upload__privacy">
        Your file is read once, in memory, to fill in the form. We don't store it, and the text
        is sent to an AI model only for that extraction. Everything you see afterwards stays in
        your browser until you generate a PDF.
      </p>

      {busy && job && (
        <p className="notice notice--status" role="status">
          <span className="spinner" aria-hidden="true" />
          {job.message}
        </p>
      )}

      {error && (
        <div className="notice notice--error" role="alert">
          <p>{error}</p>
          <button className="btn btn--secondary" onClick={onManual}>
            Fill the form in instead
          </button>
        </div>
      )}

      <div className="review__actions">
        <button className="btn btn--ghost" onClick={onBack}>
          ← Back
        </button>
        <button className="btn btn--ghost" onClick={onManual}>
          Skip — I'll type it myself
        </button>
      </div>
    </div>
  );
}
