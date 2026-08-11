import { useEffect, useState } from 'react';
import { absoluteUrl, fetchTemplates } from '../api';
import type { Template } from '../types';

/**
 * Phase 1 ships one template, but this is already a gallery grid: Phase 3 adds
 * cards to the API response and this screen needs no changes.
 */
export function TemplateGallery({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (templateId: string) => void;
}) {
  const [templates, setTemplates] = useState<Template[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch((e: Error) => setError(e.message));
  }, []);

  if (error) {
    return (
      <div className="screen">
        <p className="notice notice--error">{error}</p>
      </div>
    );
  }

  return (
    <div className="screen">
      <header className="screen__header">
        <h2>Choose a format</h2>
        <p className="muted">More formats are on the way. Each one uses the same details, so you'll
          be able to switch without retyping anything.</p>
      </header>

      {templates === null ? (
        <p className="muted">Loading formats…</p>
      ) : (
        <div className="gallery">
          {templates.map((template) => (
            <article
              key={template.id}
              className={`card${selected === template.id ? ' card--selected' : ''}`}
            >
              <a
                className="card__preview"
                href={absoluteUrl(template.preview_pdf_url)}
                target="_blank"
                rel="noreferrer"
                title={`Open the full ${template.name} sample PDF`}
              >
                <img src={absoluteUrl(template.preview_url)} alt={`${template.name} sample resume`} />
              </a>
              <div className="card__body">
                <h3>{template.name}</h3>
                <p>{template.description}</p>
                <p className="muted">{template.best_for}</p>
                <button className="btn btn--primary" onClick={() => onSelect(template.id)}>
                  Use this format
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
