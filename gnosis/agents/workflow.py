"""
Subtitle processing workflow that leverages SubtitleService and AI agents.
"""

import asyncio
import re
from typing import AsyncGenerator

from agno.workflow import RunEvent, RunResponse, Workflow

from gnosis.agents.proofreader import get_proofreader
from gnosis.agents.segmenter import get_segmenter
from gnosis.agents.translator import get_translator
from gnosis.core.logger import get_logger
from gnosis.services.subtitle import SubtitleService
from gnosis.services.subtitle.parser import (RGX_INDEX, RGX_POSSIBLE_CRLF,
                                             RGX_TIMESTAMP)

logger = get_logger(__name__)


class SubtitleWorkflow(Workflow):
    """
    A workflow for processing subtitles using AI agents.
    """
    
    # 定义匹配 SRT 块开始的正则表达式
    SRT_BLOCK_START_PATTERN = re.compile(
        r"\s*({idx})\s*{eof}({ts}) *-[ -] *> *({ts})".format(
            idx=RGX_INDEX,
            ts=RGX_TIMESTAMP,
            eof=RGX_POSSIBLE_CRLF
        )
    )
    
    # 定义匹配代码块的正则表达式
    CODE_BLOCK_PATTERN = re.compile(r'```(?:srt)?\s*\n([\s\S]*?)\n\s*```')

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

    def is_valid_srt_format(self, content: str) -> tuple[bool, str]:
        """
        验证内容是否符合 SRT 格式，如果不符合则尝试提取有效的 SRT 部分。
        
        Args:
            content: 要验证的内容
            
        Returns:
            (是否有效, 错误信息)
        """
        if not content or not content.strip():
            return False, "内容为空"
        
        # 首先尝试直接解析
        try:
            subtitle = self.subtitle_service.parse(content)
            if subtitle:
                return True, ""
        except Exception as e:
            pass
        
        # 尝试提取 SRT 内容
        try:
            # 查找第一个匹配项
            match = self.SRT_BLOCK_START_PATTERN.search(content)
            if match:
                # 从匹配到的第一个字幕编号开始截取内容
                start_pos = match.start(1)
                extracted_content = content[start_pos:]
                
                # 尝试解析提取的内容
                subtitle = self.subtitle_service.parse(extracted_content)
                if subtitle:
                    return True, ""
            
            # 尝试从代码块中提取 SRT 内容
            code_match = self.CODE_BLOCK_PATTERN.search(content)
            if code_match:
                extracted_content = code_match.group(1)
                subtitle = self.subtitle_service.parse(extracted_content)
                if subtitle:
                    return True, ""
                
            return False, "未找到有效的 SRT 格式内容"
        except Exception as e:
            return False, f"SRT 内容提取失败: {str(e)}"

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
        # 保存原始输入，用于格式无效时回退
        original_input = chunk_srt
        
        # 1. 断句修正 (Segmenter)
        logger.info(f"开始处理断句修正")
        segmented = await get_segmenter().arun(chunk_srt)
        segmented_content = segmented.content
        
        # 记录 Segmenter 返回的原始内容（截取前500个字符）
        logger.info(f"Segmenter 返回内容前500字符: {segmented_content[:500]}")
        
        # 验证 Segmenter 输出格式
        is_valid, error_msg = self.is_valid_srt_format(segmented_content)
        if not is_valid:
            # 匹配第一个字幕块开始
            match = self.SRT_BLOCK_START_PATTERN.search(segmented_content)
            if match:
                # 找到匹配项，从这里开始截取内容
                start_pos = match.start(1)  # 从字幕编号开始
                extracted_content = segmented_content[start_pos:]
                try:
                    # 检查提取的内容是否是有效的 SRT
                    subtitle = self.subtitle_service.parse(extracted_content)
                    if subtitle:
                        logger.info(f"成功从 Segmenter 输出中提取有效的 SRT 内容")
                        segmented_content = extracted_content
                        is_valid = True
                except Exception:
                    pass
                    
            # 如果仍然无效，尝试查找代码块
            if not is_valid:
                code_match = self.CODE_BLOCK_PATTERN.search(segmented_content)
                if code_match:
                    extracted_content = code_match.group(1)
                    try:
                        # 检查提取的内容是否是有效的 SRT
                        subtitle = self.subtitle_service.parse(extracted_content)
                        if subtitle:
                            logger.info(f"成功从 Segmenter 代码块中提取有效的 SRT 内容")
                            segmented_content = extracted_content
                            is_valid = True
                    except Exception:
                        pass
            
            # 如果仍然无效，回退到原始输入
            if not is_valid:
                logger.warning(f"Segmenter 输出格式无效: {error_msg}，回退到原始输入")
                # 记录更多的 Segmenter 输出内容以便分析
                logger.debug(f"Segmenter 完整输出内容: '''{segmented_content}'''")
                segmented_content = original_input
        else:
            logger.info("Segmenter 输出格式有效")

        # 2. 拼写检查 (Proofreader)
        logger.info(f"开始拼写检查")
        proofread = await get_proofreader().arun(segmented_content)
        proofread_content = proofread.content
        
        # 记录 Proofreader 返回的原始内容（截取前500个字符）
        logger.info(f"Proofreader 返回内容前500字符: {proofread_content[:500]}")
        
        # 验证 Proofreader 输出格式
        is_valid, error_msg = self.is_valid_srt_format(proofread_content)
        if not is_valid:
            # 尝试从输出中提取 SRT 内容
            # 匹配第一个字幕块开始
            match = self.SRT_BLOCK_START_PATTERN.search(proofread_content)
            if match:
                # 找到匹配项，从这里开始截取内容
                start_pos = match.start(1)  # 从字幕编号开始
                extracted_content = proofread_content[start_pos:]
                try:
                    # 检查提取的内容是否是有效的 SRT
                    subtitle = self.subtitle_service.parse(extracted_content)
                    if subtitle:
                        logger.info(f"成功从 Proofreader 输出中提取有效的 SRT 内容")
                        proofread_content = extracted_content
                        is_valid = True
                except Exception:
                    pass
                    
            # 如果仍然无效，尝试查找代码块
            if not is_valid:
                code_match = self.CODE_BLOCK_PATTERN.search(proofread_content)
                if code_match:
                    extracted_content = code_match.group(1)
                    try:
                        # 检查提取的内容是否是有效的 SRT
                        subtitle = self.subtitle_service.parse(extracted_content)
                        if subtitle:
                            logger.info(f"成功从 Proofreader 代码块中提取有效的 SRT 内容")
                            proofread_content = extracted_content
                            is_valid = True
                    except Exception:
                        pass
            
            # 如果仍然无效，回退到上一步输出
            if not is_valid:
                logger.warning(f"Proofreader 输出格式无效: {error_msg}，回退到上一步输出")
                # 记录更多的 Proofreader 输出内容以便分析
                logger.debug(f"Proofreader 完整输出内容: '''{proofread_content}'''")
                proofread_content = segmented_content
        else:
            logger.info("Proofreader 输出格式有效")

        # 3. 翻译 (Translator)
        logger.info(f"开始翻译处理")
        translated = await get_translator().arun(proofread_content)
        translated_content = translated.content
        
        # 记录 Translator 返回的原始内容（截取前500个字符）
        logger.info(f"Translator 返回内容前500字符: {translated_content[:500]}")
        
        # 验证 Translator 输出格式
        is_valid, error_msg = self.is_valid_srt_format(translated_content)
        if not is_valid:
            # 尝试从输出中提取 SRT 内容
            # 匹配第一个字幕块开始
            match = self.SRT_BLOCK_START_PATTERN.search(translated_content)
            if match:
                # 找到匹配项，从这里开始截取内容
                start_pos = match.start(1)  # 从字幕编号开始
                extracted_content = translated_content[start_pos:]
                try:
                    # 检查提取的内容是否是有效的 SRT
                    subtitle = self.subtitle_service.parse(extracted_content)
                    if subtitle:
                        logger.info(f"成功从 Translator 输出中提取有效的 SRT 内容")
                        translated_content = extracted_content
                        is_valid = True
                except Exception:
                    pass
                    
            # 如果仍然无效，尝试查找代码块
            if not is_valid:
                code_match = self.CODE_BLOCK_PATTERN.search(translated_content)
                if code_match:
                    extracted_content = code_match.group(1)
                    try:
                        # 检查提取的内容是否是有效的 SRT
                        subtitle = self.subtitle_service.parse(extracted_content)
                        if subtitle:
                            logger.info(f"成功从 Translator 代码块中提取有效的 SRT 内容")
                            translated_content = extracted_content
                            is_valid = True
                    except Exception:
                        pass
            
            # 如果仍然无效，回退到上一步输出
            if not is_valid:
                logger.warning(f"Translator 输出格式无效: {error_msg}，回退到上一步输出")
                # 记录更多的 Translator 输出内容以便分析
                logger.debug(f"Translator 完整输出内容: '''{translated_content}'''")
                translated_content = proofread_content
        else:
            logger.info("Translator 输出格式有效")
        
        return translated_content


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
