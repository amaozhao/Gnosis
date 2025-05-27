"""
Command-line interface for the Gnosis application using the TranslationTeam.
使用 Typer 构建的命令行界面，支持字幕翻译功能。
"""

import asyncio
import os
from enum import Enum
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from gnosis.agents.team import TranslationTeam
from gnosis.core.config import settings
from gnosis.services.subtitle import SubtitleService

# 创建 Typer 应用
app = typer.Typer(
    help="Gnosis CLI - 字幕翻译工具",
    add_completion=True,
    rich_markup_mode="rich",
)

# 创建控制台对象，用于美化输出
console = Console()


class ModelProvider(str, Enum):
    """模型提供商枚举类型"""

    MISTRAL = "mistral"
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    KIMI = "kimi"


@app.command("translate")
async def translate(
    file: Optional[Path] = typer.Option(
        None, "--file", "-f", help="File containing text to translate"
    ),
    text: Optional[str] = typer.Option(None, "--text", help="Text to translate"),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Output file for translated text"
    ),
    source: str = typer.Option("en", "--source", "-s", help="Source language code"),
    target: str = typer.Option("zh", "--target", "-t", help="Target language code"),
    model: ModelProvider = typer.Option(
        ModelProvider.MISTRAL, "--model", "-m", help="Model provider to use"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode"),
    test: bool = typer.Option(
        False, "--test", help="Run in test mode (skips API calls)"
    ),
):
    """Translate text or subtitle file from one language to another."""
    # 设置模型提供商
    settings.MODEL_PROVIDER = model.value

    # 获取源文本
    if text:
        source_text = text
    elif file:
        try:
            source_text = await SubtitleService.read_file(str(file))
        except Exception as e:
            console.print(f"[bold red]Error reading file:[/] {e}")
            raise typer.Exit(code=1)
    else:
        console.print("[bold yellow]Either --text or --file must be provided[/]")
        raise typer.Exit(code=1)

    # 创建翻译团队
    team = TranslationTeam()

    try:
        # 显示进度
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]Translating..."),
            console=console,
        ) as progress:
            progress.add_task("translate", total=None)
            # 翻译文本
            console.print(f"Translating from [bold]{source}[/] to [bold]{target}[/]...")
            translated_text = await team.translate(source_text, source, target)

        # 生成默认输出文件名
        output_file = output
        if not output_file and file:
            # 从输入文件名生成输出文件名
            file_name = file.stem
            file_ext = file.suffix
            output_file = Path(f"{file_name}_{target}{file_ext}")

        # 输出结果
        if output_file:
            await SubtitleService.write_file(translated_text, str(output_file))
            console.print(f"Translated text written to [bold cyan]{output_file}[/]")
        else:
            # 如果是文本输入而非文件输入，直接打印结果
            console.print("\n[bold green]Translation Result:[/]")
            console.print(translated_text)
    except Exception as e:
        console.print(f"[bold red]Translation error:[/] {e}")
        raise typer.Exit(code=1)


@app.command("batch")
async def batch_translate(
    input_dir: Path = typer.Option(
        ..., "--input-dir", "-i", help="Directory containing input files"
    ),
    output_dir: Optional[Path] = typer.Option(
        None,
        "--output-dir",
        "-o",
        help="Directory for output files (default: same as input)",
    ),
    extension: str = typer.Option(
        "srt", "--extension", "-e", help="File extension to process"
    ),
    recursive: bool = typer.Option(
        False, "--recursive", "-r", help="Recursively process subdirectories"
    ),
    source: str = typer.Option("en", "--source", "-s", help="Source language code"),
    target: str = typer.Option("zh", "--target", "-t", help="Target language code"),
    model: ModelProvider = typer.Option(
        ModelProvider.MISTRAL, "--model", "-m", help="Model provider to use"
    ),
    debug: bool = typer.Option(False, "--debug", "-d", help="Enable debug mode"),
    test: bool = typer.Option(
        False, "--test", help="Run in test mode (skips API calls)"
    ),
):
    """Batch translate multiple subtitle files."""
    # 设置模型提供商
    settings.MODEL_PROVIDER = model.value

    # 验证输入目录
    if not input_dir.is_dir():
        console.print(f"[bold red]Input directory {input_dir} does not exist[/]")
        raise typer.Exit(code=1)

    # 设置输出目录
    output_dir = output_dir or input_dir

    # 创建输出目录（如果不存在）
    output_dir.mkdir(parents=True, exist_ok=True)

    # 查找所有指定扩展名的文件
    files = []
    if recursive:
        for file_path in input_dir.rglob(f"*.{extension}"):
            if file_path.is_file():
                files.append(file_path)
    else:
        files = list(input_dir.glob(f"*.{extension}"))

    if not files:
        console.print(
            f"[bold yellow]No files with extension .{extension} found in {input_dir}[/]"
            + (" (including subdirectories)" if recursive else "")
        )
        raise typer.Exit(code=1)

    console.print(
        f"Found [bold]{len(files)}[/] {extension} files in [bold]{input_dir}[/]"
        + (" (including subdirectories)" if recursive else "")
    )

    # 创建翻译团队
    team = TranslationTeam()

    # 处理每个文件
    with Progress(
        "[progress.description]{task.description}",
        SpinnerColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        "({task.completed}/{task.total})",
        console=console,
    ) as progress:
        task = progress.add_task("[cyan]Translating files...", total=len(files))

        for input_file in files:
            # 生成输出文件路径
            rel_path = input_file.relative_to(input_dir)
            output_file = output_dir / f"{rel_path.stem}_{target}{rel_path.suffix}"

            # 创建输出目录（如果不存在）
            output_file.parent.mkdir(parents=True, exist_ok=True)

            progress.update(task, description=f"[cyan]Translating: {input_file.name}")

            try:
                # 读取源文本
                source_text = await SubtitleService.read_file(str(input_file))

                if not source_text.strip():
                    console.print(
                        f"[yellow]File {input_file} is empty or contains only whitespace. Skipping.[/]"
                    )
                    progress.update(task, advance=1)
                    continue

                # 翻译文本
                translated_text = await team.translate(source_text, source, target)

                # 将翻译后的文本写入输出文件
                await SubtitleService.write_file(translated_text, str(output_file))

            except asyncio.TimeoutError:
                console.print(
                    f"[bold red]Timeout translating {input_file}. Skipping.[/]"
                )
            except Exception as e:
                console.print(f"[bold red]Error processing {input_file}: {str(e)}[/]")
            finally:
                progress.update(task, advance=1)

    console.print(
        f"[bold green]Batch translation completed. Output files saved with '_{target}' suffix.[/]"
    )


@app.command("version")
def version():
    """Print the version of the Gnosis CLI."""
    console.print(f"Gnosis version: {settings.PROJECT_NAME} v1.0.0")


def run():
    """Run the CLI application."""
    try:
        # 注意：Typer 会自动处理异步命令
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/]")
        raise typer.Exit(code=0)
    except Exception as e:
        console.print(f"[bold red]Error:[/] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    run()
