/**
 * Two entry paths. The upload path is Phase 2 — shown but disabled, so the
 * screen doesn't need rebuilding when it ships.
 */
export function ChoosePath({ onManual }: { onManual: () => void }) {
  return (
    <div className="screen">
      <header className="screen__header">
        <h2>How would you like to start?</h2>
      </header>
      <div className="paths">
        <button className="path" onClick={onManual}>
          <h3>Fill it in myself</h3>
          <p>A guided form, one section at a time. Takes about 15 minutes.</p>
          <span className="path__cta">Start the form →</span>
        </button>

        <div className="path path--disabled" aria-disabled="true">
          <span className="badge">Coming soon</span>
          <h3>I already have a resume</h3>
          <p>
            Upload a PDF or Word file and we'll read your details into the form for you to check
            and edit.
          </p>
        </div>
      </div>
    </div>
  );
}
