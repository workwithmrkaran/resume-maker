import { useEffect, useState } from 'react';
import { Landing } from './screens/Landing';
import { TemplateGallery } from './screens/TemplateGallery';
import { ChoosePath } from './screens/ChoosePath';
import { UploadResume } from './screens/UploadResume';
import { FormWizard } from './screens/FormWizard';
import { ReviewAndDownload } from './screens/ReviewAndDownload';
import { useAutosavedResume } from './useAutosave';
import { AiFilledProvider } from './aiFilled';
import { fetchHealth, fetchTemplates } from './api';
import type { JobStatus, Resume, Template } from './types';
import './styles.css';

type Screen = 'landing' | 'templates' | 'path' | 'upload' | 'form' | 'review';

export default function App() {
  const [screen, setScreen] = useState<Screen>('landing');
  const [templateId, setTemplateId] = useState<string | null>(null);
  const { resume, setResume, savedAt, clear, hasDraft } = useAutosavedResume();
  // What the AI returned, kept so fields can show an "AI-filled" badge until
  // the user edits them. Never persisted — it's a UI hint, not resume data.
  const [extracted, setExtracted] = useState<Resume | null>(null);
  const [extractionNotes, setExtractionNotes] = useState<string[]>([]);
  const [uploadEnabled, setUploadEnabled] = useState(false);
  const [templates, setTemplates] = useState<Template[]>([]);

  useEffect(() => {
    // The upload path is only offered if the server actually has a model
    // provider configured, so the card can't lead to a dead end.
    fetchHealth()
      .then((health) => setUploadEnabled(health.extraction_enabled))
      .catch(() => setUploadEnabled(false));
    // Fetched here as well as in the gallery, so the review screen's format
    // switcher works even when someone resumes a draft and skips the gallery.
    fetchTemplates().then(setTemplates).catch(() => setTemplates([]));
  }, []);

  const update = (updater: (current: Resume) => Resume) => setResume(updater(resume));

  const startOver = () => {
    if (!window.confirm('Clear the resume you have in progress? This cannot be undone.')) return;
    clear();
    setExtracted(null);
    setExtractionNotes([]);
    setScreen('landing');
  };

  const onExtracted = (extractedResume: Resume, job: JobStatus) => {
    setResume(extractedResume);
    setExtracted(extractedResume);
    setExtractionNotes(
      job.low_confidence
        ? job.warnings
        : ['We filled this in from your upload — please check each field before generating.'],
    );
    setScreen('form');
  };

  return (
    <AiFilledProvider extracted={extracted}>
    <div className="app">
      <header className="topbar">
        <button className="topbar__brand" onClick={() => setScreen('landing')}>
          Resume Maker
        </button>
        <div className="topbar__right">
          <span className="topbar__tag">Free · no signup</span>
          {hasDraft && (
            <button className="btn btn--ghost btn--small" onClick={startOver}>
              Start over
            </button>
          )}
        </div>
      </header>

      <main className="app__main">
        {screen === 'landing' && (
          <Landing
            hasDraft={hasDraft}
            onStart={() => setScreen('templates')}
            onResume={() => {
              setTemplateId((id) => id ?? 'classic');
              setScreen('form');
            }}
          />
        )}

        {screen === 'templates' && (
          <TemplateGallery
            selected={templateId}
            onSelect={(id) => {
              setTemplateId(id);
              setScreen('path');
            }}
          />
        )}

        {screen === 'path' && (
          <ChoosePath
            uploadEnabled={uploadEnabled}
            onManual={() => setScreen('form')}
            onUpload={() => setScreen('upload')}
          />
        )}

        {screen === 'upload' && (
          <UploadResume
            onExtracted={onExtracted}
            onManual={() => setScreen('form')}
            onBack={() => setScreen('path')}
          />
        )}

        {screen === 'form' && (
          <FormWizard
            resume={resume}
            setResume={update}
            savedAt={savedAt}
            notices={extractionNotes}
            onBack={() => setScreen('path')}
            onFinish={() => setScreen('review')}
          />
        )}

        {screen === 'review' && (
          <ReviewAndDownload
            resume={resume}
            templateId={templateId ?? 'classic'}
            templates={templates}
            onTemplateChange={setTemplateId}
            onEdit={() => setScreen('form')}
          />
        )}
      </main>

      <footer className="footer">
        <p>
          Free to use, no account needed. Your details stay in this browser until you generate a
          PDF; generated files are deleted from our servers within the hour.
        </p>
      </footer>
    </div>
    </AiFilledProvider>
  );
}
