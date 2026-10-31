#!/usr/bin/env bash
# scripts/check_prerequisites.sh
# Diagnostic probe for Linux and macOS environments.
# Verifies installation of all prerequisite tools for the LLM-Wiki stack.

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

echo -e "${BOLD}${BLUE}======================================================${NC}"
echo -e "${BOLD}${BLUE}  LLM-Wiki & Knowledge Lab Prerequisite Diagnostic   ${NC}"
echo -e "${BOLD}${BLUE}  Target OS: $(uname -s) ($(uname -m))               ${NC}"
echo -e "${BOLD}${BLUE}======================================================${NC}\n"

MISSING_CRITICAL=0
MISSING_OPTIONAL=0

check_tool() {
    local cmd="$1"
    local name="$2"
    local install_hint="$3"
    local is_critical="$4" # 1 = critical, 0 = optional

    if command -v "$cmd" &> /dev/null; then
        local version=""
        case "$cmd" in
            node) version=$($cmd --version 2>&1 | head -n1) ;;
            python3) version=$($cmd --version 2>&1 | head -n1) ;;
            uv) version=$($cmd --version 2>&1 | head -n1) ;;
            git) version=$($cmd --version 2>&1 | head -n1) ;;
            gh) version=$($cmd --version 2>&1 | head -n1) ;;
            podman) version=$($cmd --version 2>&1 | head -n1) ;;
            docker) version=$($cmd --version 2>&1 | head -n1) ;;
            agy) version=$($cmd --version 2>&1 | head -n1) ;;
            obsidian) version="Installed (command detected)" ;;
            ollama) version=$($cmd --version 2>&1 | head -n1) ;;
            *) version="Installed" ;;
        esac
        echo -e "  [${GREEN}✓${NC}] ${BOLD}${name}${NC} (${cmd}): ${version}"
    else
        if [ "$is_critical" -eq 1 ]; then
            echo -e "  [${RED}✗${NC}] ${BOLD}${name}${NC} (${cmd}) is ${RED}NOT INSTALLED${NC} [CRITICAL]"
            echo -e "      ${YELLOW}Install via:${NC} ${install_hint}"
            MISSING_CRITICAL=$((MISSING_CRITICAL + 1))
        else
            echo -e "  [${YELLOW}!${NC}] ${BOLD}${name}${NC} (${cmd}) is ${YELLOW}NOT FOUND${NC} [OPTIONAL]"
            echo -e "      ${YELLOW}Install via:${NC} ${install_hint}"
            MISSING_OPTIONAL=$((MISSING_OPTIONAL + 1))
        fi
    fi
}

echo -e "${BOLD}1. Core CLI & Autonomous Agent Tooling:${NC}"
check_tool "agy" "Google Antigravity CLI" "curl -fsSL https://antigravity.google/install.sh | bash (or npm install -g @google/antigravity-cli)" 1
check_tool "git" "Git Version Control" "sudo apt install git (Ubuntu/Debian) or sudo dnf install git (Fedora)" 1
check_tool "gh" "GitHub CLI" "sudo apt install gh or brew install gh" 0

echo -e "\n${BOLD}2. Python & Package Runtime:${NC}"
check_tool "python3" "Python 3.11+" "sudo apt install python3 python3-pip" 1
check_tool "uv" "Astral uv Package Manager" "curl -LsSf https://astral.sh/uv/install.sh | sh" 1

echo -e "\n${BOLD}3. Node.js & Astro Frontend Runtime:${NC}"
check_tool "node" "Node.js (v20+)" "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs" 1
check_tool "npm" "npm Package Manager" "Included with Node.js" 1

echo -e "\n${BOLD}4. Container Engine (ArcadeDB & Chainlit):${NC}"
# Check Podman or Docker
if command -v podman &> /dev/null; then
    check_tool "podman" "Podman Container Engine" "sudo apt install podman podman-compose" 1
elif command -v docker &> /dev/null; then
    check_tool "docker" "Docker Container Engine" "sudo apt install docker.io docker-compose-plugin" 1
else
    echo -e "  [${RED}✗${NC}] ${BOLD}Container Engine (podman or docker)${NC} is ${RED}NOT INSTALLED${NC} [CRITICAL]"
    echo -e "      ${YELLOW}Install via:${NC} sudo apt install podman podman-compose (recommended) or Docker Desktop"
    MISSING_CRITICAL=$((MISSING_CRITICAL + 1))
fi

echo -e "\n${BOLD}5. Desktop IDE & Knowledge Exploration:${NC}"
# Obsidian on Linux can be flatpak, snap, or appimage
if command -v obsidian &> /dev/null; then
    echo -e "  [${GREEN}✓${NC}] ${BOLD}Obsidian${NC}: Installed in PATH"
elif command -v flatpak &> /dev/null && flatpak list | grep -qi "md.obsidian.Obsidian"; then
    echo -e "  [${GREEN}✓${NC}] ${BOLD}Obsidian${NC}: Installed via Flatpak (md.obsidian.Obsidian)"
elif command -v snap &> /dev/null && snap list | grep -qi "obsidian"; then
    echo -e "  [${GREEN}✓${NC}] ${BOLD}Obsidian${NC}: Installed via Snap"
elif [ -d "/Applications/Obsidian.app" ]; then
    echo -e "  [${GREEN}✓${NC}] ${BOLD}Obsidian${NC}: Installed in macOS /Applications/Obsidian.app"
else
    echo -e "  [${YELLOW}!${NC}] ${BOLD}Obsidian${NC}: ${YELLOW}Not detected in PATH${NC} [RECOMMENDED]"
    echo -e "      ${YELLOW}Install via:${NC} flatpak install flathub md.obsidian.Obsidian or download from https://obsidian.md"
    MISSING_OPTIONAL=$((MISSING_OPTIONAL + 1))
fi

echo -e "\n${BOLD}6. Optional Local Embedding Inference:${NC}"
check_tool "ollama" "Ollama Local LLM Runner" "curl -fsSL https://ollama.com/install.sh | sh (optional for local nomic-embed-text)" 0

echo -e "\n${BOLD}======================================================${NC}"
if [ "$MISSING_CRITICAL" -eq 0 ]; then
    echo -e "${GREEN}${BOLD}✓ System is ready for the LLM-Wiki & Knowledge Lab!${NC}"
    if [ "$MISSING_OPTIONAL" -gt 0 ]; then
        echo -e "${YELLOW}  (Notice: ${MISSING_OPTIONAL} optional component(s) missing; see recommendations above)${NC}"
    fi
else
    echo -e "${RED}${BOLD}✗ System is NOT ready: ${MISSING_CRITICAL} critical dependency/dependencies missing.${NC}"
    echo -e "${RED}  Please install the missing critical tools before bootstrapping.${NC}"
fi
echo -e "${BOLD}${BLUE}======================================================${NC}"
