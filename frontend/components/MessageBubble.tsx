"use client";

import clsx from "clsx";

import { ChatMessage } from "../lib/types";
import { isGarbledText, parseAssistantSections, safeDisplayText } from "../lib/text";
import { CitationCard } from "./CitationCard";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";
  const sections = !isUser ? parseAssistantSections(message.text) : [];
  const hasGarbled = isGarbledText(message.text);

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
