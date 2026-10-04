/** @type {import('next').NextConfig} */
const isStaticExport =
  process.env.OUTPUT_EXPORT === 'true' ||
  process.env.STATIC_EXPORT === 'true' ||
  process.env.TAURI_ENV_PLATFORM !== undefined;

const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three', 'three-stdlib', '@react-three/fiber', '@react-three/drei'],
  ...(isStaticExport
    ? {
        output: 'export',
        trailingSlash: true,
        images: {
          unoptimized: true,
        },
      }
    : {
        async rewrites() {
          return [
            {
              source: '/api/v1/:path*',
              destination: 'http://127.0.0.1:8000/api/v1/:path*',
            },
            {
              source: '/models/:path*',
              destination: 'http://127.0.0.1:8000/models/:path*',
            },
            {
              source: '/projects/:path*',
              destination: 'http://127.0.0.1:8000/projects/:path*',
            },
            {
              source: '/printers/:path*',
              destination: 'http://127.0.0.1:8000/printers/:path*',
            },
            {
              source: '/health',
              destination: 'http://127.0.0.1:8000/health',
            },
          ];
        },
      }),
};

export default nextConfig;
