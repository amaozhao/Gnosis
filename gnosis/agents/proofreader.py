# agents/proofreader.py
from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from gnosis.agents.prompts.instructions import proofreader_instructions
from gnosis.core.config import settings

# 直接创建 DeepSeek 模型实例
proofreader_model = DeepSeek(
    api_key=settings.DEEPSEEK_API_KEY,
)


def get_proofreader():
    proofreader = Agent(
        name="proofreader",
        role="错词检查专家",
        model=proofreader_model,
        markdown=False,
        instructions=proofreader_instructions,
        use_json_mode=False,
        reasoning=False,
        # debug_mode=True,
    )
    return proofreader
