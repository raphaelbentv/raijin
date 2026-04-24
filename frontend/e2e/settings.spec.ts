import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Settings — profile", () => {
  test("user can update full_name and value persists on reload", async ({ page }) => {
    const account = makeAccount("settings");
    await seedAuth(page, account);

    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Paramètres" })).toBeVisible();

    const fullNameInput = page.getByPlaceholder("Prénom Nom");
    await expect(fullNameInput).toHaveValue(account.fullName);

    const newName = `Édité ${Date.now()}`;
    await fullNameInput.fill(newName);
    await page.getByRole("button", { name: "Enregistrer" }).click();

    await expect(page.getByText("Profil enregistré")).toBeVisible();

    await page.reload();
    await expect(page.getByPlaceholder("Prénom Nom")).toHaveValue(newName);
  });

  test("password form rejects mismatch between new and confirm", async ({ page }) => {
    const account = makeAccount("settings-pwd");
    await seedAuth(page, account);
    await page.goto("/settings");

    await page.getByRole("button", { name: "Sécurité" }).click();

    await page.getByLabel("Mot de passe actuel").fill(account.password);
    await page.getByLabel("Nouveau").fill("NewPass-2026!!");
    await page.getByLabel("Confirmer").fill("Different-2026!!");
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();

    await expect(page.getByText(/ne correspondent pas/i)).toBeVisible();
  });
});
