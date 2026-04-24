import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Admin — IP whitelist", () => {
  test("admin creates a CIDR rule and sees it in the list", async ({ page }) => {
    const account = makeAccount("ip-rules");
    await seedAuth(page, account);

    await page.goto("/admin/security/ip-rules");
    await expect(
      page.getByRole("heading", { name: /restrictions ip|ip restrictions/i }),
    ).toBeVisible();

    // Empty state
    await expect(
      page.getByText(/aucune règle définie|no rules defined|tout le trafic/i),
    ).toBeVisible();

    const cidr = `203.0.113.${Math.floor(Math.random() * 254) + 1}/32`;
    await page.getByLabel("CIDR").fill(cidr);
    await page.getByRole("button", { name: "Ajouter", exact: true }).click();

    // Rule appears in the list with the CIDR code + an "active" marker.
    await expect(page.getByText(cidr, { exact: true })).toBeVisible({ timeout: 5_000 });
    await expect(page.getByText(/1 règle active/i)).toBeVisible();
  });
});
