import { getRequestConfig } from "next-intl/server";
import { cookies, headers } from "next/headers";

export const locales = ["fr", "en", "el"] as const;
export const defaultLocale = "fr";

export type Locale = (typeof locales)[number];

export default getRequestConfig(async () => {
  const cookieLocale = cookies().get("raijin.locale")?.value;
  const accepted = headers().get("accept-language") ?? "";
  const browserLocale = locales.find((candidate) => accepted.toLowerCase().startsWith(candidate));
  const locale: Locale = locales.includes(cookieLocale as Locale)
    ? (cookieLocale as Locale)
    : browserLocale ?? defaultLocale;
  return {
    locale,
    messages: (await import(`./messages/${locale}.json`)).default,
  };
});
