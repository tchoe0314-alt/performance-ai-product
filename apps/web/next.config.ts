import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  productionBrowserSourceMaps: true,
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
