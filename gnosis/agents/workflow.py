"""
Subtitle processing workflow that leverages SubtitleService and AI agents.
"""

import asyncio
from typing import AsyncGenerator

from agno.workflow import RunEvent, RunResponse, Workflow

from gnosis.agents.proofreader import get_proofreader
from gnosis.agents.segmenter import get_segmenter
from gnosis.agents.translator import get_translator
from gnosis.core.logger import get_logger
from gnosis.services.subtitle import SubtitleService

logger = get_logger(__name__)


class SubtitleWorkflow(Workflow):
    """
    A workflow for processing subtitles using AI agents.
    """

    def __init__(self, max_tokens: int = 2500):
        """
        Initialize the SubtitleWorkflow.

        Args:
            max_tokens: Maximum number of tokens per chunk for processing
        """
        super().__init__()
        self.subtitle_service = SubtitleService()
        self.max_tokens = max_tokens

    async def arun(
        self,
        input_path: str,
        output_path: str,
        source_lang: str = "en",
        target_lang: str = "zh",
    ) -> AsyncGenerator[RunResponse, None]:
        """
        Asynchronous entry point for the workflow.

        Args:
            input_path: Path to input subtitle file
            output_path: Path to save processed subtitle file
            source_lang: Source language code (default: "en")
            target_lang: Target language code (default: "zh")

        Yields:
            RunResponse: Progress updates during processing
        """
        yield RunResponse(
            content=f"开始处理字幕文件: {input_path}",
            event=RunEvent.workflow_started,
            run_id=self.run_id,
        )
        # 1. Read and parse subtitle file
        yield RunResponse(content="读取字幕文件...", run_id=self.run_id)
        subtitles = await self.subtitle_service.read(input_path)
        if not subtitles:
            yield RunResponse(
                content=f"读取失败或字幕为空: {input_path}",
                event=RunEvent.workflow_completed,
                run_id=self.run_id,
            )
            return
        yield RunResponse(
            content=f"读取完成，共 {len(subtitles)} 条字幕。", run_id=self.run_id
        )
        # 2. Split into manageable chunks
        yield RunResponse(content="分割字幕为处理块...", run_id=self.run_id)
        chunks = await self.subtitle_service.split_subtitles(subtitles, self.max_tokens)
        if not chunks:
            yield RunResponse(
                content="字幕分块失败，流程终止。",
                event=RunEvent.workflow_completed,
                run_id=self.run_id,
            )
            return
        yield RunResponse(content=f"分割为 {len(chunks)} 个块。", run_id=self.run_id)
        processed_subtitles = []
        # 3. Process each chunk
        for i, chunk in enumerate(chunks, 1):
            yield RunResponse(
                content=f"处理第 {i}/{len(chunks)} 块...", run_id=self.run_id
            )
            chunk_srt = self.subtitle_service.compose(chunk)
            if not chunk_srt:
                yield RunResponse(
                    content=f"第 {i} 块字幕合成失败，流程终止。",
                    event=RunEvent.workflow_completed,
                    run_id=self.run_id,
                )
                return
            processed_srt = await self._process_chunk(
                chunk_srt, source_lang, target_lang
            )
            if not processed_srt:
                yield RunResponse(
                    content=f"第 {i} 块字幕处理失败，流程终止。",
                    event=RunEvent.workflow_completed,
                    run_id=self.run_id,
                )
                return
            processed_chunk = self.subtitle_service.parse(processed_srt)
            if not processed_chunk:
                yield RunResponse(
                    content=f"第 {i} 块字幕解析失败，流程终止。",
                    event=RunEvent.workflow_completed,
                    run_id=self.run_id,
                )
                return
            processed_subtitles.extend(processed_chunk)
            yield RunResponse(
                content=f"已完成第 {i}/{len(chunks)} 块。", run_id=self.run_id
            )
        # 4. Save the processed subtitles
        yield RunResponse(
            content=f"保存处理后的字幕到 {output_path}...", run_id=self.run_id
        )
        await self.subtitle_service.write(
            processed_subtitles, output_path, reindex=True
        )
        yield RunResponse(
            content=f"全部完成，输出文件: {output_path}",
            event=RunEvent.workflow_completed,
            run_id=self.run_id,
        )

    # 保留 _process_chunk 方法作为内部方法

    async def _process_chunk(
        self, chunk_srt: str, source_lang: str, target_lang: str
    ) -> str:
        """
        Process a single subtitle chunk with agents in sequence, with detailed logging.
        Args:
            chunk_srt: SRT string for the chunk
            source_lang: Source language
            target_lang: Target language
        Returns:
            Processed subtitles in SRT format
        """
        # 1. 断句修正 (Segmenter)
        print(f"\n[Segmenter 输入]:\n{chunk_srt}\n")
        segmented = await get_segmenter().arun(chunk_srt)
        segmented = segmented.content
        print(f"[Segmenter 输出]:\n{segmented}\n")

        # 2. 拼写检查 (Proofreader)
        print(f"[Proofreader 输入]:\n{segmented}\n")
        proofread = await get_proofreader().arun(segmented)
        proofread = proofread.content
        print(f"[Proofreader 输出]:\n{proofread}\n")

        # 3. 翻译 (Translator)
        print(f"[Translator 输入]:\n{proofread}\n")
        translated = await get_translator().arun(proofread)
        translated = translated.content
        print(f"[Translator 输出]:\n{translated}\n")

        return translated


async def main():
    """Example usage of the SubtitleWorkflow."""
    workflow = SubtitleWorkflow(max_tokens=1000)

    input_path = "./tests/test.srt"
    output_path = "./tests/test.zh.srt"

    # 遍历异步生成器的结果
    async for response in workflow.arun(
        input_path=input_path,
        output_path=output_path,
        source_lang="en",
        target_lang="zh",
    ):
        if getattr(response, "content", None):
            print(response.content)
        if getattr(response, "error", None):
            print(f"[ERROR] {response.error}")
    print("Processing completed!")


if __name__ == "__main__":
    asyncio.run(main())
