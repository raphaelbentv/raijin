import createNextIntlPlugin from "next-intl/plugin";

const withNextIntl = createNextIntlPlugin("./src/i18n/request.ts");

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  productionBrowserSourceMaps: Boolean(process.env.NEXT_PUBLIC_SENTRY_DSN),
  experimental: {
    typedRoutes: true,
  },
};

export default withNextIntl(nextConfig);
