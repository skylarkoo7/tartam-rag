"use client";

import { useEffect, useMemo, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";

// Keep worker version exactly aligned with pdfjs runtime version to avoid API/worker mismatch.
pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

interface PdfSourceViewerProps {
  fileUrl: string;
  initialPage: number;
}

export function PdfSourceViewer({ fileUrl, initialPage }: PdfSourceViewerProps) {
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(Math.max(1, initialPage));
  const [scale, setScale] = useState(1.15);

  useEffect(() => {
    setPage(Math.max(1, initialPage));
  }, [fileUrl, initialPage]);

  const safePage = useMemo(() => {
    if (!numPages) {
      return page;
    }
    return Math.max(1, Math.min(page, numPages));
  }, [numPages, page]);

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
            renderTextLayer={false}
            className="mx-auto shadow-[0_8px_20px_rgba(60,34,17,0.15)]"
          />
        </Document>
      </div>
    </div>
  );
}
