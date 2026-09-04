"""
Filename: verify_tool.py
Description: 二次闭环合规扫描验证工具，对改写后的商品文案再次执行合规检测。
Author: ListingGuard Team
"""

from typing import Any, Dict
from langchain_core.tools import tool

from src.models.listing import ProductListing
from src.rules.engine import RuleEngine
from src.tools.scan_tool import _ensure_listing_model

_global_engine: RuleEngine = RuleEngine()


@tool
def verify_rewrite(
    original_listing: Dict[str, Any],
    rewritten_title: str,
    rewritten_description: str
) -> Dict[str, Any]:
    """对改写后的商品标题和详情执行二次闭环扫描，确保 0 违规残留并杜绝新引入隐性风险。

    Args:
        original_listing: 原始商品数据字典。
        rewritten_title: 改写后的商品标题。
        rewritten_description: 改写后的商品详情文案。

    Returns:
        闭环验证结果字典，包含 is_compliant (bool)、remaining_risks (int) 及 secondary_diagnosis。
    """
    orig_model = _ensure_listing_model(original_listing)

    # 构造改写后的验证模型
    test_model = ProductListing(
        listing_id=f"{orig_model.listing_id}-VERIFY",
        platform=orig_model.platform,
        title=rewritten_title,
        description=rewritten_description,
        category=orig_model.category,
        price=orig_model.price,
        original_price=orig_model.original_price,
        attributes=orig_model.attributes,
        images_text=orig_model.images_text
    )

    diagnosis = _global_engine.diagnose_listing(test_model)
    is_compliant = diagnosis.total_risks == 0

    return {
        "is_compliant": is_compliant,
        "remaining_risks": diagnosis.total_risks,
        "secondary_diagnosis": diagnosis.model_dump(),
        "summary": "✨ 二次验证通过，文本完全合规！" if is_compliant else f"⚠️ 仍存在 {diagnosis.total_risks} 处残留合规风险。"
    }
