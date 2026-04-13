#!/usr/bin/env python3
"""Script to download Qwen3 ASR models."""

import argparse
import sys
from pathlib import Path

try:
    from transformers import AutoModelForSpeechSeq2Seq, AutoProcessor

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print("Error: transformers library not installed")
    print("Run: pip install transformers torch")
    sys.exit(1)


# Available Qwen3-ASR models
AVAILABLE_MODELS = {
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


def download_model(model_name: str, cache_dir: Path):
    """Download a model from Hugging Face."""
    print(f"\nDownloading model: {model_name}")
    print(f"Cache directory: {cache_dir}")

    try:
        print("Downloading processor...")
        processor = AutoProcessor.from_pretrained(model_name, cache_dir=str(cache_dir))
        print("✓ Processor downloaded")

        print("Downloading model (this may take a while)...")
        model = AutoModelForSpeechSeq2Seq.from_pretrained(
            model_name, cache_dir=str(cache_dir), low_cpu_mem_usage=True, use_safetensors=True
        )
        print("✓ Model downloaded")

        print(f"\n✓ Successfully downloaded {model_name}")
        return True

    except Exception as e:
        print(f"✗ Failed to download model: {e}")
        return False


def list_available_models():
    """List available Qwen3-ASR models."""
    print("\nAvailable Qwen3-ASR Models:")
    print("=" * 60)
    for size, info in AVAILABLE_MODELS.items():
        print(f"\n  {size}:")
        print(f"    Name: {info['name']}")
        print(f"    Description: {info['description']}")
        print(f"    Size: ~{info['size_gb']} GB")
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Download Qwen3 ASR models",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --model-size 0.6B              # Download smaller model
  %(prog)s --model-size 1.7B              # Download larger model
  %(prog)s --model-size all               # Download both models
  %(prog)s --list                         # List available models
        """,
    )
    parser.add_argument(
        "--model-size",
        choices=["0.6B", "1.7B", "all"],
        help="Model size to download (0.6B, 1.7B, or all)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Legacy: Full model name (e.g., Qwen/Qwen3-ASR-1.7B)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / ".cache" / "huggingface",
        help="Cache directory for models",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available models and exit",
    )

    args = parser.parse_args()

    if args.list:
        list_available_models()
        return 0

    if not args.model_size and not args.model:
        parser.print_help()
        print("\n✗ Error: --model-size is required (unless using --list)")
        return 1

    print("=" * 60)
    print("Audio Recorder - Qwen3-ASR Model Download")
    print("=" * 60)

    # Ensure cache directory exists
    args.cache_dir.mkdir(parents=True, exist_ok=True)

    success = True

    if args.model:
        # Legacy mode: download specific model name
        print(f"\nDownloading legacy model: {args.model}")
        success = download_model(args.model, args.cache_dir)
    elif args.model_size == "all":
        # Download all models
        print("\nDownloading all available models...\n")
        for size in ["0.6B", "1.7B"]:
            model_info = AVAILABLE_MODELS[size]
            print(f"\n--- Downloading {size} model ---")
            if not download_model(model_info["name"], args.cache_dir):
                success = False
    else:
        # Download specific size
        if args.model_size not in AVAILABLE_MODELS:
            print(f"✗ Unknown model size: {args.model_size}")
            return 1

        model_info = AVAILABLE_MODELS[args.model_size]
        print(f"\n--- Downloading {args.model_size} model ---")
        print(f"Model: {model_info['name']}")
        print(f"Description: {model_info['description']}")
        print(f"Approximate size: {model_info['size_gb']} GB\n")

        success = download_model(model_info["name"], args.cache_dir)

    if success:
        print("\n" + "=" * 60)
        print("✓ Model download complete!")
        print(f"Models cached at: {args.cache_dir}")
        print("\nYou can now use these models in the application.")
        print("Update your config to use the downloaded model size:")
        print('    config.set("qwen_asr.model_size", "0.6B")  # or "1.7B"')
        print("=" * 60)
        return 0
    else:
        print("\n✗ Model download failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
