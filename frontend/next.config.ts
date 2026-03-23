/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_OUTPUT === "export" ? "export" : "standalone",
  images: {
    unoptimized: true,
  },
};

module.exports = nextConfig;