#!/usr/bin/env bash
set -e

# ─── Vuddy Frontend + Cloudflare Tunnel (no account) ───
# Starts the Vite dev server and exposes it via a free Cloudflare tunnel.

FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"
VITE_PORT=5173

cleanup() {
  echo ""
  echo "🛑 Shutting down..."
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null
  [[ -n "$VITE_PID" ]]   && kill "$VITE_PID"   2>/dev/null
  wait 2>/dev/null
  echo "✅ All processes stopped."
  exit 0
}
trap cleanup INT TERM

# ─── 1. Ensure cloudflared is installed ───
if ! command -v cloudflared &>/dev/null; then
  echo "📦 Installing cloudflared to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  curl -sL -o "$HOME/.local/bin/cloudflared" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x "$HOME/.local/bin/cloudflared"
  export PATH="$HOME/.local/bin:$PATH"
  echo "✅ cloudflared installed"
fi
export PATH="$HOME/.local/bin:$PATH"

# ─── 2. Install npm deps if needed ───
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "📦 Installing npm dependencies..."
  cd "$FRONTEND_DIR" && npm install
fi

# ─── 3. Start Vite dev server ───
echo "🚀 Starting Vite dev server on port $VITE_PORT..."
cd "$FRONTEND_DIR"
npm run dev &
VITE_PID=$!

# Wait for Vite to be ready
echo "⏳ Waiting for Vite..."
for i in $(seq 1 30); do
  if curl -s "http://localhost:$VITE_PORT" >/dev/null 2>&1; then
    echo "✅ Vite is ready!"
    break
  fi
  sleep 0.5
done

# ─── 4. Start Cloudflare tunnel (no account) ───
echo ""
echo "🌐 Starting Cloudflare tunnel..."
echo "   (Look for the *.trycloudflare.com URL below)"
echo ""
cloudflared tunnel --url "http://localhost:$VITE_PORT" &
TUNNEL_PID=$!

# ─── 5. Keep running ───
wait
