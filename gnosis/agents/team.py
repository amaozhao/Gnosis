"""翻译团队模块，使用 Agno 团队组件整合翻译和审核流程。"""

import re

from agno.models.deepseek import DeepSeek
from agno.team.team import Team

from gnosis.agents.improver import improver
from gnosis.agents.reviewer import reviewer
from gnosis.agents.translator import translator
from gnosis.core.config import settings


class TranslationTeam:
    """翻译团队类，使用 Agno 的 Team 组件整合翻译和审核流程。"""

    def __init__(self):
        """初始化翻译团队。"""
        # 创建翻译团队
        self.team = Team(
            name="Translation Team",
            mode="coordinate",  # 使用协调模式
            model=DeepSeek(api_key=settings.DEEPSEEK_API_KEY),
            members=[translator, reviewer, improver],
            description="你是一个字幕翻译团队的协调者，负责协调翻译、审核和改进流程。",
            instructions=[
                "你的任务是协调字幕翻译流程，包括翻译、审核和改进三个步骤。",
                "1. 首先，将原始字幕内容发送给翻译专家进行翻译。",
                "2. 然后，将翻译结果和原始内容一起发送给审核专家进行审核。",
                "3. 最后，如果审核发现问题，将翻译结果和审核反馈发送给改进专家进行改进。",
                "4. 如果审核未发现问题或评分较高（8分以上），可以直接返回翻译结果，无需改进。",
                "5. 翻译时必须注意处理连续字幕，如果一个完整的句子被分割到多个字幕单元中，必须将它们合并后再翻译，确保语义完整。",
                "6. 清除字幕文本行开头和结尾的空格，确保输出格式整洁。",
                "7. 最终只返回翻译后的字幕内容，严格按照SRT字幕格式，不要添加任何评分、评价或描述性文字。",
                "8. 不要在输出中包含'审核评分'、'翻译质量'等任何额外信息，只返回纯粹的字幕内容。",
                "9. **必须保留原始英文字幕**，英文在上，中文在下。在原始英文行的下方添加对应的中文翻译行。中英文之间必须换行，不能在同一行内。",
                "10. 当英文字幕有多行时，必须先列出所有英文行，然后再列出对应的中文翻译行。",
            ],
            enable_agentic_context=True,  # 启用智能体上下文
            share_member_interactions=True,  # 共享成员交互
            show_members_responses=True,  # 显示成员响应
            markdown=False,  # 不使用 Markdown
        )

    async def translate(
        self, content: str, source_language: str = "en", target_language: str = "zh"
    ) -> str:
        """翻译字幕内容。

        Args:
            content: 完整的字幕内容
            source_language: 源语言代码，默认为英文
            target_language: 目标语言代码，默认为中文

        Returns:
            str: 翻译后的字幕内容
        """
        # 如果内容为空，直接返回
        if not content or not content.strip():
            return content

        # 预处理内容，清除字幕开头/结尾的空格
        processed_content = self._preprocess_content(content)

        # 构建提示词
        prompt = f"请将以下{source_language}字幕翻译为{target_language}，并按照要求进行审核和改进：\n\n{processed_content}"

        # 执行翻译
        response = await self.team.arun(prompt)

        # 处理响应
        if not response or not response.content:
            return content

        # 过滤掉可能的评分或描述性文字
        translated_content = self._clean_output(response.content)
        return translated_content

    async def batch_translate(
        self,
        contents: list[str],
        source_language: str = "en",
        target_language: str = "zh",
    ) -> list[str]:
        """批量翻译字幕内容。

        Args:
            contents: 需要翻译的字幕内容列表
            source_language: 源语言代码，默认为英文
            target_language: 目标语言代码，默认为中文

        Returns:
            list[str]: 翻译后的字幕内容列表
        """
        results = []
        for content in contents:
            translated = await self.translate(content, source_language, target_language)
            results.append(translated)
        return results

    def _clean_output(self, content: str) -> str:
        """清理输出内容，移除可能的评分或描述性文字。

        Args:
            content: 原始输出内容

        Returns:
            str: 清理后的内容
        """
        # 如果内容为空，直接返回
        if not content:
            return content

        # 分割内容为行
        lines = content.split("\n")
        cleaned_lines = []

        # 寻找第一个字幕序号行
        start_index = -1
        for i, line in enumerate(lines):
            # 如果是序号行（数字）并且后面跟着时间戳行
            if (
                line.strip().isdigit()
                and i + 1 < len(lines)
                and re.match(
                    r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}",
                    lines[i + 1].strip(),
                )
            ):
                start_index = i
                break

        # 如果找到了字幕开始的地方，只保留从这里开始的内容
        if start_index >= 0:
            cleaned_lines = lines[start_index:]
        else:
            # 如果没找到字幕开始的地方，尝试其他清理方法
            skip_line = False
            for line in lines:
                # 跳过包含评分或评价的行
                if re.search(
                    r"审核评分|翻译质量|分，翻译|评分为|符合要求|以下是|最终翻译|翻译后的|字幕内容|已将|翻译任务|等待|完成|下一步|审核流程",
                    line,
                ):
                    skip_line = True
                    continue

                # 跳过分隔线
                if re.match(r"^-{3,}$|^={3,}$|^\*{3,}$", line.strip()):
                    skip_line = True
                    continue

                # 如果前面有跳过的行，并且当前行是空行，也跳过
                if skip_line and not line.strip():
                    continue

                # 重置跳过标志
                skip_line = False

                # 添加有效行
                cleaned_lines.append(line)

        # 返回清理后的内容
        return "\n".join(cleaned_lines)

    def _preprocess_content(self, content: str) -> str:
        """预处理字幕内容，清除字幕开头/结尾的空格，并合并语义相关的连续字幕。

        Args:
            content: 原始字幕内容

        Returns:
            str: 处理后的字幕内容
        """
        # 如果内容为空，直接返回
        if not content:
            return content

        # 分割内容为行
        lines = content.split("\n")

        # 第一步：清除每行开头/结尾的空格
        clean_lines = []
        for line in lines:
            # 如果是序号行或时间戳行，保持原样
            if line.strip().isdigit() or re.match(
                r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}", line.strip()
            ):
                clean_lines.append(line)
            else:
                # 清除字幕文本行开头/结尾的空格
                clean_lines.append(line.strip())

        # 第二步：分割字幕内容为字幕块
        subtitle_blocks = []
        current_block = []

        for i, line in enumerate(clean_lines):
            # 如果是序号行（数字），开始新的字幕块
            if (
                line.strip().isdigit()
                and i + 1 < len(clean_lines)
                and re.match(
                    r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}",
                    clean_lines[i + 1].strip(),
                )
            ):
                if current_block:
                    subtitle_blocks.append(current_block)
                current_block = [line]
            else:
                current_block.append(line)

        # 添加最后一个字幕块
        if current_block:
            subtitle_blocks.append(current_block)

        # 第三步：分析并合并语义相关的字幕块
        # 修改策略：不在预处理阶段合并字幕块，只清除空格
        # 字幕块合并将由翻译智能体完成
        processed_lines = []

        for line in clean_lines:
            # 清除空格后添加到结果中
            processed_lines.append(line)

        # 第四步：保持字幕块之间的空行
        # 添加空行分隔字幕块
        final_lines = []
        prev_is_empty = False

        for i, line in enumerate(processed_lines):
            # 如果是序号行（数字）且前一行不是空行，添加空行
            if line.strip().isdigit() and i > 0 and not prev_is_empty:
                final_lines.append("")

            final_lines.append(line)
            prev_is_empty = line.strip() == ""

        # 去除最后一个空行
        if final_lines and not final_lines[-1].strip():
            final_lines.pop()

        processed_lines = final_lines

        # 返回处理后的内容
        return "\n".join(processed_lines)
