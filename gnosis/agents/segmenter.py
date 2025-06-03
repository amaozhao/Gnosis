# agents/segmenter.py
from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from gnosis.agents.prompts.instructions import segmenter_instructions
from gnosis.core.config import settings

# 直接创建 DeepSeek 模型实例
segmenter_model = DeepSeek(
    api_key=settings.DEEPSEEK_API_KEY,
)


def get_segmenter():

    segmenter = Agent(
        name="segmenter",
        role="断句错误修复专家",
        model=segmenter_model,
        markdown=False,
        instructions=segmenter_instructions,
        use_json_mode=False,
        reasoning=False,
        # debug_mode=True,
    )
    return segmenter
