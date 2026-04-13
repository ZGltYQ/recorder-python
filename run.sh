#!/bin/bash
# Quick start script for Audio Recorder Python Edition

set -e

echo "========================================"
echo "Audio Recorder STT - Python Edition"
echo "========================================"
echo ""

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Virtual environment not found. Running setup..."
    python3 scripts/setup.py
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "Creating .env file..."
    cat > .env << EOF
# OpenRouter API Configuration
# Get your API key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet
EOF
    echo "⚠ Please edit .env file with your OpenRouter API key"
fi

# Run the application
echo "Starting Audio Recorder..."
python -m src.main "$@"
