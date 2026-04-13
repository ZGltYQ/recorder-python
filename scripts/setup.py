#!/usr/bin/env python3
"""Setup script for Audio Recorder Python Edition."""

import subprocess
import sys
from pathlib import Path


def check_python_version():
    """Check if Python version is 3.10 or higher."""
    if sys.version_info < (3, 10):
        print("Error: Python 3.10 or higher is required")
        sys.exit(1)
    print(
        f"✓ Python version: {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    )


def install_system_dependencies():
    """Install system dependencies."""
    print("\nInstalling system dependencies...")

    # Check if we're on a Debian/Ubuntu-based system
    try:
        subprocess.run(["apt-get", "--version"], capture_output=True, check=True)
        deps = ["portaudio19-dev", "pulseaudio-utils", "pipewire"]
        cmd = ["sudo", "apt-get", "install", "-y"] + deps
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Check if we're on Fedora/RHEL-based system
        try:
            subprocess.run(["dnf", "--version"], capture_output=True, check=True)
            deps = ["portaudio-devel", "pulseaudio-utils", "pipewire"]
            cmd = ["sudo", "dnf", "install", "-y"] + deps
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("⚠ Could not detect package manager. Please install manually:")
            print("  - portaudio development files")
            print("  - pulseaudio-utils")
            print("  - pipewire")
            return

    try:
        subprocess.run(cmd, check=True)
        print("✓ System dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"⚠ Failed to install system dependencies: {e}")
        print("  You may need to install them manually")


def create_virtual_environment():
    """Create Python virtual environment."""
    print("\nCreating virtual environment...")

    venv_path = Path("venv")

    if venv_path.exists():
        print("✓ Virtual environment already exists")
        return

    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✓ Virtual environment created")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to create virtual environment: {e}")
        sys.exit(1)


def install_python_dependencies():
    """Install Python dependencies."""
    print("\nInstalling Python dependencies...")

    pip_cmd = "venv/bin/pip" if sys.platform != "win32" else "venv\\Scripts\\pip.exe"

    try:
        # Upgrade pip
        subprocess.run([pip_cmd, "install", "--upgrade", "pip"], check=True)

        # Install requirements
        subprocess.run([pip_cmd, "install", "-r", "requirements.txt"], check=True)

        print("✓ Python dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"✗ Failed to install Python dependencies: {e}")
        sys.exit(1)


def create_directories():
    """Create necessary directories."""
    print("\nCreating directories...")

    dirs = ["models", "assets/icons", "assets/styles"]

    for dir_path in dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)

    print("✓ Directories created")


def create_env_file():
    """Create .env file template."""
    print("\nCreating environment file...")

    env_file = Path(".env")

    if env_file.exists():
        print("✓ .env file already exists")
        return

    env_content = """# OpenRouter API Configuration
# Get your API key at: https://openrouter.ai/keys
OPENROUTER_API_KEY=your_api_key_here
OPENROUTER_MODEL=anthropic/claude-3.5-sonnet

# Optional: GPU acceleration
# CUDA_VISIBLE_DEVICES=0
"""

    env_file.write_text(env_content)
    print("✓ .env file created (please edit with your API key)")


def main():
    """Main setup function."""
    print("=" * 60)
    print("Audio Recorder STT - Python Edition Setup")
    print("=" * 60)

    # Check Python version
    check_python_version()

    # Install system dependencies
    install_system_dependencies()

    # Create virtual environment
    create_virtual_environment()

    # Install Python dependencies
    install_python_dependencies()

    # Create directories
    create_directories()

    # Create env file
    create_env_file()

    print("\n" + "=" * 60)
    print("Setup complete!")
    print("=" * 60)
    print("\nTo run the application:")
    print("  source venv/bin/activate  # On Windows: venv\\Scripts\\activate")
    print("  python -m src.main")
    print("\nDon't forget to:")
    print("  1. Edit .env file with your OpenRouter API key")
    print("  2. Download ASR models on first run")
    print()


if __name__ == "__main__":
    main()
