import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Security — API keys", () => {
  test("admin creates an API key, sees the secret once, then revokes it", async ({ page }) => {
    const account = makeAccount("apikeys");
    await seedAuth(page, account);

    await page.goto("/settings");
    await page.getByRole("button", { name: "Sécurité", exact: true }).click();

    // The "Clés API" section has a name input (defaults to "Integration key") + "Créer" button.
    const apiKeysHeading = page.getByText("Clés API", { exact: true });
    await expect(apiKeysHeading).toBeVisible();

    // There's only one input with value "Integration key" on this page.
    const nameInput = page.locator('input[value="Integration key"]');
    await nameInput.fill("Integration QA");

    // Fire the create button (unique "Créer" in that area).
    await page.getByRole("button", { name: "Créer", exact: true }).click();

    // Secret is displayed once with rjn_ prefix — use .first() because the key prefix also
    // appears in the list row below the secret banner.
    await expect(page.locator("text=/rjn_/").first()).toBeVisible({ timeout: 7_500 });

    // Revoke the key.
    await page.getByRole("button", { name: "Révoquer", exact: true }).click();

    // After revoke, the button flips to "Révoquée".
    await expect(page.getByRole("button", { name: "Révoquée", exact: true })).toBeVisible();
  });
});
