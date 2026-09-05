"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { t, type CopyKey } from "./i18n";
import type { Language } from "./types";

interface LanguageContextValue {
  /** UI language. Ready to forward to the Python Agent as `language`. */
  language: Language;
  setLanguage: (language: Language) => void;
  /** Resolves a UI/content copy key for the active language. */
  copy: (key: CopyKey | string) => string;
}

const LanguageContext = createContext<LanguageContextValue | null>(null);

export function LanguageProvider({
  children,
  initialLanguage = "en",
}: {
  children: ReactNode;
  initialLanguage?: Language;
}) {
  const [language, setLanguageState] = useState<Language>(initialLanguage);

  const setLanguage = useCallback((next: Language) => {
    setLanguageState(next);
  }, []);

  const copy = useCallback(
    (key: CopyKey | string) => t(key as CopyKey, language),
    [language],
  );

  const value = useMemo(
    () => ({ language, setLanguage, copy }),
    [language, setLanguage, copy],
  );

  return (
    <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
  );
}

export function useLanguage(): LanguageContextValue {
  const ctx = useContext(LanguageContext);
  if (!ctx) {
    throw new Error("useLanguage must be used within LanguageProvider");
  }
  return ctx;
}
