"""
测试字幕处理服务模块。
"""

from datetime import timedelta

import pytest

from gnosis.services.subtitle.parser import (SRTParseError, SrtParser,
                                             Subtitle, TimestampParseError)
from gnosis.services.subtitle.service import SubtitleService


class TestSubtitleService:
    """测试字幕处理服务。"""

    @pytest.mark.asyncio
    async def test_read(self, temp_file_path, sample_srt_content):
        """测试读取SRT文件。"""
        # 准备测试文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write(sample_srt_content)

        # 测试读取字幕
        subtitles = await SubtitleService().read(temp_file_path)
        assert len(subtitles) == 3
        assert subtitles[0].content == "Hello world!"
        assert subtitles[1].content == "This is a test\nof subtitle formatting."
        assert subtitles[2].content == "Another subtitle line."

    @pytest.mark.asyncio
    async def test_read_invalid_srt(self, temp_file_path):
        """测试读取无效的SRT文件。"""
        # 准备无效的SRT文件
        with open(temp_file_path, "w", encoding="utf-8") as f:
            f.write("Invalid SRT content")

        # 测试读取无效SRT文件
        with pytest.raises(SRTParseError):
            await SubtitleService().read(temp_file_path, ignore_errors=False)

    @pytest.mark.asyncio
    async def test_write(self, temp_file_path, sample_subtitles):
        """测试写入字幕到SRT文件。"""
        # 测试写入字幕
        result = await SubtitleService().write(sample_subtitles, temp_file_path)
        assert result == temp_file_path

        # 验证文件内容
        with open(temp_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "Hello world!" in content
            assert "This is a test" in content
            assert "Another subtitle line" in content

    @pytest.mark.asyncio
    async def test_count_tokens(self):
        """测试计算token数量。"""
        service = SubtitleService()
        text = "Hello world"
        token_count = service._count_tokens(text)
        assert isinstance(token_count, int)
        assert token_count > 0

    @pytest.mark.asyncio
    async def test_split_subtitles_basic(self, sample_subtitles):
        """测试基本的分割字幕功能。"""
        service = SubtitleService()
        chunks = await service.split_subtitles(sample_subtitles, max_tokens=100)

        # 验证返回类型和结构
        assert len(chunks) > 0
        assert all(isinstance(chunk, list) for chunk in chunks)
        assert all(isinstance(sub, Subtitle) for chunk in chunks for sub in chunk)

        # 验证所有原始字幕都在结果中
        original_contents = {sub.content for sub in sample_subtitles}
        result_contents = {sub.content for chunk in chunks for sub in chunk}
        assert original_contents.issubset(result_contents)

    @pytest.mark.asyncio
    async def test_split_subtitles_merges_short_subtitles(self):
        """测试合并短字幕到同一个chunk。"""
        service = SubtitleService()

        # 创建多个短字幕
        subtitles = [
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=2),
                content="Short one.",
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=4),
                content="Another short one.",
            ),
            Subtitle(
                index=3,
                start=timedelta(seconds=5),
                end=timedelta(seconds=6),
                content="And another one.",
            ),
        ]

        # 设置足够大的max_tokens以合并所有短字幕
        chunks = await service.split_subtitles(subtitles, max_tokens=100)

        # 应该合并成一个块
        assert len(chunks) == 1
        assert len(chunks[0]) == 3  # 包含所有三个短字幕

    @pytest.mark.asyncio
    async def test_split_subtitles_mixed_lengths(self):
        """测试混合长度的字幕。"""
        service = SubtitleService()

        # 创建多个短字幕
        short_sub1 = Subtitle(
            index=1,
            start=timedelta(seconds=1),
            end=timedelta(seconds=2),
            content="Short one.",  # ~2 tokens
        )

        # 创建一个中等长度的字幕
        medium_sub = Subtitle(
            index=2,
            start=timedelta(seconds=3),
            end=timedelta(seconds=4),
            content="This is a medium length subtitle that should be long enough to test the token limit. "
            * 2,  # ~30 tokens
        )

        # 创建一个非常长的字幕（超过token限制）
        long_sub = Subtitle(
            index=3,
            start=timedelta(seconds=5),
            end=timedelta(seconds=6),
            content=(
                "This is a very long subtitle that should exceed the token limit. " * 10
            )
            + (
                "It contains multiple sentences to ensure it's long enough. " * 5
            ),  # ~300 tokens
        )

        short_sub2 = Subtitle(
            index=4,
            start=timedelta(seconds=7),
            end=timedelta(seconds=8),
            content="Another short one.",  # ~3 tokens
        )

        subtitles = [short_sub1, medium_sub, long_sub, short_sub2]

        # 设置max_tokens为100，应该足够让短字幕和中等长度字幕合并，但长字幕单独成块
        chunks = await service.split_subtitles(subtitles, max_tokens=100)

        # 应该分成3个块：
        # 1. 第一个短字幕 + 中等长度字幕
        # 2. 长字幕（单独一个块，因为超过限制）
        # 3. 第二个短字幕
        assert len(chunks) == 3

        # 检查第一个块（短字幕 + 中等长度字幕）
        assert len(chunks[0]) == 2
        assert chunks[0][0].index == 1  # 第一个短字幕
        assert chunks[0][1].index == 2  # 中等长度字幕

        # 检查第二个块（长字幕）
        assert len(chunks[1]) == 1
        assert chunks[1][0].index == 3  # 长字幕

        # 检查第三个块（第二个短字幕）
        assert len(chunks[2]) == 1
        assert chunks[2][0].index == 4  # 第二个短字幕

    @pytest.mark.asyncio
    async def test_split_subtitles_preserves_order(self):
        """测试分割后字幕的顺序是否保持不变。"""
        service = SubtitleService()

        # 创建多个短字幕
        subtitles = [
            Subtitle(
                index=i,
                start=timedelta(seconds=i * 2),
                end=timedelta(seconds=i * 2 + 1),
                content=f"Subtitle {i}.",
            )
            for i in range(1, 6)
        ]

        chunks = await service.split_subtitles(subtitles, max_tokens=15)

        # 展平所有块
        all_subs = [sub for chunk in chunks for sub in chunk]

        # 验证顺序是否保持不变
        for i in range(1, 6):
            assert all_subs[i - 1].index == i
            assert f"Subtitle {i}." in all_subs[i - 1].content

    @pytest.mark.asyncio
    async def test_split_subtitles_sentence_completeness(self):
        """测试分割字幕时确保每个块的最后一条字幕是完整的句子。"""
        service = SubtitleService()

        # 创建一系列字幕，其中一些以句子结束符结尾，一些没有
        subtitles = [
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=2),
                content="This is the first part of a sentence",  # 不以句子结束符结尾
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=4),
                content="and this is the second part.",  # 以句号结尾
            ),
            Subtitle(
                index=3,
                start=timedelta(seconds=5),
                end=timedelta(seconds=6),
                content="This is another sentence?",  # 以问号结尾
            ),
            Subtitle(
                index=4,
                start=timedelta(seconds=7),
                end=timedelta(seconds=8),
                content="This is an incomplete",  # 不以句子结束符结尾
            ),
            Subtitle(
                index=5,
                start=timedelta(seconds=9),
                end=timedelta(seconds=10),
                content="sentence that continues here",  # 不以句子结束符结尾
            ),
            Subtitle(
                index=6,
                start=timedelta(seconds=11),
                end=timedelta(seconds=12),
                content="and finally ends here!",  # 以感叹号结尾
            ),
        ]

        # 设置 max_tokens 为 2000，符合实际使用场景
        chunks = await service.split_subtitles(subtitles, max_tokens=2000)

        # 验证每个块的最后一条字幕是否以句子结束符结尾
        for i, chunk in enumerate(chunks):
            if chunk:  # 确保块不为空
                last_sub = chunk[-1]
                content = last_sub.content.strip()
                assert content, f"块 {i+1} 的最后一条字幕内容为空"

                # 验证最后一条字幕是否以句子结束符结尾
                assert service._is_sentence_ender(
                    content[-1]
                ), f"块 {i+1} 的最后一条字幕不是完整句子: '{content}'"

        # 验证所有字幕都被包含在某个块中
        all_subs = [sub for chunk in chunks for sub in chunk]
        assert len(all_subs) == len(subtitles)

        # 验证字幕顺序是否保持不变
        for i, sub in enumerate(subtitles):
            assert all_subs[i].index == sub.index
            assert all_subs[i].content == sub.content

    @pytest.mark.asyncio
    async def test_split_subtitles_oversized_subtitle(self):
        """测试处理超长且不以句子结束符结尾的字幕的情况。"""
        service = SubtitleService()

        # 创建一个超长且不以句子结束符结尾的字幕
        oversized_subtitle = Subtitle(
            index=1,
            start=timedelta(seconds=1),
            end=timedelta(seconds=5),
            content="This is an extremely long subtitle that exceeds the token limit and does not end with a sentence-ending punctuation mark "
            * 10,  # 不以句子结束符结尾
        )

        # 创建一些正常的字幕，以句子结束符结尾
        normal_subtitle1 = Subtitle(
            index=2,
            start=timedelta(seconds=6),
            end=timedelta(seconds=8),
            content="This is a normal subtitle that ends properly.",
        )

        normal_subtitle2 = Subtitle(
            index=3,
            start=timedelta(seconds=9),
            end=timedelta(seconds=11),
            content="Another normal subtitle!",
        )

        subtitles = [oversized_subtitle, normal_subtitle1, normal_subtitle2]

        # 设置一个小于超长字幕token数的max_tokens值
        # 这将强制系统将超长字幕单独作为一个块，即使它不以句子结束符结尾
        chunks = await service.split_subtitles(subtitles, max_tokens=100)

        # 验证分块结果
        assert len(chunks) >= 2, "应该至少分成两个块"

        # 验证第一个块应该只包含超长字幕
        assert len(chunks[0]) == 1, "第一个块应该只包含超长字幕"
        assert chunks[0][0].index == 1, "第一个块应该包含索引为1的字幕"

        # 验证后续块的最后一条字幕应该以句子结束符结尾
        for i in range(1, len(chunks)):
            if chunks[i]:  # 确保块不为空
                last_sub = chunks[i][-1]
                content = last_sub.content.strip()
                assert content, f"块 {i+1} 的最后一条字幕内容为空"

                # 验证最后一条字幕是否以句子结束符结尾
                assert service._is_sentence_ender(
                    content[-1]
                ), f"块 {i+1} 的最后一条字幕不是完整句子: '{content}'"

        # 验证所有字幕都被包含在某个块中
        all_subs = [sub for chunk in chunks for sub in chunk]
        assert len(all_subs) == len(subtitles), "所有字幕都应该被包含在某个块中"

        # 验证字幕顺序是否保持不变
        for i, sub in enumerate(subtitles):
            assert all_subs[i].index == sub.index, f"字幕 {i+1} 的索引不匹配"
            assert all_subs[i].content == sub.content, f"字幕 {i+1} 的内容不匹配"

    @pytest.mark.asyncio
    async def test_split_subtitles_sentence_continuity(self):
        """测试连续的不完整句子字幕会被正确处理，确保它们被分组到同一个块中。"""
        service = SubtitleService()

        # 创建一系列连续的不完整句子字幕
        subtitles = [
            # 第一个句子分成多个字幕
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=2),
                content="This is the beginning of",  # 不完整
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=3),
                end=timedelta(seconds=4),
                content="a very long sentence that",  # 不完整
            ),
            Subtitle(
                index=3,
                start=timedelta(seconds=5),
                end=timedelta(seconds=6),
                content="continues across multiple subtitles.",  # 完整句子
            ),
            # 第二个句子分成多个字幕
            Subtitle(
                index=4,
                start=timedelta(seconds=7),
                end=timedelta(seconds=8),
                content="Now we have another",  # 不完整
            ),
            Subtitle(
                index=5,
                start=timedelta(seconds=9),
                end=timedelta(seconds=10),
                content="sentence that spans across",  # 不完整
            ),
            Subtitle(
                index=6,
                start=timedelta(seconds=11),
                end=timedelta(seconds=12),
                content="multiple subtitle entries!",  # 完整句子
            ),
            # 第三个句子是完整的
            Subtitle(
                index=7,
                start=timedelta(seconds=13),
                end=timedelta(seconds=14),
                content="This is a complete sentence in one subtitle.",  # 完整句子
            ),
        ]

        # 设置一个足够大的 max_tokens 值，以便可以容纳多个字幕
        # 但不足以容纳所有字幕，以便强制分块
        chunks = await service.split_subtitles(subtitles, max_tokens=100)

        # 验证分块结果
        assert len(chunks) >= 2, "应该至少分成两个块"

        # 验证每个块的最后一条字幕是否以句子结束符结尾
        for i, chunk in enumerate(chunks):
            if chunk:  # 确保块不为空
                last_sub = chunk[-1]
                content = last_sub.content.strip()
                assert content, f"块 {i+1} 的最后一条字幕内容为空"

                # 验证最后一条字幕是否以句子结束符结尾
                assert service._is_sentence_ender(
                    content[-1]
                ), f"块 {i+1} 的最后一条字幕不是完整句子: '{content}'"

        # 验证不完整句子的字幕应该被分组在一起
        # 验证第一个句子的三个字幕应该在同一个块中
        first_sentence_indices = {1, 2, 3}
        first_sentence_chunk = None

        # 找到包含第一个句子第一部分的块
        for chunk in chunks:
            for sub in chunk:
                if sub.index == 1:
                    first_sentence_chunk = chunk
                    break
            if first_sentence_chunk:
                break

        # 验证第一个句子的所有部分都在同一个块中
        assert first_sentence_chunk is not None, "找不到包含第一个句子的块"
        chunk_indices = {sub.index for sub in first_sentence_chunk}
        assert first_sentence_indices.issubset(
            chunk_indices
        ), f"第一个句子的字幕应该在同一个块中，实际块内索引: {chunk_indices}"

        # 验证第二个句子的三个字幕应该在同一个块中
        second_sentence_indices = {4, 5, 6}
        second_sentence_chunk = None

        # 找到包含第二个句子第一部分的块
        for chunk in chunks:
            for sub in chunk:
                if sub.index == 4:
                    second_sentence_chunk = chunk
                    break
            if second_sentence_chunk:
                break

        # 验证第二个句子的所有部分都在同一个块中
        assert second_sentence_chunk is not None, "找不到包含第二个句子的块"
        chunk_indices = {sub.index for sub in second_sentence_chunk}
        assert second_sentence_indices.issubset(
            chunk_indices
        ), f"第二个句子的字幕应该在同一个块中，实际块内索引: {chunk_indices}"

        # 验证所有字幕都被包含在某个块中
        all_subs = [sub for chunk in chunks for sub in chunk]
        assert len(all_subs) == len(subtitles), "所有字幕都应该被包含在某个块中"

        # 验证字幕顺序是否保持不变
        for i, sub in enumerate(subtitles):
            assert all_subs[i].index == sub.index, f"字幕 {i+1} 的索引不匹配"
            assert all_subs[i].content == sub.content, f"字幕 {i+1} 的内容不匹配"

    @pytest.mark.asyncio
    async def test_merge_subtitles(self, sample_subtitles):
        """测试合并字幕。"""
        service = SubtitleService()
        chunks = [sample_subtitles[:2], sample_subtitles[2:]]
        merged = await service.merge_subtitles(chunks)
        assert len(merged) == 3
        assert merged[0].index == 1
        assert merged[-1].index == 3

        # 验证合并后的内容是否正确
        assert "Hello world!" in merged[0].content
        assert "This is a test" in merged[1].content
        assert "Another subtitle line" in merged[2].content

    @pytest.mark.asyncio
    async def test_coalesce_subtitles(self, sample_subtitles):
        """测试合并连续字幕。"""
        service = SubtitleService()
        mergeable_subtitles = [
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=3),
                content="First part",
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=3, milliseconds=500),
                end=timedelta(seconds=6),
                content="Second part",
            ),
        ]
        coalesced = await service.coalesce_subtitles(
            mergeable_subtitles, max_pause=timedelta(seconds=1)
        )
        assert len(coalesced) == 1
        assert "First part" in coalesced[0].content
        assert "Second part" in coalesced[0].content
        # 允许内容为 'First part Second part' 或 'First part\nSecond part'
        assert coalesced[0].content.replace("\n", " ") == "First part Second part"

    @pytest.mark.asyncio
    async def test_coalesce_subtitles_with_punctuation(self):
        """测试带标点符号的字幕合并。"""
        service = SubtitleService()
        subtitles = [
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=3),
                content="First part.",
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=3, milliseconds=100),
                end=timedelta(seconds=6),
                content="Second part.",
            ),
        ]
        coalesced = await service.coalesce_subtitles(subtitles, punct_end=".!?。！？")
        assert len(coalesced) == 2

    @pytest.mark.asyncio
    async def test_coalesce_subtitles_max_duration(self):
        """测试最大持续时间限制。"""
        service = SubtitleService()
        subtitles = [
            Subtitle(
                index=1,
                start=timedelta(seconds=1),
                end=timedelta(seconds=5),
                content="First part",
            ),
            Subtitle(
                index=2,
                start=timedelta(seconds=5, milliseconds=100),
                end=timedelta(seconds=10),
                content="Second part",
            ),
            Subtitle(
                index=3,
                start=timedelta(seconds=10, milliseconds=100),
                end=timedelta(seconds=16),
                content="Third part",
            ),
        ]
        coalesced = await service.coalesce_subtitles(
            subtitles, max_dur=timedelta(seconds=10)
        )
        assert len(coalesced) == 2

    @pytest.mark.asyncio
    async def test_format_timestamp(self):
        """测试时间戳格式化。"""
        subtitle = Subtitle(
            index=1,
            start=timedelta(hours=1, minutes=23, seconds=45, milliseconds=678),
            end=timedelta(hours=1, minutes=24, seconds=45, milliseconds=678),
            content="Test",
        )
        srt_block = subtitle.to_srt()
        assert "01:23:45,678" in srt_block
        assert "01:24:45,678" in srt_block

    @pytest.mark.asyncio
    async def test_parse_timestamp(self):
        """测试解析时间戳。"""
        srt = "1\n01:23:45,678 --> 01:24:45,678\nTest\n"
        parser = SrtParser()
        subtitles = parser.parse(srt)
        assert subtitles[0].start == timedelta(
            hours=1, minutes=23, seconds=45, milliseconds=678
        )
        assert subtitles[0].end == timedelta(
            hours=1, minutes=24, seconds=45, milliseconds=678
        )

    @pytest.mark.asyncio
    async def test_invalid_timestamp(self):
        """测试无效时间戳解析。"""
        srt = "1\ninvalid-timestamp --> 01:24:45,678\nTest\n"
        parser = SrtParser()
        with pytest.raises(SRTParseError):
            parser.parse(srt)

    @pytest.mark.asyncio
    async def test_parse_srt_with_proprietary(self):
        """测试解析包含专有信息的SRT。"""
        srt_content = (
            "1\n"
            "00:00:01,000 --> 00:00:04,000 X1:0 X2:100 Y1:0 Y2:50\n"
            "Hello world!\n"
        )
        parser = SrtParser()
        subtitles = parser.parse(srt_content)
        assert len(subtitles) == 1
        assert subtitles[0].proprietary == "X1:0 X2:100 Y1:0 Y2:50"
        assert subtitles[0].content == "Hello world!"

    @pytest.mark.asyncio
    async def test_write_with_custom_eol(self, temp_file_path, sample_subtitles):
        """测试使用自定义行结束符写入SRT。"""
        service = SubtitleService()
        await service.write(
            sample_subtitles, temp_file_path, eol="\r\n"  # Windows风格换行
        )

        with open(temp_file_path, "rb") as f:
            content = f.read()
            assert b"\r\n" in content  # 应该包含CRLF

    @pytest.mark.asyncio
    async def test_write_without_reindex(self, temp_file_path, sample_subtitles):
        """测试不重新索引写入SRT。"""
        service = SubtitleService()
        # 设置不连续的索引
        sample_subtitles[0].index = 10
        sample_subtitles[1].index = 20
        sample_subtitles[2].index = 30

        await service.write(sample_subtitles, temp_file_path, reindex=False)

        # 读取并验证索引
        with open(temp_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert lines[0].strip() == "10"  # 第一个字幕的索引应该是10

    @pytest.mark.asyncio
    async def test_timestamp_formatting_through_write(self, temp_file_path):
        """测试时间戳格式化（通过写入功能）。"""
        service = SubtitleService()
        subtitle = Subtitle(
            index=1,
            start=timedelta(hours=1, minutes=23, seconds=45, milliseconds=678),
            end=timedelta(hours=1, minutes=24, seconds=45, milliseconds=678),
            content="Test timestamp formatting",
        )

        await service.write([subtitle], temp_file_path)

        with open(temp_file_path, "r", encoding="utf-8") as f:
            content = f.read()
            assert "01:23:45,678" in content
            assert "01:24:45,678" in content

    @pytest.mark.asyncio
    async def test_reindex_through_write(self, temp_file_path, sample_subtitles):
        """测试重新索引（通过写入功能）。"""
        service = SubtitleService()
        # 打乱索引
        sample_subtitles[0].index = 10
        sample_subtitles[1].index = 20
        sample_subtitles[2].index = 30

        # 写入时不重新索引
        await service.write(sample_subtitles, temp_file_path, reindex=False)

        # 读取并验证索引
        with open(temp_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert lines[0].strip() == "10"  # 第一个字幕的索引应该是10

        # 写入时重新索引
        await service.write(
            sample_subtitles, temp_file_path, reindex=True, start_index=100
        )

        # 读取并验证索引
        with open(temp_file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert lines[0].strip() == "100"  # 第一个字幕的索引应该是100
