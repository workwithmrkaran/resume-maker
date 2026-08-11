import type { Resume } from './types';
import { STEPS, type StepId } from './steps';

// Mirrors the caps in backend/app/schema.py, so the user sees a friendly
// message as they type instead of a 422 at the end.
export const LIMITS = { short: 120, medium: 300, long: 2000 };

export type Errors = Record<string, string>;

const EMAIL = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

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
      if (link.url.trim() && !/^(https?:\/\/|mailto:|[\w.-]+\.[a-z]{2,})/i.test(link.url.trim())) {
        errors[`contact.links.${i}.url`] = 'Enter a web address, e.g. github.com/you';
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
    });
  }

  if (step === 'publications') {
    resume.publications.forEach((pub, i) => {
      const started = pub.title.trim() || pub.authors.trim() || pub.venue.trim();
      if (started && !pub.title.trim()) {
        errors[`publications.${i}.title`] = 'Publication title is required.';
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
