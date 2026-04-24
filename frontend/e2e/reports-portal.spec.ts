import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { expect, test } from "@playwright/test";
import { makeAccount, registerViaApi } from "./helpers";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:6200";

async function currentUser(accessToken: string) {
  const res = await fetch(`${API_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!res.ok) throw new Error(`me failed ${res.status}: ${await res.text()}`);
  return (await res.json()) as { id: string; tenant: { id: string } };
}

function seedInvoice(sql: string) {
  execFileSync(
    "docker",
    ["compose", "-f", "../docker-compose.yml", "exec", "-T", "postgres", "psql", "-U", "raijin", "-d", "raijin", "-v", "ON_ERROR_STOP=1", "-c", sql],
    { cwd: process.cwd(), stdio: "pipe" },
  );
}

test.describe("Reports and portal", () => {
  test("admin reviews reports and opens a public invoice portal link", async ({ page }) => {
    const account = makeAccount("reports");
    const tokens = await registerViaApi(account);
    const me = await currentUser(tokens.access_token);
    const invoiceId = randomUUID();
    const stamp = Date.now();

    seedInvoice(`
      INSERT INTO invoices (
        id, tenant_id, uploader_user_id, status, invoice_number,
        issue_date, due_date, currency, total_ht, total_vat, total_ttc,
        source_file_key, source_file_mime, source_file_size, source_file_checksum,
        source_file_name
      ) VALUES (
        '${invoiceId}', '${me.tenant.id}', '${me.id}', 'confirmed', 'RPT-${stamp}',
        '2026-04-01', '2026-04-30', 'EUR', 100.00, 24.00, 124.00,
        'e2e/${stamp}/portal.pdf', 'application/pdf', 1200, '${randomUUID().replaceAll("-", "")}',
        'portal-${stamp}.pdf'
      );
    `);

    await page.goto("/login");
    await page.evaluate(
      ({ access, refresh }) => {
        window.localStorage.setItem("raijin.access", access);
        window.localStorage.setItem("raijin.refresh", refresh);
      },
      { access: tokens.access_token, refresh: tokens.refresh_token },
    );

    await page.goto("/reports");
    await expect(page.getByRole("heading", { name: "Rapports" })).toBeVisible();
    await expect(page.getByText("TVA", { exact: true })).toBeVisible();

    const shareRes = await fetch(`${API_URL}/invoices/${invoiceId}/share`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    expect(shareRes.ok).toBeTruthy();
    const share = (await shareRes.json()) as { url: string };

    await page.goto(share.url);
    await expect(page.getByRole("heading", { name: `RPT-${stamp}` })).toBeVisible();
    await expect(page.getByText(/124,00/)).toBeVisible();
  });
});
