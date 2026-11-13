import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backend = process.env.TELEMETRYX_API_URL || "http://127.0.0.1:8000";
    return [{ source: "/api/v1/industrial/:path*", destination: `${backend}/api/v1/industrial/:path*` }];
  },
};

export default nextConfig;
