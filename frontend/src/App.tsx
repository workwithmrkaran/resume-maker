import { useState } from 'react';
import { Landing } from './screens/Landing';
import { TemplateGallery } from './screens/TemplateGallery';
import { ChoosePath } from './screens/ChoosePath';
import { FormWizard } from './screens/FormWizard';
import { ReviewAndDownload } from './screens/ReviewAndDownload';
import { useAutosavedResume } from './useAutosave';
import type { Resume } from './types';
import './styles.css';

type Screen = 'landing' | 'templates' | 'path' | 'form' | 'review';

export default function App() {
  const [screen, setScreen] = useState<Screen>('landing');
  const [templateId, setTemplateId] = useState<string | null>(null);
  const { resume, setResume, savedAt, clear, hasDraft } = useAutosavedResume();

  const update = (updater: (current: Resume) => Resume) => setResume(updater(resume));

  const startOver = () => {
    if (!window.confirm('Clear the resume you have in progress? This cannot be undone.')) return;
    clear();
    setScreen('landing');
  };

  return (
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

        {screen === 'path' && <ChoosePath onManual={() => setScreen('form')} />}

        {screen === 'form' && (
          <FormWizard
            resume={resume}
            setResume={update}
            savedAt={savedAt}
            onBack={() => setScreen('path')}
            onFinish={() => setScreen('review')}
          />
        )}

        {screen === 'review' && (
          <ReviewAndDownload
            resume={resume}
            templateId={templateId ?? 'classic'}
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
  );
}
