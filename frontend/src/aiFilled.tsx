/**
 * Tracks which fields came from AI extraction rather than the user.
 *
 * The product plan asks for a visible cue on auto-extracted fields, because a
 * pre-filled form otherwise looks like something the user typed and checked. A
 * field counts as AI-filled while it still holds exactly what the model
 * produced — the moment someone edits it, it's theirs and the badge goes.
 */
import { useCallback, useMemo, type ReactNode } from 'react';
import { AiFilledContext, type AiFilledChecker } from './aiFilledContext';
import type { Resume } from './types';

/** Read `contact.links.0.url`-style paths out of a nested object. */
function valueAt(source: unknown, path: string): unknown {
  return path.split('.').reduce<unknown>((node, key) => {
    if (node === null || node === undefined) return undefined;
    if (Array.isArray(node)) return node[Number(key)];
    if (typeof node === 'object') return (node as Record<string, unknown>)[key];
    return undefined;
  }, source);
}

const isEmpty = (value: unknown) =>
  value === null ||
  value === undefined ||
  value === '' ||
  (Array.isArray(value) && value.length === 0);

export function AiFilledProvider({ extracted, children }: {
  extracted: Resume | null;
  children: ReactNode;
}) {
  const check = useCallback<AiFilledChecker>(
    (path, value) => {
      if (!extracted || isEmpty(value)) return false;
      const original = valueAt(extracted, path);
      if (isEmpty(original)) return false;
      return JSON.stringify(original) === JSON.stringify(value);
    },
    [extracted],
  );
  const value = useMemo(() => check, [check]);
  return <AiFilledContext.Provider value={value}>{children}</AiFilledContext.Provider>;
}
