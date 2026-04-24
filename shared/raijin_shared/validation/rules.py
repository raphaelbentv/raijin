from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

Severity = Literal["error", "warning", "info"]


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    field: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "issues": [
                {
                    "code": i.code,
                    "severity": i.severity,
                    "message": i.message,
                    "field": i.field,
                }
                for i in self.issues
            ]
        }


def _near(a: Decimal, b: Decimal, tolerance: Decimal = Decimal("0.02")) -> bool:
    return abs(a - b) <= tolerance


def validate_totals(
    subtotal: Decimal | None,
    total_tax: Decimal | None,
    invoice_total: Decimal | None,
    report: ValidationReport,
) -> None:
    if subtotal is None and total_tax is None and invoice_total is None:
        return

    if invoice_total is None:
        report.add(
            ValidationIssue(
                code="missing_invoice_total",
                severity="error",
                message="Total TTC manquant.",
                field="invoice_total",
            )
        )
        return

    if subtotal is not None and total_tax is not None:
        expected = subtotal + total_tax
        if not _near(expected, invoice_total):
            report.add(
                ValidationIssue(
                    code="totals_mismatch",
                    severity="error",
                    message=f"HT + TVA = {expected} ≠ TTC = {invoice_total}.",
                )
            )

    if subtotal is not None and subtotal > invoice_total:
        report.add(
            ValidationIssue(
                code="subtotal_gt_total",
                severity="error",
                message="Le total HT est supérieur au total TTC.",
            )
        )


def validate_confidence(
    overall: float | None,
    report: ValidationReport,
    *,
    error_threshold: float = 0.70,
    warning_threshold: float = 0.90,
) -> None:
    if overall is None:
        report.add(
            ValidationIssue(
                code="no_confidence",
                severity="warning",
                message="Confidence OCR non reportée.",
            )
        )
        return

    if overall < error_threshold:
        report.add(
            ValidationIssue(
                code="low_confidence",
                severity="error",
                message=f"Confidence OCR {overall:.2f} < seuil {error_threshold}.",
            )
        )
    elif overall < warning_threshold:
        report.add(
            ValidationIssue(
                code="medium_confidence",
                severity="warning",
                message=f"Confidence OCR {overall:.2f} < seuil {warning_threshold}.",
            )
        )


def validate_required_fields(
    vendor_name: str | None,
    invoice_id: str | None,
    invoice_date,  # date | None
    report: ValidationReport,
) -> None:
    if not vendor_name:
        report.add(
            ValidationIssue(
                code="missing_vendor_name",
                severity="error",
                message="Nom du fournisseur manquant.",
                field="vendor_name",
            )
        )
    if not invoice_id:
        report.add(
            ValidationIssue(
                code="missing_invoice_id",
                severity="warning",
                message="Numéro de facture manquant.",
                field="invoice_id",
            )
        )
    if invoice_date is None:
        report.add(
            ValidationIssue(
                code="missing_invoice_date",
                severity="error",
                message="Date d'émission manquante.",
                field="invoice_date",
            )
        )


def validate_dates(issue_date, due_date, report: ValidationReport) -> None:
    """Vérifie la cohérence des dates (émission ≤ échéance, émission pas trop future)."""
    from datetime import date, timedelta

    if issue_date and due_date and issue_date > due_date:
        report.add(
            ValidationIssue(
                code="issue_after_due",
                severity="error",
                message="La date d'émission est postérieure à l'échéance.",
                field="issue_date",
            )
        )

    if issue_date and issue_date > date.today() + timedelta(days=7):
        report.add(
            ValidationIssue(
                code="issue_date_future",
                severity="warning",
                message="Date d'émission dans le futur (>7 jours).",
                field="issue_date",
            )
        )


def validate_duplicate(has_duplicate: bool, existing_id, report: ValidationReport) -> None:
    if has_duplicate:
        report.add(
            ValidationIssue(
                code="possible_duplicate",
                severity="warning",
                message=f"Une facture similaire existe déjà ({existing_id}).",
            )
        )
