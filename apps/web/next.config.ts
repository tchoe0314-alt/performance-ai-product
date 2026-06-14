import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  productionBrowserSourceMaps: process.env.NEXT_PRODUCTION_BROWSER_SOURCE_MAPS !== "0",
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
};

export default nextConfig;
