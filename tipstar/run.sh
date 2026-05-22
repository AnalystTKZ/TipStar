#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

BLUE='\033[0;34m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

prefix_output() {
    local label="$1"
    local color="$2"
    while IFS= read -r line; do
        printf "${color}[%-8s]${NC} %s\n" "$label" "$line"
    done
}

cleanup() {
    echo -e "\n${YELLOW}Shutting down...${NC}"
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null
    echo -e "${YELLOW}Done.${NC}"
}
trap cleanup EXIT INT TERM

# Backend
TQDM_DISABLE=1 HF_HUB_DISABLE_PROGRESS_BARS=1 \
.venv/bin/uvicorn backend.api.main:app --reload --port 8000 2>&1 \
    | prefix_output "backend" "$BLUE" &
BACKEND_PID=$!

# Wait for backend to be ready before starting frontend
printf "${YELLOW}Waiting for backend...${NC}"
for i in $(seq 1 20); do
    if curl -sf http://localhost:8000/health >/dev/null 2>&1; then
        echo -e " ${GREEN}ready${NC}"
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo -e " ${RED}timeout${NC}"
    fi
    printf "."
    sleep 1
done

# Frontend
cd frontend
npm run dev 2>&1 \
    | prefix_output "frontend" "$GREEN" &
FRONTEND_PID=$!
cd "$SCRIPT_DIR"

echo -e "${YELLOW}TipStar running:${NC}"
echo -e "  ${BLUE}Backend${NC}   http://localhost:8000"
echo -e "  ${GREEN}Frontend${NC}  http://localhost:5173"
echo -e "  ${YELLOW}Ctrl+C to stop both${NC}"
echo ""

wait "$BACKEND_PID" "$FRONTEND_PID"
