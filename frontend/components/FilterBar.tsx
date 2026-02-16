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
      <label className="text-xs text-[#8b5f3c]">
        Language
        <select
          className="mt-1 w-full rounded-lg border border-[#dbc2ab] bg-white px-3 py-2 text-sm text-[#5b3923] focus:border-[#cb8854] focus:outline-none"
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

      <label className="text-xs text-[#8b5f3c]">
        Granth
        <select
          className="mt-1 w-full rounded-lg border border-[#dbc2ab] bg-white px-3 py-2 text-sm text-[#5b3923] focus:border-[#cb8854] focus:outline-none"
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

      <label className="text-xs text-[#8b5f3c]">
        Prakran
        <input
          list="prakran-options"
          placeholder="Type Prakran (e.g. Prakran 14)"
          className="mt-1 w-full rounded-lg border border-[#dbc2ab] bg-white px-3 py-2 text-sm text-[#5b3923] focus:border-[#cb8854] focus:outline-none"
          value={prakran}
          onChange={(event) => onPrakran(event.target.value)}
        />
        <datalist id="prakran-options">
          {prakrans.map((item) => (
            <option key={item} value={item} />
          ))}
        </datalist>
      </label>
    </div>
  );
}
