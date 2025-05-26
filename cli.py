"""
Command-line interface for the Gnosis application using the TranslationTeam.
"""

import argparse
import asyncio
import os
import sys

from tqdm import tqdm

from gnosis.agents.team import TranslationTeam
from gnosis.core.config import settings
from gnosis.services.subtitle import SubtitleService


def parse_args() -> argparse.Namespace:
    """Parse command line arguments.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
    parser = argparse.ArgumentParser(description="Gnosis CLI")

    # Global arguments
    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Enable debug mode with verbose logging",
    )
    parser.add_argument(
        "--test", action="store_true", help="Run in test mode (skips actual API calls)"
    )

    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Translate command
    translate_parser = subparsers.add_parser("translate", help="Translate text")
    translate_parser.add_argument(
        "--source", "-s", default="en", help="Source language (default: en)"
    )
    translate_parser.add_argument(
        "--target", "-t", default="zh", help="Target language (default: zh)"
    )
    translate_parser.add_argument("--text", help="Text to translate")
    translate_parser.add_argument(
        "--file", "-f", help="File containing text to translate"
    )
    translate_parser.add_argument(
        "--output", "-o", help="Output file for translated text"
    )

    # Batch translate command
    batch_parser = subparsers.add_parser("batch", help="Batch translate multiple files")
    batch_parser.add_argument(
        "--source", "-s", default="en", help="Source language (default: en)"
    )
    batch_parser.add_argument(
        "--target", "-t", default="zh", help="Target language (default: zh)"
    )
    batch_parser.add_argument(
        "--input-dir", "-i", required=True, help="Directory containing input files"
    )
    batch_parser.add_argument(
        "--output-dir", "-o", help="Directory for output files (default: same as input)"
    )
    batch_parser.add_argument(
        "--extension",
        "-e",
        default="srt",
        help="File extension to process (default: srt)",
    )
    batch_parser.add_argument(
        "--recursive",
        "-r",
        action="store_true",
        help="Recursively process subdirectories",
    )

    # Version command
    subparsers.add_parser("version", help="Show version information")

    return parser.parse_args()


async def handle_translate_command(args: argparse.Namespace) -> None:
    """Handle the translate command.

    Args:
        args: Command line arguments.
    """
    # Get the source text
    if args.text:
        source_text = args.text
    elif args.file:
        try:
            source_text = await SubtitleService.read_file(args.file)
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        print("Either --text or --file must be provided")
        sys.exit(1)

    # Create a translation team
    team = TranslationTeam()

    try:
        # Translate the text
        print(f"Translating from {args.source} to {args.target}...")
        translated_text = await team.translate(source_text, args.source, args.target)

        # Output the result
        if args.output:
            await SubtitleService.write_file(translated_text, args.output)
            print(f"Translated text written to {args.output}")
        else:
            print(translated_text)
    except Exception as e:
        print(f"Translation error: {e}")


async def handle_batch_command(args: argparse.Namespace) -> None:
    """Handle the batch translate command.

    Args:
        args: Command line arguments.
    """
    # Check if input directory exists
    if not os.path.isdir(args.input_dir):
        print(f"Input directory does not exist: {args.input_dir}")
        sys.exit(1)

    # Set output directory to input directory if not specified
    output_dir = args.output_dir if args.output_dir else args.input_dir

    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Find all files with the specified extension
    input_files = []
    if args.recursive:
        # Recursively walk through all subdirectories
        for root, _, files in os.walk(args.input_dir):
            for file in files:
                if file.endswith(f".{args.extension}"):
                    input_files.append(os.path.join(root, file))
    else:
        # Only process files in the top-level directory
        for file in os.listdir(args.input_dir):
            file_path = os.path.join(args.input_dir, file)
            if os.path.isfile(file_path) and file.endswith(f".{args.extension}"):
                input_files.append(file_path)

    if not input_files:
        print(f"No .{args.extension} files found in {args.input_dir}")
        sys.exit(1)

    print(f"Found {len(input_files)} files to translate")

    # Create a translation team
    team = TranslationTeam()

    # Process each file
    for input_file in tqdm(input_files, desc="Translating files"):
        try:
            # Generate output file path with target language suffix
            file_dir = os.path.dirname(input_file)
            file_name = os.path.basename(input_file)
            file_base, file_ext = os.path.splitext(file_name)

            # If input and output directories are different, maintain directory structure
            if args.input_dir != output_dir:
                rel_dir = os.path.relpath(file_dir, args.input_dir)
                target_dir = os.path.join(output_dir, rel_dir)
                os.makedirs(target_dir, exist_ok=True)
                output_file = os.path.join(
                    target_dir, f"{file_base}_{args.target}{file_ext}"
                )
            else:
                # If same directory, just add target language suffix
                output_file = os.path.join(
                    file_dir, f"{file_base}_{args.target}{file_ext}"
                )

            print(f"Processing file: {input_file}")

            # Read the file
            source_text = await SubtitleService.read_file(input_file)

            if not source_text.strip():
                print(
                    f"File {input_file} is empty or contains only whitespace. Skipping."
                )
                continue

            # Translate the text with timeout
            print(f"Starting translation for {input_file}")
            try:
                # 设置超时时间为 5 分钟
                translated_text = await asyncio.wait_for(
                    team.translate(source_text, args.source, args.target), timeout=300
                )
                print(f"Translation completed for {input_file}")
            except asyncio.TimeoutError:
                print(f"Translation timed out for {input_file} after 5 minutes")
                continue
            except Exception as e:
                print(f"Translation error for {input_file}: {e}")
                continue

            # Write the translated text
            await SubtitleService.write_file(translated_text, output_file)
            print(f"Translated text written to {output_file}")

        except Exception as e:
            print(f"Error processing {input_file}: {str(e)}")
            continue

    print(
        f"Batch translation completed. Output files saved with '_{args.target}' suffix."
    )


def handle_version_command() -> None:
    """Handle the version command."""
    print(f"Gnosis version: {settings.PROJECT_NAME} v1.0.0")


async def main() -> None:
    """Main entry point for the CLI application."""
    args = parse_args()

    if args.command == "translate":
        await handle_translate_command(args)
    elif args.command == "batch":
        await handle_batch_command(args)
    elif args.command == "version":
        handle_version_command()
    else:
        print("No command specified")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Operation cancelled by user")
        sys.exit(0)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
