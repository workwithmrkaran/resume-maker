/**
 * On-screen approximation of the compiled PDF.
 *
 * Not a real LaTeX render — that takes seconds and can't run per keystroke.
 * The CSS deliberately mirrors the template's structure (centred header,
 * uppercase rules sections, title/date rows) so the final PDF holds no
 * surprises. If you change classic.tex.j2's layout, change this too.
 */
import type { Resume } from '../types';
import { forApi } from '../api';

const dateRange = (start: string, end: string) =>
  [start, end].filter(Boolean).join(' – ');

const displayUrl = (url: string) => url.replace(/^https?:\/\/(www\.)?/, '').replace(/\/$/, '');

export function ResumePreview({ resume }: { resume: Resume }) {
  // Preview exactly what would be sent to the compiler — blank scaffolding
  // rows included in the form must not show up here either.
  const data = forApi(resume);
  const { contact } = data;
  const contactLine = [contact.location, contact.phone].filter(Boolean);

  return (
    <article className="paper" aria-label="Resume preview">
      <header className="paper__header">
        <h1 className="paper__name">{contact.full_name || 'Your name'}</h1>
        {contact.headline && <p className="paper__headline">{contact.headline}</p>}
        <p className="paper__contact">
          {contactLine.map((part) => (
            <span key={part}>{part}</span>
          ))}
          {contact.email && <span>{contact.email}</span>}
          {contact.links.map((link) => (
            <span key={link.url}>{link.label || displayUrl(link.url)}</span>
          ))}
        </p>
      </header>

      {data.summary && (
        <Section title="Summary">
          <p>{data.summary}</p>
        </Section>
      )}

      {data.experience.length > 0 && (
        <Section title="Experience">
          {data.experience.map((job, i) => (
            <div className="paper__entry" key={i}>
              <div className="paper__row">
                <strong>{job.title}</strong>
                <strong>{dateRange(job.start_date, job.end_date)}</strong>
              </div>
              <div className="paper__row paper__row--italic">
                <span>{job.company}</span>
                <span>{job.location}</span>
              </div>
              {job.bullets.length > 0 && (
                <ul>
                  {job.bullets.map((bullet, j) => (
                    <li key={j}>{bullet}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </Section>
      )}

      {data.education.length > 0 && (
        <Section title="Education">
          {data.education.map((edu, i) => (
            <div className="paper__entry" key={i}>
              <div className="paper__row">
                <strong>{edu.institution}</strong>
                <strong>{dateRange(edu.start_date, edu.end_date)}</strong>
              </div>
              <div className="paper__row paper__row--italic">
                <span>{edu.degree}</span>
                <span>{edu.location}</span>
              </div>
              {edu.grade && <p>{edu.grade}</p>}
              {edu.details && <p>{edu.details}</p>}
            </div>
          ))}
        </Section>
      )}

      {data.skills.length > 0 && (
        <Section title="Skills">
          {data.skills.map((group, i) => (
            <p key={i}>
              {group.category && <strong>{group.category}: </strong>}
              {group.skills.join(', ')}
            </p>
          ))}
        </Section>
      )}

      {data.projects.length > 0 && (
        <Section title="Projects">
          {data.projects.map((project, i) => (
            <div className="paper__entry" key={i}>
              <div className="paper__row">
                <strong>
                  {project.name}
                  {project.role && <em> — {project.role}</em>}
                </strong>
                <strong>{dateRange(project.start_date, project.end_date)}</strong>
              </div>
              {project.description && <p>{project.description}</p>}
              {project.bullets.length > 0 && (
                <ul>
                  {project.bullets.map((bullet, j) => (
                    <li key={j}>{bullet}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </Section>
      )}

      {data.publications.length > 0 && (
        <Section title="Publications">
          <ol className="paper__pubs">
            {data.publications.map((pub, i) => (
              <li key={i}>
                {pub.authors && `${pub.authors}. `}
                <em>{pub.title}</em>.{pub.venue && ` ${pub.venue}.`}
                {pub.year && ` ${pub.year}.`}
              </li>
            ))}
          </ol>
        </Section>
      )}
    </article>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="paper__section">
      <h2 className="paper__section-title">{title}</h2>
      {children}
    </section>
  );
}
