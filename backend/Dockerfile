# ── What is this file? ─────────────────────────────────────────────────────────
# A Dockerfile is a step-by-step recipe Docker reads top-to-bottom to build an
# image.  Each instruction creates a "layer" that Docker caches independently.
# Layers are like git commits: only the changed layers and everything after them
# are rebuilt.  That's why we copy requirements.txt BEFORE the rest of the code
# — pip install is slow and only needs to re-run when requirements.txt changes,
# not on every code edit.
# ──────────────────────────────────────────────────────────────────────────────

# FROM picks the base image — the starting filesystem.
# python:3.11-slim is a minimal Debian image with Python 3.11 pre-installed.
# "slim" removes docs, tests, and locale data (~50 MB vs ~350 MB for "full").
FROM python:3.11-slim

# WORKDIR sets the current directory for all subsequent instructions.
# If the path doesn't exist, Docker creates it.  Think of it like "cd /app"
# that persists for the rest of the build AND when the container starts.
WORKDIR /app

# --- Dependency layer (cached until requirements.txt changes) ---
# COPY <host path> <container path>
# We copy only requirements.txt first so Docker can cache the pip install layer.
COPY requirements.txt .

# RUN executes a shell command during the build (not at runtime).
# --no-cache-dir stops pip from writing its download cache inside the image,
# keeping the final image smaller.
RUN pip install --no-cache-dir -r requirements.txt

# --- Source layer (changes on every code edit) ---
# Now copy everything else.  Because this layer changes often, it comes last
# so it doesn't bust the pip-install cache above.
COPY . .

# EXPOSE is documentation only — it tells humans and orchestrators which port
# the process will listen on.  It does NOT open a port by itself; that's done
# by the "ports:" mapping in docker-compose.yml.
EXPOSE 8000

# CMD is the default command that runs when the container starts.
# Using JSON array form ("exec form") avoids wrapping the command in /bin/sh,
# which means signals like SIGTERM reach uvicorn directly (clean shutdown).
#
# --host 0.0.0.0  — bind to ALL network interfaces inside the container.
#                    Without this, uvicorn binds to 127.0.0.1 (loopback only)
#                    and is unreachable from outside the container.
# --reload        — watch source files and restart on changes (dev only).
CMD ["/bin/sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
