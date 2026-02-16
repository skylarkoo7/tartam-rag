"use client";

import { useMemo, useState } from "react";

import { Citation } from "../lib/types";
import { safeDisplayText, scriptClassName } from "../lib/text";

interface CitationCardProps {
  citation: Citation;
  onSelect?: (citation: Citation) => void;
  active?: boolean;
}

export function CitationCard({ citation, onSelect, active = false }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  const chopaiPreview = useMemo(() => {
    const joined = citation.chopai_lines.join(" ");
    return safeDisplayText(joined, "Chopai text unavailable due source encoding on this page.");
  }, [citation.chopai_lines]);

  const meaning = useMemo(
    () => safeDisplayText(citation.meaning_text, "Meaning text unavailable due source encoding on this page."),
    [citation.meaning_text]
  );

  const prevContext = useMemo(
    () => safeDisplayText(citation.prev_context ?? "", ""),
    [citation.prev_context]
  );

  const nextContext = useMemo(
    () => safeDisplayText(citation.next_context ?? "", ""),
    [citation.next_context]
  );

  const chopaiFontClass = scriptClassName(chopaiPreview);
  const meaningFontClass = scriptClassName(meaning);

  return (
    <article className={`rounded-xl border p-3 transition ${active ? "border-[#cc7d33] bg-[#fff5e8]" : "border-[#e7d5c3] bg-[#fffdf9]"}`}>
      <button
        className="w-full cursor-pointer text-left"
        onClick={() => {
          setExpanded((prev) => !prev);
          onSelect?.(citation);
        }}
        type="button"
      >
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-[#5a3a22]">
            {citation.granth_name} <span className="text-[#9a6d48]">·</span> {citation.prakran_name}
          </h4>
          <div className="flex items-center gap-2">
            {citation.prakran_chopai_index ? (
              <span className="rounded-full border border-[#e6c8ab] bg-[#fff8ef] px-2 py-0.5 text-xs text-[#805331]">
                Pk-Ch.{citation.prakran_chopai_index}
              </span>
            ) : null}
            {citation.chopai_number ? (
              <span className="rounded-full border border-[#e6c8ab] bg-[#fff8ef] px-2 py-0.5 text-xs text-[#805331]">
                Ch.{citation.chopai_number}
              </span>
            ) : null}
            <span className="rounded-full border border-[#e6c8ab] bg-[#fff8ef] px-2 py-0.5 text-xs text-[#805331]">
              p.{citation.page_number}
            </span>
          </div>
        </div>

        <p className={`mt-2 text-sm text-[#5f3a21] ${chopaiFontClass}`}>{chopaiPreview}</p>
      </button>

      {expanded ? (
        <div className="mt-3 space-y-2 border-t border-[#efd7c2] pt-3 text-sm text-[#5f3a21]">
          <p className={meaningFontClass}>
            <span className="font-semibold text-[#4a2e1d]">Meaning: </span>
            {meaning}
          </p>

          {prevContext ? (
            <p className={scriptClassName(prevContext)}>
              <span className="font-semibold text-[#4a2e1d]">Previous context: </span>
              {prevContext}
            </p>
          ) : null}

          {nextContext ? (
            <p className={scriptClassName(nextContext)}>
              <span className="font-semibold text-[#4a2e1d]">Next context: </span>
              {nextContext}
            </p>
          ) : null}

          <p className="text-xs text-[#8b5f3c]">Click card to open PDF on the right panel.</p>
        </div>
      ) : null}
    </article>
  );
}
