import { expect, Page } from "@playwright/test";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:6200";

export type TestAccount = {
  email: string;
  password: string;
  tenantName: string;
  fullName: string;
};

export function makeAccount(prefix = "e2e"): TestAccount {
  const stamp = Date.now();
  const rand = Math.random().toString(36).slice(2, 8);
  return {
    email: `${prefix}+${stamp}-${rand}@raijin-e2e.com`,
    password: "PassWord-E2E-2026!",
    tenantName: `E2E ${stamp}`,
    fullName: `E2E User ${rand}`,
  };
}

export async function registerViaApi(account: TestAccount) {
  const res = await fetch(`${API_URL}/auth/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email: account.email,
      password: account.password,
      full_name: account.fullName,
      tenant_name: account.tenantName,
    }),
  });
  if (!res.ok) {
    throw new Error(`register failed ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as { access_token: string; refresh_token: string };
}

export async function createSupplierViaApi(
  accessToken: string,
  supplier: {
    name: string;
    vat_number?: string;
    country_code?: string;
    city?: string;
    email?: string;
    phone?: string;
  },
) {
  const res = await fetch(`${API_URL}/suppliers`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify(supplier),
  });
  if (!res.ok) {
    throw new Error(`supplier create failed ${res.status}: ${await res.text()}`);
  }
  return (await res.json()) as { id: string; name: string };
}

export async function loginViaUi(page: Page, account: TestAccount) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(account.email);
  await page.getByLabel("Mot de passe", { exact: true }).fill(account.password);
  await page.getByRole("button", { name: "Se connecter" }).click();
  await expect(page).toHaveURL(/\/dashboard/);
}

export async function seedAuth(page: Page, account: TestAccount) {
  const tokens = await registerViaApi(account);
  await page.goto("/login");
  await page.evaluate(
    ({ access, refresh }) => {
      window.localStorage.setItem("raijin.access", access);
      window.localStorage.setItem("raijin.refresh", refresh);
    },
    { access: tokens.access_token, refresh: tokens.refresh_token },
  );
}
