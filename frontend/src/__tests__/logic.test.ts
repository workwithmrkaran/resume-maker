import { describe, expect, it } from 'vitest';
import { forApi } from '../api';
import { emptyResume, type Resume } from '../types';
import { validateAll, validateStep } from '../validation';

const withName = (overrides: Partial<Resume> = {}): Resume => ({
  ...emptyResume(),
  contact: { ...emptyResume().contact, full_name: 'Sam Doe' },
  ...overrides,
});

describe('forApi', () => {
  it('drops the blank scaffolding rows the form starts with', () => {
    const payload = forApi(withName());
    expect(payload.experience).toEqual([]);
    expect(payload.education).toEqual([]);
    expect(payload.skills).toEqual([]);
  });

  it('keeps entries the user actually filled in', () => {
    const resume = withName();
    resume.experience[0] = {
      ...resume.experience[0],
      title: 'Engineer',
      company: 'Acme',
      bullets: ['Shipped it', '   ', ''],
    };
    const payload = forApi(resume);
    expect(payload.experience).toHaveLength(1);
    expect(payload.experience[0].bullets).toEqual(['Shipped it']);
  });

  it('sends null rather than an empty string for a missing email', () => {
    expect(forApi(withName()).contact.email).toBeNull();
  });

  it('drops links with no address', () => {
    const resume = withName();
    resume.contact.links = [
      { label: 'GitHub', url: 'github.com/sam' },
      { label: 'Empty', url: '' },
    ];
    expect(forApi(resume).contact.links).toHaveLength(1);
  });
});

describe('validation', () => {
  it('requires a name', () => {
    expect(validateStep('contact', emptyResume())['contact.full_name']).toBeDefined();
  });

  it('accepts a complete contact step', () => {
    expect(validateStep('contact', withName())).toEqual({});
  });

  it('rejects a malformed email', () => {
    const resume = withName();
    resume.contact.email = 'nope';
    expect(validateStep('contact', resume)['contact.email']).toBeDefined();
  });

  it('ignores an untouched blank experience entry', () => {
    expect(validateStep('experience', withName())).toEqual({});
  });

  it('flags a half-filled experience entry', () => {
    const resume = withName();
    resume.experience[0] = { ...resume.experience[0], title: 'Engineer' };
    expect(validateStep('experience', resume)['experience.0.company']).toBeDefined();
  });

  it('reports nothing for a valid resume across all steps', () => {
    expect(validateAll(withName())).toEqual({});
  });
});

describe('link validation', () => {
  const withProjectUrl = (url: string): Resume => {
    const resume = withName();
    resume.projects = [
      { name: 'Thing', role: '', url, start_date: '', end_date: '', description: '', bullets: [] },
    ];
    return resume;
  };

  it.each(['github.com/sam', 'https://example.com/a?b=1&c=2', 'mailto:sam@example.com'])(
    'accepts %s',
    (url) => {
      expect(validateStep('projects', withProjectUrl(url))['projects.0.url']).toBeUndefined();
    },
  );

  it.each(['not a url', 'my project page', 'C:\\Users\\sam\\project'])(
    'rejects %s in the form rather than letting the API 422',
    (url) => {
      expect(validateStep('projects', withProjectUrl(url))['projects.0.url']).toBeDefined();
    },
  );

  it('treats an empty link as fine — the field is optional', () => {
    expect(validateStep('projects', withProjectUrl(''))['projects.0.url']).toBeUndefined();
  });

  it('blocks the whole form so Generate is disabled before the request', () => {
    expect(validateAll(withProjectUrl('not a url'))['projects.0.url']).toBeDefined();
  });
});
