"use client";

import { useMemo, useState } from "react";

import { Citation } from "../lib/types";
import { safeDisplayText } from "../lib/text";

interface CitationCardProps {
  citation: Citation;
}

export function CitationCard({ citation }: CitationCardProps) {
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

  return (
    <article className="rounded-xl border border-[#d9b48b] bg-[#fff6e9] p-3">
      <button className="w-full text-left" onClick={() => setExpanded((prev) => !prev)} type="button">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-[#6d4326]">
            {citation.granth_name} <span className="text-[#9a6d48]">·</span> {citation.prakran_name}
          </h4>
          <span className="rounded-full border border-[#d9b48b] bg-[#fffaf3] px-2 py-0.5 text-xs text-[#805331]">
            p.{citation.page_number}
          </span>
        </div>

        <p className="mt-2 text-sm text-[#5f3a21]">{chopaiPreview}</p>
      </button>

      {expanded ? (
        <div className="mt-3 space-y-2 border-t border-[#e2c4a5] pt-3 text-sm text-[#5f3a21]">
          <p>
            <span className="font-semibold text-[#4a2e1d]">Meaning: </span>
            {meaning}
          </p>

          {prevContext ? (
            <p>
              <span className="font-semibold text-[#4a2e1d]">Previous context: </span>
              {prevContext}
            </p>
          ) : null}

          {nextContext ? (
            <p>
              <span className="font-semibold text-[#4a2e1d]">Next context: </span>
              {nextContext}
            </p>
          ) : null}

          <p className="text-xs text-[#8b5f3c]">Source: {citation.pdf_path}</p>
        </div>
      ) : null}
    </article>
  );
}
