import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { createSupplierViaApi, makeAccount, registerViaApi } from "./helpers";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:6200";

async function currentUser(accessToken: string) {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`me failed ${res.status}: ${await res.text()}`);
  return (await res.json()) as { id: string; tenant: { id: string } };
}

function seedInvoicePair(sql: string) {
  execFileSync(
    "docker",
    ["compose", "-f", "../docker-compose.yml", "exec", "-T", "postgres", "psql", "-U", "raijin", "-d", "raijin", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { cwd: process.cwd(), stdio: "pipe" },
  );
}

test.describe("Invoices — duplicate detection", () => {
  test("reviewer sees a possible duplicate badge after fuzzy match", async ({ page }) => {
    const account = makeAccount("dupe");
    const tokens = await registerViaApi(account);
    const me = await currentUser(tokens.access_token);
    const supplier = await createSupplierViaApi(tokens.access_token, {
      name: `Duplicate Supplier ${Date.now()}`,
      vat_number: `FRD${Date.now()}`,
      country_code: "FR",
    });
    await page.goto("/login");
    await page.evaluate(
      ({ access, refresh }) => {
        window.localStorage.setItem("raijin.access", access);
        window.localStorage.setItem("raijin.refresh", refresh);
      },
      { access: tokens.access_token, refresh: tokens.refresh_token },
    );

    const existingId = randomUUID();
    const candidateId = randomUUID();
    const stamp = Date.now();
    seedInvoicePair(`
      INSERT INTO invoices (
        id, tenant_id, uploader_user_id, supplier_id, status, invoice_number,
        issue_date, due_date, currency, total_ht, total_vat, total_ttc,
        source_file_key, source_file_mime, source_file_size, source_file_checksum,
        source_file_name
      ) VALUES
      (
        '${existingId}', '${me.tenant.id}', '${me.id}', '${supplier.id}', 'confirmed',
        'INV-2026-0042', '2026-04-01', '2026-04-30', 'EUR', 100.00, 20.00, 120.00,
        'e2e/${stamp}/existing.pdf', 'application/pdf', 1200, '${randomUUID().replaceAll("-", "")}',
        'existing-duplicate.pdf'
      ),
      (
        '${candidateId}', '${me.tenant.id}', '${me.id}', '${supplier.id}', 'ready_for_review',
        'INV 2026 004Z', '2026-04-02', '2026-04-30', 'EUR', 100.00, 20.00, 120.00,
        'e2e/${stamp}/candidate.pdf', 'application/pdf', 1200, '${randomUUID().replaceAll("-", "")}',
        'candidate-duplicate.pdf'
      );
    `);

    await page.goto(`/invoices/${candidateId}`);
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await page.reload();
    await expect(page.getByRole("link", { name: "Possible doublon" })).toBeVisible();

    await page.goto("/invoices");
    await expect(page.getByText("Doublon")).toBeVisible();
  });
});
