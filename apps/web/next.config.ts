import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: ["@larder/api-client", "@larder/design-tokens"],
};

export default nextConfig;
