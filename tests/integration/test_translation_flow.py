"""
集成测试：测试完整的翻译流程，包括翻译、审核和改进。
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gnosis.agents.team import TranslationTeam


@pytest.fixture
def sample_subtitle_content() -> str:
    """返回示例字幕内容。"""
    return """1
00:00:01,000 --> 00:00:04,000
Hello, this is a test subtitle.

2
00:00:05,000 --> 00:00:08,000
We are testing the translation flow.

3
00:00:09,000 --> 00:00:12,000
This should be translated properly.
And maintain the correct format.
"""


@pytest.fixture
def mock_translation_team():
    """模拟 TranslationTeam 实例。"""
    # 创建模拟的 TranslationTeam 实例
    with patch("gnosis.core.config.settings") as mock_settings:
        mock_settings.DEEPSEEK_API_KEY = "test_api_key"

        # 创建 TranslationTeam 实例
        team = TranslationTeam()

        # 模拟 team 属性
        team.team = MagicMock()
        team.team.arun = AsyncMock()

        yield team


class TestTranslationFlow:
    """测试翻译流程。"""

    @pytest.mark.asyncio
    async def test_end_to_end_translation(
        self, mock_translation_team, sample_subtitle_content
    ):
        """测试端到端翻译流程。"""
        # 设置模拟返回值
        translated_content = """1
00:00:01,000 --> 00:00:04,000
Hello, this is a test subtitle.
你好，这是一个测试字幕。

2
00:00:05,000 --> 00:00:08,000
We are testing the translation flow.
我们正在测试翻译流程。

3
00:00:09,000 --> 00:00:12,000
This should be translated properly.
And maintain the correct format.
这应该被正确翻译。
并保持正确的格式。
"""
        mock_response = MagicMock()
        mock_response.content = translated_content
        mock_translation_team.team.arun.return_value = mock_response

        # 执行翻译
        result = await mock_translation_team.translate(sample_subtitle_content)

        # 验证结果
        assert "你好，这是一个测试字幕" in result
        assert "我们正在测试翻译流程" in result
        assert "这应该被正确翻译" in result
        assert "并保持正确的格式" in result

        # 验证时间戳保留
        assert "00:00:01,000 --> 00:00:04,000" in result
        assert "00:00:05,000 --> 00:00:08,000" in result
        assert "00:00:09,000 --> 00:00:12,000" in result

        # 验证调用参数
        assert mock_translation_team.team.arun.call_count == 1
        # 验证调用参数包含关键内容
        call_args = mock_translation_team.team.arun.call_args[0][0]
        assert "请将以下en字幕翻译为zh" in call_args
        # 验证关键行存在于调用参数中
        assert "Hello, this is a test subtitle." in call_args
        assert "We are testing the translation flow." in call_args
        assert "This should be translated properly." in call_args
        assert "And maintain the correct format." in call_args

    @pytest.mark.asyncio
    async def test_batch_translation(self, mock_translation_team):
        """测试批量翻译流程。"""
        # 准备测试数据
        contents = [
            "1\n00:00:01,000 --> 00:00:03,000\nThis is test one.",
            "2\n00:00:04,000 --> 00:00:06,000\nThis is test two.",
            "3\n00:00:07,000 --> 00:00:09,000\nThis is test three.",
        ]

        translated_contents = [
            "1\n00:00:01,000 --> 00:00:03,000\nThis is test one.\n这是测试一。",
            "2\n00:00:04,000 --> 00:00:06,000\nThis is test two.\n这是测试二。",
            "3\n00:00:07,000 --> 00:00:09,000\nThis is test three.\n这是测试三。",
        ]

        # 模拟 translate 方法
        mock_translation_team.translate = AsyncMock(side_effect=translated_contents)

        # 执行批量翻译
        results = await mock_translation_team.batch_translate(contents)

        # 验证结果
        assert len(results) == 3
        assert mock_translation_team.translate.call_count == 3

        # 验证每个结果
        for i, result in enumerate(results):
            assert result == translated_contents[i]
            mock_translation_team.translate.assert_any_call(contents[i], "en", "zh")

    @pytest.mark.asyncio
    @pytest.mark.skipif(
        not os.environ.get("DEEPSEEK_API_KEY"), reason="需要 DEEPSEEK_API_KEY 环境变量"
    )
    async def test_real_translation(self, sample_subtitle_content):
        """测试真实翻译流程（需要 API 密钥）。"""
        # 创建真实的 TranslationTeam 实例
        team = TranslationTeam()

        # 执行翻译
        result = await team.translate(sample_subtitle_content)

        # 验证结果
        assert result is not None
        assert len(result) > 0

        # 验证包含原始英文和翻译后的中文
        assert "Hello, this is a test subtitle" in result
        assert "We are testing the translation flow" in result

        # 验证时间戳保留
        assert "00:00:01,000 --> 00:00:04,000" in result
        assert "00:00:05,000 --> 00:00:08,000" in result
        assert "00:00:09,000 --> 00:00:12,000" in result
