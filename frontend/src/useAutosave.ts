import { useEffect, useRef, useState } from 'react';
import { emptyResume, type Resume } from './types';

const KEY = 'resume-maker:draft:v1';

/**
 * Keeps the in-progress resume in the browser only.
 *
 * A refresh mid-form shouldn't wipe half an hour of typing, and Phase 1 has no
 * accounts — so the draft lives in localStorage, on the user's machine, and
 * never touches the server until they press Generate.
 */
export function useAutosavedResume() {
  const [resume, setResume] = useState<Resume>(() => load());
  const [savedAt, setSavedAt] = useState<Date | null>(null);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      try {
        window.localStorage.setItem(KEY, JSON.stringify(resume));
        setSavedAt(new Date());
      } catch {
        // Private browsing or a full quota — autosave is a convenience, so
        // failing to save must never interrupt the user.
      }
    }, 400);
    return () => window.clearTimeout(timer.current);
  }, [resume]);

  const clear = () => {
    window.localStorage.removeItem(KEY);
    setResume(emptyResume());
    setSavedAt(null);
  };

  return { resume, setResume, savedAt, clear, hasDraft: hasStoredDraft() };
}

function load(): Resume {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return emptyResume();
    // Merge over a fresh resume so a draft written by an older version of the
    // app (missing newer fields) still loads.
    return { ...emptyResume(), ...(JSON.parse(raw) as Partial<Resume>) } as Resume;
  } catch {
    return emptyResume();
  }
}

export function hasStoredDraft(): boolean {
  try {
    const raw = window.localStorage.getItem(KEY);
    if (!raw) return false;
    const draft = JSON.parse(raw) as Resume;
    return Boolean(draft?.contact?.full_name?.trim());
  } catch {
    return false;
  }
}
