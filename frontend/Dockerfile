# ── Frontend Dockerfile ────────────────────────────────────────────────────────
# This runs Vite's dev server inside a container, giving you Hot Module
# Replacement (HMR) while editing files on your host machine.
# ──────────────────────────────────────────────────────────────────────────────

# node:20-alpine is the Node.js 20 LTS image built on Alpine Linux (~180 MB).
# Alpine is a security-focused minimal distro — much smaller than Debian-based
# images.  Use it when you don't need glibc-specific native modules.
FROM node:20-alpine

WORKDIR /app

# --- Dependency layer ---
# Copy package manifests first.  npm ci (clean install) is stricter than
# npm install: it uses package-lock.json exactly, fails on mismatches, and
# is reproducible.  Ideal for CI and containers.
COPY package.json package-lock.json ./
RUN npm ci

# --- Source layer ---
COPY . .

EXPOSE 5173

# npm run dev starts the Vite dev server.
# "-- --host 0.0.0.0" passes --host to the underlying Vite process.
# Without --host, Vite binds to 127.0.0.1 inside the container and is
# unreachable from your browser on the host machine.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
