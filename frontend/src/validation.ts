import type { Resume } from './types';
import { STEPS, type StepId } from './steps';

// Mirrors the caps in backend/app/schema.py, so the user sees a friendly
// message as they type instead of a 422 at the end.
export const LIMITS = { short: 120, medium: 300, long: 2000 };

export type Errors = Record<string, string>;

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

/**
 * Mirrors the URL rule in backend/app/schema.py: an http(s) address, a
 * mailto:, or a bare domain we can prefix with https://. Anything else would
 * be embedded in the PDF as a clickable link, so the server rejects it — this
 * catches it in the form instead of as a 422 after the user hits Generate.
 */
const URL_LIKE = /^(https?:\/\/|mailto:|[\w.-]+\.[a-z]{2,}(\/|$))/i;

const linkError = 'Enter a web address, e.g. github.com/you — or leave it empty.';

export function validateStep(step: StepId, resume: Resume): Errors {
  const errors: Errors = {};

  if (step === 'contact') {
    const { contact } = resume;
    if (!contact.full_name.trim()) {
      errors['contact.full_name'] = 'Your name is required — it heads the resume.';
    } else if (contact.full_name.length > LIMITS.short) {
      errors['contact.full_name'] = `Keep this under ${LIMITS.short} characters.`;
    }
    if (contact.email && !EMAIL.test(contact.email.trim())) {
      errors['contact.email'] = "That doesn't look like an email address.";
    }
    contact.links.forEach((link, i) => {
      if (link.url.trim() && !URL_LIKE.test(link.url.trim())) {
        errors[`contact.links.${i}.url`] = linkError;
      }
    });
  }

  if (step === 'summary' && resume.summary.length > LIMITS.long) {
    errors['summary'] = `Keep your summary under ${LIMITS.long} characters.`;
  }

  if (step === 'experience') {
    resume.experience.forEach((job, i) => {
      const started = job.title.trim() || job.company.trim() || job.bullets.some((b) => b.trim());
      if (!started) return; // an untouched blank entry is fine — we drop it
      if (!job.title.trim()) errors[`experience.${i}.title`] = 'Job title is required.';
      if (!job.company.trim()) errors[`experience.${i}.company`] = 'Company is required.';
    });
  }

  if (step === 'education') {
    resume.education.forEach((edu, i) => {
      const started = edu.degree.trim() || edu.institution.trim() || edu.grade.trim();
      if (!started) return;
      if (!edu.degree.trim()) errors[`education.${i}.degree`] = 'Degree is required.';
      if (!edu.institution.trim()) {
        errors[`education.${i}.institution`] = 'Institution is required.';
      }
    });
  }

  if (step === 'projects') {
    resume.projects.forEach((project, i) => {
      const started =
        project.name.trim() || project.description.trim() || project.bullets.some((b) => b.trim());
      if (started && !project.name.trim()) {
        errors[`projects.${i}.name`] = 'Project name is required.';
      }
      if (project.url.trim() && !URL_LIKE.test(project.url.trim())) {
        errors[`projects.${i}.url`] = linkError;
      }
    });
  }

  if (step === 'publications') {
    resume.publications.forEach((pub, i) => {
      const started = pub.title.trim() || pub.authors.trim() || pub.venue.trim();
      if (started && !pub.title.trim()) {
        errors[`publications.${i}.title`] = 'Publication title is required.';
      }
      if (pub.url.trim() && !URL_LIKE.test(pub.url.trim())) {
        errors[`publications.${i}.url`] = linkError;
      }
    });
  }

  return errors;
}

/** Every error across the whole form — used to gate the final compile. */
export function validateAll(resume: Resume): Errors {
  return STEPS.reduce<Errors>(
    (all, step) => ({ ...all, ...validateStep(step.id, resume) }),
    {},
  );
}
