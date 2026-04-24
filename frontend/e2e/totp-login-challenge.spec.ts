import { expect, test } from "@playwright/test";
import { makeAccount, registerViaApi } from "./helpers";

const API_URL = process.env.E2E_API_URL ?? "http://localhost:6200";

test.describe("Security — TOTP login challenge", () => {
  test("login with 2FA-enabled user displays the TOTP input after 428", async ({ page }) => {
    const account = makeAccount("totp-chall");
    const tokens = await registerViaApi(account);

    // Enable TOTP via API (setup → enable with a known secret path).
    const setupRes = await fetch(`${API_URL}/security/totp/setup`, {
      method: "POST",
      headers: { Authorization: `Bearer ${tokens.access_token}` },
    });
    expect(setupRes.ok).toBeTruthy();
    const setup = (await setupRes.json()) as { secret: string };

    // Generate a TOTP code server-side by crafting a minimal RFC6238 computation via Node's crypto.
    const code = await totpCode(setup.secret);

    const enableRes = await fetch(`${API_URL}/security/totp/enable`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${tokens.access_token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ code }),
    });
    expect(enableRes.ok).toBeTruthy();

    // Now attempt login without TOTP → expect UI to surface the 2FA prompt.
    await page.goto("/login");
    await page.getByLabel("Email").fill(account.email);
    await page.getByLabel("Mot de passe", { exact: true }).fill(account.password);
    await page.getByRole("button", { name: "Se connecter" }).click();

    await expect(page.getByLabel(/code 2fa/i)).toBeVisible({ timeout: 7_500 });
    await expect(page.getByText(/code 2fa requis/i)).toBeVisible();
  });
});

// RFC 6238 TOTP generator (SHA-1, 30 s step, 6 digits).
async function totpCode(secretBase32: string): Promise<string> {
  const { createHmac } = await import("crypto");
  const key = base32Decode(secretBase32);
  const counter = Math.floor(Date.now() / 1000 / 30);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter));
  const hmac = createHmac("sha1", key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0xf;
  const bin =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);
  return (bin % 1_000_000).toString().padStart(6, "0");
}

function base32Decode(input: string): Buffer {
  const alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";
  const clean = input.toUpperCase().replace(/=+$/g, "").replace(/\s+/g, "");
  let bits = "";
  for (const ch of clean) {
    const idx = alphabet.indexOf(ch);
    if (idx === -1) continue;
    bits += idx.toString(2).padStart(5, "0");
  }
  const bytes: number[] = [];
  for (let i = 0; i + 8 <= bits.length; i += 8) {
    bytes.push(parseInt(bits.slice(i, i + 8), 2));
  }
  return Buffer.from(bytes);
}
