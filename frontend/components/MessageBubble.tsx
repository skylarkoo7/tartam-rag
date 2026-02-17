"use client";

import { useState } from "react";
import clsx from "clsx";

import { convertAnswer } from "../lib/api";
import { ChatMessage, ConvertMode } from "../lib/types";
import { isGarbledText, parseAssistantSections, safeDisplayText, scriptClassName } from "../lib/text";
import { CitationCard } from "./CitationCard";

interface MessageBubbleProps {
  message: ChatMessage;
  onCitationSelect?: (citation: ChatMessage["citations"][number]) => void;
  activeCitationId?: string | null;
}

const CONVERT_OPTIONS: Array<{ label: string; value: ConvertMode }> = [
  { label: "English", value: "en" },
  { label: "Hindi", value: "hi" },
  { label: "Gujarati", value: "gu" },
  { label: "Hindi (Roman)", value: "hi_latn" },
  { label: "Gujarati (Roman)", value: "gu_latn" },
  { label: "English in Hindi script", value: "en_deva" },
  { label: "English in Gujarati script", value: "en_gu" }
];

export function MessageBubble({ message, onCitationSelect, activeCitationId }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const sections = !isUser ? parseAssistantSections(message.text) : [];
  const hasGarbled = isGarbledText(message.text);
  const isNotFoundResponse =
    !isUser && message.text.trim().toLowerCase().startsWith("i could not find this clearly in available texts");
  const messageFontClass = scriptClassName(message.text);
  const [convertMode, setConvertMode] = useState<ConvertMode>("en");
  const [convertedText, setConvertedText] = useState("");
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState("");
  const [showCostDetails, setShowCostDetails] = useState(false);

  async function onConvert() {
    if (isUser || !message.text.trim()) {
      return;
    }
    setConverting(true);
    setConvertError("");
    try {
      const response = await convertAnswer(message.text, convertMode);
      setConvertedText(response.text);
    } catch (error) {
      setConvertError(error instanceof Error ? error.message : "Conversion failed");
    } finally {
      setConverting(false);
    }
  }

  return (
    <article className="space-y-3">
      <div className={clsx("flex items-start gap-3", isUser ? "justify-end" : "justify-start")}>
        {!isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-[#d8b99c] text-[11px] font-semibold text-[#5d3d24] grid place-items-center">AI</div> : null}

        <div
          className={clsx(
            "max-w-3xl rounded-2xl px-4 py-3 text-[15px] leading-7 shadow-[0_6px_18px_rgba(70,40,20,0.06)]",
            isUser
              ? "bg-[#be6a31] text-[#fff7ef]"
              : "border border-[#e6d5c5] bg-white text-[#4a2e1d]"
          )}
        >
          {isUser ? (
            <p className={clsx("whitespace-pre-wrap", messageFontClass)}>{message.text}</p>
          ) : hasGarbled ? (
            <div className="space-y-2">
              <p className="font-medium text-[#9a4b1d]">Source encoding issue detected</p>
              <p className="text-sm text-[#6f4a2e]">
                Retrieved text from this page is not Unicode-readable. Try re-ingesting with OCR recovery enabled.
              </p>
            </div>
          ) : sections.length > 1 ? (
            <div className="space-y-3">
              {sections.map((section) => (
                <section key={section.title} className="space-y-1">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-[#8b5f3c]">{section.title}</h4>
                  <p className={clsx("whitespace-pre-wrap text-[#4a2e1d]", scriptClassName(section.content))}>
                    {safeDisplayText(section.content, "")}
                  </p>
                </section>
              ))}
            </div>
          ) : (
            <p className={clsx("whitespace-pre-wrap text-[#4a2e1d]", messageFontClass)}>
              {safeDisplayText(message.text, "No readable response text.")}
            </p>
          )}

          {!isUser && message.costSummary ? (
            <div className="mt-3 space-y-2 rounded-xl border border-[#e8d4c0] bg-[#fff8ef] px-3 py-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-semibold text-[#734f33]">
                  Prompt cost: ₹{message.costSummary.total_inr.toFixed(4)} (${message.costSummary.total_usd.toFixed(6)})
                </p>
                <button
                  type="button"
                  className="rounded-md border border-[#dabc9f] bg-white px-2 py-1 text-[11px] text-[#6a4529]"
                  onClick={() => setShowCostDetails((prev) => !prev)}
                >
                  {showCostDetails ? "Hide details" : "Show details"}
                </button>
              </div>
              <p className="text-[11px] text-[#8a674a]">
                FX: {message.costSummary.fx_rate.toFixed(2)} ({message.costSummary.fx_source})
              </p>
              {showCostDetails ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[540px] border-collapse text-[11px]">
                    <thead>
                      <tr className="text-left text-[#7a573b]">
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">Stage</th>
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">Model</th>
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">Input</th>
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">Cached</th>
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">Output</th>
                        <th className="border-b border-[#e8d4c0] pb-1 pr-2">USD</th>
                        <th className="border-b border-[#e8d4c0] pb-1">INR</th>
                      </tr>
                    </thead>
                    <tbody>
                      {message.costSummary.line_items.map((item, idx) => (
                        <tr key={`${item.stage}_${idx}`} className="text-[#5f3a21]">
                          <td className="py-1 pr-2">{item.stage}</td>
                          <td className="py-1 pr-2">{item.model}</td>
                          <td className="py-1 pr-2">{item.input_tokens}</td>
                          <td className="py-1 pr-2">{item.cached_input_tokens}</td>
                          <td className="py-1 pr-2">{item.output_tokens}</td>
                          <td className="py-1 pr-2">{item.usd_cost.toFixed(6)}</td>
                          <td className="py-1">{item.inr_cost.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </div>
          ) : null}

          {!isUser && isNotFoundResponse ? (
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="rounded-full border border-[#ddc1a8] bg-[#fff8ef] px-2.5 py-1 text-[11px] text-[#7a563a]">
                Try adding granth name
              </span>
              <span className="rounded-full border border-[#ddc1a8] bg-[#fff8ef] px-2.5 py-1 text-[11px] text-[#7a563a]">
                Add prakran number
              </span>
              <span className="rounded-full border border-[#ddc1a8] bg-[#fff8ef] px-2.5 py-1 text-[11px] text-[#7a563a]">
                Add a direct chopai phrase
              </span>
            </div>
          ) : null}

          {!isUser ? (
            <div className="mt-3 space-y-2 border-t border-[#f1e3d7] pt-3">
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className="rounded-md border border-[#dcc3ac] bg-[#fffdf8] px-2 py-1 text-xs text-[#5f3a21]"
                  value={convertMode}
                  onChange={(event) => setConvertMode(event.target.value as ConvertMode)}
                >
                  {CONVERT_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <button
                  type="button"
                  className="rounded-md bg-[#bc682d] px-2.5 py-1 text-xs font-medium text-white hover:bg-[#a95a24] disabled:opacity-60"
                  disabled={converting}
                  onClick={() => void onConvert()}
                >
                  {converting ? "Converting..." : "Convert answer"}
                </button>
              </div>

              {convertedText ? (
                <div className="rounded-xl border border-[#edd8c2] bg-[#fffaf3] p-2 text-sm text-[#4a2e1d]">
                  <p className={clsx("whitespace-pre-wrap", scriptClassName(convertedText))}>{convertedText}</p>
                </div>
              ) : null}
              {convertError ? <p className="text-xs text-[#a1451f]">{convertError}</p> : null}
            </div>
          ) : null}

          <p className={clsx("mt-3 text-[11px]", isUser ? "text-[#fde4c8]" : "text-[#8b5f3c]")}>{message.styleTag}</p>
        </div>

        {isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-[#f0ddc8] text-[11px] font-semibold text-[#6d4326] grid place-items-center">You</div> : null}
      </div>

      {!isUser && message.citations.length > 0 ? (
        <div className="ml-10 grid gap-2">
          {message.citations.map((citation) => (
            <CitationCard
              key={citation.citation_id}
              citation={citation}
              onSelect={onCitationSelect}
              active={activeCitationId === citation.citation_id}
            />
          ))}
        </div>
      ) : null}
    </article>
  );
}
