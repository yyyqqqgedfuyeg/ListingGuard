"""
Filename: diagnose_tool.py
Description: 商品 Listing 合规诊断分析工具，集成法规 RAG 进行法律归因与责任溯源。
Author: ListingGuard Team
"""

from typing import Any, Dict, Union
from langchain_core.tools import tool

from src.models.listing import ProductListing
from src.rules.engine import RuleEngine
from src.tools.rag_tool import get_regulation_retriever
from src.tools.scan_tool import _ensure_listing_model

_global_engine: RuleEngine = RuleEngine()


@tool
def diagnose_violation(listing: Dict[str, Any]) -> Dict[str, Any]:
    """对商品 Listing 进行深入合规诊断，结合广告法与电商法规库输出权威溯源结果。

    Args:
        listing: 商品数据字典，包含 title、description、platform 等字段。

    Returns:
        综合诊断结果字典，包含 total_risks、max_severity、violations、legal_citations 与 summary。
    """
    model: ProductListing = _ensure_listing_model(listing)
    diagnosis = _global_engine.diagnose_listing(model)

    # 如果有违规项，利用 RAG 检索补充法条正文引用
    if diagnosis.violations:
        retriever = get_regulation_retriever()
        for v in diagnosis.violations:
            query = f"{v.category.value} {v.trigger_pattern} {v.explanation}"
            rag_results = retriever.search(query=query, platform=model.platform, top_k=1)
            if rag_results:
                top_hit = rag_results[0].to_citation_dict()
                # 若尚未补充法条正文详情，予以丰富
                if not v.cited_regulation or "《" not in v.cited_regulation:
                    v.cited_regulation = top_hit["regulation"]

    return diagnosis.model_dump()
