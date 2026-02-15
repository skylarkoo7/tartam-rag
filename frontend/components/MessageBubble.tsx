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
        {!isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-zinc-800 text-[11px] font-semibold text-white grid place-items-center">AI</div> : null}

        <div
          className={clsx(
            "max-w-3xl rounded-2xl px-4 py-3 text-[15px] leading-7",
            isUser
              ? "bg-zinc-900 text-white"
              : "border border-zinc-200 bg-white text-zinc-900 shadow-[0_2px_12px_rgba(0,0,0,0.03)]"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.text}</p>
          ) : hasGarbled ? (
            <div className="space-y-2">
              <p className="font-medium text-amber-700">Source encoding issue detected</p>
              <p className="text-sm text-zinc-700">
                Retrieved text from this page is not Unicode-readable. Try re-ingesting with OCR recovery enabled.
              </p>
            </div>
          ) : sections.length > 1 ? (
            <div className="space-y-3">
              {sections.map((section) => (
                <section key={section.title} className="space-y-1">
                  <h4 className="text-xs font-semibold uppercase tracking-wide text-zinc-500">{section.title}</h4>
                  <p className="whitespace-pre-wrap text-zinc-800">{safeDisplayText(section.content, "")}</p>
                </section>
              ))}
            </div>
          ) : (
            <p className="whitespace-pre-wrap text-zinc-800">{safeDisplayText(message.text, "No readable response text.")}</p>
          )}

          <p className={clsx("mt-3 text-[11px]", isUser ? "text-zinc-300" : "text-zinc-500")}>{message.styleTag}</p>
        </div>

        {isUser ? <div className="mt-1 h-7 w-7 rounded-full bg-zinc-300 text-[11px] font-semibold text-zinc-700 grid place-items-center">You</div> : null}
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
