import type { JobStatus, Resume, Template } from './types';

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json' },
      ...init,
    });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    // The API returns { error }; anything else means an unexpected failure,
    // and either way the user gets plain language rather than internals.
    const body = await response.json().catch(() => null);
    throw new ApiError(
      body?.error ?? 'Something went wrong. Please try again.',
      response.status,
    );
  }
  return response.json() as Promise<T>;
}

export interface Health {
  status: string;
  engine_available: boolean;
  extraction_enabled: boolean;
}

export const fetchHealth = () => request<Health>('/api/health');

export const fetchTemplates = () =>
  request<{ templates: Template[] }>('/api/templates').then((r) => r.templates);

export const startCompile = (resume: Resume, templateId: string) =>
  request<JobStatus>('/api/compile', {
    method: 'POST',
    body: JSON.stringify({ template_id: templateId, resume: forApi(resume) }),
  });

export const fetchJob = (jobId: string) => request<JobStatus>(`/api/jobs/${jobId}`);

/**
 * Upload a resume for AI extraction.
 *
 * No `Content-Type` header: the browser must set the multipart boundary
 * itself, and overriding it breaks the upload.
 */
export async function startExtraction(file: File): Promise<JobStatus> {
  const body = new FormData();
  body.append('file', file);
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/api/extract`, { method: 'POST', body });
  } catch {
    throw new ApiError("We couldn't reach the server. Check your connection and try again.", 0);
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new ApiError(
      payload?.error ?? "We couldn't read that file. Please try another.",
      response.status,
    );
  }
  return response.json() as Promise<JobStatus>;
}

export const absoluteUrl = (path: string) => `${API_BASE}${path}`;

/**
 * Strip the form's empty scaffolding rows before sending.
 *
 * The form keeps blank entries around so the user has something to type into;
 * the API would reject them (a work entry needs a title and a company).
 */
export function forApi(resume: Resume): Resume {
  const filled = (...values: string[]) => values.some((v) => v.trim() !== '');
  return {
    contact: {
      ...resume.contact,
      email: resume.contact.email?.trim() ? resume.contact.email.trim() : null,
      links: resume.contact.links.filter((l) => filled(l.url)),
    },
    summary: resume.summary,
    experience: resume.experience
      .filter((e) => filled(e.title, e.company))
      .map((e) => ({ ...e, bullets: e.bullets.filter((b) => b.trim() !== '') })),
    education: resume.education.filter((e) => filled(e.degree, e.institution)),
    skills: resume.skills
      .map((g) => ({ ...g, skills: g.skills.filter((s) => s.trim() !== '') }))
      .filter((g) => g.skills.length > 0),
    projects: resume.projects
      .filter((p) => filled(p.name))
      .map((p) => ({ ...p, bullets: p.bullets.filter((b) => b.trim() !== '') })),
    publications: resume.publications.filter((p) => filled(p.title)),
  };
}
