import { expect, test } from "@playwright/test";
import { makeAccount } from "./helpers";

test.describe("Auth — register & login golden paths", () => {
  test("register new tenant then lands on dashboard", async ({ page }) => {
    const account = makeAccount();

    await page.goto("/register");
    await page.getByLabel("Entreprise").fill(account.tenantName);
    await page.getByLabel("Nom complet").fill(account.fullName);
    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Créer mon compte" }).click();

    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  });

  test("login with wrong credentials shows error", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill("nobody@raijin-e2e.com");
    await page.getByLabel("Mot de passe", { exact: true }).fill("WrongPass-2026!");
    await page.getByRole("button", { name: "Se connecter" }).click();

    await expect(page.getByText("Email ou mot de passe incorrect")).toBeVisible();
  });

  test("login then logout returns to /login", async ({ page }) => {
    const account = makeAccount();
    await page.goto("/register");
    await page.getByLabel("Entreprise").fill(account.tenantName);
    await page.getByLabel("Nom complet").fill(account.fullName);
    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Créer mon compte" }).click();
    await expect(page).toHaveURL(/\/dashboard/);

    const tokens = await page.evaluate(() => ({
      access: localStorage.getItem("raijin.access"),
      refresh: localStorage.getItem("raijin.refresh"),
    }));
    expect(tokens.access).toBeTruthy();
    expect(tokens.refresh).toBeTruthy();

    await page.evaluate(() => {
      localStorage.removeItem("raijin.access");
      localStorage.removeItem("raijin.refresh");
    });
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});
