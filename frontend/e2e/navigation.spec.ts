import { expect, test } from "@playwright/test";
import { makeAccount, seedAuth } from "./helpers";

const PAGES: { path: string; expect: RegExp }[] = [
  { path: "/dashboard", expect: /Bonjour|Bon après-midi|Bonsoir/i },
  { path: "/invoices", expect: /Factures/i },
  { path: "/suppliers", expect: /Fournisseurs/i },
  { path: "/upload", expect: /Importer des factures/i },
  { path: "/integrations", expect: /Intégrations/i },
  { path: "/notifications", expect: /Notifications/i },
  { path: "/settings", expect: /Paramètres/i },
  { path: "/admin/users", expect: /Utilisateurs/i },
  { path: "/admin/audit", expect: /Journal d'audit/i },
];

test.describe("Navigation — main routes render without error", () => {
  // Next.js dev mode compiles routes on first load; allow generous per-page timeout.
  test.setTimeout(180_000);

  test("authenticated admin can open every page", async ({ page }) => {
    await seedAuth(page, makeAccount("nav"));

    const errors: string[] = [];
    page.on("pageerror", (err) => errors.push(err.message));

    for (const { path, expect: re } of PAGES) {
      await page.goto(path, { timeout: 90_000 });
      await expect(page).toHaveURL(new RegExp(path));
      await expect(page.getByRole("heading", { level: 1 })).toContainText(re);
    }

    expect(errors, `uncaught page errors: ${errors.join(" | ")}`).toEqual([]);
  });
});
