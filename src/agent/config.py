"""
Filename: config.py
Description: LLM 配置管理与客户端工厂函数，支持从 .env 动态加载模型参数与重试策略。
Author: Risk-Aware Agent Team
"""

import os
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field


class AgentSettings(BaseModel):
    """LLM 与 Agent 基础运行配置模型。

    Attributes:
        api_key (str): OpenAI / DeepSeek 接口密钥。
        base_url (str): API 端点基础 URL。
        model_name (str): 调用的模型名称标识。
        temperature (float): 采样温度，默认为 0.1。
        max_tokens (Optional[int]): 单次回复最大 Token 数。
        max_retries (int): LLM 请求失败时的最大重试次数。
        streaming (bool): 是否启用流式输出。
    """

    api_key: str = Field(..., description="API Key for LLM service")
    base_url: str = Field(..., description="Base URL for LLM service")
    model_name: str = Field(default="deepseek-chat", description="Model name")
    temperature: float = Field(default=0.1, description="Sampling temperature")
    max_tokens: Optional[int] = Field(default=None, description="Max tokens limit")
    max_retries: int = Field(default=3, description="LLM 请求失败重试次数")
    streaming: bool = Field(default=False, description="Enable streaming mode")


def load_agent_settings(env_file: Optional[str] = None) -> AgentSettings:
    """从 .env 文件或系统环境变量加载 Agent 配置。

    Args:
        env_file (Optional[str], optional): 指定 .env 文件路径。默认为 None，将自动寻找项目根目录的 .env。

    Returns:
        AgentSettings: 校验并填充后的配置对象。

    Raises:
        ValueError: 当未提供有效的 API Key 时抛出。
    """
    if env_file:
        load_dotenv(dotenv_path=env_file, override=True)
    else:
        # 向上寻找 .env 文件
        root_dir = Path(__file__).resolve().parent.parent.parent
        env_path = root_dir / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
        else:
            load_dotenv(override=True)

    api_key = (
        os.getenv("OPENAI_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or ""
    )
    base_url = (
        os.getenv("OPENAI_BASE_URL")
        or os.getenv("DEEPSEEK_BASE_URL")
        or "https://api.deepseek.com/v1"
    )
    model_name = (
        os.getenv("MODEL_NAME")
        or os.getenv("DEEPSEEK_MODEL")
        or "deepseek-chat"
    )
    temperature = float(os.getenv("LLM_TEMPERATURE", "0.1"))
    max_tokens_raw = os.getenv("LLM_MAX_TOKENS")
    max_tokens = int(max_tokens_raw) if max_tokens_raw and max_tokens_raw.isdigit() else None

    max_retries_raw = os.getenv("LLM_MAX_RETRIES") or os.getenv("MAX_RETRIES")
    max_retries = int(max_retries_raw) if max_retries_raw and max_retries_raw.isdigit() else 3

    if not api_key or api_key == "your_deepseek_api_key_here":
        raise ValueError(
            "未检测到有效的 OPENAI_API_KEY 或 DEEPSEEK_API_KEY，请检查 .env 配置文件。"
        )

    return AgentSettings(
        api_key=api_key,
        base_url=base_url,
        model_name=model_name,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
        streaming=False,
    )


def get_llm(
    settings: Optional[AgentSettings] = None,
    streaming: bool = False,
    temperature: Optional[float] = None,
    max_retries: Optional[int] = None,
) -> ChatOpenAI:
    """构建并返回 LangChain ChatOpenAI 客户端实例。

    Args:
        settings (Optional[AgentSettings], optional): 配置对象。若为 None 则自动从环境加载。
        streaming (bool, optional): 是否开启流式传输。默认为 False。
        temperature (Optional[float], optional): 覆盖默认温度。默认为 None。
        max_retries (Optional[int], optional): 覆盖默认最大重试次数。默认为 None。

    Returns:
        ChatOpenAI: 已配置完成的 ChatOpenAI 模型客户端。
    """
    if settings is None:
        settings = load_agent_settings()

    temp = temperature if temperature is not None else settings.temperature
    retries = max_retries if max_retries is not None else settings.max_retries

    return ChatOpenAI(
        api_key=settings.api_key,
        base_url=settings.base_url,
        model=settings.model_name,
        temperature=temp,
        max_tokens=settings.max_tokens,
        max_retries=retries,
        streaming=streaming,
    )
