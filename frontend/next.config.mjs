import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  productionBrowserSourceMaps: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  // typedRoutes was experimental and rejected string-typed hrefs (notifications entity links).
  // Disable it until we convert the remaining dynamic hrefs to typed Route<> forms.
};

export default withNextIntl(nextConfig);
