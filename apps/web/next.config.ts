import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  productionBrowserSourceMaps: true,
  allowedDevOrigins: ["127.0.0.1"],
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
