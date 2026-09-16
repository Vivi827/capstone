/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep `next build` from replacing the CSS and manifests used by a running dev server.
  distDir: process.env.NODE_ENV === "development" ? ".next-dev" : ".next",
};

export default nextConfig;
