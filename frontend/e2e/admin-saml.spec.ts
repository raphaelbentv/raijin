import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

test.describe("Admin — SAML SSO config", () => {
  test("admin fills and saves SAML config", async ({ page }) => {
    const account = makeAccount("saml-cfg");
    await seedAuth(page, account);

    await page.goto("/admin/security/saml");
    await expect(page.getByRole("heading", { name: /sso saml|saml sso/i })).toBeVisible();

    // SP metadata block is rendered dynamically with tenant slug
    await expect(page.getByText(/auth\/saml\/acs\//)).toBeVisible();

    await page.getByLabel("IdP Entity ID").fill("http://idp.example.com/entity");
    await page.getByLabel("SSO URL (Single Sign-On)").fill("https://idp.example.com/sso");
    await page
      .getByLabel(/certificat x\.509|x509|public key/i)
      .fill("-----BEGIN CERTIFICATE-----\nMIIBfake\n-----END CERTIFICATE-----");

    await page.getByRole("button", { name: /enregistrer la configuration/i }).click();
    await expect(page.getByText(/configuration saml enregistrée/i)).toBeVisible();
  });
});
