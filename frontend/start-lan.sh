#!/usr/bin/env bash
set -e

# Starts backend + Vite for local/LAN testing (no Cloudflare tunnel).
# Usage:
#   ./start-lan.sh
#   BACKEND_CMD="micromamba run -n vuddy python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000" ./start-lan.sh

FRONTEND_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$FRONTEND_DIR/.." && pwd)"
VITE_PORT="${VITE_PORT:-5173}"
BACKEND_PORT="${BACKEND_PORT:-8000}"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_CMD="${BACKEND_CMD:-}"
BACKEND_STARTED_BY_SCRIPT=0

choose_backend_cmd() {
  if [ -n "$BACKEND_CMD" ]; then
    return
  fi

  if /home/nathan/micromamba/envs/vuddy/bin/python -c "import uvicorn" >/dev/null 2>&1; then
    BACKEND_CMD="/home/nathan/micromamba/envs/vuddy/bin/python -m uvicorn backend.main:app --host $BACKEND_HOST --port $BACKEND_PORT"
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
  exit 1
}

cleanup() {
  echo ""
  echo "🛑 Shutting down..."
  if [[ -n "$BACKEND_PID" && "$BACKEND_STARTED_BY_SCRIPT" = "1" ]]; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$VITE_PID" ]]; then
    kill "$VITE_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
  echo "✅ All processes stopped."
  exit 0
}
trap cleanup INT TERM

if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "📦 Installing npm dependencies..."
  cd "$FRONTEND_DIR" && npm install
fi

if curl -s "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
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
  for i in $(seq 1 80); do
    if curl -s "http://127.0.0.1:$BACKEND_PORT/health" >/dev/null 2>&1; then
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

echo "🚀 Starting Vite dev server on port $VITE_PORT (LAN mode)..."
cd "$FRONTEND_DIR"
npm run dev -- --host 0.0.0.0 --port "$VITE_PORT" &
VITE_PID=$!

echo "⏳ Waiting for Vite..."
VITE_READY=0
for i in $(seq 1 60); do
  if curl -s "http://127.0.0.1:$VITE_PORT" >/dev/null 2>&1; then
    VITE_READY=1
    echo "✅ Vite is ready!"
    break
  fi
  if ! kill -0 "$VITE_PID" >/dev/null 2>&1; then
    echo "❌ Vite process exited early."
    wait "$VITE_PID" || true
    exit 1
  fi
  sleep 0.5
done

if [ "$VITE_READY" -ne 1 ]; then
  echo "❌ Vite did not become ready on :$VITE_PORT"
  exit 1
fi

WSL_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"

echo ""
echo "✅ LAN mode is up:"
echo "   Frontend (local): http://localhost:$VITE_PORT"
echo "   Backend  (local): http://localhost:$BACKEND_PORT"
if [ -n "$WSL_IP" ]; then
  echo "   Frontend (WSL IP): http://$WSL_IP:$VITE_PORT"
  echo "   Backend  (WSL IP): http://$WSL_IP:$BACKEND_PORT"
fi
echo ""
echo "ℹ️ Use your Windows LAN IPv4 in mobile browser if needed."
echo "   Also ensure Windows firewall allows inbound TCP $VITE_PORT and $BACKEND_PORT."

wait
