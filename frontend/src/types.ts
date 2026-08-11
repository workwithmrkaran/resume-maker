// Mirrors the backend's canonical schema (backend/app/schema.py). Keep the two
// in step: the API rejects unknown fields, so a drift here surfaces as a 422.

export interface Link {
  label: string;
  url: string;
}

export interface Contact {
  full_name: string;
  headline: string;
  email: string | null;
  phone: string;
  location: string;
  links: Link[];
}

export interface Experience {
  title: string;
  company: string;
  location: string;
  start_date: string;
  end_date: string;
  bullets: string[];
}

export interface Education {
  degree: string;
  institution: string;
  location: string;
  start_date: string;
  end_date: string;
  grade: string;
  details: string;
}

export interface SkillGroup {
  category: string;
  skills: string[];
}

export interface Project {
  name: string;
  role: string;
  url: string;
  start_date: string;
  end_date: string;
  description: string;
  bullets: string[];
}

export interface Publication {
  title: string;
  authors: string;
  venue: string;
  year: string;
  url: string;
}

export interface Resume {
  contact: Contact;
  summary: string;
  experience: Experience[];
  education: Education[];
  skills: SkillGroup[];
  projects: Project[];
  publications: Publication[];
}

export interface Template {
  id: string;
  name: string;
  description: string;
  best_for: string;
  preview_url: string;
  preview_pdf_url: string;
}

export type JobState = 'queued' | 'running' | 'done' | 'error';

export interface JobStatus {
  job_id: string;
  status: JobState;
  message: string;
  download_url: string | null;
}

export const emptyExperience = (): Experience => ({
  title: '',
  company: '',
  location: '',
  start_date: '',
  end_date: '',
  bullets: [''],
});

export const emptyEducation = (): Education => ({
  degree: '',
  institution: '',
  location: '',
  start_date: '',
  end_date: '',
  grade: '',
  details: '',
});

export const emptySkillGroup = (): SkillGroup => ({ category: '', skills: [] });

export const emptyProject = (): Project => ({
  name: '',
  role: '',
  url: '',
  start_date: '',
  end_date: '',
  description: '',
  bullets: [''],
});

export const emptyPublication = (): Publication => ({
  title: '',
  authors: '',
  venue: '',
  year: '',
  url: '',
});

export const emptyResume = (): Resume => ({
  contact: {
    full_name: '',
    headline: '',
    email: '',
    phone: '',
    location: '',
    links: [],
  },
  summary: '',
  experience: [emptyExperience()],
  education: [emptyEducation()],
  skills: [emptySkillGroup()],
  projects: [],
  publications: [],
});
