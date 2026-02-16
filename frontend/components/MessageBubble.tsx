"use client";

import { useState } from "react";
import clsx from "clsx";

import { convertAnswer } from "../lib/api";
import { ChatMessage, ConvertMode } from "../lib/types";
import { isGarbledText, parseAssistantSections, safeDisplayText } from "../lib/text";
import { CitationCard } from "./CitationCard";

interface MessageBubbleProps {
  message: ChatMessage;
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

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const sections = !isUser ? parseAssistantSections(message.text) : [];
  const hasGarbled = isGarbledText(message.text);
  const [convertMode, setConvertMode] = useState<ConvertMode>("en");
  const [convertedText, setConvertedText] = useState("");
  const [converting, setConverting] = useState(false);
  const [convertError, setConvertError] = useState("");

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
        {!isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-[#9f5729] text-[11px] font-semibold text-[#fff7ef] grid place-items-center">AI</div> : null}

        <div
          className={clsx(
            "max-w-3xl rounded-2xl px-4 py-3 text-[15px] leading-7",
            isUser
              ? "bg-[#c66a2e] text-[#fff7ef]"
              : "border border-[#d8b68f] bg-[#fff7ed] text-[#4a2e1d] shadow-[0_2px_12px_rgba(125,74,37,0.08)]"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.text}</p>
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
                  <p className="whitespace-pre-wrap text-[#4a2e1d]">{safeDisplayText(section.content, "")}</p>
                </section>
              ))}
            </div>
          ) : (
            <p className="whitespace-pre-wrap text-[#4a2e1d]">{safeDisplayText(message.text, "No readable response text.")}</p>
          )}

          {!isUser ? (
            <div className="mt-3 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <select
                  className="rounded-md border border-[#d2a67d] bg-[#fffaf1] px-2 py-1 text-xs text-[#5f3a21]"
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
                  className="rounded-md bg-[#c66a2e] px-2.5 py-1 text-xs font-medium text-[#fff7ef] hover:bg-[#b75f28] disabled:opacity-60"
                  disabled={converting}
                  onClick={() => void onConvert()}
                >
                  {converting ? "Converting..." : "Convert answer"}
                </button>
              </div>

              {convertedText ? (
                <div className="rounded-xl border border-[#e1bd98] bg-[#fffaf3] p-2 text-sm text-[#4a2e1d]">
                  <p className="whitespace-pre-wrap">{convertedText}</p>
                </div>
              ) : null}
              {convertError ? <p className="text-xs text-[#a1451f]">{convertError}</p> : null}
            </div>
          ) : null}

          <p className={clsx("mt-3 text-[11px]", isUser ? "text-[#fde4c8]" : "text-[#8b5f3c]")}>{message.styleTag}</p>
        </div>

        {isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-[#e6c49e] text-[11px] font-semibold text-[#6d4326] grid place-items-center">You</div> : null}
      </div>

      {!isUser && message.citations.length > 0 ? (
        <div className="ml-10 grid gap-2">
          {message.citations.map((citation) => (
            <CitationCard key={citation.citation_id} citation={citation} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
