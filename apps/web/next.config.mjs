/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  transpilePackages: ['three', 'three-stdlib', '@react-three/fiber', '@react-three/drei'],
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
};

export default nextConfig;
