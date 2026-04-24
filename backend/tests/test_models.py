from app.models import (
    AuditLog,
    Base,
    Invoice,
    InvoiceLine,
    InvoiceStatus,
    Supplier,
    Tenant,
    User,
    UserRole,
)


def test_metadata_registers_all_tables() -> None:
    expected = {
        "tenants",
        "users",
        "suppliers",
        "invoices",
        "invoice_lines",
        "audit_logs",
    }
    assert expected.issubset(set(Base.metadata.tables.keys()))


def test_invoice_status_enum_values() -> None:
    assert {s.value for s in InvoiceStatus} == {
        "uploaded",
        "processing",
        "ready_for_review",
        "confirmed",
        "rejected",
        "failed",
    }


def test_user_role_enum_values() -> None:
    assert {r.value for r in UserRole} == {"admin", "user", "reviewer", "viewer"}


def test_tenant_tablename() -> None:
    assert Tenant.__tablename__ == "tenants"
    assert User.__tablename__ == "users"
    assert Supplier.__tablename__ == "suppliers"
    assert Invoice.__tablename__ == "invoices"
    assert InvoiceLine.__tablename__ == "invoice_lines"
    assert AuditLog.__tablename__ == "audit_logs"
