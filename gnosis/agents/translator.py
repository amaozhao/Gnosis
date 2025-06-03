# agents/translator.py
from agno.agent import Agent
from agno.models.deepseek import DeepSeek

from gnosis.agents.prompts.instructions import translator_instructions
from gnosis.core.config import settings

# 直接创建 DeepSeek 模型实例
translator_model = DeepSeek(
    api_key=settings.DEEPSEEK_API_KEY,
)


def get_translator():
    translator = Agent(
        name="Translator",
        role="翻译专家",
        model=translator_model,
        markdown=False,
        instructions=translator_instructions,
        use_json_mode=False,
        reasoning=False,
        # debug_mode=True,
    )
    return translator
