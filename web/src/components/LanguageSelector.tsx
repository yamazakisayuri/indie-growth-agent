"use client";

import { useLanguage } from "@/lib/language-context";
import type { Language } from "@/lib/types";

const OPTIONS: { value: Language; label: string }[] = [
  { value: "ja", label: "日本語" },
  { value: "en", label: "English" },
];

export function LanguageSelector() {
  const { language, setLanguage, copy } = useLanguage();

  return (
    <div className="lang-selector">
      <span className="lang-selector__label" id="lang-selector-label">
        {copy("language")}
      </span>
      <div
        className="lang-selector__group"
        role="group"
        aria-labelledby="lang-selector-label"
      >
        {OPTIONS.map((option) => {
          const selected = language === option.value;
          return (
            <button
              key={option.value}
              type="button"
              className={
                selected
                  ? "lang-selector__btn lang-selector__btn--active"
                  : "lang-selector__btn"
              }
              aria-pressed={selected}
              onClick={() => setLanguage(option.value)}
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
