/**
 * Renders a PDF in the page, using pdf.js.
 *
 * The obvious approach — `<object type="application/pdf">` — depends on the
 * browser having a built-in viewer. Chrome and Firefox do; plenty of setups
 * don't, and headless browsers show a black rectangle. Since the whole point
 * of this screen is "see exactly what you're about to download", it can't be
 * left to chance: pdf.js draws the pages to canvases and looks identical
 * everywhere.
 *
 * The worker is bundled locally (Vite `?url` import), not fetched from a CDN.
 *
 * pdfjs-dist is pinned to the v4 line on purpose: v5/v6 use very new JS
 * built-ins (`Map.prototype.getOrInsertComputed`) that throw on browsers only
 * a version or two old, which defeats the point of rendering it ourselves.
 */
import { useEffect, useRef, useState } from 'react';
import * as pdfjs from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

// Cap the backing-store resolution: on a 3x display a full-page canvas at
// devicePixelRatio is enormous, and the extra pixels aren't visible.
const MAX_SCALE = 2;

interface Props {
  url: string;
  /** Rendered width in CSS pixels; pages scale to fit. */
  width?: number;
  fallbackHref?: string;
}

export function PdfViewer({ url, width = 900, fallbackHref }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [pages, setPages] = useState(0);

  useEffect(() => {
    let cancelled = false;
    const container = containerRef.current;
    if (!container) return;

    const render = async () => {
      setError(null);
      container.replaceChildren();
      try {
        const doc = await pdfjs.getDocument({ url }).promise;
        if (cancelled) return;
        setPages(doc.numPages);

        const scale = Math.min(window.devicePixelRatio || 1, MAX_SCALE);
        for (let pageNumber = 1; pageNumber <= doc.numPages; pageNumber += 1) {
          const page = await doc.getPage(pageNumber);
          if (cancelled) return;

          const unscaled = page.getViewport({ scale: 1 });
          const viewport = page.getViewport({ scale: (width / unscaled.width) * scale });

          const canvas = document.createElement('canvas');
          canvas.className = 'pdf-page';
          canvas.width = Math.floor(viewport.width);
          canvas.height = Math.floor(viewport.height);
          canvas.style.width = '100%';
          canvas.style.height = 'auto';
          canvas.setAttribute('role', 'img');
          canvas.setAttribute('aria-label', `Resume page ${pageNumber} of ${doc.numPages}`);

          const context = canvas.getContext('2d');
          if (!context) throw new Error('canvas unavailable');
          container.append(canvas);
          await page.render({ canvasContext: context, viewport }).promise;
        }
      } catch (e) {
        if (!cancelled) {
          console.error('pdf render failed', e);
          setError((e as Error).message || 'could not render');
        }
      }
    };

    void render();
    return () => {
      cancelled = true;
    };
  }, [url, width]);

  return (
    <div className="pdf-viewer">
      <div ref={containerRef} className="pdf-viewer__pages" />
      {pages > 1 && <p className="muted pdf-viewer__count">{pages} pages</p>}
      {error && (
        <p className="muted">
          Couldn't display the PDF here.{' '}
          <a href={fallbackHref ?? url} target="_blank" rel="noreferrer">
            Open it in a new tab
          </a>{' '}
          instead — the download works either way.
        </p>
      )}
    </div>
  );
}
