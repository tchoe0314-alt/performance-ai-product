import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  productionBrowserSourceMaps: process.env.NEXT_PRODUCTION_BROWSER_SOURCE_MAPS === "1",
  allowedDevOrigins: ["127.0.0.1"],
  ...(process.env.NODE_ENV === "production"
    ? {
        experimental: {
          cpus: Number(process.env.NEXT_BUILD_CPUS ?? "1"),
          staticGenerationMaxConcurrency: Number(
            process.env.NEXT_STATIC_GENERATION_MAX_CONCURRENCY ?? "1",
          ),
        },
      }
    : {}),
  async rewrites() {
    return [
      {
        source: "/demo/workspace",
        destination: "/",
      },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          {
            key: "Permissions-Policy",
            value: "camera=(), microphone=(), geolocation=()",
          },
        ],
      },
    ];
  },
};

export default nextConfig;
