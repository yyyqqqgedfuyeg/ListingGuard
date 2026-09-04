"""
Filename: state.py
Description: ListingGuard 闭环自省状态机契约状态定义 (ComplianceAgentState)。
Author: ListingGuard Team
"""

from typing import Annotated, Any, Dict, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


class ComplianceAgentState(TypedDict):
    """ListingGuard 智能体在状态图流转中的上下文状态。"""
    # 原始商品 Listing 数据字典
    listing: Dict[str, Any]
    # 初次扫描与法规 RAG 诊断结果
    initial_diagnosis: Optional[Dict[str, Any]]
    # 当前轮次改写后的标题
    rewritten_title: Optional[str]
    # 当前轮次改写后的商品详情
    rewritten_description: Optional[str]
    # 二次闭环扫描复检结果
    secondary_diagnosis: Optional[Dict[str, Any]]
    # 改写后最终是否合规通过
    is_compliant: bool
    # 当前已迭代自省次数
    iteration: int
    # 允许的最大自省改写轮次
    max_iterations: int
    # 最终汇总的合规审核报告
    report: Optional[Dict[str, Any]]
    # LangGraph 对话/消息历史
    messages: Annotated[List[BaseMessage], add_messages]
