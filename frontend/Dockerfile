# Stage 1: Install dependencies and build the Next.js app
# Stage 2: Copy only the production build output
#
# Next.js with output: "standalone" bundles everything needed
# to run into .next/standalone, so the runtime image doesn't
# need the full node_modules directory.
# ============================================================

# --- Stage 1: Builder ---
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for layer caching
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source code and build
COPY . .

# Build the Next.js app.
# This generates .next/standalone (a self-contained Node.js server)
# and .next/static (static assets like CSS and images).
RUN npm run build

# --- Stage 2: Runtime ---
FROM node:20-alpine

WORKDIR /app

# Copy the standalone build output.
# This includes a minimal Node.js server that serves the app
# without needing the full node_modules.
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

# HOSTNAME 0.0.0.0 tells Next.js to listen on all interfaces
# (same reason as the backend — containers need external access)
ENV HOSTNAME="0.0.0.0"
ENV PORT=3000

CMD ["node", "server.js"]