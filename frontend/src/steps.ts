export const STEPS = [
  { id: 'contact', label: 'Contact', optional: false },
  { id: 'summary', label: 'Summary', optional: true },
  { id: 'experience', label: 'Experience', optional: false },
  { id: 'education', label: 'Education', optional: false },
  { id: 'skills', label: 'Skills', optional: false },
  { id: 'projects', label: 'Projects', optional: true },
  { id: 'publications', label: 'Publications', optional: true },
] as const;

export type StepId = (typeof STEPS)[number]['id'];
