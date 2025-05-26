"""
审核智能体，负责审核和优化翻译后的字幕内容。
"""

from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from gnosis.core.config import settings

reviewer = Agent(
    name="Reviewer",
    role="审核专家",
    model=DeepSeek(api_key=settings.DEEPSEEK_API_KEY),
    markdown=False,
    instructions=[
        (
            "请根据输入的字幕内容，分析并返回："
            "1. 改进后的字幕内容（improved_content，字符串）；"
            "2. 发现的问题列表（issues，数组），每个问题包含行号、问题类型、描述和建议；"
            "3. 翻译质量评分（quality_score，1-10的整数）；"
            "4. 总体评价（comments，字符串）。"
            "以JSON格式返回，如："
            '{"improved_content":"...",'
            '"issues":[{"line_number":10,"issue_type":"accuracy","description":"...","suggestion":"..."}],'
            '"quality_score":8,'
            '"comments":"..."}'
        ),
        "必须使用中文返回所有结果，包括问题描述、建议和评价中的所有文本。",
        "只返回原始 JSON，不要输出 Markdown 代码块或其他多余文本。",
        "不要在返回的 JSON 前后添加 ```json 或 ``` 标记。",
        "注意：你的评分和评价仅用于内部处理，不会直接显示给用户。最终输出中不应包含评分或评价信息。",
    ],
)
