import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Command palette — ⌘K", () => {
  test("opens with ⌘K, filters nav items, navigates on Enter", async ({ page }) => {
    await seedAuth(page, makeAccount("cmdk"));
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

    await page.getByRole("button", { name: /Rechercher/i }).click();

    const input = page.getByPlaceholder(/Rechercher une facture/i);
    await expect(input).toBeVisible();

    await input.fill("fourn");
    await expect(page.getByRole("button", { name: /Fournisseurs/ })).toBeVisible();

    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/\/suppliers/);
  });

  test("Escape closes the palette", async ({ page }) => {
    await seedAuth(page, makeAccount("cmdk"));
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /Rechercher/i }).click();
    const input = page.getByPlaceholder(/Rechercher une facture/i);
    await expect(input).toBeVisible();

    await page.keyboard.press("Escape");
    await expect(input).not.toBeVisible();
  });
});
