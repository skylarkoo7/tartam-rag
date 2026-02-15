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
    <article className="rounded-xl border border-zinc-200 bg-zinc-50 p-3">
      <button className="w-full text-left" onClick={() => setExpanded((prev) => !prev)} type="button">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-zinc-800">
            {citation.granth_name} <span className="text-zinc-500">·</span> {citation.prakran_name}
          </h4>
          <span className="rounded-full border border-zinc-300 bg-white px-2 py-0.5 text-xs text-zinc-600">
            p.{citation.page_number}
          </span>
        </div>

        <p className="mt-2 text-sm text-zinc-700">{chopaiPreview}</p>
      </button>

      {expanded ? (
        <div className="mt-3 space-y-2 border-t border-zinc-200 pt-3 text-sm text-zinc-700">
          <p>
            <span className="font-semibold text-zinc-900">Meaning: </span>
            {meaning}
          </p>

          {prevContext ? (
            <p>
              <span className="font-semibold text-zinc-900">Previous context: </span>
              {prevContext}
            </p>
          ) : null}

          {nextContext ? (
            <p>
              <span className="font-semibold text-zinc-900">Next context: </span>
              {nextContext}
            </p>
          ) : null}

          <p className="text-xs text-zinc-500">Source: {citation.pdf_path}</p>
        </div>
      ) : null}
    </article>
  );
}
