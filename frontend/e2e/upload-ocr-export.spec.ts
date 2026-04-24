import path from "node:path";
import { expect, test } from "@playwright/test";
import { makeAccount, registerViaApi } from "./helpers";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:6200";

async function waitForReview(invoiceId: string, accessToken: string) {
  await expect
    .poll(
      async () => {
        const res = await fetch(`${API_URL}/invoices/${invoiceId}`, {
          headers: { Authorization: `Bearer ${accessToken}` },
        });
        if (!res.ok) return "missing";
        const invoice = (await res.json()) as { status: string };
        return invoice.status;
      },
      { timeout: 45_000, intervals: [1000, 1500, 2500] },
    )
    .toBe("ready_for_review");
}

test.describe("Invoices — upload OCR review export", () => {
  // TODO(raijin-staging-debug): investigate why the POST /invoices/upload fetch is never
  // emitted in GitHub Actions (button enabled + file attached, yet waitForResponse times out
  // at 60 s). Suspected network/CORS preflight race specific to the docker-compose runner.
  // Passes locally; re-enable once the CI-only flake is reproduced in a debuggable env.
  test.skip(!!process.env.CI, "flaky in GitHub Actions — tracked under raijin-staging-debug");

  test("uploads a PDF, waits for mocked OCR, confirms, and exports Excel", async ({ page }) => {
    test.setTimeout(90_000); // CI worker cold-start can delay OCR processing
    const account = makeAccount("upload");
    const tokens = await registerViaApi(account);
    await page.goto("/login");
    await page.evaluate(
      ({ access, refresh }) => {
        window.localStorage.setItem("raijin.access", access);
        window.localStorage.setItem("raijin.refresh", refresh);
      },
      { access: tokens.access_token, refresh: tokens.refresh_token },
    );

    await page.goto("/upload");
    await page
      .locator('input[type="file"]')
      .setInputFiles(path.join(process.cwd(), "e2e/fixtures/invoice-sprint5.pdf"));

    // Wait until the pending file shows up in the drop zone list — ensures React has processed
    // the file-input onChange before we click the submit button.
    const importButton = page.getByRole("button", { name: /^Importer/ });
    await expect(importButton).toBeEnabled({ timeout: 5_000 });
    await expect(importButton).toContainText(/\(1\)/);

    // Match any response on /invoices/upload with an explicit 60 s timeout — in CI the first
    // upload can take longer due to MinIO + Celery enqueue cold start.
    const uploadResponsePromise = page.waitForResponse(
      (response) => response.url().includes("/invoices/upload"),
      { timeout: 60_000 },
    );
    await importButton.click();
    const uploadResponse = await uploadResponsePromise;
    expect(uploadResponse.status(), `upload response body: ${await uploadResponse.text().catch(() => "<n/a>")}`).toBe(201);
    const uploaded = (await uploadResponse.json()) as { id: string };
    await page.goto(`/invoices/${uploaded.id}`);

    await waitForReview(uploaded.id, tokens.access_token);
    await page.reload();
    await expect(page.getByText("À valider")).toBeVisible();
    await expect(page.locator('input[value^="SPR5-"]')).toBeVisible();

    await page.getByRole("button", { name: "Valider" }).click();
    await expect(page.getByText("Validée", { exact: true })).toBeVisible();

    await page.goto("/invoices");
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("button", { name: /Exporter Excel/ }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toMatch(/raijin.*\.xlsx$/);
  });
});
