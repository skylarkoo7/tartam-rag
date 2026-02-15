"use client";

import clsx from "clsx";

import { ChatMessage } from "../lib/types";
import { CitationCard } from "./CitationCard";

interface MessageBubbleProps {
  message: ChatMessage;
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div className={clsx("space-y-2", isUser ? "items-end" : "items-start")}> 
      <div
        className={clsx(
          "max-w-3xl rounded-2xl px-4 py-3 text-sm shadow-soft",
          isUser ? "ml-auto bg-vermilion text-white" : "bg-white text-ink"
        )}
      >
        <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
        <p className={clsx("mt-2 text-[11px]", isUser ? "text-white/80" : "text-ink/50")}>{message.styleTag}</p>
      </div>

      {!isUser && message.citations.length > 0 ? (
        <div className="grid gap-2">
          {message.citations.map((citation) => (
            <CitationCard key={citation.citation_id} citation={citation} />
          ))}
        </div>
      ) : null}
    </div>
  );
}
