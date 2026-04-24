"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  AlertTriangle,
  Check,
  RotateCcw,
  Save,
  SkipForward,
  Sparkles,
  X,
} from "lucide-react";
import { toast } from "sonner";
import { ApiError, apiFetch } from "@/lib/api";
import type { InvoiceComment, InvoiceDetail, InvoiceLine, InvoicePatch } from "@/lib/types";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { StatusBadge } from "@/components/status-badge";
import { PdfPreview } from "@/components/invoice-review/pdf-preview";
import { InvoiceLinesEditor } from "@/components/invoice-review/invoice-lines-editor";

const EDITABLE_STATUSES = new Set(["ready_for_review", "rejected"]);

const inputClass =
  "h-9 w-full rounded-lg border border-white/10 bg-white/[0.04] px-3 text-[13px] text-white placeholder:text-white/35 focus:border-violet-500/40 focus:outline-none focus:ring-1 focus:ring-violet-500/30 disabled:opacity-60";

function fmtDate(iso: string | null): string {
  return iso ?? "";
}

function toDecimal(n: number): string {
  return (Math.round(n * 100) / 100).toFixed(2);
}

function sumDecimal(values: (string | null)[]): number {
  return values.reduce<number>((acc, v) => {
    if (!v) return acc;
    const n = Number(v.replace(",", "."));
    return Number.isFinite(n) ? acc + n : acc;
  }, 0);
}

// ── Section card ─────────────────────────────────────────────
function Section({
  title,
  hint,
  children,
}: {
  title: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="glass p-5" style={{ borderRadius: 18 }}>
      <div className="relative z-10">
        <div className="mb-4 flex items-baseline justify-between">
          <h3 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
            {title}
          </h3>
          {hint && <span className="text-[11px] text-white/35">{hint}</span>}
        </div>
        {children}
      </div>
    </div>
  );
}

// ── Validation banner ─────────────────────────────────────────
function ValidationBanner({
  errors,
}: {
  errors: InvoiceDetail["validation_errors"];
}) {
  if (!errors || errors.issues.length === 0) {
    return (
      <div
        className="flex items-center gap-2 rounded-xl border border-emerald-500/25 bg-emerald-500/[0.06] px-4 py-2.5 text-[13px] text-emerald-300"
        style={{ backdropFilter: "blur(20px)" }}
      >
        <Check className="h-4 w-4" strokeWidth={2.5} />
        Aucune erreur de validation — prête à être validée.
      </div>
    );
  }

  const errorCount = errors.issues.filter((i) => i.severity === "error").length;
  const warnCount = errors.issues.filter((i) => i.severity === "warning").length;

  return (
    <div
      className={`rounded-xl border px-4 py-3 ${
        errorCount > 0
          ? "border-rose-500/30 bg-rose-500/[0.06]"
          : "border-amber-500/30 bg-amber-500/[0.06]"
      }`}
      style={{ backdropFilter: "blur(20px)" }}
    >
      <div
        className={`mb-2 text-[13px] font-medium ${
          errorCount > 0 ? "text-rose-300" : "text-amber-300"
        }`}
      >
        {errorCount > 0
          ? `${errorCount} erreur${errorCount > 1 ? "s" : ""} à corriger`
          : `${warnCount} avertissement${warnCount > 1 ? "s" : ""}`}
      </div>
      <ul className="space-y-1">
        {errors.issues.map((issue, idx) => (
          <li
            key={idx}
            className={`flex items-start gap-2 text-[12px] ${
              issue.severity === "error" ? "text-rose-200/80" : "text-amber-200/80"
            }`}
          >
            <span
              className={`mt-1.5 h-[5px] w-[5px] shrink-0 rounded-full ${
                issue.severity === "error" ? "bg-rose-400" : "bg-amber-400"
              }`}
            />
            <span>{issue.message}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function InvoiceReviewPage({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();

  const [invoice, setInvoice] = useState<InvoiceDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const [invoiceNumber, setInvoiceNumber] = useState("");
  const [issueDate, setIssueDate] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [currency, setCurrency] = useState("EUR");
  const [totalHt, setTotalHt] = useState("");
  const [totalVat, setTotalVat] = useState("");
  const [totalTtc, setTotalTtc] = useState("");
  const [paidAt, setPaidAt] = useState("");
  const [paymentReference, setPaymentReference] = useState("");
  const [tags, setTags] = useState("");
  const [lines, setLines] = useState<InvoiceLine[]>([]);
  const [comments, setComments] = useState<InvoiceComment[]>([]);
  const [commentBody, setCommentBody] = useState("");
  const [rejectReason, setRejectReason] = useState("");
  const [showReject, setShowReject] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await apiFetch<InvoiceDetail>(`/invoices/${id}`);
      setInvoice(data);
      setInvoiceNumber(data.invoice_number ?? "");
      setIssueDate(fmtDate(data.issue_date));
      setDueDate(fmtDate(data.due_date));
      setCurrency(data.currency);
      setTotalHt(data.total_ht ?? "");
      setTotalVat(data.total_vat ?? "");
      setTotalTtc(data.total_ttc ?? "");
      setPaidAt(data.paid_at ?? "");
      setPaymentReference(data.payment_reference ?? "");
      setTags((data.tags ?? []).join(", "));
      setLines(data.lines);
      apiFetch<InvoiceComment[]>(`/invoices/${id}/comments`).then(setComments).catch(() => {});
    } catch (err) {
      setError(err instanceof ApiError ? `Erreur ${err.status}` : "Erreur réseau");
    }
  }, [id]);

  useEffect(() => {
    void load();
  }, [load]);

  const editable = invoice && EDITABLE_STATUSES.has(invoice.status);

  const computedLinesHt = useMemo(
    () => sumDecimal(lines.map((l) => l.line_total_ht)),
    [lines],
  );

  const totalsMismatch = useMemo(() => {
    const ht = Number(totalHt.replace(",", "."));
    const vat = Number(totalVat.replace(",", "."));
    const ttc = Number(totalTtc.replace(",", "."));
    if (!Number.isFinite(ht) || !Number.isFinite(vat) || !Number.isFinite(ttc)) return false;
    return Math.abs(ht + vat - ttc) > 0.02;
  }, [totalHt, totalVat, totalTtc]);

  async function save(): Promise<InvoiceDetail | null> {
    if (!invoice) return null;
    setSaving(true);
    setError(null);
    try {
      const patch: InvoicePatch = {
        invoice_number: invoiceNumber || null,
        issue_date: issueDate || null,
        due_date: dueDate || null,
        currency: currency || "EUR",
        total_ht: totalHt || null,
        total_vat: totalVat || null,
        total_ttc: totalTtc || null,
        paid_at: paidAt || null,
        payment_reference: paymentReference || null,
        payment_method: paidAt ? "manual" : null,
        tags: tags
          .split(",")
          .map((tag) => tag.trim())
          .filter(Boolean),
        lines,
      };
      const updated = await apiFetch<InvoiceDetail>(`/invoices/${invoice.id}`, {
        method: "PATCH",
        json: patch,
      });
      setInvoice(updated);
      toast.success("Modifications enregistrées");
      return updated;
    } catch (err) {
      const msg = err instanceof ApiError ? `Erreur ${err.status}` : "Erreur d'enregistrement";
      setError(msg);
      toast.error(msg);
      return null;
    } finally {
      setSaving(false);
    }
  }

  async function confirm() {
    const updated = await save();
    if (!updated) return;
    try {
      const confirmed = await apiFetch<InvoiceDetail>(`/invoices/${updated.id}/confirm`, {
        method: "POST",
      });
      setInvoice(confirmed);
      toast.success("Facture validée");
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 422
          ? "Corrige les erreurs de validation avant de confirmer."
          : "Impossible de confirmer la facture.";
      toast.error(msg);
    }
  }

  async function reject() {
    if (!invoice) return;
    try {
      const rejected = await apiFetch<InvoiceDetail>(`/invoices/${invoice.id}/reject`, {
        method: "POST",
        json: { reason: rejectReason },
      });
      setInvoice(rejected);
      setShowReject(false);
      setRejectReason("");
      toast.success("Facture rejetée");
    } catch {
      toast.error("Impossible de rejeter");
    }
  }

  async function skip() {
    if (!invoice) return;
    try {
      await apiFetch(`/invoices/${invoice.id}/skip`, { method: "POST" });
      router.push("/invoices");
    } catch {
      toast.error("Impossible de passer");
    }
  }

  async function reopen() {
    if (!invoice) return;
    try {
      const reopened = await apiFetch<InvoiceDetail>(`/invoices/${invoice.id}/reopen`, {
        method: "POST",
      });
      setInvoice(reopened);
      toast.success("Facture réouverte");
    } catch {
      toast.error("Impossible de réouvrir");
    }
  }

  async function approve() {
    if (!invoice) return;
    const approved = await apiFetch<InvoiceDetail>(`/invoices/${invoice.id}/approve`, {
      method: "POST",
    });
    setInvoice(approved);
    toast.success("Approbation enregistrée");
  }

  async function addComment() {
    if (!invoice || !commentBody.trim()) return;
    const comment = await apiFetch<InvoiceComment>(`/invoices/${invoice.id}/comments`, {
      method: "POST",
      json: { body: commentBody },
    });
    setComments((items) => [...items, comment]);
    setCommentBody("");
  }

  if (error && !invoice) return <p className="text-sm text-rose-400">{error}</p>;
  if (!invoice) return <p className="text-sm text-white/50">Chargement…</p>;

  const confidence = invoice.ocr_confidence
    ? Math.round(Number(invoice.ocr_confidence) * 100)
    : null;

  return (
    <div className="flex h-[calc(100vh-56px)] flex-col">
      {/* ── Header ───────────────────────────────────────── */}
      <header className="mb-4 flex flex-wrap items-center justify-between gap-4">
        <div className="flex items-center gap-3 min-w-0">
          <Link
            href="/invoices"
            className="flex items-center gap-1 text-[12px] text-white/45 transition hover:text-white/80"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Factures
          </Link>
          <div className="h-4 w-px bg-white/10" />
          <h1 className="font-serif-italic text-[24px] leading-tight text-white/95 truncate max-w-[480px]">
            {invoice.source_file_name}
          </h1>
          <StatusBadge status={invoice.status} />
          {invoice.possible_duplicate_of_id && (
            <Link
              href={`/invoices/${invoice.possible_duplicate_of_id}` as never}
              className="inline-flex items-center gap-1 rounded-full border border-amber-300/25 bg-amber-300/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.08em] text-amber-200 transition hover:bg-amber-300/15"
            >
              <AlertTriangle className="h-3 w-3" />
              Possible doublon
            </Link>
          )}
        </div>
        <div className="flex items-center gap-4 text-[12px] text-white/45">
          {invoice.supplier?.name && (
            <span>
              <span className="text-white/35">Fournisseur · </span>
              <span className="text-white/75">{invoice.supplier.name}</span>
            </span>
          )}
          {confidence !== null && (
            <span className="flex items-center gap-1.5">
              <span className="text-white/35">OCR</span>
              <span
                className={`font-mono-display ${
                  confidence >= 90 ? "text-emerald-300" : "text-amber-300"
                }`}
              >
                {confidence}%
              </span>
            </span>
          )}
        </div>
      </header>

      {/* ── Split view ───────────────────────────────────── */}
      <div className="grid min-h-0 flex-1 gap-4 lg:grid-cols-5">
        {/* PDF ─────────────────────────────────────────── */}
        <div
          className="glass lg:col-span-3 overflow-hidden"
          style={{ borderRadius: 18 }}
        >
          <div className="relative z-10 h-full">
            {invoice.file_url ? (
              <PdfPreview url={invoice.file_url} mime={invoice.source_file_mime} />
            ) : (
              <div className="flex h-full items-center justify-center text-[13px] text-white/45">
                Pas d&apos;aperçu disponible
              </div>
            )}
          </div>
        </div>

        {/* Form ────────────────────────────────────────── */}
        <div className="raijin-scroll flex min-h-0 flex-col gap-4 overflow-y-auto pr-2 lg:col-span-2">
          <ValidationBanner errors={invoice.validation_errors} />

          <Section title="Identité" hint={!editable ? "lecture seule" : undefined}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5 sm:col-span-2">
                <Label className="text-[11px] text-white/55">Numéro de facture</Label>
                <input
                  value={invoiceNumber}
                  onChange={(e) => setInvoiceNumber(e.target.value)}
                  disabled={!editable}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px] text-white/55">Date d&apos;émission</Label>
                <input
                  type="date"
                  value={issueDate}
                  onChange={(e) => setIssueDate(e.target.value)}
                  disabled={!editable}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px] text-white/55">Date d&apos;échéance</Label>
                <input
                  type="date"
                  value={dueDate}
                  onChange={(e) => setDueDate(e.target.value)}
                  disabled={!editable}
                  className={inputClass}
                />
              </div>
            </div>
          </Section>

          <Section
            title="Montants"
            hint={
              totalsMismatch
                ? "⚠️ HT + TVA ≠ TTC"
                : lines.length > 0
                  ? `Σ lignes HT : ${toDecimal(computedLinesHt)}`
                  : undefined
            }
          >
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="space-y-1.5">
                <Label className="text-[11px] text-white/55">Devise</Label>
                <input
                  value={currency}
                  onChange={(e) => setCurrency(e.target.value.toUpperCase())}
                  disabled={!editable}
                  maxLength={3}
                  className={`${inputClass} font-mono-display`}
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label className="text-[11px] text-white/55">Total HT</Label>
                <input
                  value={totalHt}
                  onChange={(e) => setTotalHt(e.target.value)}
                  disabled={!editable}
                  className={`${inputClass} font-mono-display`}
                />
              </div>
              <div className="space-y-1.5 sm:col-span-3">
                <Label className="text-[11px] text-white/55">Total TVA</Label>
                <input
                  value={totalVat}
                  onChange={(e) => setTotalVat(e.target.value)}
                  disabled={!editable}
                  className={`${inputClass} font-mono-display`}
                />
              </div>
              <div className="space-y-1.5 sm:col-span-3">
                <Label
                  className={`text-[11px] ${
                    totalsMismatch ? "text-rose-300" : "text-white/55"
                  }`}
                >
                  Total TTC
                </Label>
                <input
                  value={totalTtc}
                  onChange={(e) => setTotalTtc(e.target.value)}
                  disabled={!editable}
                  className={`${inputClass} font-serif-display text-[18px] ${
                    totalsMismatch ? "border-rose-500/40" : ""
                  }`}
                />
              </div>
            </div>
          </Section>

          <Section title="Paiement & workflow" hint={invoice.approval_status}>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label className="text-[11px] text-white/55">Payée le</Label>
                <input
                  type="date"
                  value={paidAt}
                  onChange={(e) => setPaidAt(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-[11px] text-white/55">Référence paiement</Label>
                <input
                  value={paymentReference}
                  onChange={(e) => setPaymentReference(e.target.value)}
                  className={inputClass}
                />
              </div>
              <div className="space-y-1.5 sm:col-span-2">
                <Label className="text-[11px] text-white/55">Tags</Label>
                <input
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                  placeholder="marketing, urgent"
                  className={inputClass}
                />
              </div>
              <button className="btn-glass w-fit" onClick={approve}>
                Approuver
              </button>
            </div>
          </Section>

          <Section
            title="Lignes"
            hint={`${lines.length} ligne${lines.length > 1 ? "s" : ""}`}
          >
            {editable ? (
              <InvoiceLinesEditor lines={lines} onChange={setLines} />
            ) : lines.length > 0 ? (
              <div className="space-y-2">
                {lines.map((line) => (
                  <div
                    key={line.id}
                    className="flex items-center gap-3 rounded-lg border border-white/[0.06] bg-white/[0.02] px-3 py-2 text-[12px]"
                  >
                    <span className="w-4 font-mono-display text-white/35">
                      {line.line_number}
                    </span>
                    <span className="flex-1 truncate text-white/75">
                      {line.description ?? "—"}
                    </span>
                    <span className="font-mono-display text-white/60">
                      {line.line_total_ht ?? "—"}
                    </span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-[12px] text-white/35">Aucune ligne.</p>
            )}
          </Section>

          <Section title="Commentaires" hint={`${comments.length}`}>
            <div className="space-y-3">
              {comments.map((comment) => (
                <div
                  key={comment.id}
                  className="rounded-lg border border-white/[0.06] bg-white/[0.02] p-3 text-[12px] text-white/75"
                >
                  {comment.body}
                </div>
              ))}
              <Textarea
                value={commentBody}
                onChange={(e) => setCommentBody(e.target.value)}
                placeholder="Ajouter un commentaire, mentionner @email si besoin"
                className="border-white/10 bg-white/[0.04] text-white"
              />
              <button className="btn-glass" onClick={addComment}>
                Commenter
              </button>
            </div>
          </Section>

          {invoice.rejected_reason && (
            <div
              className="rounded-xl border border-rose-500/25 bg-rose-500/[0.06] p-4 text-[13px] text-rose-200/80"
              style={{ backdropFilter: "blur(20px)" }}
            >
              <div className="mb-1 text-[11px] font-semibold uppercase tracking-[0.12em] text-rose-300">
                Raison du rejet
              </div>
              {invoice.rejected_reason}
            </div>
          )}

          {/* ── Actions bar ────────────────────────────── */}
          <div className="sticky bottom-0 -mx-2 mt-auto flex flex-wrap gap-2 rounded-xl border border-white/[0.08] bg-black/60 p-3 backdrop-blur-xl">
            {editable && (
              <>
                <button
                  onClick={save}
                  disabled={saving}
                  className="btn-glass flex-1 justify-center disabled:opacity-60 sm:flex-none"
                >
                  <Save className="h-3.5 w-3.5" />
                  {saving ? "Enregistrement…" : "Enregistrer"}
                </button>
                <button
                  onClick={confirm}
                  disabled={saving}
                  className="btn-primary-violet flex-1 justify-center disabled:opacity-60 sm:flex-none"
                >
                  <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
                  Valider
                </button>
                <button
                  onClick={() => setShowReject((s) => !s)}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/30 bg-rose-500/10 px-3.5 py-2 text-[12px] font-medium text-rose-300 transition hover:bg-rose-500/20"
                >
                  <X className="h-3.5 w-3.5" />
                  Rejeter
                </button>
                <button
                  onClick={skip}
                  disabled={saving}
                  className="inline-flex items-center gap-1.5 rounded-lg px-3.5 py-2 text-[12px] font-medium text-white/45 transition hover:bg-white/[0.05] hover:text-white/80"
                >
                  <SkipForward className="h-3.5 w-3.5" />
                  Passer
                </button>
              </>
            )}
            {(invoice.status === "confirmed" || invoice.status === "rejected") && (
              <button onClick={reopen} className="btn-glass">
                <RotateCcw className="h-3.5 w-3.5" />
                Réouvrir
              </button>
            )}
          </div>

          {showReject && editable && (
            <div className="glass p-4" style={{ borderRadius: 18 }}>
              <div className="relative z-10 space-y-2.5">
                <Label className="text-[11px] font-semibold uppercase tracking-[0.12em] text-white/45">
                  Raison du rejet
                </Label>
                <Textarea
                  value={rejectReason}
                  onChange={(e) => setRejectReason(e.target.value)}
                  placeholder="Document illisible, mauvais fournisseur, etc."
                  className="border-white/10 bg-white/[0.04] text-white placeholder:text-white/35 focus-visible:ring-rose-500/40"
                />
                <div className="flex gap-2">
                  <button
                    onClick={reject}
                    disabled={!rejectReason}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-rose-500/40 bg-rose-500/20 px-3.5 py-2 text-[12px] font-medium text-rose-100 transition hover:bg-rose-500/30 disabled:opacity-40"
                  >
                    Confirmer le rejet
                  </button>
                  <button
                    onClick={() => setShowReject(false)}
                    className="inline-flex items-center rounded-lg px-3.5 py-2 text-[12px] text-white/45 hover:text-white/80"
                  >
                    Annuler
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
