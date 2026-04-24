import { expect, test } from "@playwright/test";
import { createSupplierViaApi, makeAccount, registerViaApi } from "./helpers";

test.describe("Suppliers — manual management", () => {
  test("admin creates, edits, and merges a supplier", async ({ page }) => {
    const account = makeAccount("supplier");
    const tokens = await registerViaApi(account);
    await page.goto("/login");
    await page.evaluate(
      ({ access, refresh }) => {
        window.localStorage.setItem("raijin.access", access);
        window.localStorage.setItem("raijin.refresh", refresh);
      },
      { access: tokens.access_token, refresh: tokens.refresh_token },
    );

    const stamp = Date.now();
    const name = `Helios Services ${stamp}`;
    const duplicateName = `Helios Service ${stamp}`;
    await createSupplierViaApi(tokens.access_token, {
      name: duplicateName,
      vat_number: `FRDUP${stamp}`,
      country_code: "FR",
      city: "Lyon",
    });

    await page.goto("/suppliers");
    await page.getByRole("button", { name: "Nouveau" }).click();
    await page.getByLabel("Nom").fill(name);
    await page.getByLabel("VAT").fill(`FRNEW${stamp}`);
    await page.getByLabel("Pays").fill("FR");
    await page.getByLabel("Ville").fill("Paris");
    await page.getByLabel("Email").fill(`ap@helios-${stamp}.example`);
    await page.getByPlaceholder("Téléphone").fill("+33101010101");
    await page.getByRole("button", { name: "Créer" }).click();

    await expect(page).toHaveURL(/\/suppliers\/[^/]+$/);
    await expect(page.getByRole("heading", { level: 1 })).toContainText(name);

    await page.getByRole("button", { name: "Modifier" }).click();
    await page.getByLabel("Ville").fill("Marseille");
    await page.getByRole("button", { name: "Enregistrer" }).click();
    await expect(page.getByText("Marseille")).toBeVisible();

    await page.getByRole("button", { name: "Fusionner" }).click();
    await page.getByPlaceholder("Rechercher le fournisseur à absorber…").fill("Helios Service");
    await expect(page.getByText(duplicateName)).toBeVisible();
    await page.getByRole("button", { name: "Absorber" }).click();
    await expect(page.getByText(duplicateName)).toBeHidden();
  });
});
