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
  const messageFontClass = scriptClassName(message.text);
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
