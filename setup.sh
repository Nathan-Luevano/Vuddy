#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0

pass() { echo -e "${GREEN}[PASS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
fail() { echo -e "${RED}[FAIL]${NC} $1"; ERRORS=$((ERRORS + 1)); }

echo "========================================"
echo "  Vuddy Campus Desk Buddy - Setup"
echo "  Software-first voice assistant"
echo "========================================"
echo ""

if ! grep -qi "ubuntu" /etc/os-release 2>/dev/null; then
    warn "Not running Ubuntu. Some apt commands may not work."
fi

echo "--- 1. System packages ---"
sudo apt-get update -qq
sudo apt-get install -y -qq \
    build-essential \
    git \
    curl \
    wget \
    python3-dev \
    libffi-dev \
    libssl-dev \
    ffmpeg \
    portaudio19-dev \
    2>/dev/null && pass "System packages installed" || fail "System packages failed"

echo ""
echo "--- 2. micromamba ---"
if command -v micromamba &>/dev/null; then
    pass "micromamba already installed"
else
    echo "Installing micromamba..."
    "${SHELL}" <(curl -L micro.mamba.pm/install.sh) <<EOF
y

y
EOF
    export MAMBA_ROOT_PREFIX="$HOME/micromamba"
    eval "$(micromamba shell hook --shell bash)"
    pass "micromamba installed"
fi

eval "$(micromamba shell hook --shell bash 2>/dev/null)" || true

echo ""
echo "--- 3. Python environment (vuddy) ---"
if micromamba env list 2>/dev/null | grep -q "vuddy"; then
    pass "vuddy env already exists"
    micromamba activate vuddy
else
    echo "Creating vuddy environment..."
    micromamba create -n vuddy python=3.11 -y -q && pass "vuddy env created" || fail "env creation failed"
    micromamba activate vuddy
fi

echo ""
echo "--- 4. Python dependencies ---"
pip install --quiet --upgrade pip
pip install --quiet \
    fastapi \
    "uvicorn[standard]" \
    websockets \
    aiofiles \
    httpx \
    pyserial \
    python-dotenv \
    aiosqlite \
    pydantic \
    && pass "Python packages installed" || fail "Python packages failed"

echo ""
echo "--- 5. Node.js (frontend) ---"
if command -v node &>/dev/null; then
    NODE_VER=$(node --version)
    pass "Node.js found: $NODE_VER"
else
    echo "Installing Node.js 20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - 2>/dev/null
    sudo apt-get install -y -qq nodejs 2>/dev/null && pass "Node.js installed" || fail "Node.js install failed"
fi

if command -v npm &>/dev/null; then
    pass "npm found: $(npm --version)"
else
    fail "npm not found"
fi

echo ""
echo "--- 6. Directory structure ---"
mkdir -p data/audio/tts
mkdir -p data/fixtures
mkdir -p data/profile
mkdir -p data/memory
mkdir -p data/db
mkdir -p credentials
mkdir -p shared
mkdir -p scripts
pass "Directory structure created"

echo ""
echo "--- 7. Shared schemas check ---"
for schema in shared/ws_messages.schema.json shared/tools.schema.json shared/events.schema.json; do
    if [ -f "$schema" ]; then
        pass "$schema present"
    else
        warn "$schema not found. Person 3 should create it."
    fi
done

echo ""
echo "--- 8. Seeded data check ---"
if [ -f "data/events_seed.json" ]; then
    EVENT_COUNT=$(python3 -c "import json; print(len(json.load(open('data/events_seed.json'))))" 2>/dev/null || echo "0")
    pass "Seed events data present ($EVENT_COUNT events)"
elif [ -f "data/fixtures/campus_events.json" ]; then
    EVENT_COUNT=$(python3 -c "import json; print(len(json.load(open('data/fixtures/campus_events.json'))))" 2>/dev/null || echo "0")
    pass "Campus events data present ($EVENT_COUNT events) [alternate location]"
else
    warn "No events seed data found. Create data/events_seed.json before demo."
fi

if [ -f "data/fixtures/calendar.json" ]; then
    pass "Calendar fixture data present"
else
    warn "data/fixtures/calendar.json not found. Calendar will show empty."
fi

echo ""
echo "--- 9. Environment variables check ---"
if [ -f ".env" ]; then
    pass ".env file exists"

    # Check LLM provider setting
    LLM_PROVIDER=$(grep "^LLM_PROVIDER=" .env 2>/dev/null | cut -d= -f2 || echo "not set")
    echo "  LLM_PROVIDER=$LLM_PROVIDER"

    if [ "$LLM_PROVIDER" = "ollama" ]; then
        # Check Ollama is running
        if curl -s http://localhost:11434/api/tags &>/dev/null; then
            pass "Ollama is reachable"
        else
            warn "Ollama is not running. Start with: ollama serve"
        fi
    elif [ "$LLM_PROVIDER" = "patriotai" ]; then
        if grep -q "PATRIOTAI_API_KEY=" .env && ! grep -q "PATRIOTAI_API_KEY=your_" .env; then
            pass "PATRIOTAI_API_KEY is set"
        else
            fail "PATRIOTAI_API_KEY is not set in .env (required for patriotai provider)"
        fi
    fi

    # Check ElevenLabs key
    if grep -q "ELEVENLABS_API_KEY=" .env && ! grep -q "ELEVENLABS_API_KEY=your_" .env; then
        pass "ELEVENLABS_API_KEY is set"
    else
        warn "ELEVENLABS_API_KEY is not set (TTS will fall back to text-only)"
    fi

    # Check hardware mode
    HW_MODE=$(grep "^HARDWARE_MODE=" .env 2>/dev/null | cut -d= -f2 || echo "sim")
    echo "  HARDWARE_MODE=$HW_MODE"
    if [ "$HW_MODE" = "sim" ]; then
        pass "Hardware mode is sim (no Arduino needed)"
    elif [ "$HW_MODE" = "arduino" ]; then
        warn "Hardware mode is arduino (requires physical device)"
    fi
else
    fail ".env file not found. Copy .env.example to .env and fill in values."
fi

echo ""
echo "--- 10. Verification tests ---"

python3 -c "import fastapi; print(f'FastAPI {fastapi.__version__}')" 2>/dev/null && pass "FastAPI importable" || fail "FastAPI import failed"
python3 -c "import httpx; print(f'httpx {httpx.__version__}')" 2>/dev/null && pass "httpx importable" || fail "httpx import failed"
python3 -c "import uvicorn; print('uvicorn OK')" 2>/dev/null && pass "uvicorn importable" || fail "uvicorn import failed"

echo ""
echo "--- 11. Backend smoke test ---"
echo "Starting backend for smoke test..."

cd backend 2>/dev/null || cd .
uvicorn main:app --host 0.0.0.0 --port 8000 &>/dev/null &
BACKEND_PID=$!
sleep 3

if kill -0 $BACKEND_PID 2>/dev/null; then
    if curl -s http://localhost:8000/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); assert d.get('ok')" 2>/dev/null; then
        pass "Backend health check passed"
    else
        warn "Backend started but health check returned unexpected response (OK if main.py is not built yet)"
    fi

    # Run smoke test if available
    cd ..
    if [ -f "scripts/smoke_ws_client.py" ]; then
        echo "Running WebSocket smoke test..."
        timeout 30 python3 scripts/smoke_ws_client.py --timeout 10 2>/dev/null && pass "Smoke test passed" || warn "Smoke test did not pass (OK if backend is not fully built yet)"
    fi

    kill $BACKEND_PID 2>/dev/null || true
else
    warn "Backend did not start (OK if main.py is not built yet)"
fi

echo ""
echo "========================================"
if [ "$ERRORS" -eq 0 ]; then
    echo -e "${GREEN}ALL CHECKS PASSED. Environment ready.${NC}"
else
    echo -e "${RED}${ERRORS} CHECK(S) FAILED. Fix the above errors and re-run.${NC}"
fi
echo "========================================"
echo ""
echo "Next steps:"
echo "  1. micromamba activate vuddy"
echo "  2. Copy .env.example to .env and configure:"
echo "     - LLM_PROVIDER=ollama (default) or patriotai (for judging)"
echo "     - ELEVENLABS_API_KEY (for TTS)"
echo "     - HARDWARE_MODE=sim (default, no Arduino needed)"
echo "  3. cd frontend && npm install"
echo "  4. cd backend && uvicorn main:app --reload"
echo "  5. Open http://localhost:5173 in Chrome"
echo "  6. Run smoke test: python scripts/smoke_ws_client.py"
exit $ERRORS
