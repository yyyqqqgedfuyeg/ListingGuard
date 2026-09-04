"""
Filename: response.py
Description: Agent 结构化响应数据模型、流式响应收集器与工具调用简洁渲染格式化工具。
Author: Risk-Aware Agent Team
"""

from datetime import datetime, timezone
import json
import time
from typing import Any, Dict, List, Optional
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    """Token 消耗度量数据模型。

    Attributes:
        prompt_tokens (int): 输入 Prompt 消耗的 Token 数。
        completion_tokens (int): 模型生成回复消耗的 Token 数。
        total_tokens (int): 本次交互消耗的总 Token 数。
    """

    prompt_tokens: int = Field(default=0, description="输入 Prompt 所消耗的 Token 数")
    completion_tokens: int = Field(default=0, description="模型回复生成的 Token 数")
    total_tokens: int = Field(default=0, description="本次交互总 Token 数")


class AgentResponse(BaseModel):
    """Agent 单次结构化回复数据模型。

    Attributes:
        content (str): 模型生成的文本回复内容。
        start_timestamp (float): 开始推理的 Unix 时间戳 (秒)。
        end_timestamp (float): 结束推理的 Unix 时间戳 (秒)。
        start_time (str): 开始推理的 ISO 8601 可读时间格式。
        end_time (str): 结束推理的 ISO 8601 可读时间格式。
        duration_seconds (float): 模型推理耗时（秒，保留 4 位小数）。
        token_usage (TokenUsage): Token 消耗统计对象。
        retry_count (int): 推理过程中的重试尝试次数（0 表示一次成功）。
        model_name (Optional[str]): 调用的模型标识名称。
        message_id (Optional[str]): 响应消息唯一标识 ID。
        raw_metadata (Dict[str, Any]): 底层模型返回的原始元数据。
    """

    content: str = Field(..., description="模型生成的文本回复内容")
    start_timestamp: float = Field(..., description="开始推理时间戳 (Unix Timestamp)")
    end_timestamp: float = Field(..., description="结束推理时间戳 (Unix Timestamp)")
    start_time: str = Field(..., description="开始时间可读字符串 (ISO 8601)")
    end_time: str = Field(..., description="结束时间可读字符串 (ISO 8601)")
    duration_seconds: float = Field(..., description="推理总耗时 (秒)")
    token_usage: TokenUsage = Field(default_factory=TokenUsage, description="Token 消耗度量")
    retry_count: int = Field(default=0, description="推理重试次数")
    model_name: Optional[str] = Field(default=None, description="调用的模型标识")
    message_id: Optional[str] = Field(default=None, description="响应消息 ID")
    raw_metadata: Dict[str, Any] = Field(default_factory=dict, description="底层模型返回的原始元数据")

    @classmethod
    def from_ai_message(
        cls,
        ai_message: AIMessage,
        start_timestamp: float,
        end_timestamp: Optional[float] = None,
        model_name: Optional[str] = None,
        retry_count: int = 0,
    ) -> "AgentResponse":
        """从 LangChain AIMessage 与时间戳构建结构化 AgentResponse 对象。

        Args:
            ai_message (AIMessage): 模型返回的 AIMessage 实例。
            start_timestamp (float): 推理开始的 Unix 时间戳。
            end_timestamp (Optional[float], optional): 推理结束的 Unix 时间戳。若为 None 则取当前时间戳。
            model_name (Optional[str], optional): 模型名称标识。默认为 None。
            retry_count (int, optional): 发生的重试次数。默认为 0。

        Returns:
            AgentResponse: 封装后的结构化响应对象。
        """
        end_ts = end_timestamp if end_timestamp is not None else time.time()
        duration = max(0.0, round(end_ts - start_timestamp, 4))

        start_dt = datetime.fromtimestamp(start_timestamp, tz=timezone.utc).isoformat()
        end_dt = datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat()

        # 提取 Token 使用量（优先 usage_metadata，其次 response_metadata）
        prompt_tokens = 0
        completion_tokens = 0
        total_tokens = 0

        usage_meta = getattr(ai_message, "usage_metadata", None)
        if usage_meta and isinstance(usage_meta, dict):
            prompt_tokens = usage_meta.get("input_tokens", 0)
            completion_tokens = usage_meta.get("output_tokens", 0)
            total_tokens = usage_meta.get("total_tokens", prompt_tokens + completion_tokens)
        else:
            resp_meta = getattr(ai_message, "response_metadata", {})
            token_dict = resp_meta.get("token_usage") or resp_meta.get("usage") or {}
            if isinstance(token_dict, dict):
                prompt_tokens = token_dict.get("prompt_tokens", 0)
                completion_tokens = token_dict.get("completion_tokens", 0)
                total_tokens = token_dict.get("total_tokens", prompt_tokens + completion_tokens)

        # 提取模型名称与消息 ID
        resp_meta = getattr(ai_message, "response_metadata", {})
        actual_model = model_name or resp_meta.get("model_name") or resp_meta.get("model")
        msg_id = getattr(ai_message, "id", None) or resp_meta.get("id")

        return cls(
            content=str(ai_message.content),
            start_timestamp=start_timestamp,
            end_timestamp=end_ts,
            start_time=start_dt,
            end_time=end_dt,
            duration_seconds=duration,
            token_usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            retry_count=retry_count,
            model_name=actual_model,
            message_id=msg_id,
            raw_metadata=resp_meta if isinstance(resp_meta, dict) else {},
        )


class ResponseStreamHandler:
    """流式推理响应收集器，用于在实时输出 Token 的同时完整捕获时间戳与度量指标。

    Attributes:
        start_timestamp (float): 流开始的 Unix 时间戳。
        accumulated_chunks (List[str]): 累积收到的文本块。
        retry_count (int): 当前流发生的重试次数。
        model_name (Optional[str]): 模型标识。
    """

    def __init__(self, model_name: Optional[str] = None, retry_count: int = 0):
        """初始化流收集器并记录开始时间戳。"""
        self.start_timestamp = time.time()
        self.accumulated_chunks: List[str] = []
        self.retry_count = retry_count
        self.model_name = model_name

    def append_chunk(self, chunk_text: str) -> str:
        """接收一个文本 Token 块并追加到缓存中。

        Args:
            chunk_text (str): 新生成的 Token 文本。

        Returns:
            str: 传入的文本块。
        """
        self.accumulated_chunks.append(chunk_text)
        return chunk_text

    @property
    def full_content(self) -> str:
        """获取目前已累积的完整字符串。"""
        return "".join(self.accumulated_chunks)

    def finalize(
        self,
        final_message: Optional[AIMessage] = None,
        end_timestamp: Optional[float] = None,
    ) -> AgentResponse:
        """结束流并打包生成最终的 AgentResponse 结构体。

        Args:
            final_message (Optional[AIMessage], optional): 完整的 AIMessage。
            end_timestamp (Optional[float], optional): 结束时间戳。默认为当前时间。

        Returns:
            AgentResponse: 最终生成的结构化响应数据。
        """
        end_ts = end_timestamp if end_timestamp is not None else time.time()
        if final_message is not None:
            return AgentResponse.from_ai_message(
                ai_message=final_message,
                start_timestamp=self.start_timestamp,
                end_timestamp=end_ts,
                model_name=self.model_name,
                retry_count=self.retry_count,
            )

        duration = max(0.0, round(end_ts - self.start_timestamp, 4))
        content = self.full_content
        return AgentResponse(
            content=content,
            start_timestamp=self.start_timestamp,
            end_timestamp=end_ts,
            start_time=datetime.fromtimestamp(self.start_timestamp, tz=timezone.utc).isoformat(),
            end_time=datetime.fromtimestamp(end_ts, tz=timezone.utc).isoformat(),
            duration_seconds=duration,
            token_usage=TokenUsage(
                prompt_tokens=0,
                completion_tokens=len(self.accumulated_chunks),
                total_tokens=len(self.accumulated_chunks),
            ),
            retry_count=self.retry_count,
            model_name=self.model_name,
        )


def format_tool_call_concise(tool_name: str, tool_args: Dict[str, Any], max_val_len: int = 60) -> str:
    """将工具调用入参转换为简洁单行描述，避免长文本霸屏。

    Args:
        tool_name (str): 工具名称（如 'read_file'）。
        tool_args (Dict[str, Any]): 工具入参字典。
        max_val_len (int, optional): 单参数最长展示字符数。默认为 60。

    Returns:
        str: 简洁的调用表达式（如 `read_file(file_path='tests/calc.py')`）。
    """
    arg_parts = []
    for k, v in tool_args.items():
        v_str = str(v).replace("\n", "\\n")
        if len(v_str) > max_val_len:
            v_str = f"{v_str[:max_val_len]}... (共{len(v_str)}字符)"
        arg_parts.append(f"{k}='{v_str}'" if isinstance(v, str) else f"{k}={v_str}")
    args_repr = ", ".join(arg_parts)
    return f"{tool_name}({args_repr})"


def format_tool_result_concise(tool_name: str, raw_output: str, max_lines: int = 3, max_chars: int = 180) -> str:
    """将工具返回的原始内容提炼为简洁摘要，突出核心结论与状态。

    Args:
        tool_name (str): 工具名称。
        raw_output (str): 工具返回的原始完整文本。
        max_lines (int, optional): 最多展示行数。默认为 3。
        max_chars (int, optional): 最多展示字符数。默认为 180。

    Returns:
        str: 提炼后的简明摘要。
    """
    if not raw_output:
        return "(无输出)"

    lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]
    if not lines:
        return "(空内容)"

    # 优先提取前置状态指示符（✅, ❌, 📄, 💻, 📁）
    primary_line = lines[0]
    total_chars = len(raw_output)

    if len(lines) == 1 and len(primary_line) <= max_chars:
        return primary_line

    preview_lines = lines[:max_lines]
    preview_text = " | ".join(preview_lines)
    if len(preview_text) > max_chars:
        preview_text = preview_text[:max_chars] + "..."

    return f"{preview_text} [dim](全量共 {len(lines)} 行 / {total_chars} 字符)[/dim]"
