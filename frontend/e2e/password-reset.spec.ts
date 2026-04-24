import { expect, test } from "@playwright/test";
import { makeAccount, registerViaApi } from "./helpers";

test.describe("Auth — password reset", () => {
  test("user resets password from a signed email link", async ({ page }) => {
    const account = makeAccount("reset");
    await registerViaApi(account);
    const newPassword = "NewPass-E2E-2026!";

    await page.goto("/forgot-password");
    await page.getByLabel("Email").fill(account.email);
    await page.getByRole("button", { name: "Envoyer le lien" }).click();
    await expect(page.getByText("Email envoyé si ce compte existe.")).toBeVisible();
    await page.getByRole("link", { name: "Ouvrir le lien de reset dev" }).click();

    await expect(page).toHaveURL(/\/reset-password\?token=/);
    await page.getByLabel("Mot de passe", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();
    await expect(page.getByText("Mot de passe mis à jour.")).toBeVisible();
    await expect(page).toHaveURL(/\/login/);

    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(newPassword);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
