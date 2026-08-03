#!/bin/bash
#
# Build script for recorder-python AppImage
# Supports local builds without GitHub Actions
# Includes CUDA support for GPU acceleration
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ARCH=$(uname -m)
RECIPE_FILE="AppImageBuilder.yml"
OUTPUT_DIR="."
VERSION=$(python3 -c "import tomllib; print(tomllib.load(open('pyproject.toml', 'rb'))['project']['version'])" 2>/dev/null || echo "2.0.0")
BUILD_TYPE="cuda"  # or "cpu"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --arch)
            ARCH="$2"
            shift 2
            ;;
        --recipe)
            RECIPE_FILE="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        --version)
            VERSION="$2"
            shift 2
            ;;
        --cpu)
            BUILD_TYPE="cpu"
            shift
            ;;
        --cuda)
            BUILD_TYPE="cuda"
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --arch ARCH         Target architecture (default: $(uname -m))"
            echo "  --recipe FILE       Path to AppImageBuilder.yml (default: AppImageBuilder.yml)"
            echo "  --output-dir DIR    Output directory (default: .)"
            echo "  --version VERSION   Version string (default: from pyproject.toml)"
            echo "  --cpu               Build CPU-only version (no CUDA)"
            echo "  --cuda              Build with CUDA support (default)"
            echo "  --help, -h          Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Map architecture names
case $ARCH in
    x86_64|amd64)
        TARGET_ARCH="x86_64"
        ;;
    aarch64|arm64)
        TARGET_ARCH="aarch64"
        ;;
    *)
        TARGET_ARCH="$ARCH"
        ;;
esac

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  recorder-python AppImage Builder${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}Build Configuration:${NC}"
echo "  Architecture: $TARGET_ARCH"
echo "  Build Type:   $BUILD_TYPE"
echo "  Version:      $VERSION"
echo "  Recipe:       $RECIPE_FILE"
echo "  Output Dir:   $OUTPUT_DIR"
echo ""

# Check if running on Linux
if [[ "$(uname -s)" != "Linux" ]]; then
    echo -e "${RED}Error: This script must be run on Linux${NC}"
    exit 1
fi

# Check for required tools
check_command() {
    if ! command -v "$1" &> /dev/null; then
        echo -e "${RED}Error: Required command '$1' not found${NC}"
        MISSING_DEPS=true
    fi
}

echo -e "${YELLOW}Checking prerequisites...${NC}"
MISSING_DEPS=false
check_command python3
check_command pip3
check_command apt-get
check_command docker  # Optional for testing

if $MISSING_DEPS; then
    echo -e "${RED}Please install missing dependencies and try again${NC}"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
REQUIRED_PYTHON="3.10"
if [[ "$(printf '%s\n' "$REQUIRED_PYTHON" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_PYTHON" ]]; then
    echo -e "${RED}Error: Python $REQUIRED_PYTHON+ is required (found: $PYTHON_VERSION)${NC}"
    exit 1
fi
echo -e "${GREEN}  Python version: $PYTHON_VERSION${NC}"

# Install system dependencies
echo ""
echo -e "${YELLOW}Installing system dependencies...${NC}"
sudo apt-get update

# Base build dependencies
BASE_DEPS=(
    git
    wget
    curl
    build-essential
    cmake
    ninja-build
)

# Python build dependencies
PYTHON_BUILD_DEPS=(
    python3-dev
    python3-pip
    python3-venv
    python3-wheel
)

# Qt and GUI dependencies
QT_DEPS=(
    libglib2.0-0
    libxcb-xinerama0
    libxkbcommon-x11-0
    libegl1
    libdbus-1-3
    libxcb-icccm4
    libxcb-image0
    libxcb-keysyms1
    libxcb-randr0
    libxcb-render-util0
    libxcb-shape0
    libxcb-xfixes0
    libxcb-cursor0
    libxcb-glx0
    libxcb-xkb1
    libxcb-xinput0
    libxcb-errors0
    libopengl0
    libgbm1
    libasound2-dev
    libpulse-mainloop-glib0
    libpulse0
    libportaudio2
)

# NVIDIA/CUDA dependencies
if [[ "$BUILD_TYPE" == "cuda" ]]; then
    CUDA_DEPS=(
        nvidia-cuda-toolkit-gcc
        libcudnn8
        libcublas-12-2
        nvidia-driver-535  # or whatever driver is available
    )
    ALL_DEPS=("${BASE_DEPS[@]}" "${PYTHON_BUILD_DEPS[@]}" "${QT_DEPS[@]}" "${CUDA_DEPS[@]}")
else
    ALL_DEPS=("${BASE_DEPS[@]}" "${PYTHON_BUILD_DEPS[@]}" "${QT_DEPS[@]}")
fi

# Remove duplicates and install
IFS=' ' read -r -a UNIQUE_DEPS <<< "$(printf '%s\n' "${ALL_DEPS[@]}" | sort -u | tr '\n' ' ')"
sudo apt-get install -y "${UNIQUE_DEPS[@]}"

echo -e "${GREEN}  System dependencies installed${NC}"

# Install appimage-builder
echo ""
echo -e "${YELLOW}Installing appimage-builder...${NC}"
pip3 install --user appimage-builder 2>/dev/null || pip3 install --break-system-packages appimage-builder

if command -v appimage-builder &> /dev/null; then
    echo -e "${GREEN}  appimage-builder installed: $(appimage-builder --version)${NC}"
else
    echo -e "${RED}  Warning: appimage-builder not in PATH, trying to add to PATH${NC}"
    export PATH="$HOME/.local/bin:$PATH"
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate AppImage
echo ""
echo -e "${YELLOW}Building AppImage...${NC}"
echo "  This may take a while (10-30 minutes on first run)"
echo ""

# Update recipe version
if [[ -f "$RECIPE_FILE" ]]; then
    sed -i "s/version: \"2.0.0\"/version: \"$VERSION\"/" "$RECIPE_FILE"
    sed -i "s/arch: x86_64/arch: $TARGET_ARCH/" "$RECIPE_FILE"
fi

# Run appimage-builder
if appimage-builder --recipe "$RECIPE_FILE" --skip-test; then
    echo -e "${GREEN}  AppImage built successfully!${NC}"
else
    echo -e "${RED}  AppImage build failed${NC}"
    exit 1
fi

# Find and rename the output AppImage with architecture encoding
echo ""
echo -e "${YELLOW}Processing output...${NC}"

# Find the generated AppImage
APPIMAGE_FILE=$(find . -maxdepth 1 -name "*.AppImage" -type f 2>/dev/null | head -n1)

if [[ -z "$APPIMAGE_FILE" ]]; then
    # Try alternative names
    APPIMAGE_FILE=$(find . -maxdepth 1 -name "*recorder*.AppImage" -type f 2>/dev/null | head -n1)
fi

if [[ -n "$APPIMAGE_FILE" && -f "$APPIMAGE_FILE" ]]; then
    # Rename with architecture encoding
    BASENAME=$(basename "$APPIMAGE_FILE" .AppImage)
    NEW_NAME="${BASENAME}-${TARGET_ARCH}.AppImage"

    mv "$APPIMAGE_FILE" "$OUTPUT_DIR/$NEW_NAME"

    echo ""
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}  Build Complete!${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    echo -e "${YELLOW}Output:${NC} $OUTPUT_DIR/$NEW_NAME"
    echo -e "${YELLOW}Size:${NC} $(du -h "$OUTPUT_DIR/$NEW_NAME" | cut -f1)"
    echo ""
    echo -e "${BLUE}Note: The AppImage includes CUDA support.${NC}"
    echo -e "${BLUE}      Requires NVIDIA driver and CUDA runtime on target system.${NC}"
    echo ""
else
    echo -e "${RED}  Could not find generated AppImage file${NC}"
    echo "  Build may have succeeded but output file not found"
    exit 1
fi

# Cleanup
rm -rf AppDir AppImageBuilder.yml.bak 2>/dev/null || true

echo -e "${GREEN}Done!${NC}"
