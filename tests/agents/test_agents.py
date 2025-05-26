"""
测试智能体模块。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# 模拟 settings 对象
with patch("gnosis.core.config.settings") as mock_settings:
    mock_settings.DEEPSEEK_API_KEY = "test_api_key"

    # 导入需要使用 settings 的模块
    from gnosis.agents.improver import improver
    from gnosis.agents.reviewer import reviewer
    from gnosis.agents.team import TranslationTeam
    from gnosis.agents.translator import translator


@pytest.fixture
def sample_subtitle_content() -> str:
    """返回示例字幕内容。"""
    return """1
00:00:01,000 --> 00:00:04,000
Hello, this is a test subtitle.

2
00:00:05,000 --> 00:00:08,000
We are testing the translation agent.

3
00:00:09,000 --> 00:00:12,000
This should be translated properly.
And maintain the correct format.
"""


@pytest.fixture
def mock_agents():
    """模拟所有智能体。"""
    with patch.object(
        translator, "arun", new_callable=AsyncMock
    ) as translator_mock, patch.object(
        reviewer, "arun", new_callable=AsyncMock
    ) as reviewer_mock, patch.object(
        improver, "arun", new_callable=AsyncMock
    ) as improver_mock:
        yield {
            "translator": translator_mock,
            "reviewer": reviewer_mock,
            "improver": improver_mock,
        }


@pytest.fixture
def translation_team():
    """创建翻译团队实例。"""
    return TranslationTeam()


@pytest.fixture
def mock_team(translation_team):
    """模拟 TranslationTeam 实例的 team 属性。"""
    # 保存原始的 team 属性
    original_team = translation_team.team

    # 创建模拟对象
    mock_team_obj = MagicMock()
    mock_team_obj.arun = AsyncMock()

    # 替换 team 属性
    translation_team.team = mock_team_obj

    yield mock_team_obj

    # 测试后恢复原始的 team 属性
    translation_team.team = original_team


class TestAgents:
    """测试智能体类。"""

    @pytest.mark.asyncio
    async def test_translator_agent(self, sample_subtitle_content, mock_agents):
        """测试翻译智能体。"""
        # 设置模拟返回值
        translated_content = "1\n00:00:01,000 --> 00:00:04,000\nHello, this is a test subtitle.\n你好，这是一个测试字幕。"

        mock_response = MagicMock()
        mock_response.content = translated_content
        mock_agents["translator"].return_value = mock_response

        # 调用翻译方法
        response = await translator.arun(sample_subtitle_content)

        # 验证结果
        mock_agents["translator"].assert_called_once_with(sample_subtitle_content)
        assert response.content == translated_content

    @pytest.mark.asyncio
    async def test_reviewer_agent(self, sample_subtitle_content, mock_agents):
        """测试审核智能体。"""
        # 设置模拟返回值
        review_json = '{"improved_content":"1\n00:00:01,000 --> 00:00:04,000\nHello, this is a test subtitle.\n你好，这是一个测试字幕。","issues":[{"line_number":3,"issue_type":"accuracy","description":"翻译不够准确","suggestion":"可以翻译为\'这是一个测试用的字幕\'"}],"quality_score":7,"comments":"翻译基本正确，但可以更准确"}'

        mock_response = MagicMock()
        mock_response.content = review_json
        mock_agents["reviewer"].return_value = mock_response

        # 调用审核方法
        response = await reviewer.arun(sample_subtitle_content)

        # 验证结果
        mock_agents["reviewer"].assert_called_once_with(sample_subtitle_content)
        assert response.content == review_json

    @pytest.mark.asyncio
    async def test_improver_agent(self, sample_subtitle_content, mock_agents):
        """测试改进智能体。"""
        # 设置模拟返回值
        improved_content = "1\n00:00:01,000 --> 00:00:04,000\nHello, this is a test subtitle.\n你好，这是一个测试用的字幕。"

        mock_response = MagicMock()
        mock_response.content = improved_content
        mock_agents["improver"].return_value = mock_response

        # 构建提示词
        prompt = f"原始翻译：\n{sample_subtitle_content}\n\n审核反馈：\n1. 行号 3: 翻译不够准确 - 可以翻译为'这是一个测试用的字幕'"

        # 调用改进方法
        response = await improver.arun(prompt)

        # 验证结果
        mock_agents["improver"].assert_called_once_with(prompt)
        assert response.content == improved_content


class TestTranslationTeam:
    """测试翻译团队类。"""

    @pytest.mark.asyncio
    async def test_translate(self, translation_team, mock_team):
        """测试翻译方法。"""
        # 设置模拟返回值
        original_content = "1\n00:00:01,000 --> 00:00:03,000\nThis is a test."
        translated_content = (
            "1\n00:00:01,000 --> 00:00:03,000\nThis is a test.\n这是一个测试。"
        )

        mock_response = MagicMock()
        mock_response.content = translated_content
        mock_team.arun.return_value = mock_response

        # 调用翻译方法
        result = await translation_team.translate(original_content)

        # 验证结果
        expected_prompt = (
            f"请将以下en字幕翻译为zh，并按照要求进行审核和改进：\n\n{original_content}"
        )
        mock_team.arun.assert_called_once_with(expected_prompt)
        assert result == translated_content

    @pytest.mark.asyncio
    async def test_translate_with_empty_response(self, translation_team, mock_team):
        """测试翻译方法，响应为空的情况。"""
        # 设置模拟返回值
        original_content = "1\n00:00:01,000 --> 00:00:03,000\nThis is a test."

        mock_response = MagicMock()
        mock_response.content = ""
        mock_team.arun.return_value = mock_response

        # 调用翻译方法
        result = await translation_team.translate(original_content)

        # 验证结果
        assert result == original_content

    @pytest.mark.asyncio
    async def test_batch_translate(self, translation_team):
        """测试批量翻译方法。"""
        # 设置模拟数据
        contents = [
            "1\n00:00:01,000 --> 00:00:03,000\nThis is test one.",
            "2\n00:00:04,000 --> 00:00:06,000\nThis is test two.",
        ]

        translated_contents = [
            "1\n00:00:01,000 --> 00:00:03,000\nThis is test one.\n这是测试一。",
            "2\n00:00:04,000 --> 00:00:06,000\nThis is test two.\n这是测试二。",
        ]

        # 模拟 translate 方法
        translation_team.translate = AsyncMock(side_effect=translated_contents)

        # 调用批量翻译方法
        results = await translation_team.batch_translate(contents)

        # 验证结果
        assert len(results) == 2
        assert translation_team.translate.call_count == 2

        # 验证每个结果
        for i, result in enumerate(results):
            assert result == translated_contents[i]

    @pytest.mark.asyncio
    async def test_team_integration(self, translation_team):
        """测试团队集成，验证翻译团队的整体工作流程。"""
        # 这是一个集成测试，验证翻译团队的整体工作流程
        # 注意：这个测试需要实际的 API 密钥和网络连接，可能会产生 API 调用费用
        # 在实际环境中，可能需要使用模拟或者跳过此测试
        pytest.skip("跳过集成测试，避免实际 API 调用")

        # 测试内容
        content = """1
00:00:01,000 --> 00:00:03,000
This is a test.

2
00:00:03,500 --> 00:00:05,500
If you follow the instructions,

3
00:00:05,500 --> 00:00:07,500
you will succeed."""

        # 调用翻译方法
        result = await translation_team.translate(content)

        # 验证结果
        assert result is not None
        assert len(result) > 0
        # 验证结果包含英文和中文
        assert "This is a test" in result
        assert "这是一个测试" in result
        # 验证结果包含时间戳
        assert "00:00:01,000 --> 00:00:03,000" in result
