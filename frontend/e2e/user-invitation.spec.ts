import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Users — email invitation", () => {
  test("admin invites a user who activates the account from email link", async ({ page }) => {
    const admin = makeAccount("invite-admin");
    await seedAuth(page, admin);

    const stamp = Date.now();
    const invitedEmail = `invitee+${stamp}@raijin-e2e.com`;
    const invitedPassword = "InvitePass-E2E-2026!";

    await page.goto("/admin/users");
    await page.getByLabel("Email").fill(invitedEmail);
    await page.getByLabel("Nom").fill("Invited Reviewer");
    await page.getByLabel("Rôle").selectOption("reviewer");
    await page.getByRole("button", { name: "Inviter" }).click();

    await expect(page.getByText("Lien d'activation dev :")).toBeVisible();
    await page.getByRole("link", { name: /reset-password\?token=/ }).click();

    await expect(page).toHaveURL(/\/reset-password\?token=/);
    await page.waitForLoadState("networkidle");
    await page.getByLabel("Mot de passe", { exact: true }).fill(invitedPassword);
    await page.getByRole("button", { name: "Changer le mot de passe" }).click();
    await expect(page).toHaveURL(/\/login/);

    await page.getByLabel("Email").fill(invitedEmail);
    await page.getByLabel("Mot de passe", { exact: true }).fill(invitedPassword);
    await page.getByRole("button", { name: "Se connecter" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
