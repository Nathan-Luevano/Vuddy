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
echo "  Vuddy v2 Environment Setup"
echo "  Ubuntu 24.04 + micromamba"
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
    libasound2-dev \
    portaudio19-dev \
    ffmpeg \
    usbutils \
    2>/dev/null && pass "System packages installed" || fail "System packages failed"

if groups | grep -q dialout; then
    pass "User in dialout group (serial port access)"
else
    sudo usermod -aG dialout "$USER" && warn "Added $USER to dialout group. Log out and back in for serial access." || fail "Could not add to dialout group"
fi

echo ""
echo "--- 2. NVIDIA drivers + CUDA toolkit ---"
if command -v nvidia-smi &>/dev/null; then
    DRIVER_VERSION=$(nvidia-smi --query-gpu=driver_version --format=csv,noheader 2>/dev/null || echo "unknown")
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null || echo "unknown")
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader 2>/dev/null || echo "unknown")
    pass "NVIDIA driver found: $DRIVER_VERSION ($GPU_NAME, $GPU_MEM)"
else
    fail "nvidia-smi not found. Install NVIDIA drivers first:"
    echo "  sudo apt install nvidia-driver-560"
    echo "  Reboot, then re-run this script."
fi

if command -v nvcc &>/dev/null; then
    CUDA_VER=$(nvcc --version | grep -oP 'release \K[0-9.]+' || echo "unknown")
    pass "CUDA toolkit found: $CUDA_VER"
else
    warn "nvcc not found. Installing CUDA toolkit..."
    sudo apt-get install -y -qq nvidia-cuda-toolkit 2>/dev/null && pass "CUDA toolkit installed" || fail "CUDA toolkit install failed"
fi

echo ""
echo "--- 3. micromamba ---"
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
echo "--- 4. Python environment (vuddy) ---"
if micromamba env list 2>/dev/null | grep -q "vuddy"; then
    pass "vuddy env already exists"
    micromamba activate vuddy
else
    echo "Creating vuddy environment..."
    micromamba create -n vuddy python=3.11 -y -q && pass "vuddy env created" || fail "env creation failed"
    micromamba activate vuddy
fi

echo ""
echo "--- 5. Python dependencies ---"
pip install --quiet --upgrade pip
pip install --quiet \
    fastapi \
    "uvicorn[standard]" \
    websockets \
    aiofiles \
    httpx \
    pyserial \
    faiss-cpu \
    sentence-transformers \
    google-api-python-client \
    google-auth \
    piper-tts \
    opencv-python-headless \
    python-dotenv \
    aiosqlite \
    && pass "Python packages installed" || fail "Python packages failed"

echo ""
echo "--- 6. Ollama ---"
if command -v ollama &>/dev/null; then
    pass "Ollama already installed"
else
    echo "Installing Ollama..."
    curl -fsSL https://ollama.ai/install.sh | sh && pass "Ollama installed" || fail "Ollama install failed"
fi

if pgrep -x "ollama" >/dev/null 2>&1; then
    pass "Ollama is running"
else
    echo "Starting Ollama..."
    OLLAMA_KEEP_ALIVE=-1 OLLAMA_MAX_LOADED_MODELS=2 OLLAMA_NUM_PARALLEL=1 ollama serve &>/dev/null &
    sleep 3
    if pgrep -x "ollama" >/dev/null 2>&1; then
        pass "Ollama started"
    else
        fail "Could not start Ollama"
    fi
fi

echo ""
echo "--- 7. Ollama models ---"
pull_model() {
    local model=$1
    if ollama list 2>/dev/null | grep -q "$model"; then
        pass "Model $model already pulled"
    else
        echo "Pulling $model..."
        ollama pull "$model" && pass "Model $model pulled" || fail "Failed to pull $model"
    fi
}

pull_model "qwen3:8b"
pull_model "qwen3:4b"
pull_model "moondream"

echo ""
echo "--- 8. Piper TTS voice models ---"
VOICE_DIR="data/voices"
mkdir -p "$VOICE_DIR"

download_voice() {
    local name=$1
    local full_name="en_US-${name}"
    local base_url="https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US"
    local voice_path="${name%%-*}"
    local quality="${name##*-}"

    if [ -f "$VOICE_DIR/${full_name}.onnx" ]; then
        pass "Voice $full_name already downloaded"
        return
    fi

    echo "Downloading voice $full_name..."
    wget -q -O "$VOICE_DIR/${full_name}.onnx" \
        "${base_url}/${voice_path}/${quality}/${full_name}.onnx" 2>/dev/null \
        && pass "Voice ${full_name}.onnx downloaded" \
        || fail "Failed to download ${full_name}.onnx"

    wget -q -O "$VOICE_DIR/${full_name}.onnx.json" \
        "${base_url}/${voice_path}/${quality}/${full_name}.onnx.json" 2>/dev/null \
        && pass "Voice ${full_name}.onnx.json downloaded" \
        || fail "Failed to download ${full_name}.onnx.json"
}

download_voice "lessac-medium"
download_voice "ryan-medium"

echo ""
echo "--- 9. Directory structure ---"
mkdir -p data/audio/fillers/sweetheart
mkdir -p data/audio/fillers/coach
mkdir -p data/audio/fillers/chill
mkdir -p data/audio/tts
mkdir -p data/memory
mkdir -p data/fixtures
mkdir -p data/db
mkdir -p credentials
pass "Directory structure created"

echo ""
echo "--- 10. Node.js (frontend) ---"
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
echo "--- 11. Verification tests ---"

python3 -c "import fastapi; print(f'FastAPI {fastapi.__version__}')" 2>/dev/null && pass "FastAPI importable" || fail "FastAPI import failed"
python3 -c "import faiss; print(f'FAISS {faiss.__version__}')" 2>/dev/null && pass "FAISS importable" || fail "FAISS import failed"
python3 -c "from sentence_transformers import SentenceTransformer; print('sentence-transformers OK')" 2>/dev/null && pass "sentence-transformers importable" || fail "sentence-transformers import failed"
python3 -c "import cv2; print(f'OpenCV {cv2.__version__}')" 2>/dev/null && pass "OpenCV importable" || fail "OpenCV import failed"
python3 -c "import serial; print('pyserial OK')" 2>/dev/null && pass "pyserial importable" || fail "pyserial import failed"

if curl -s http://localhost:11434/api/tags >/dev/null 2>&1; then
    pass "Ollama API reachable"
else
    fail "Ollama API not reachable at localhost:11434"
fi

if [ -f "$VOICE_DIR/en_US-lessac-medium.onnx" ] && [ -f "$VOICE_DIR/en_US-ryan-medium.onnx" ]; then
    pass "Both Piper voice models present"
else
    fail "Missing Piper voice models in $VOICE_DIR"
fi

if [ -f "credentials/calendar-service-account.json" ]; then
    pass "Google Calendar credentials file present"
else
    warn "credentials/calendar-service-account.json not found. Calendar will use fixture data."
fi

echo ""
echo "--- 12. VRAM co-residency test ---"
echo "Loading both models to verify they fit..."
VRAM_BEFORE=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo "0")

curl -s http://localhost:11434/api/chat -d '{
    "model": "qwen3:8b",
    "messages": [{"role":"user","content":"hi"}],
    "options": {"num_ctx": 4096},
    "keep_alive": -1,
    "stream": false
}' >/dev/null 2>&1 && pass "Qwen3 8B loaded" || fail "Qwen3 8B failed to load"

curl -s http://localhost:11434/api/chat -d '{
    "model": "moondream",
    "messages": [{"role":"user","content":"describe this","images":[]}],
    "options": {"num_ctx": 4096},
    "keep_alive": -1,
    "stream": false
}' >/dev/null 2>&1 && pass "moondream loaded" || warn "moondream load test (may need an image)"

VRAM_AFTER=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null || echo "0")
echo "VRAM usage: ${VRAM_BEFORE}MB → ${VRAM_AFTER}MB"
if [ "$VRAM_AFTER" -gt 0 ] && [ "$VRAM_AFTER" -lt 7500 ]; then
    pass "Both models fit in VRAM (${VRAM_AFTER}MB < 7500MB)"
elif [ "$VRAM_AFTER" -ge 7500 ]; then
    warn "VRAM usage high (${VRAM_AFTER}MB). Monitor during demo."
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
echo "  2. Copy .env.example to .env and fill in values"
echo "  3. cd frontend && npm install"
echo "  4. Start coding!"
exit $ERRORS
