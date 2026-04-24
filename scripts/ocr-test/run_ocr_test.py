#!/usr/bin/env python3
"""Run Azure Document Intelligence prebuilt-invoice on a folder of invoices.

Produces per-file JSON extractions and an aggregated markdown report.
Usage: python run_ocr_test.py [--samples samples] [--reports reports]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent

CRITICAL_FIELDS = [
    "VendorName",
    "VendorTaxId",
    "InvoiceId",
    "InvoiceDate",
    "DueDate",
    "SubTotal",
    "TotalTax",
    "InvoiceTotal",
]


@dataclass
class FieldResult:
    value: Any = None
    confidence: float | None = None
    found: bool = False


@dataclass
class FileResult:
    filename: str
    ok: bool
    duration_sec: float
    fields: dict[str, FieldResult] = field(default_factory=dict)
    items_count: int = 0
    error: str | None = None


def extract_fields(result: AnalyzeResult) -> tuple[dict[str, FieldResult], int]:
    fields: dict[str, FieldResult] = {f: FieldResult() for f in CRITICAL_FIELDS}
    items_count = 0

    if not result.documents:
        return fields, 0

    doc = result.documents[0]
    doc_fields = doc.fields or {}

    for name in CRITICAL_FIELDS:
        raw = doc_fields.get(name)
        if raw is None:
            continue
        value = getattr(raw, "value_string", None) or getattr(raw, "content", None)
        if value is None:
            value = getattr(raw, "value_currency", None)
            if value is not None:
                value = {"amount": value.amount, "currency": value.currency_code}
        if value is None:
            value = getattr(raw, "value_date", None)
            if value is not None:
                value = value.isoformat() if hasattr(value, "isoformat") else str(value)

        fields[name] = FieldResult(
            value=value,
            confidence=getattr(raw, "confidence", None),
            found=value is not None,
        )

    items = doc_fields.get("Items")
    if items is not None and hasattr(items, "value_array"):
        items_count = len(items.value_array or [])

    return fields, items_count


def analyse_file(client: DocumentIntelligenceClient, path: Path, model: str, locale: str) -> FileResult:
    start = time.perf_counter()
    try:
        with path.open("rb") as fh:
            poller = client.begin_analyze_document(
                model_id=model,
                body=fh,
                locale=locale,
                content_type="application/octet-stream",
            )
        result: AnalyzeResult = poller.result()
    except Exception as exc:  # noqa: BLE001
        return FileResult(
            filename=path.name,
            ok=False,
            duration_sec=round(time.perf_counter() - start, 2),
            error=str(exc),
        )

    fields, items_count = extract_fields(result)
    return FileResult(
        filename=path.name,
        ok=True,
        duration_sec=round(time.perf_counter() - start, 2),
        fields=fields,
        items_count=items_count,
    )


def write_json_report(results: list[FileResult], reports_dir: Path) -> None:
    for r in results:
        path = reports_dir / f"{r.filename}.json"
        payload = {
            "filename": r.filename,
            "ok": r.ok,
            "duration_sec": r.duration_sec,
            "error": r.error,
            "items_count": r.items_count,
            "fields": {
                name: {"found": f.found, "value": f.value, "confidence": f.confidence}
                for name, f in r.fields.items()
            },
        }
        path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


def write_summary(results: list[FileResult], reports_dir: Path) -> None:
    ok_results = [r for r in results if r.ok]

    lines: list[str] = []
    lines.append("# OCR Test Summary — Azure DI prebuilt-invoice")
    lines.append("")
    lines.append(f"- Total files: **{len(results)}**")
    lines.append(f"- Successful analyses: **{len(ok_results)}**")
    lines.append(f"- Failed analyses: **{len(results) - len(ok_results)}**")
    if ok_results:
        durations = [r.duration_sec for r in ok_results]
        lines.append(f"- Mean duration: **{statistics.mean(durations):.2f}s**")
        lines.append(f"- Median duration: **{statistics.median(durations):.2f}s**")
    lines.append("")

    lines.append("## Field coverage & confidence")
    lines.append("")
    lines.append("| Field | Detection rate | Mean confidence |")
    lines.append("|-------|----------------|-----------------|")

    for name in CRITICAL_FIELDS:
        found_count = sum(1 for r in ok_results if r.fields.get(name) and r.fields[name].found)
        detection = found_count / len(ok_results) if ok_results else 0.0
        confidences = [
            r.fields[name].confidence
            for r in ok_results
            if r.fields.get(name) and r.fields[name].confidence is not None
        ]
        mean_conf = statistics.mean(confidences) if confidences else None
        conf_str = f"{mean_conf:.3f}" if mean_conf is not None else "—"
        lines.append(f"| {name} | {detection:.0%} | {conf_str} |")

    lines.append("")
    lines.append("## Go / No-Go verdict")
    lines.append("")
    mean_overall = statistics.mean(
        [
            r.fields[name].confidence
            for r in ok_results
            for name in CRITICAL_FIELDS
            if r.fields.get(name) and r.fields[name].confidence is not None
        ]
    ) if ok_results else None

    if mean_overall is None:
        verdict = "⚠️ Not enough data"
    elif mean_overall >= 0.90:
        verdict = f"✅ **GO** — mean confidence {mean_overall:.3f} ≥ 0.90"
    elif mean_overall >= 0.80:
        verdict = f"🟠 **CAUTION** — mean confidence {mean_overall:.3f} in 0.80–0.90"
    else:
        verdict = f"❌ **NO-GO** — mean confidence {mean_overall:.3f} < 0.80. Pivot to Plan B (Google DocAI / Mindee / custom)"
    lines.append(verdict)
    lines.append("")

    if any(not r.ok for r in results):
        lines.append("## Failures")
        lines.append("")
        for r in results:
            if not r.ok:
                lines.append(f"- `{r.filename}` — {r.error}")
        lines.append("")

    (reports_dir / "summary.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    load_dotenv(HERE / ".env")

    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", default=str(HERE / "samples"))
    parser.add_argument("--reports", default=str(HERE / "reports"))
    args = parser.parse_args()

    endpoint = os.environ.get("AZURE_DI_ENDPOINT", "").strip()
    key = os.environ.get("AZURE_DI_KEY", "").strip()
    model = os.environ.get("AZURE_DI_MODEL", "prebuilt-invoice")
    locale = os.environ.get("AZURE_DI_LOCALE", "el-GR")

    if not endpoint or not key:
        print("ERROR: AZURE_DI_ENDPOINT and AZURE_DI_KEY must be set in .env", file=sys.stderr)
        return 2

    samples_dir = Path(args.samples)
    reports_dir = Path(args.reports)

    if not samples_dir.is_dir():
        print(f"ERROR: samples directory not found: {samples_dir}", file=sys.stderr)
        return 2

    files = sorted(
        p
        for p in samples_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".pdf", ".jpg", ".jpeg", ".png", ".tiff", ".tif"}
    )
    if not files:
        print(f"ERROR: no invoice files found in {samples_dir}", file=sys.stderr)
        return 2

    reports_dir.mkdir(parents=True, exist_ok=True)
    client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))

    print(f"Analysing {len(files)} file(s) with model '{model}' (locale={locale})…")
    results: list[FileResult] = []
    for idx, path in enumerate(files, 1):
        print(f"  [{idx}/{len(files)}] {path.name}…", end=" ", flush=True)
        result = analyse_file(client, path, model, locale)
        results.append(result)
        if result.ok:
            print(f"ok ({result.duration_sec}s)")
        else:
            print(f"FAILED — {result.error}")

    write_json_report(results, reports_dir)
    write_summary(results, reports_dir)
    print(f"\nReports written to {reports_dir}/")
    print(f"Summary: {reports_dir / 'summary.md'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
