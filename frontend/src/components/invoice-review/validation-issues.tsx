import type { ValidationErrors } from "@/lib/types";

const SEVERITY_CLASSES: Record<string, string> = {
  error: "border-destructive bg-destructive/10 text-destructive",
  warning: "border-amber-500 bg-amber-50 text-amber-800",
  info: "border-blue-500 bg-blue-50 text-blue-800",
};

export function ValidationIssues({ errors }: { errors: ValidationErrors | null }) {
  if (!errors || errors.issues.length === 0) {
    return (
      <div className="rounded-md border border-emerald-500 bg-emerald-50 p-3 text-sm text-emerald-800">
        ✓ Aucune erreur de validation détectée.
      </div>
    );
  }

  return (
    <ul className="space-y-2">
      {errors.issues.map((issue, idx) => (
        <li
          key={`${issue.code}-${idx}`}
          className={`rounded-md border p-2 text-sm ${SEVERITY_CLASSES[issue.severity] ?? ""}`}
        >
          <span className="font-medium uppercase">{issue.severity}</span> —{" "}
          <span>{issue.message}</span>
          {issue.field && (
            <span className="ml-2 text-xs opacity-70">({issue.field})</span>
          )}
        </li>
      ))}
    </ul>
  );
}
