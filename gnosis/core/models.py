"""
模型工厂，用于创建不同类型的 LLM 模型实例。
"""

from typing import Literal, Optional

from agno.models.base import BaseModel
from agno.models.deepseek import DeepSeek
from agno.models.mistral import MistralChat
from agno.models.openai import OpenAIChat
from agno.models.openai.like import OpenAILike

from gnosis.core.config import settings


def create_model(
    provider: Literal["mistral", "openai", "deepseek", "kimi"] = "mistral",
    model_id: Optional[str] = None,
    api_key: Optional[str] = None,
    base_url: Optional[str] = None,
) -> BaseModel:
    """
    创建并返回指定提供商的模型实例。

    Args:
        provider: 模型提供商，可选值为 "mistral", "openai", "deepseek", "kimi"
        model_id: 模型 ID，如果未提供则使用配置中的默认值
        api_key: API 密钥，如果未提供则使用配置中的默认值
        base_url: API 基础 URL，如果未提供则使用配置中的默认值

    Returns:
        BaseModel: 模型实例
    """
    if provider == "mistral":
        return MistralChat(
            id=model_id or settings.MISTRAL_MODEL,
            api_key=api_key or settings.MISTRAL_API_KEY,
        )
    elif provider == "openai":
        return OpenAIChat(
            id=model_id or settings.OPENAI_MODEL,
            api_key=api_key or settings.OPENAI_API_KEY,
        )
    elif provider == "kimi":
        return OpenAILike(
            id=model_id or settings.KIMI_MODEL,
            api_key=api_key or settings.KIMI_API_KEY,
            base_url=base_url or settings.KIMI_BASE_URL,
        )
    return DeepSeek(
        api_key=api_key or settings.DEEPSEEK_API_KEY,
    )
