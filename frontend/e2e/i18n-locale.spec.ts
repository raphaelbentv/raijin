import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("i18n — locale switcher", () => {
  test("switching to English translates the sidebar nav", async ({ page }) => {
    const account = makeAccount("i18n");
    await seedAuth(page, account);

    await page.goto("/settings");

    // baseline FR
    await expect(page.getByRole("link", { name: "Tableau de bord" })).toBeVisible();

    // switch to English via preferences tab
    await page.getByRole("button", { name: /préférences/i }).click();
    const localeSelect = page.locator("select").first();
    await localeSelect.selectOption("en");
    await page.getByRole("button", { name: /enregistrer la langue/i }).click();

    // cookie+reload kicks in from saveProfile; wait for reloaded page to render EN nav
    await expect(page.getByRole("link", { name: "Dashboard" })).toBeVisible({
      timeout: 10_000,
    });
    await expect(page.getByRole("link", { name: "Invoices" })).toBeVisible();
  });
});
