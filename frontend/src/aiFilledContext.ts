import { createContext, useContext } from 'react';

/** `(schemaPath, currentValue) => true` while a value is still the AI's. */
export type AiFilledChecker = (path: string, value: unknown) => boolean;

export const AiFilledContext = createContext<AiFilledChecker>(() => false);

export const useAiFilled = () => useContext(AiFilledContext);
