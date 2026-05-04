/** @type {import('next').NextConfig} */
const nextConfig = {
  outputFileTracingIncludes: {
    "/api/portfolio": ["./data/symbols/*.json"],
    "/api/symbols": ["./data/symbols/*.json"],
  },
};

export default nextConfig;
