"""
Filename: message_queue.py
Description: Queued Messages 消息队列管理器，支持并发/异步场景下用户 Query 的 FIFO 排队与顺序消费。
Author: Risk-Aware Agent Team
"""

import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Dict, List, Optional
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field


class QueuedMessage(BaseModel):
    """排队消息数据模型。

    Attributes:
        message_id (str): 消息唯一标识 ID。
        content (str): 用户输入的自然语言 Query。
        thread_id (str): 归属的会话 Thread ID。
        created_at (float): 入队时间戳 (Unix Timestamp)。
    """

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str = Field(..., description="用户输入的 Query 内容")
    thread_id: str = Field(..., description="所属会话标识 ID")
    created_at: float = Field(default_factory=time.time, description="入队时间戳")


class MessageQueueManager:
    """线程安全的用户消息排队管理器。

    用于在 LLM 正在响应当前轮次时，接收并暂存用户后续输入的 Query，
    待当前轮次完成后，按严格的 FIFO（先进先出）顺序依次派发至 Agent。
    """

    def __init__(self):
        """初始化全局消息队列字典与线程互斥锁。"""
        self._queues: Dict[str, deque[QueuedMessage]] = {}
        self._busy_flags: Dict[str, bool] = {}
        self._lock = threading.Lock()

    def enqueue(self, thread_id: str, content: str) -> QueuedMessage:
        """将用户 Query 加入指定 thread_id 的等待队列末尾。

        Args:
            thread_id (str): 目标会话 ID。
            content (str): 用户输入的文本。

        Returns:
            QueuedMessage: 封装后的排队消息对象。
        """
        msg = QueuedMessage(content=content, thread_id=thread_id)
        with self._lock:
            if thread_id not in self._queues:
                self._queues[thread_id] = deque()
            self._queues[thread_id].append(msg)
        return msg

    def dequeue(self, thread_id: str) -> Optional[QueuedMessage]:
        """从指定 thread_id 的队列头部弹出下一条待处理消息（FIFO）。

        Args:
            thread_id (str): 目标会话 ID。

        Returns:
            Optional[QueuedMessage]: 下一条消息对象；若队列为空则返回 None。
        """
        with self._lock:
            queue = self._queues.get(thread_id)
            if queue and len(queue) > 0:
                return queue.popleft()
            return None

    def peek(self, thread_id: str) -> Optional[QueuedMessage]:
        """查看指定 thread_id 队列头部的下一条消息，但不弹出。

        Args:
            thread_id (str): 目标会话 ID。

        Returns:
            Optional[QueuedMessage]: 队列头部消息；若为空则返回 None。
        """
        with self._lock:
            queue = self._queues.get(thread_id)
            if queue and len(queue) > 0:
                return queue[0]
            return None

    def get_queue(self, thread_id: str) -> List[QueuedMessage]:
        """获取指定 thread_id 当前全部排队中的消息快照列表。

        Args:
            thread_id (str): 目标会话 ID。

        Returns:
            List[QueuedMessage]: 队列消息列表。
        """
        with self._lock:
            queue = self._queues.get(thread_id)
            return list(queue) if queue else []

    def get_queue_length(self, thread_id: str) -> int:
        """获取指定 thread_id 当前排队消息数量。

        Args:
            thread_id (str): 目标会话 ID。

        Returns:
            int: 队列中的消息数量。
        """
        with self._lock:
            queue = self._queues.get(thread_id)
            return len(queue) if queue else 0

    def clear(self, thread_id: str) -> None:
        """清空指定 thread_id 的所有排队消息。

        Args:
            thread_id (str): 目标会话 ID。
        """
        with self._lock:
            if thread_id in self._queues:
                self._queues[thread_id].clear()

    def is_busy(self, thread_id: str) -> bool:
        """检查指定 thread_id 当前是否正在执行推理。

        Args:
            thread_id (str): 目标会话 ID。

        Returns:
            bool: 是否处于忙碌状态。
        """
        with self._lock:
            return self._busy_flags.get(thread_id, False)

    def set_busy(self, thread_id: str, busy: bool) -> None:
        """设置指定 thread_id 的忙碌状态。

        Args:
            thread_id (str): 目标会话 ID。
            busy (bool): 忙碌标志。
        """
        with self._lock:
            self._busy_flags[thread_id] = busy

    def process_all_queued(
        self,
        agent: Any,
        thread_id: str,
        on_turn_start: Optional[Callable[[int, QueuedMessage], None]] = None,
        on_turn_complete: Optional[Callable[[int, QueuedMessage, Dict[str, Any]], None]] = None,
    ) -> List[Dict[str, Any]]:
        """顺序消费并执行指定 thread_id 队列中的全部消息，确保无并发混乱。

        Args:
            agent (Any): 已编译的 LangGraph Agent 实例。
            thread_id (str): 目标会话 ID。
            on_turn_start (Optional[Callable], optional): 每轮开始执行时的回调函数。
            on_turn_complete (Optional[Callable], optional): 每轮执行完成时的回调函数。

        Returns:
            List[Dict[str, Any]]: 各轮推理结果的列表。
        """
        results: List[Dict[str, Any]] = []
        turn_index = 0
        config = {"configurable": {"thread_id": thread_id}}

        self.set_busy(thread_id, True)
        try:
            while True:
                msg = self.dequeue(thread_id)
                if msg is None:
                    break

                turn_index += 1
                if on_turn_start:
                    on_turn_start(turn_index, msg)

                result = agent.invoke(
                    {"messages": [HumanMessage(content=msg.content)]},
                    config=config,
                )
                results.append(result)

                if on_turn_complete:
                    on_turn_complete(turn_index, msg, result)
        finally:
            self.set_busy(thread_id, False)

        return results

