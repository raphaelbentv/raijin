"""Seed demo data pour la démo / le dev.

Usage :
    docker compose exec backend python -m app.scripts.seed_demo [--tenant-slug venio] [--reset]

Crée ~35 factures avec statuts variés, ~5 suppliers, des lignes, des corrections
et quelques audit logs. Idempotent par défaut (ne duplique pas).
"""
from __future__ import annotations

import argparse
import asyncio
import random
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from raijin_shared.models.audit import AuditLog
from raijin_shared.models.correction import InvoiceCorrection
from raijin_shared.models.invoice import Invoice, InvoiceLine, InvoiceStatus
from raijin_shared.models.notification import Notification, NotificationKind
from raijin_shared.models.supplier import Supplier
from raijin_shared.models.tenant import Tenant
from raijin_shared.models.user import User
from sqlalchemy import delete, select

from app.core.database import SessionLocal

SUPPLIERS_DATA = [
    {
        "name": "ΕΛΛΗΝΙΚΗ ΒΙΟΜΗΧΑΝΙΑ ΑΕ",
        "vat_number": "EL123456789",
        "country_code": "GR",
        "city": "Athènes",
        "postal_code": "11251",
    },
    {
        "name": "Acme SA",
        "vat_number": "FR12345678901",
        "country_code": "FR",
        "city": "Paris",
        "postal_code": "75008",
    },
    {
        "name": "Olivier Logistics SARL",
        "vat_number": "FR78901234567",
        "country_code": "FR",
        "city": "Lyon",
        "postal_code": "69002",
    },
    {
        "name": "Epsilon Hellas Ltd",
        "vat_number": "EL987654321",
        "country_code": "GR",
        "city": "Thessalonique",
        "postal_code": "54621",
    },
    {
        "name": "Nord Energy",
        "vat_number": "DE234567891",
        "country_code": "DE",
        "city": "Hambourg",
        "postal_code": "20095",
    },
]

ACTIONS_LOG = [
    "invoice.confirm",
    "invoice.reject",
    "invoice.reopen",
    "user.create",
    "user.update",
]


def _make_invoice_row(
    tenant_id: uuid.UUID,
    supplier: Supplier,
    uploader_id: uuid.UUID,
    idx: int,
    status: InvoiceStatus,
) -> tuple[Invoice, list[InvoiceLine]]:
    issue = date.today() - timedelta(days=random.randint(0, 28))
    due = issue + timedelta(days=random.choice([15, 30, 45, 60]))

    ht = Decimal(random.randint(120, 4200))
    vat_rate = random.choice([Decimal("0.06"), Decimal("0.13"), Decimal("0.24")])
    vat = (ht * vat_rate).quantize(Decimal("0.01"))
    ttc = (ht + vat).quantize(Decimal("0.01"))

    checksum = uuid.uuid4().hex
    key_prefix = f"tenants/{tenant_id}/invoices/{issue:%Y/%m}"
    file_key = f"{key_prefix}/{uuid.uuid4()}.pdf"
    file_name = f"facture-{supplier.name.split()[0].lower()}-{idx:04d}.pdf"
    invoice_num = f"{random.choice(['A', 'INV', 'F'])}-{issue:%Y%m}-{idx:03d}"

    has_extraction = status in {
        InvoiceStatus.READY_FOR_REVIEW,
        InvoiceStatus.CONFIRMED,
        InvoiceStatus.REJECTED,
    }

    confidence = None
    if has_extraction:
        confidence = Decimal(str(round(random.uniform(0.82, 0.98), 4)))

    invoice = Invoice(
        tenant_id=tenant_id,
        uploader_user_id=uploader_id,
        supplier_id=supplier.id if has_extraction else None,
        status=status,
        invoice_number=invoice_num if has_extraction else None,
        issue_date=issue if has_extraction else None,
        due_date=due if has_extraction else None,
        currency="EUR",
        total_ht=ht if has_extraction else None,
        total_vat=vat if has_extraction else None,
        total_ttc=ttc if has_extraction else None,
        source_file_key=file_key,
        source_file_mime="application/pdf",
        source_file_size=random.randint(80_000, 450_000),
        source_file_checksum=checksum,
        source_file_name=file_name,
        ocr_confidence=confidence,
        confirmed_at=issue + timedelta(days=random.randint(0, 5))
        if status == InvoiceStatus.CONFIRMED
        else None,
        rejected_reason="Document illisible — demande de ré-upload" if status == InvoiceStatus.REJECTED else None,
    )

    lines: list[InvoiceLine] = []
    if has_extraction:
        n_lines = random.randint(1, 4)
        remaining_ht = ht
        for line_n in range(1, n_lines + 1):
            if line_n == n_lines:
                line_ht = remaining_ht
            else:
                line_ht = (remaining_ht * Decimal(str(random.uniform(0.25, 0.55)))).quantize(
                    Decimal("0.01")
                )
                remaining_ht -= line_ht
            qty = Decimal(random.randint(1, 10))
            unit_price = (line_ht / qty).quantize(Decimal("0.01"))
            line_ttc = (line_ht * (Decimal("1") + vat_rate)).quantize(Decimal("0.01"))
            lines.append(
                InvoiceLine(
                    line_number=line_n,
                    description=random.choice(
                        [
                            "Prestation de conseil",
                            "Licence logicielle mensuelle",
                            "Matières premières lot A",
                            "Transport express",
                            "Maintenance préventive",
                            "Hébergement cloud",
                        ]
                    ),
                    quantity=qty,
                    unit_price=unit_price,
                    vat_rate=vat_rate,
                    line_total_ht=line_ht,
                    line_total_ttc=line_ttc,
                )
            )
    return invoice, lines


async def seed(tenant_slug: str, reset: bool) -> None:
    async with SessionLocal() as session:
        tenant = await session.scalar(select(Tenant).where(Tenant.slug == tenant_slug))
        if tenant is None:
            print(f"❌ Tenant introuvable : slug={tenant_slug}")
            print("   → register un compte via /auth/register d'abord.")
            return

        admin = await session.scalar(
            select(User)
            .where(User.tenant_id == tenant.id, User.is_active.is_(True))
            .order_by(User.created_at.asc())
            .limit(1)
        )
        if admin is None:
            print(f"❌ Aucun utilisateur actif pour le tenant {tenant_slug}.")
            return

        if reset:
            print(f"🧹 Reset data tenant {tenant_slug}…")
            await session.execute(
                delete(AuditLog).where(AuditLog.tenant_id == tenant.id)
            )
            await session.execute(
                delete(InvoiceCorrection).where(InvoiceCorrection.tenant_id == tenant.id)
            )
            await session.execute(
                delete(Invoice).where(Invoice.tenant_id == tenant.id)
            )
            await session.execute(
                delete(Supplier).where(Supplier.tenant_id == tenant.id)
            )
            await session.commit()

        # ─── Suppliers ─────────────────────────────────────────
        suppliers: list[Supplier] = []
        for data in SUPPLIERS_DATA:
            existing = await session.scalar(
                select(Supplier).where(
                    Supplier.tenant_id == tenant.id,
                    Supplier.vat_number == data["vat_number"],
                )
            )
            if existing:
                suppliers.append(existing)
                continue
            s = Supplier(tenant_id=tenant.id, **data)
            session.add(s)
            suppliers.append(s)
        await session.flush()
        print(f"✅ {len(suppliers)} fournisseurs prêts")

        # ─── Invoices ──────────────────────────────────────────
        status_mix = (
            [InvoiceStatus.CONFIRMED] * 18
            + [InvoiceStatus.READY_FOR_REVIEW] * 8
            + [InvoiceStatus.PROCESSING] * 3
            + [InvoiceStatus.UPLOADED] * 2
            + [InvoiceStatus.REJECTED] * 3
            + [InvoiceStatus.FAILED] * 1
        )
        random.shuffle(status_mix)

        created_invoices: list[Invoice] = []
        for idx, status in enumerate(status_mix, start=1):
            supplier = random.choice(suppliers)
            invoice, lines = _make_invoice_row(
                tenant.id, supplier, admin.id, idx, status
            )
            session.add(invoice)
            await session.flush()
            for line in lines:
                line.invoice_id = invoice.id
                session.add(line)
            created_invoices.append(invoice)
        await session.flush()
        print(f"✅ {len(created_invoices)} factures créées")

        # ─── Corrections ───────────────────────────────────────
        confirmed = [i for i in created_invoices if i.status == InvoiceStatus.CONFIRMED]
        for inv in random.sample(confirmed, min(6, len(confirmed))):
            for field in random.sample(
                ["invoice_number", "total_vat", "due_date"],
                k=random.randint(1, 2),
            ):
                session.add(
                    InvoiceCorrection(
                        tenant_id=tenant.id,
                        invoice_id=inv.id,
                        user_id=admin.id,
                        field=field,
                        before_value=f"auto_{field}",
                        after_value=f"human_{field}",
                    )
                )
        print("✅ Quelques corrections ajoutées")

        # ─── Audit logs ────────────────────────────────────────
        now = datetime.now(UTC)
        for _ in range(20):
            action = random.choice(ACTIONS_LOG)
            entity_type = "invoice" if action.startswith("invoice") else "user"
            ts = now - timedelta(minutes=random.randint(1, 48 * 60))
            log = AuditLog(
                tenant_id=tenant.id,
                user_id=admin.id,
                action=action,
                entity_type=entity_type,
                entity_id=random.choice(created_invoices).id
                if entity_type == "invoice"
                else admin.id,
                ip_address="127.0.0.1",
                user_agent="seed-demo",
            )
            log.created_at = ts  # type: ignore
            session.add(log)
        await session.commit()
        print("✅ 20 audit logs créés")

        # ─── Notifications ────────────────────────────────────
        review_invoices = [
            i for i in created_invoices if i.status == InvoiceStatus.READY_FOR_REVIEW
        ]
        failed_invoices = [
            i for i in created_invoices if i.status == InvoiceStatus.FAILED
        ]

        notif_specs = []
        for inv in review_invoices[:3]:
            notif_specs.append(
                (
                    NotificationKind.INVOICE_READY,
                    "Nouvelle facture à valider",
                    f"{inv.source_file_name} — OCR terminé",
                    "invoice",
                    inv.id,
                )
            )
        for inv in failed_invoices[:1]:
            notif_specs.append(
                (
                    NotificationKind.INVOICE_FAILED,
                    "Échec OCR",
                    f"Le traitement de {inv.source_file_name} a échoué après 3 tentatives.",
                    "invoice",
                    inv.id,
                )
            )
        notif_specs.append(
            (
                NotificationKind.INTEGRATION_SYNCED,
                "Outlook synchronisé",
                "12 pièces jointes récupérées sur les 24 dernières heures.",
                "email_source",
                None,
            )
        )
        notif_specs.append(
            (
                NotificationKind.SYSTEM,
                "Bienvenue sur Raijin",
                "Commence par connecter une boîte Outlook ou Gmail pour automatiser l'ingestion.",
                None,
                None,
            )
        )

        for kind, title, body, ent_type, ent_id in notif_specs:
            session.add(
                Notification(
                    tenant_id=tenant.id,
                    user_id=admin.id,
                    kind=kind,
                    title=title,
                    body=body,
                    entity_type=ent_type,
                    entity_id=ent_id,
                )
            )
        await session.commit()
        print(f"✅ {len(notif_specs)} notifications créées")

        print(f"\n🎉 Seed terminé pour {tenant.name} ({tenant_slug})")
        print(f"   · {len(suppliers)} fournisseurs · {len(created_invoices)} factures")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-slug", default="venio", help="slug du tenant à seeder")
    parser.add_argument("--reset", action="store_true", help="supprime les données existantes")
    args = parser.parse_args()
    asyncio.run(seed(args.tenant_slug, args.reset))


if __name__ == "__main__":
    main()
