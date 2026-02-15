"use client";

import { StyleMode } from "../lib/types";

interface FilterBarProps {
  styleMode: StyleMode;
  onStyleMode: (next: StyleMode) => void;
  granth: string;
  prakran: string;
  granths: string[];
  prakrans: string[];
  onGranth: (value: string) => void;
  onPrakran: (value: string) => void;
}

const STYLE_OPTIONS: Array<{ label: string; value: StyleMode }> = [
  { label: "Auto", value: "auto" },
  { label: "Hindi", value: "hi" },
  { label: "Gujarati", value: "gu" },
  { label: "English", value: "en" },
  { label: "Hindi (Roman)", value: "hi_latn" },
  { label: "Gujarati (Roman)", value: "gu_latn" }
];

export function FilterBar(props: FilterBarProps) {
  const { styleMode, onStyleMode, granth, prakran, granths, prakrans, onGranth, onPrakran } = props;

  return (
    <div className="grid gap-3 rounded-2xl border border-white/50 bg-white/70 p-4 shadow-soft backdrop-blur-sm md:grid-cols-3">
      <label className="text-sm text-ink/80">
        Language Mode
        <select
          className="mt-1 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm"
          value={styleMode}
          onChange={(event) => onStyleMode(event.target.value as StyleMode)}
        >
          {STYLE_OPTIONS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm text-ink/80">
        Granth Filter
        <select
          className="mt-1 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm"
          value={granth}
          onChange={(event) => onGranth(event.target.value)}
        >
          <option value="">All Granths</option>
          {granths.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>

      <label className="text-sm text-ink/80">
        Prakran Filter
        <select
          className="mt-1 w-full rounded-xl border border-ink/10 bg-white px-3 py-2 text-sm"
          value={prakran}
          onChange={(event) => onPrakran(event.target.value)}
        >
          <option value="">All Prakrans</option>
          {prakrans.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
