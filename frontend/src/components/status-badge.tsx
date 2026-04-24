import { cn } from "@/lib/utils";
import type { InvoiceStatus } from "@/lib/types";

const LABELS: Record<InvoiceStatus, string> = {
  uploaded: "Reçue",
  processing: "Traitement",
  ready_for_review: "À valider",
  confirmed: "Validée",
  rejected: "Rejetée",
  failed: "Échec",
};

const CLASSES: Record<InvoiceStatus, string> = {
  uploaded: "bg-slate-100 text-slate-700",
  processing: "bg-blue-100 text-blue-700",
  ready_for_review: "bg-amber-100 text-amber-800",
  confirmed: "bg-emerald-100 text-emerald-800",
  rejected: "bg-rose-100 text-rose-800",
  failed: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: InvoiceStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium",
        CLASSES[status],
      )}
    >
      {LABELS[status]}
    </span>
  );
}
