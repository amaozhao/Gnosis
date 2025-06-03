"""
文本文件处理服务，提供基本的文件读写功能。
使用 aiofiles 实现异步文件操作。
"""

import os
from datetime import timedelta
from typing import List

import aiofiles
import tiktoken

from .parser import SrtParser, Subtitle


class SubtitleService:
    """文本文件处理服务类，提供基本的文件读写功能。"""

    def __init__(self, encoding_name: str = "cl100k_base"):
        """
        初始化 SubtitleService。

        Args:
            encoding_name: 用于 token 计数的编码模型名称，默认为 "cl100k_base" (用于 GPT-3.5/4)。
                           你可以根据需要更改为其他 tiktoken 支持的编码，例如 "p50k_base" 或 "gpt2"。
        """
        self._srt_parser = SrtParser()
        self.compose = self._srt_parser.compose
        self.parse = self._srt_parser.parse
        try:
            self._tokenizer = tiktoken.get_encoding(encoding_name)
        except ValueError:
            raise ValueError(f"无效的 tiktoken 编码名称: {encoding_name}")

    @staticmethod
    async def load(file_path: str, encoding: str = "utf-8") -> str:
        """异步读取文本文件的内容。

        Args:
            file_path: 文件路径
            encoding: 文件编码，默认为 UTF-8

        Returns:
            str: 文件内容

        Raises:
            FileNotFoundError: 如果文件不存在
            PermissionError: 如果没有权限读取文件
            UnicodeDecodeError: 如果文件编码不匹配
        """
        # 检查文件是否存在
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件不存在: {file_path}")

        # 检查文件是否可读
        if not os.access(file_path, os.R_OK):
            raise PermissionError(f"没有权限读取文件: {file_path}")

        async with aiofiles.open(file_path, "r", encoding=encoding) as file:
            content = await file.read()
            return content

    @staticmethod
    async def save(content: str, file_path: str, encoding: str = "utf-8") -> str:
        """异步将内容写入文本文件。

        Args:
            content: 要写入的文本内容
            file_path: 目标文件路径
            encoding: 文件编码，默认为 UTF-8

        Returns:
            str: 写入的文件路径

        Raises:
            PermissionError: 如果没有权限写入文件
            OSError: 如果目录不存在或无法创建
        """
        # 确保目标目录存在
        directory = os.path.dirname(file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)

        async with aiofiles.open(file_path, "w", encoding=encoding) as file:
            await file.write(content)
            return file_path

    async def read(
        self, file_path: str, encoding: str = "utf-8", ignore_errors: bool = False
    ) -> List[Subtitle]:
        """
        异步从 SRT 文件中解析字幕内容。

        Args:
            file_path: SRT 字幕文件的路径。
            encoding: 文件编码，默认为 UTF-8。
            ignore_errors: 如果为 True，则忽略解析错误。

        Returns:
            List[Subtitle]: 解析后的 Subtitle 对象列表。

        Raises:
            FileNotFoundError: 如果文件不存在。
            PermissionError: 如果没有读取文件的权限。
            UnicodeDecodeError: 如果文件编码不匹配。
            SRTParseError: 如果解析过程中遇到不可恢复的错误且 ignore_errors 为 False。
        """
        srt_content = await self.load(file_path, encoding)
        return self._srt_parser.parse(srt_content, ignore_errors)

    async def write(
        self,
        subtitles: List[Subtitle],
        file_path: str,
        encoding: str = "utf-8",
        reindex: bool = True,
        start_index: int = 1,
        strict: bool = True,
        eol: str = None,
    ) -> str:
        """
        异步将 Subtitle 对象列表合成 SRT 字符串并写入文件。

        Args:
            subtitles: 要合成的 Subtitle 对象列表。
            file_path: 目标 SRT 文件的路径。
            encoding: 文件编码，默认为 UTF-8。
            reindex: 是否根据开始时间重新索引字幕。
            start_index: 如果重新索引，起始索引。
            strict: 是否启用严格模式（移除内容中的空行）。
            eol: 使用的行结束符（默认为 "\\n"）。

        Returns:
            str: 写入的文件路径。

        Raises:
            PermissionError: 如果没有权限写入文件。
            OSError: 如果目录不存在或无法创建。
        """
        composed = self.compose(subtitles, reindex, start_index, strict, eol)
        return await self.save(composed, file_path, encoding)

    def _count_tokens(self, text: str) -> int:
        """
        使用 tiktoken 计算给定文本的 token 数量。

        Args:
            text: 要计算 token 数量的文本。对于 Subtitle 对象，应该传入其 SRT 格式的字符串表示。

        Returns:
            int: 文本的 token 数量。
        """
        return len(self._tokenizer.encode(text))

    def _is_sentence_ender(self, char: str) -> bool:
        """检查字符是否是句子结束标点。"""
        return char in {".", "?", "!", "。", "？", "！"}

    def _can_merge_to_chunk(
        self, chunk: List[Subtitle], new_sub: Subtitle, max_tokens: int
    ) -> bool:
        """
        检查是否可以将新字幕添加到当前块中而不超过最大 token 限制。

        Args:
            chunk: 当前块中的字幕列表
            new_sub: 要添加的新字幕
            max_tokens: 最大 token 限制

        Returns:
            bool: 如果可以添加则返回 True，否则返回 False
        """
        if not chunk:
            return True

        # 计算当前块中所有字幕的 SRT 格式字符串的 token 数量
        chunk_srt = "".join(sub.to_srt() for sub in chunk)
        chunk_tokens = self._count_tokens(chunk_srt)

        # 计算新字幕的 SRT 格式字符串的 token 数量
        new_srt = new_sub.to_srt()
        new_tokens = self._count_tokens(new_srt)

        return chunk_tokens + new_tokens <= max_tokens

    async def split_subtitles(
        self, subtitles: List[Subtitle], max_tokens: int
    ) -> List[List[Subtitle]]:
        """
        根据指定的 token 数量上限，将字幕列表切分成多个子列表（字幕块）。
        每个字幕块包含一个或多个完整的字幕，且总 token 数（包括 SRT 格式的索引、时间戳和内容）不超过 max_tokens。
        同时确保每个块的最后一条字幕是一个完整的句子（以句子结束符结尾）。

        Args:
            subtitles: 原始 Subtitle 对象的列表。
            max_tokens: 每个字幕块允许的最大 token 数量。

        Returns:
            List[List[Subtitle]]: 包含多个字幕块的列表，每个字幕块是一个 Subtitle 列表。
        """
        if not subtitles or max_tokens <= 0:
            return []

        chunks = []
        current_chunk = []
        pending_subs = []  # 存储未完成句子的字幕

        for sub in subtitles:
            # 计算当前字幕的 SRT 格式字符串的 token 数量
            sub_srt = sub.to_srt()
            sub_tokens = self._count_tokens(sub_srt)

            # 如果单个字幕就超过了最大 token 限制，则单独作为一个块
            if sub_tokens > max_tokens:
                # 先处理之前积累的未完成句子
                if pending_subs:
                    if current_chunk:
                        chunks.append(current_chunk)
                    chunks.append(pending_subs)
                    pending_subs = []
                    current_chunk = []

                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = []

                chunks.append([sub])
                continue

            # 检查字幕内容是否以句子结束符结尾
            content = sub.content.strip()
            is_sentence_end = (
                content and self._is_sentence_ender(content[-1]) if content else False
            )

            # 将当前字幕添加到待处理列表
            pending_subs.append(sub)

            # 检查添加当前待处理字幕后是否会超过 token 限制
            all_subs = current_chunk + pending_subs
            all_srt = "".join(s.to_srt() for s in all_subs)
            all_tokens = self._count_tokens(all_srt)

            # 如果添加后不超过限制且当前字幕是句子结束，则合并到当前块
            if all_tokens <= max_tokens:
                if is_sentence_end:
                    current_chunk.extend(pending_subs)
                    pending_subs = []
            else:
                # 超过限制，需要开始新块
                if current_chunk:
                    chunks.append(current_chunk)

                # 如果待处理字幕本身不超过限制，则作为新块的开始
                pending_srt = "".join(s.to_srt() for s in pending_subs)
                pending_tokens = self._count_tokens(pending_srt)

                if pending_tokens <= max_tokens:
                    if is_sentence_end:
                        chunks.append(pending_subs)
                        pending_subs = []
                        current_chunk = []
                    else:
                        current_chunk = pending_subs
                        pending_subs = []
                else:
                    # 待处理字幕太大，需要进一步拆分
                    # 这种情况应该很少发生，因为我们已经处理了单个字幕超限的情况
                    for p_sub in pending_subs:
                        p_srt = p_sub.to_srt()
                        p_tokens = self._count_tokens(p_srt)

                        if (
                            current_chunk
                            and self._count_tokens(
                                "".join(s.to_srt() for s in current_chunk)
                            )
                            + p_tokens
                            > max_tokens
                        ):
                            chunks.append(current_chunk)
                            current_chunk = [p_sub]
                        else:
                            current_chunk.append(p_sub)

                    pending_subs = []

        # 处理剩余的字幕
        if pending_subs:
            if (
                current_chunk
                and self._count_tokens(
                    "".join(s.to_srt() for s in current_chunk + pending_subs)
                )
                <= max_tokens
            ):
                current_chunk.extend(pending_subs)
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = pending_subs

        # 添加最后一个块
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    async def merge_subtitles(
        self, subtitle_blocks: List[List[Subtitle]]
    ) -> List[Subtitle]:
        """
        根据给定的多个字幕块，按照时间顺序合并为一个单一的字幕列表。
        此方法主要用于将 `split_subtitles` 的输出（多个字幕块）平铺合并为一个有序的列表。

        Args:
            subtitle_blocks: 包含多个字幕块的列表，每个字幕块是一个 Subtitle 列表。

        Returns:
            List[Subtitle]: 合并后的单一 Subtitle 列表，已按时间顺序排序。
        """
        if not subtitle_blocks:
            return []

        all_subtitles: List[Subtitle] = []
        for block in subtitle_blocks:
            all_subtitles.extend(block)

        # 对所有字幕进行排序，确保最终列表是按时间顺序的
        # Subtitle 类已经实现了 __lt__，所以可以直接排序
        all_subtitles.sort()

        return all_subtitles

    async def coalesce_subtitles(
        self,
        subtitles: List[Subtitle],
        max_pause: timedelta = timedelta(seconds=0.7),
        punct_end: str = ",，.?!。？！",
        max_dur: timedelta = timedelta(seconds=15),
    ) -> List[Subtitle]:
        """
        智能合并时间上连续或重叠的字幕条目，旨在将逻辑上属于“一句话”但被分割的字幕合并。
        合并逻辑考虑：
        1. 相邻字幕之间的时间间隔。
        2. 字幕内容是否以句子结束标点符号结尾。
        3. 合并后的字幕总时长限制。

        Args:
            subtitles: 原始 Subtitle 对象的列表。
            max_pause: 允许合并的相邻字幕之间的最大暂停时间。
                       如果字幕结束和下一个字幕开始之间的实际暂停时间超过此值，则不合并。
                       默认为 0.7 秒。
            punct_end: 严格的句子结束标点符号字符串。如果一个字幕以这些标点符号结尾，
                       它通常被视为一个句子的结束，即使时间间隔很短，也不会与下一个字幕合并。
                       可以设置为空字符串 "" 来禁用此检查。
            max_dur: 单个合并后的字幕允许的最大持续时间。
                     防止将非常长的多句话合并成一个字幕条目，这可能不利于阅读。
                     默认为 15 秒。

        Returns:
            List[Subtitle]: 合并后的 Subtitle 对象列表，其中逻辑上连续的短字幕已合并为更长的字幕。
        """
        if not subtitles:
            return []

        sorted_subtitles = sorted(subtitles, key=lambda s: s.start)

        coalesced_subtitles: List[Subtitle] = []

        if not sorted_subtitles:
            return []

        current_subtitle = sorted_subtitles[0]

        for next_subtitle in sorted_subtitles[1:]:
            current_content_stripped = current_subtitle.content.strip()
            ends_with_sentence_punct = False
            if punct_end:
                if (
                    current_content_stripped
                    and current_content_stripped[-1] in punct_end
                ):
                    ends_with_sentence_punct = True

            pause_duration = next_subtitle.start - current_subtitle.end
            potential_total_duration = next_subtitle.end - current_subtitle.start

            should_merge = (
                not ends_with_sentence_punct
                and pause_duration <= max_pause
                and potential_total_duration <= max_dur
            )

            if should_merge:
                merged_content = (
                    current_subtitle.content.strip()
                    + " "
                    + next_subtitle.content.strip()
                )
                new_start = current_subtitle.start
                new_end = max(current_subtitle.end, next_subtitle.end)

                current_subtitle = Subtitle(
                    index=None,
                    start=new_start,
                    end=new_end,
                    content=merged_content,
                    proprietary=current_subtitle.proprietary,
                )
            else:
                coalesced_subtitles.append(current_subtitle)
                current_subtitle = next_subtitle

        coalesced_subtitles.append(current_subtitle)

        return coalesced_subtitles
