/**
 * Two entry paths: type it in, or upload an existing resume and edit what the
 * AI extracted. Both land in the same form.
 */
export function ChoosePath({ onManual, onUpload, uploadEnabled }: {
  onManual: () => void;
  onUpload: () => void;
  uploadEnabled: boolean;
}) {
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

        {uploadEnabled ? (
          <button className="path" onClick={onUpload}>
            <h3>I already have a resume</h3>
            <p>
              Upload a PDF or Word file and we'll read your details into the form for you to
              check and edit.
            </p>
            <span className="path__cta">Upload a file →</span>
          </button>
        ) : (
          /* Extraction needs a configured model provider; without one the card
             stays visible but honest rather than failing on click. */
          <div className="path path--disabled" aria-disabled="true">
            <span className="badge">Unavailable</span>
            <h3>I already have a resume</h3>
            <p>Resume reading is switched off on this server. The manual form works as normal.</p>
          </div>
        )}
      </div>
    </div>
  );
}
