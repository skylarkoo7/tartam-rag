const GARBLED_PATTERN = /[Ÿ¢£¤¥¦§¨©ª«¬®±²³´µ¶·¸¹º»¼½¾¿ÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞß]/g;

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

export function parseAssistantSections(text: string): { title: string; content: string }[] {
  const input = text?.trim() ?? "";
  if (!input) {
    return [];
  }

  const markers = ["Direct Answer:", "Explanation from Chopai:", "Grounding:"];
  const hasStructured = markers.every((marker) => input.includes(marker));
  if (!hasStructured) {
    return [{ title: "Response", content: input }];
  }

  const directIndex = input.indexOf("Direct Answer:");
  const explainIndex = input.indexOf("Explanation from Chopai:");
  const groundingIndex = input.indexOf("Grounding:");

  if (directIndex === -1 || explainIndex === -1 || groundingIndex === -1) {
    return [{ title: "Response", content: input }];
  }

  const direct = input.slice(directIndex + "Direct Answer:".length, explainIndex).trim();
  const explanation = input.slice(explainIndex + "Explanation from Chopai:".length, groundingIndex).trim();
  const grounding = input.slice(groundingIndex + "Grounding:".length).trim();

  return [
    { title: "Direct Answer", content: direct },
    { title: "Explanation", content: explanation },
    { title: "Grounding", content: grounding }
  ].filter((item) => item.content.length > 0);
}
