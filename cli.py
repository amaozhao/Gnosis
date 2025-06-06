"""
Gnosis CLI - 字幕翻译工具

使用 Typer 构建的命令行界面，支持字幕翻译功能。
基于 SubtitleWorkflow 实现字幕文件的翻译处理。
"""

import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from gnosis.agents.workflow import SubtitleWorkflow
from gnosis.services.transcribe import Transcriber

app = typer.Typer(help="Gnosis CLI - 字幕翻译工具")
console = Console()


@app.command("file")
def trans_file(
    file: Path = typer.Argument(..., help="SRT文件"),
    out: Optional[Path] = typer.Option(None, "-o", help="输出路径"),
    src: str = typer.Option("en", "-s", help="源语言"),
    tgt: str = typer.Option("zh", "-t", help="目标语言"),
    tokens: int = typer.Option(2000, "-m", help="最大token数"),
):
    """翻译单个SRT文件"""
    if not file.exists():
        console.print(f"[bold red]错误:[/bold red] 文件{file}不存在")
        raise typer.Exit(1)

    if not out:
        out = file.with_stem(f"{file.stem}_{tgt}")

    console.print(f"[bold green]开始:[/bold green] {file} -> {out}")
    asyncio.run(_trans_file(file, out, src, tgt, tokens))


async def _trans_file(in_path: Path, out_path: Path, src: str, tgt: str, tokens: int):
    """处理单个文件"""
    wf = SubtitleWorkflow(max_tokens=tokens)

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}[/bold blue]"),
        console=console,
    ) as progress:
        task = progress.add_task("处理中", total=None)

        async for resp in wf.arun(
            input_path=str(in_path),
            output_path=str(out_path),
            source_lang=src,
            target_lang=tgt,
        ):
            if hasattr(resp, "content"):
                progress.update(task, description=resp.content)

            if hasattr(resp, "error") and resp.error:
                console.print(f"[bold red]错误:[/bold red] {resp.error}")
                raise typer.Exit(1)

    console.print(f"[bold green]完成:[/bold green] {out_path}")


@app.command("dir")
def trans_dir(
    dir: Path = typer.Argument(..., help="SRT目录"),
    out_dir: Optional[Path] = typer.Option(None, "-o", help="输出目录"),
    src: str = typer.Option("en", "-s", help="源语言"),
    tgt: str = typer.Option("zh", "-t", help="目标语言"),
    rec: bool = typer.Option(False, "-r", help="递归处理"),
    tokens: int = typer.Option(2000, "-m", help="最大token数"),
):
    """批量翻译目录下的SRT文件"""
    if not dir.exists() or not dir.is_dir():
        console.print(f"[bold red]错误:[/bold red] {dir}不存在或非目录")
        raise typer.Exit(1)

    if out_dir and not out_dir.exists():
        out_dir.mkdir(parents=True, exist_ok=True)

    asyncio.run(_trans_dir(dir, out_dir, src, tgt, rec, tokens))


async def _trans_dir(
    in_dir: Path, out_dir: Optional[Path], src: str, tgt: str, rec: bool, tokens: int
):
    """处理目录中的所有文件"""
    pattern = "**/*.srt" if rec else "*.srt"
    files = list(in_dir.glob(pattern))

    if not files:
        console.print(f"[bold yellow]警告:[/bold yellow] {in_dir}中无SRT文件")
        return

    console.print(f"[bold blue]找到{len(files)}个SRT文件[/bold blue]")

    for i, in_file in enumerate(files, 1):
        if out_dir:
            rel_path = in_file.relative_to(in_dir)
            out_file = out_dir / rel_path.with_stem(f"{rel_path.stem}_{tgt}")
            out_file.parent.mkdir(parents=True, exist_ok=True)
        else:
            out_file = in_file.with_stem(f"{in_file.stem}_{tgt}")

        console.print(f"[{i}/{len(files)}] 处理: {in_file}")

        try:
            await _trans_file(
                in_path=in_file, out_path=out_file, src=src, tgt=tgt, tokens=tokens
            )
        except Exception as e:
            console.print(f"[bold red]错误:[/bold red] {in_file}: {str(e)}")

    console.print(f"[bold green]全部完成![/bold green]")


if __name__ == "__main__":
    app()
