"use client";

import { useState } from "react";

import { Citation } from "../lib/types";

interface CitationCardProps {
  citation: Citation;
}

export function CitationCard({ citation }: CitationCardProps) {
  const [expanded, setExpanded] = useState(false);

  return (
    <article className="rounded-xl border border-leaf/20 bg-sand p-3 shadow-sm transition hover:shadow-md">
      <button
        className="w-full text-left"
        onClick={() => setExpanded((prev) => !prev)}
        type="button"
      >
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-leaf">
            {citation.granth_name} · {citation.prakran_name}
          </h4>
          <span className="rounded-full bg-leaf/10 px-2 py-1 text-xs text-leaf">
            p.{citation.page_number}
          </span>
        </div>

        <p className="mt-2 text-sm text-ink/90">{citation.chopai_lines.slice(0, 2).join(" ")}</p>
      </button>

      {expanded ? (
        <div className="mt-3 space-y-2 border-t border-leaf/20 pt-3 text-sm text-ink/90">
          <p>
            <span className="font-semibold text-leaf">Meaning: </span>
            {citation.meaning_text}
          </p>
          {citation.prev_context ? (
            <p>
              <span className="font-semibold text-leaf">Previous context: </span>
              {citation.prev_context}
            </p>
          ) : null}
          {citation.next_context ? (
            <p>
              <span className="font-semibold text-leaf">Next context: </span>
              {citation.next_context}
            </p>
          ) : null}
          <p className="text-xs text-ink/60">Source: {citation.pdf_path}</p>
        </div>
      ) : null}
    </article>
  );
}
