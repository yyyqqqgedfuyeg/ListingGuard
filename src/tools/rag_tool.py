"""
Filename: rag_tool.py
Description: 法规知识库 RAG 检索工具，支持条款级精准定位与法理依据溯源。
Author: ListingGuard Team
"""

from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from src.models.enums import Platform
from src.rag.retriever import RegulationRetriever

_global_retriever: Optional[RegulationRetriever] = None


def get_regulation_retriever() -> RegulationRetriever:
    """获取或延迟初始化全局单例法规检索器。

    Returns:
        RegulationRetriever: 检索器实例。
    """
    global _global_retriever
    if _global_retriever is None:
        _global_retriever = RegulationRetriever()
    return _global_retriever


@tool
def query_regulation(query: str, platform: Optional[str] = None, top_k: int = 3) -> List[Dict[str, Any]]:
    """检索国家广告法、电子商务法及电商平台官方合规规则中的权威条款依据。

    Args:
        query: 检索词或违规行为描述（例如：“广告法极限词最高级规定”、“淘宝好评返现处理细则”、“eBay VeRO侵权”）。
        platform: 限定电商平台，可选 'taobao'、'pdd'、'ebay' 或留空。
        top_k: 最多返回的匹配条款数量，默认 3 条。

    Returns:
        匹配法规条款的详细信息列表，包含法规名称、条款编号、正文片段及相关性得分。
    """
    target_platform = None
    if platform:
        try:
            target_platform = Platform(platform.lower())
        except ValueError:
            target_platform = None

    retriever = get_regulation_retriever()
    results = retriever.search(query=query, platform=target_platform, top_k=top_k)
    return [r.to_citation_dict() for r in results]
