import { useMemo, useState } from 'react';
import {
  ContactStep,
  EducationStep,
  ExperienceStep,
  ProjectsStep,
  PublicationsStep,
  SkillsStep,
  SummaryStep,
} from '../components/StepForms';
import { ResumePreview } from '../components/ResumePreview';
import { STEPS, type StepId } from '../steps';
import type { Resume } from '../types';
import { validateStep, type Errors } from '../validation';

const FORMS: Record<StepId, typeof ContactStep> = {
  contact: ContactStep,
  summary: SummaryStep,
  experience: ExperienceStep,
  education: EducationStep,
  skills: SkillsStep,
  projects: ProjectsStep,
  publications: PublicationsStep,
};

interface Props {
  resume: Resume;
  setResume: (updater: (current: Resume) => Resume) => void;
  savedAt: Date | null;
  onFinish: () => void;
  onBack: () => void;
}

export function FormWizard({ resume, setResume, savedAt, onFinish, onBack }: Props) {
  const [index, setIndex] = useState(0);
  // Errors show as the user types, but only for steps they've tried to leave —
  // flagging an empty form on arrival is hostile.
  const [touched, setTouched] = useState<Set<StepId>>(new Set());

  const step = STEPS[index];
  const StepForm = FORMS[step.id];

  const errors: Errors = useMemo(
    () => (touched.has(step.id) ? validateStep(step.id, resume) : {}),
    [touched, step.id, resume],
  );

  const patch = (changes: Partial<Resume>) =>
    setResume((current) => ({ ...current, ...changes }));

  const goTo = (target: number) => {
    setTouched((t) => new Set(t).add(step.id));
    if (Object.keys(validateStep(step.id, resume)).length > 0 && target > index) return;
    setIndex(Math.max(0, Math.min(STEPS.length - 1, target)));
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const finish = () => {
    setTouched(new Set(STEPS.map((s) => s.id)));
    if (Object.keys(validateStep(step.id, resume)).length > 0) return;
    onFinish();
  };

  const blocked = touched.has(step.id) && Object.keys(errors).length > 0;

  return (
    <div className="wizard">
      <div className="wizard__main">
        <nav className="progress" aria-label="Form progress">
          <p className="progress__label">
            Step {index + 1} of {STEPS.length}
            {savedAt && <span className="progress__saved">· saved in this browser</span>}
          </p>
          <ol className="progress__steps">
            {STEPS.map((s, i) => (
              <li key={s.id}>
                <button
                  className={`progress__step${i === index ? ' is-current' : ''}${
                    i < index ? ' is-done' : ''
                  }`}
                  aria-current={i === index ? 'step' : undefined}
                  onClick={() => goTo(i)}
                >
                  {s.label}
                </button>
              </li>
            ))}
          </ol>
        </nav>

        <section className="wizard__step">
          <h2>
            {step.label}
            {step.optional && <span className="field__optional">optional</span>}
          </h2>
          <StepForm resume={resume} errors={errors} patch={patch} />
        </section>

        <div className="wizard__nav">
          <button
            className="btn btn--ghost"
            onClick={() => (index === 0 ? onBack() : goTo(index - 1))}
          >
            ← Back
          </button>
          {blocked && <p className="notice notice--inline">Fix the highlighted fields to continue.</p>}
          {index < STEPS.length - 1 ? (
            <button className="btn btn--primary" onClick={() => goTo(index + 1)}>
              Next: {STEPS[index + 1].label} →
            </button>
          ) : (
            <button className="btn btn--primary" onClick={finish}>
              Review and generate →
            </button>
          )}
        </div>
      </div>

      <aside className="wizard__preview" aria-label="Live preview">
        <p className="wizard__preview-label">Preview — approximate layout</p>
        <ResumePreview resume={resume} />
      </aside>
    </div>
  );
}
