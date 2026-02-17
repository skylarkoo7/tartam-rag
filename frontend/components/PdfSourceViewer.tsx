"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// Keep worker version aligned with installed pdfjs-dist from the local bundle.
pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();

interface PdfSourceViewerProps {
  fileUrl: string;
  initialPage: number;
  highlightText?: string;
}

export function PdfSourceViewer({ fileUrl, initialPage, highlightText = "" }: PdfSourceViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(Math.max(1, initialPage));
  const [scale, setScale] = useState(1.15);
  const [textLayerRendered, setTextLayerRendered] = useState(false);
  const [highlightHits, setHighlightHits] = useState(0);
  const highlightHitsRef = useRef(0);

  useEffect(() => {
    setPage(Math.max(1, initialPage));
  }, [fileUrl, initialPage]);

  useEffect(() => {
    setTextLayerRendered(false);
    setHighlightHits(0);
    highlightHitsRef.current = 0;
  }, [fileUrl, page, highlightText]);

  const safePage = useMemo(() => {
    if (!numPages) {
      return page;
    }
    return Math.max(1, Math.min(page, numPages));
  }, [numPages, page]);

  const highlightNeedle = useMemo(() => {
    const value = (highlightText || "").trim();
    return value.length >= 3 ? value : "";
  }, [highlightText]);

  const customTextRenderer = useMemo(
    () => (item: { str: string }) => {
      const text = item?.str || "";
      if (!highlightNeedle) {
        return text;
      }
      const escaped = highlightNeedle.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const matcher = new RegExp(`(${escaped})`, "gi");
      if (!matcher.test(text)) {
        return text;
      }
      highlightHitsRef.current += 1;
      return text.replace(matcher, "<mark class=\"pdf-hit\">$1</mark>");
    },
    [highlightNeedle]
  );

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-[#eadaca] bg-[#fff8ef] px-3 py-2 text-xs text-[#6c472a]">
        <div className="flex items-center gap-2">
          <button
            type="button"
            className="rounded-md border border-[#dabf9f] bg-white px-2 py-1 disabled:opacity-50"
            disabled={safePage <= 1}
            onClick={() => setPage((prev) => Math.max(prev - 1, 1))}
          >
            Prev
          </button>
          <span>
            Page {safePage}{numPages ? ` / ${numPages}` : ""}
          </span>
          <button
            type="button"
            className="rounded-md border border-[#dabf9f] bg-white px-2 py-1 disabled:opacity-50"
            disabled={!!numPages && safePage >= numPages}
            onClick={() => setPage((prev) => (numPages ? Math.min(prev + 1, numPages) : prev + 1))}
          >
            Next
          </button>
        </div>
        <div className="flex items-center gap-1">
          <button
            type="button"
            className="rounded-md border border-[#dabf9f] bg-white px-2 py-1"
            onClick={() => setScale((prev) => Math.max(0.75, prev - 0.1))}
          >
            -
          </button>
          <span>{Math.round(scale * 100)}%</span>
          <button
            type="button"
            className="rounded-md border border-[#dabf9f] bg-white px-2 py-1"
            onClick={() => setScale((prev) => Math.min(2.2, prev + 0.1))}
          >
            +
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-[#fbf6ef] p-3">
        <Document
          key={fileUrl}
          file={fileUrl}
          loading={<div className="text-xs text-[#8a674a]">Loading PDF...</div>}
          error={<div className="text-xs text-[#9a4f22]">Could not render PDF page.</div>}
          onLoadSuccess={(doc) => {
            setNumPages(doc.numPages || 0);
            setPage((prev) => Math.max(1, Math.min(prev, doc.numPages || prev)));
          }}
        >
          <Page
            pageNumber={safePage}
            scale={scale}
            renderAnnotationLayer={false}
            renderTextLayer
            customTextRenderer={customTextRenderer}
            onRenderTextLayerSuccess={() => {
              setTextLayerRendered(true);
              setHighlightHits(highlightHitsRef.current);
            }}
            className="mx-auto shadow-[0_8px_20px_rgba(60,34,17,0.15)]"
          />
        </Document>
        {highlightNeedle && textLayerRendered && highlightHits === 0 ? (
          <div className="mt-2 text-[11px] text-[#9a5e2c]">
            Text highlight unavailable on this page (likely scanned image or low text-layer quality).
          </div>
        ) : null}
      </div>
    </div>
  );
}
