import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // We open the site at http://127.0.0.1:3000 (same site as the backend at
  // 127.0.0.1:8000, so cookies work). The dev server only trusts "localhost"
  // by default, so allow 127.0.0.1 too.
  allowedDevOrigins: ["127.0.0.1"],
};

export default nextConfig;
