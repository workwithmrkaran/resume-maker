export function Landing({ onStart, onResume, hasDraft }: {
  onStart: () => void;
  onResume: () => void;
  hasDraft: boolean;
}) {
  return (
    <div className="landing">
      <div className="landing__copy">
        <p className="eyebrow">Free · No signup · No paywall</p>
        <h1>A professional resume, typeset properly, in one sitting.</h1>
        <p className="lede">
          Fill in a guided form and get back a clean, ATS-friendly PDF built from a real LaTeX
          template. No LaTeX knowledge needed, no account, and nothing to pay — now or later.
        </p>
        <div className="landing__actions">
          <button className="btn btn--primary btn--large" onClick={onStart}>
            Build my resume
          </button>
          {hasDraft && (
            <button className="btn btn--ghost" onClick={onResume}>
              Continue where I left off
            </button>
          )}
        </div>
        <ul className="landing__points">
          <li>Typeset with LaTeX — the format hiring committees are used to reading.</li>
          <li>Your details stay in your browser until you press Generate.</li>
          <li>Generated PDFs are deleted from our servers within the hour.</li>
        </ul>
      </div>
      <figure className="landing__preview" aria-hidden="true">
        <div className="mock">
          <div className="mock__name" />
          <div className="mock__line mock__line--sub" />
          {['Summary', 'Experience', 'Education', 'Skills'].map((section) => (
            <div className="mock__section" key={section}>
              <div className="mock__heading">{section}</div>
              <div className="mock__line" />
              <div className="mock__line" />
              <div className="mock__line mock__line--short" />
            </div>
          ))}
        </div>
      </figure>
    </div>
  );
}
