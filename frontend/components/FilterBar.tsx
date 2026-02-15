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
    <div className="grid gap-2 md:grid-cols-3">
      <label className="text-xs text-zinc-500">
        Language
        <select
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-800"
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

      <label className="text-xs text-zinc-500">
        Granth
        <select
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-800"
          value={granth}
          onChange={(event) => onGranth(event.target.value)}
        >
          <option value="">All granths</option>
          {granths.map((item) => (
            <option key={item} value={item}>
              {item}
            </option>
          ))}
        </select>
      </label>

      <label className="text-xs text-zinc-500">
        Prakran
        <select
          className="mt-1 w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-800"
          value={prakran}
          onChange={(event) => onPrakran(event.target.value)}
        >
          <option value="">All prakrans</option>
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
