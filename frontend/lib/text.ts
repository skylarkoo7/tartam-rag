const GARBLED_PATTERN = /[Ÿ¢£¤¥¦§¨©ª«¬®±²³´µ¶·¸¹º»¼½¾¿ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß]/g;

export type ScriptTag = "latin" | "deva" | "guj";

export function garbledRatio(text: string): number {
  if (!text) {
    return 0;
  }
  const matches = text.match(GARBLED_PATTERN) ?? [];
  return matches.length / Math.max(text.length, 1);
}

export function isGarbledText(text: string, threshold = 0.015): boolean {
  return garbledRatio(text) >= threshold;
}

export function safeDisplayText(text: string, fallback: string): string {
  const normalized = (text ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) {
    return fallback;
  }
  if (isGarbledText(normalized)) {
    return fallback;
  }
  return normalized;
}

export function detectScriptTag(text: string): ScriptTag {
  const value = text ?? "";
  let deva = 0;
  let guj = 0;
  let latin = 0;
  for (const ch of value) {
    const code = ch.charCodeAt(0);
    if (code >= 0x0900 && code <= 0x097f) {
      deva += 1;
    } else if (code >= 0x0a80 && code <= 0x0aff) {
      guj += 1;
    } else if ((code >= 0x0041 && code <= 0x005a) || (code >= 0x0061 && code <= 0x007a)) {
      latin += 1;
    }
  }
  if (deva > guj && deva > latin) {
    return "deva";
  }
  if (guj > deva && guj > latin) {
    return "guj";
  }
  return "latin";
}

export function scriptClassName(text: string): string {
  const script = detectScriptTag(text);
  if (script === "deva") {
    return "font-devanagari";
  }
  if (script === "guj") {
    return "font-gujarati";
  }
  return "font-latin";
}

export function parseAssistantSections(text: string): { title: string; content: string }[] {
  const input = (text ?? "").trim();
  if (!input) {
    return [];
  }

  const normalized = input
    .replace(/\b1\)\s*/g, "")
    .replace(/\b2\)\s*/g, "")
    .replace(/\b3\)\s*/g, "")
    .replace(/Grounding:\s*\[[^\]]+\]/gi, "Grounding:");
  const markers = ["Direct Answer:", "Explanation from Chopai:", "Grounding:"];
  const hasStructured = markers.every((marker) => normalized.includes(marker));
  if (!hasStructured) {
    return [{ title: "Response", content: normalized }];
  }

  const directIndex = normalized.indexOf("Direct Answer:");
  const explainIndex = normalized.indexOf("Explanation from Chopai:");
  const groundingIndex = normalized.indexOf("Grounding:");

  if (directIndex === -1 || explainIndex === -1 || groundingIndex === -1) {
    return [{ title: "Response", content: normalized }];
  }

  const direct = normalized.slice(directIndex + "Direct Answer:".length, explainIndex).trim();
  const explanation = normalized.slice(explainIndex + "Explanation from Chopai:".length, groundingIndex).trim();
  const grounding = normalized.slice(groundingIndex + "Grounding:".length).trim();

  return [
    { title: "Direct Answer", content: direct },
    { title: "Explanation", content: explanation },
    { title: "Grounding", content: grounding }
  ].filter((item) => item.content.length > 0);
}
