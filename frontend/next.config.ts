import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Section 12 cua spec: Docker Compose deployment - "standalone" gom du
  // node_modules can thiet vao .next/standalone, giup Dockerfile khong can
  // copy toan bo node_modules (nhieu tram MB) vao image production.
  output: "standalone",
};

export default nextConfig;
