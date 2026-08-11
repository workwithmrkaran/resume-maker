/** One component per wizard step. All state lives in the parent's Resume. */
import {
  emptyEducation,
  emptyExperience,
  emptyProject,
  emptyPublication,
  emptySkillGroup,
  type Resume,
} from '../types';
import type { Errors } from '../validation';
import { BulletList, DateRange, Repeatable, TagInput, TextArea, TextInput } from './fields';

interface StepProps {
  resume: Resume;
  errors: Errors;
  patch: (patch: Partial<Resume>) => void;
}

export function ContactStep({ resume, errors, patch }: StepProps) {
  const { contact } = resume;
  const set = (p: Partial<typeof contact>) => patch({ contact: { ...contact, ...p } });

  return (
    <>
      <TextInput
        label="Full name"
        value={contact.full_name}
        error={errors['contact.full_name']}
        placeholder="Alex Rivera"
        onChange={(v) => set({ full_name: v })}
      />
      <TextInput
        label="Headline"
        optional
        value={contact.headline}
        hint="One line under your name — e.g. your role and focus."
        placeholder="Backend Engineer — distributed systems"
        onChange={(v) => set({ headline: v })}
      />
      <div className="field-row">
        <TextInput
          label="Email"
          type="email"
          value={contact.email ?? ''}
          error={errors['contact.email']}
          placeholder="alex@example.com"
          onChange={(v) => set({ email: v })}
        />
        <TextInput
          label="Phone"
          type="tel"
          optional
          value={contact.phone}
          placeholder="+1 (555) 014-2288"
          onChange={(v) => set({ phone: v })}
        />
      </div>
      <TextInput
        label="Location"
        optional
        value={contact.location}
        placeholder="Austin, TX"
        onChange={(v) => set({ location: v })}
      />
      <Repeatable
        items={contact.links}
        onChange={(links) => set({ links })}
        create={() => ({ label: '', url: '' })}
        addLabel="+ Add a link"
        max={8}
        itemLabel={(link, i) => link.label || `Link ${i + 1}`}
        emptyMessage="Add LinkedIn, GitHub or a portfolio if you have them."
      >
        {(link, index, update) => (
          <div className="field-row">
            <TextInput
              label="Label"
              value={link.label}
              placeholder="LinkedIn"
              onChange={(v) => update({ label: v })}
            />
            <TextInput
              label="Address"
              type="url"
              value={link.url}
              error={errors[`contact.links.${index}.url`]}
              placeholder="linkedin.com/in/alexrivera"
              maxLength={300}
              onChange={(v) => update({ url: v })}
            />
          </div>
        )}
      </Repeatable>
    </>
  );
}

export function SummaryStep({ resume, errors, patch }: StepProps) {
  return (
    <TextArea
      label="Professional summary"
      optional
      rows={6}
      value={resume.summary}
      error={errors['summary']}
      hint="Two or three sentences: what you do, how long, and what you're best at."
      placeholder="Backend engineer with six years building high-throughput services…"
      onChange={(summary) => patch({ summary })}
    />
  );
}

export function ExperienceStep({ resume, errors, patch }: StepProps) {
  return (
    <Repeatable
      items={resume.experience}
      onChange={(experience) => patch({ experience })}
      create={emptyExperience}
      addLabel="+ Add another job"
      itemLabel={(job, i) => job.title || job.company || `Position ${i + 1}`}
      emptyMessage="No roles yet — add your most recent one first."
    >
      {(job, index, update) => (
        <>
          <div className="field-row">
            <TextInput
              label="Job title"
              value={job.title}
              error={errors[`experience.${index}.title`]}
              placeholder="Senior Software Engineer"
              onChange={(v) => update({ title: v })}
            />
            <TextInput
              label="Company"
              value={job.company}
              error={errors[`experience.${index}.company`]}
              placeholder="Northwind Data"
              onChange={(v) => update({ company: v })}
            />
          </div>
          <TextInput
            label="Location"
            optional
            value={job.location}
            placeholder="Austin, TX or Remote"
            onChange={(v) => update({ location: v })}
          />
          <DateRange
            start={job.start_date}
            end={job.end_date}
            onChange={(start_date, end_date) => update({ start_date, end_date })}
          />
          <BulletList
            label="What you did"
            bullets={job.bullets}
            hint="One achievement per line. Lead with the result and include a number where you can."
            onChange={(bullets) => update({ bullets })}
          />
        </>
      )}
    </Repeatable>
  );
}

export function EducationStep({ resume, errors, patch }: StepProps) {
  return (
    <Repeatable
      items={resume.education}
      onChange={(education) => patch({ education })}
      create={emptyEducation}
      addLabel="+ Add another qualification"
      max={10}
      itemLabel={(edu, i) => edu.institution || edu.degree || `Education ${i + 1}`}
      emptyMessage="Add your highest or most relevant qualification."
    >
      {(edu, index, update) => (
        <>
          <div className="field-row">
            <TextInput
              label="Degree or qualification"
              value={edu.degree}
              error={errors[`education.${index}.degree`]}
              placeholder="B.S. Computer Science"
              onChange={(v) => update({ degree: v })}
            />
            <TextInput
              label="Institution"
              value={edu.institution}
              error={errors[`education.${index}.institution`]}
              placeholder="University of Texas at Austin"
              onChange={(v) => update({ institution: v })}
            />
          </div>
          <div className="field-row">
            <TextInput
              label="Location"
              optional
              value={edu.location}
              onChange={(v) => update({ location: v })}
            />
            <TextInput
              label="Grade"
              optional
              value={edu.grade}
              placeholder="GPA 3.8/4.0 or First Class"
              onChange={(v) => update({ grade: v })}
            />
          </div>
          <DateRange
            start={edu.start_date}
            end={edu.end_date}
            endPlaceholder="2019"
            onChange={(start_date, end_date) => update({ start_date, end_date })}
          />
          <TextInput
            label="Details"
            optional
            value={edu.details}
            maxLength={300}
            placeholder="Relevant coursework, honours, thesis"
            onChange={(v) => update({ details: v })}
          />
        </>
      )}
    </Repeatable>
  );
}

export function SkillsStep({ resume, patch }: StepProps) {
  return (
    <Repeatable
      items={resume.skills}
      onChange={(skills) => patch({ skills })}
      create={emptySkillGroup}
      addLabel="+ Add a skill group"
      max={12}
      itemLabel={(group, i) => group.category || `Group ${i + 1}`}
      emptyMessage="Group your skills so they scan quickly — e.g. Languages, Tools."
    >
      {(group, _index, update) => (
        <>
          <TextInput
            label="Category"
            value={group.category}
            placeholder="Languages"
            onChange={(v) => update({ category: v })}
          />
          <TagInput
            label="Skills"
            values={group.skills}
            hint="Separate with commas."
            onChange={(skills) => update({ skills })}
          />
        </>
      )}
    </Repeatable>
  );
}

export function ProjectsStep({ resume, errors, patch }: StepProps) {
  return (
    <Repeatable
      items={resume.projects}
      onChange={(projects) => patch({ projects })}
      create={emptyProject}
      addLabel="+ Add a project"
      itemLabel={(project, i) => project.name || `Project ${i + 1}`}
      emptyMessage="Nothing here yet — this section is optional, skip it if it doesn't apply."
    >
      {(project, index, update) => (
        <>
          <div className="field-row">
            <TextInput
              label="Project name"
              value={project.name}
              error={errors[`projects.${index}.name`]}
              placeholder="queuelite"
              onChange={(v) => update({ name: v })}
            />
            <TextInput
              label="Your role"
              optional
              value={project.role}
              placeholder="Author"
              onChange={(v) => update({ role: v })}
            />
          </div>
          <TextInput
            label="Link"
            type="url"
            optional
            value={project.url}
            maxLength={300}
            placeholder="github.com/you/project"
            onChange={(v) => update({ url: v })}
          />
          <DateRange
            start={project.start_date}
            end={project.end_date}
            onChange={(start_date, end_date) => update({ start_date, end_date })}
          />
          <TextArea
            label="Description"
            optional
            rows={2}
            value={project.description}
            placeholder="A dependency-free job queue for Postgres."
            onChange={(v) => update({ description: v })}
          />
          <BulletList
            label="Highlights"
            bullets={project.bullets}
            onChange={(bullets) => update({ bullets })}
          />
        </>
      )}
    </Repeatable>
  );
}

export function PublicationsStep({ resume, errors, patch }: StepProps) {
  return (
    <>
      <p className="muted">
        Only relevant for academic or research-heavy resumes. Skip this step if you have none.
      </p>
      <Repeatable
        items={resume.publications}
        onChange={(publications) => patch({ publications })}
        create={emptyPublication}
        addLabel="+ Add a publication"
        max={30}
        itemLabel={(pub, i) => pub.title || `Publication ${i + 1}`}
      >
        {(pub, index, update) => (
          <>
            <TextInput
              label="Title"
              value={pub.title}
              error={errors[`publications.${index}.title`]}
              maxLength={300}
              onChange={(v) => update({ title: v })}
            />
            <TextInput
              label="Authors"
              optional
              value={pub.authors}
              maxLength={300}
              placeholder="A. Rivera, J. Okonkwo"
              onChange={(v) => update({ authors: v })}
            />
            <div className="field-row">
              <TextInput
                label="Venue"
                optional
                value={pub.venue}
                maxLength={300}
                placeholder="USENIX SREcon"
                onChange={(v) => update({ venue: v })}
              />
              <TextInput
                label="Year"
                optional
                value={pub.year}
                maxLength={20}
                placeholder="2024"
                onChange={(v) => update({ year: v })}
              />
            </div>
            <TextInput
              label="Link"
              type="url"
              optional
              value={pub.url}
              maxLength={300}
              onChange={(v) => update({ url: v })}
            />
          </>
        )}
      </Repeatable>
    </>
  );
}
