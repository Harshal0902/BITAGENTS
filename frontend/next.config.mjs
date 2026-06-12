/** @type {import('next').NextConfig} */
const nextConfig = {
  transpilePackages: ["@bitagents/shared"],
  experimental: {
    typedRoutes: false
  }
};

export default nextConfig;
