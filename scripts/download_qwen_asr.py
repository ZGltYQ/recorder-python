#!/usr/bin/env python3
"""
Qwen3-ASR Model Download Utility

This script downloads Qwen3-ASR models (0.6B or 1.7B) from Hugging Face.
Run this before starting the application to pre-download models.

Usage:
    python download_qwen_asr.py --model 0.6B
    python download_qwen_asr.py --model 1.7B
    python download_qwen_asr.py --model all
"""

import argparse
import sys
from pathlib import Path


def get_available_models():
    """Get available Qwen3-ASR model configurations."""
    return {
        "0.6B": {
            "name": "Qwen/Qwen3-ASR-0.6B",
            "description": "Smaller, faster model (~0.6B parameters)",
            "size_gb": 1.2,
        },
        "1.7B": {
            "name": "Qwen/Qwen3-ASR-1.7B",
            "description": "Larger, more accurate model (~1.7B parameters)",
            "size_gb": 3.4,
        },
    }


def download_model(model_size: str, cache_dir: str = None) -> bool:
    """Download a specific Qwen3-ASR model size.

    Args:
        model_size: Model size to download ("0.6B" or "1.7B")
        cache_dir: Optional custom cache directory

    Returns:
        True if download successful, False otherwise
    """
    models = get_available_models()

    if model_size not in models:
        print(f"❌ Error: Unknown model size '{model_size}'")
        print(f"   Available sizes: {', '.join(models.keys())}")
        return False

    model_info = models[model_size]
    model_name = model_info["name"]

    print(f"📥 Downloading Qwen3-ASR-{model_size} model...")
    print(f"   Model: {model_name}")
    print(f"   Description: {model_info['description']}")
    print(f"   Approximate size: {model_info['size_gb']} GB")

    try:
        # Try to import transformers for downloading
        try:
            from transformers import AutoModel, AutoTokenizer

            transformers_available = True
        except ImportError:
            transformers_available = False
            print("   Note: transformers not available, trying qwen-asr package...")

        if transformers_available:
            # Download using transformers
            print("\n   Downloading tokenizer...")
            tokenizer = AutoTokenizer.from_pretrained(
                model_name, cache_dir=cache_dir, trust_remote_code=True
            )

            print("   Downloading model weights...")
            model = AutoModel.from_pretrained(
                model_name, cache_dir=cache_dir, trust_remote_code=True
            )

            print("   Model downloaded successfully!")
        else:
            # Alternative: just use huggingface_hub to download
            try:
                from huggingface_hub import snapshot_download

                print("\n   Using huggingface_hub to download...")
                snapshot_download(
                    repo_id=model_name,
                    cache_dir=cache_dir,
                    local_files_only=False,
                )
                print("   Model downloaded successfully!")
            except ImportError:
                print("❌ Error: Neither transformers nor huggingface_hub is installed.")
                print("   Please install one of them:")
                print("       pip install transformers")
                print("       pip install huggingface-hub")
                return False

        print(f"✅ Qwen3-ASR-{model_size} download complete!")
        return True

    except Exception as e:
        print(f"❌ Error downloading model: {e}")
        return False


def list_models():
    """List all available models."""
    print("\nAvailable Qwen3-ASR Models:")
    print("=" * 60)

    models = get_available_models()
    for size, info in models.items():
        print(f"\n{size}:")
        print(f"  Name: {info['name']}")
        print(f"  Description: {info['description']}")
        print(f"  Size: ~{info['size_gb']} GB")

    print("\n" + "=" * 60)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Download Qwen3-ASR models for speech recognition",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --model 0.6B              # Download smaller model
  %(prog)s --model 1.7B              # Download larger model  
  %(prog)s --model all               # Download both models
  %(prog)s --model 0.6B --cache-dir /path/to/cache  # Custom cache directory
  %(prog)s --list                    # List available models
        """,
    )

    parser.add_argument(
        "--model",
        type=str,
        choices=["0.6B", "1.7B", "all"],
        help="Model size to download (0.6B, 1.7B, or all)",
    )

    parser.add_argument(
        "--cache-dir",
        type=str,
        default=None,
        help="Custom cache directory for models (default: Hugging Face default)",
    )

    parser.add_argument("--list", action="store_true", help="List available models and exit")

    args = parser.parse_args()

    if args.list:
        list_models()
        return 0

    if not args.model:
        parser.print_help()
        print("\n❌ Error: --model is required (unless using --list)")
        return 1

    print("=" * 60)
    print("Qwen3-ASR Model Downloader")
    print("=" * 60)

    success = True

    if args.model == "all":
        print("\nDownloading all available models...\n")
        for size in ["0.6B", "1.7B"]:
            if not download_model(size, args.cache_dir):
                success = False
            print()
    else:
        success = download_model(args.model, args.cache_dir)

    if success:
        print("\n✅ All downloads completed successfully!")
        print("\nYou can now use these models in the application.")
        print("Update your settings to use the downloaded model size.")
        return 0
    else:
        print("\n❌ Some downloads failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
