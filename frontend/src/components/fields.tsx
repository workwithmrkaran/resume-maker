/**
 * Reusable form primitives, one per field type.
 *
 * Every screen that edits resume data — the manual form now, the AI review
 * screen in Phase 2, any future template's form in Phase 3 — is built from
 * these, so field behaviour (labels, hints, inline errors) stays consistent.
 */
import { useId, type ReactNode } from 'react';
import { useAiFilled } from '../aiFilledContext';

interface FieldShellProps {
  label: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  aiFilled?: boolean;
  htmlFor: string;
  children: ReactNode;
}

/** Marks a value the AI extracted and the user hasn't touched yet. */
export function AiBadge() {
  return (
    <span className="ai-badge" title="Filled in from your uploaded resume — please check it">
      AI-filled
    </span>
  );
}

function FieldShell({ label, hint, error, optional, aiFilled, htmlFor, children }: FieldShellProps) {
  return (
    <div className={`field${error ? ' field--error' : ''}`}>
      <label className="field__label" htmlFor={htmlFor}>
        {label}
        {optional && <span className="field__optional">optional</span>}
        {aiFilled && <AiBadge />}
      </label>
      {children}
      {hint && !error && <p className="field__hint">{hint}</p>}
      {error && (
        <p className="field__error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

interface TextInputProps {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  hint?: string;
  error?: string;
  optional?: boolean;
  maxLength?: number;
  type?: 'text' | 'email' | 'tel' | 'url';
  /** Schema path, e.g. `contact.full_name`, used to show the AI-filled badge. */
  path?: string;
}

export function TextInput({
  label,
  value,
  onChange,
  placeholder,
  hint,
  error,
  optional,
  maxLength = 120,
  type = 'text',
  path,
}: TextInputProps) {
  const id = useId();
  const aiFilled = useAiFilled()(path ?? '', value);
  return (
    <FieldShell label={label} hint={hint} error={error} optional={optional}
                aiFilled={aiFilled} htmlFor={id}>
      <input
        id={id}
        className="field__input"
        type={type}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        onChange={(e) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}

interface TextAreaProps extends Omit<TextInputProps, 'type'> {
  rows?: number;
}

export function TextArea({
  label,
  value,
  onChange,
  placeholder,
  hint,
  error,
  optional,
  maxLength = 2000,
  rows = 4,
  path,
}: TextAreaProps) {
  const id = useId();
  const remaining = maxLength - value.length;
  const aiFilled = useAiFilled()(path ?? '', value);
  return (
    <FieldShell
      label={label}
      hint={remaining < maxLength * 0.15 ? `${remaining} characters left` : hint}
      error={error}
      optional={optional}
      aiFilled={aiFilled}
      htmlFor={id}
    >
      <textarea
        id={id}
        className="field__input field__input--area"
        rows={rows}
        value={value}
        placeholder={placeholder}
        maxLength={maxLength}
        aria-invalid={Boolean(error)}
        onChange={(e) => onChange(e.target.value)}
      />
    </FieldShell>
  );
}

interface DateRangeProps {
  start: string;
  end: string;
  onChange: (start: string, end: string) => void;
  endPlaceholder?: string;
  /** Path of the entry itself, e.g. `experience.0`. */
  path?: string;
}

/**
 * Dates are free text on purpose: resumes say "Jan 2023", "Summer 2024" and
 * "Present", and a strict date picker fights every one of those.
 */
export function DateRange({ start, end, onChange, endPlaceholder = 'Present',
                            path }: DateRangeProps) {
  return (
    <div className="field-row">
      <TextInput
        label="Start"
        value={start}
        placeholder="Mar 2022"
        maxLength={40}
        path={path && `${path}.start_date`}
        onChange={(v) => onChange(v, end)}
      />
      <TextInput
        label="End"
        value={end}
        placeholder={endPlaceholder}
        maxLength={40}
        path={path && `${path}.end_date`}
        onChange={(v) => onChange(start, v)}
      />
    </div>
  );
}

interface BulletListProps {
  label: string;
  bullets: string[];
  onChange: (bullets: string[]) => void;
  hint?: string;
  max?: number;
  path?: string;
}

export function BulletList({ label, bullets, onChange, hint, max = 12, path }: BulletListProps) {
  const isAiFilled = useAiFilled();
  const update = (index: number, value: string) =>
    onChange(bullets.map((b, i) => (i === index ? value : b)));
  const remove = (index: number) =>
    onChange(bullets.length === 1 ? [''] : bullets.filter((_, i) => i !== index));

  return (
    <div className="field">
      <span className="field__label">
        {label}
        {isAiFilled(path ?? '', bullets) && <AiBadge />}
      </span>
      {hint && <p className="field__hint">{hint}</p>}
      <ul className="bullets">
        {bullets.map((bullet, index) => (
          <li key={index} className="bullets__item">
            <textarea
              className="field__input field__input--area"
              rows={2}
              value={bullet}
              maxLength={2000}
              aria-label={`${label} — point ${index + 1}`}
              placeholder="Cut p99 latency by 60% by adding a read-through cache"
              onChange={(e) => update(index, e.target.value)}
            />
            <button
              type="button"
              className="btn btn--icon"
              aria-label={`Remove point ${index + 1}`}
              onClick={() => remove(index)}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
      {bullets.length < max && (
        <button type="button" className="btn btn--ghost" onClick={() => onChange([...bullets, ''])}>
          + Add a point
        </button>
      )}
    </div>
  );
}

interface TagInputProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  hint?: string;
}

/** Comma-separated entry, kept as an array underneath. */
export function TagInput({ label, values, onChange, hint }: TagInputProps) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} htmlFor={id}>
      <input
        id={id}
        className="field__input"
        value={values.join(', ')}
        placeholder="Python, Go, PostgreSQL"
        onChange={(e) =>
          onChange(
            e.target.value
              .split(',')
              .map((s) => s.trimStart())
              .filter((s, i, all) => s !== '' || i === all.length - 1),
          )
        }
      />
    </FieldShell>
  );
}

interface RepeatableProps<T> {
  items: T[];
  onChange: (items: T[]) => void;
  create: () => T;
  addLabel: string;
  itemLabel: (item: T, index: number) => string;
  max?: number;
  emptyMessage?: string;
  children: (item: T, index: number, update: (patch: Partial<T>) => void) => ReactNode;
}

/**
 * The repeatable-section wrapper (work history, education, projects…).
 * Add/remove controls live here so they behave identically everywhere —
 * this is the part that feels clunky in most resume builders.
 */
export function Repeatable<T>({
  items,
  onChange,
  create,
  addLabel,
  itemLabel,
  max = 15,
  emptyMessage,
  children,
}: RepeatableProps<T>) {
  const update = (index: number, patch: Partial<T>) =>
    onChange(items.map((item, i) => (i === index ? { ...item, ...patch } : item)));
  const remove = (index: number) => onChange(items.filter((_, i) => i !== index));
  const move = (index: number, delta: number) => {
    const target = index + delta;
    if (target < 0 || target >= items.length) return;
    const next = [...items];
    [next[index], next[target]] = [next[target], next[index]];
    onChange(next);
  };

  return (
    <div className="repeatable">
      {items.length === 0 && emptyMessage && <p className="muted">{emptyMessage}</p>}
      {items.map((item, index) => (
        <section className="entry" key={index}>
          <header className="entry__header">
            <h3 className="entry__title">{itemLabel(item, index)}</h3>
            <div className="entry__controls">
              <button
                type="button"
                className="btn btn--icon"
                aria-label={`Move ${itemLabel(item, index)} up`}
                disabled={index === 0}
                onClick={() => move(index, -1)}
              >
                ↑
              </button>
              <button
                type="button"
                className="btn btn--icon"
                aria-label={`Move ${itemLabel(item, index)} down`}
                disabled={index === items.length - 1}
                onClick={() => move(index, 1)}
              >
                ↓
              </button>
              <button
                type="button"
                className="btn btn--icon"
                aria-label={`Remove ${itemLabel(item, index)}`}
                onClick={() => remove(index)}
              >
                ×
              </button>
            </div>
          </header>
          {children(item, index, (patch) => update(index, patch))}
        </section>
      ))}
      {items.length < max && (
        <button type="button" className="btn btn--secondary" onClick={() => onChange([...items, create()])}>
          {addLabel}
        </button>
      )}
    </div>
  );
}
