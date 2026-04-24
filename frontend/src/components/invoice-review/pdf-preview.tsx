"use client";

import { useEffect, useState } from "react";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

if (typeof window !== "undefined") {
  pdfjs.GlobalWorkerOptions.workerSrc = `https://unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;
}

export function PdfPreview({ url, mime }: { url: string; mime: string }) {
  const [numPages, setNumPages] = useState(0);
  const [width, setWidth] = useState(600);

  useEffect(() => {
    const el = document.getElementById("pdf-preview-container");
    if (el) setWidth(Math.min(el.clientWidth - 32, 820));
  }, []);

  if (!mime.includes("pdf")) {
    return (
      <div className="flex h-full items-center justify-center bg-muted/20">
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={url} alt="Facture" className="max-h-full max-w-full object-contain" />
      </div>
    );
  }

  return (
    <div id="pdf-preview-container" className="h-full overflow-y-auto bg-muted/20 p-4">
      <Document
        file={url}
        onLoadSuccess={({ numPages }) => setNumPages(numPages)}
        loading={
          <p className="text-center text-sm text-muted-foreground">Chargement du PDF…</p>
        }
        error={
          <p className="text-center text-sm text-destructive">Impossible d&apos;afficher le PDF.</p>
        }
      >
        {Array.from({ length: numPages }, (_, i) => (
          <Page
            key={i}
            pageNumber={i + 1}
            width={width}
            className="mb-4 border bg-white shadow"
          />
        ))}
      </Document>
    </div>
  );
}
