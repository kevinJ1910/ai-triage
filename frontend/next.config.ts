import type {NextConfig} from 'next';

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  output: process.env.NEXT_STANDALONE === 'true' || process.env.DOCKER_BUILD === 'true' ? 'standalone' : undefined,
  transpilePackages: ['motion'],
};

export default nextConfig;
