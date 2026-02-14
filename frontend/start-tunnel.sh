#!/usr/bin/env bash
set -e

# Starts backend + Vite + Cloudflare tunnel together.

FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$FRONTEND_DIR/.." && pwd)"
VITE_PORT=5173
BACKEND_PORT=8000
BACKEND_HOST=0.0.0.0
BACKEND_CMD="${BACKEND_CMD:-}"
BACKEND_STARTED_BY_SCRIPT=0

choose_backend_cmd() {
  if [ -n "$BACKEND_CMD" ]; then
    return
  fi

  if python3 -c "import uvicorn" >/dev/null 2>&1; then
    BACKEND_CMD="python3 -m uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT"
    return
  fi

  if python -c "import uvicorn" >/dev/null 2>&1; then
    BACKEND_CMD="python -m uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT"
    return
  fi

  if command -v uvicorn >/dev/null 2>&1; then
    BACKEND_CMD="uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT"
    return
  fi

  echo "❌ Could not find uvicorn in current environment."
  echo "   Activate your micromamba env first, or pass BACKEND_CMD explicitly."
  echo "   Example:"
  echo "   BACKEND_CMD='micromamba run -n YOUR_ENV python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000' ./start-tunnel.sh"
  exit 1
}

cleanup() {
  echo ""
  echo "🛑 Shutting down..."
  if [[ -n "$BACKEND_PID" && "$BACKEND_STARTED_BY_SCRIPT" = "1" ]]; then
    kill "$BACKEND_PID" 2>/dev/null
  fi
  [[ -n "$TUNNEL_PID" ]] && kill "$TUNNEL_PID" 2>/dev/null
  [[ -n "$VITE_PID" ]] && kill "$VITE_PID" 2>/dev/null
  wait 2>/dev/null
  echo "✅ All processes stopped."
  exit 0
}
trap cleanup INT TERM

if ! command -v cloudflared &>/dev/null; then
  echo "📦 Installing cloudflared to ~/.local/bin..."
  mkdir -p "$HOME/.local/bin"
  curl -sL -o "$HOME/.local/bin/cloudflared" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64
  chmod +x "$HOME/.local/bin/cloudflared"
  export PATH="$HOME/.local/bin:$PATH"
  echo "✅ cloudflared installed"
fi
export PATH="$HOME/.local/bin:$PATH"

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "📦 Installing npm dependencies..."
  cd "$FRONTEND_DIR" && npm install
fi

if curl -s "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
  echo "✅ Existing backend detected on port $BACKEND_PORT (reusing)"
else
  echo "🚀 Starting backend on port $BACKEND_PORT..."
  cd "$ROOT_DIR"
  choose_backend_cmd
  echo "   Backend command: $BACKEND_CMD"
  eval "$BACKEND_CMD" &
  BACKEND_PID=$!
  BACKEND_STARTED_BY_SCRIPT=1

  echo "⏳ Waiting for backend health..."
  BACKEND_READY=0
  for i in $(seq 1 60); do
    if curl -s "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
      BACKEND_READY=1
      echo "✅ Backend is ready!"
      break
    fi
    if ! kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
      echo "❌ Backend process exited early."
      wait "$BACKEND_PID" || true
      exit 1
    fi
    sleep 0.5
  done

  if [ "$BACKEND_READY" -ne 1 ]; then
    echo "❌ Backend did not become ready on :$BACKEND_PORT"
    exit 1
  fi
fi

echo "🚀 Starting Vite dev server on port $VITE_PORT..."
cd "$FRONTEND_DIR"
npm run dev &
VITE_PID=$!

echo "⏳ Waiting for Vite..."
for i in $(seq 1 40); do
  if curl -s "http://localhost:$VITE_PORT" >/dev/null 2>&1; then
    echo "✅ Vite is ready!"
    break
  fi
  sleep 0.5
done

echo ""
echo "🌐 Starting Cloudflare tunnel..."
echo "   Backend proxy target: http://localhost:$BACKEND_PORT"
echo "   Look for the *.trycloudflare.com URL below."
echo ""
cloudflared tunnel --url "http://localhost:$VITE_PORT" &
TUNNEL_PID=$!

wait
