"""
Filename: scan_tool.py
Description: 商品 Listing 合规扫描工具，检测极限词、医疗宣称、价格欺诈及知识产权侵权。
Author: ListingGuard Team
"""

from typing import Any, Dict, List, Union
from langchain_core.tools import tool

from src.models.enums import Platform
from src.models.listing import ProductListing
from src.rules.engine import RuleEngine

_global_engine: RuleEngine = RuleEngine()


def _ensure_listing_model(data: Union[Dict[str, Any], ProductListing]) -> ProductListing:
    """确保入参转为 ProductListing 对象。

    Args:
        data (Union[Dict[str, Any], ProductListing]): 商品入参字典或模型。

    Returns:
        ProductListing: 规范化商品对象。
    """
    if isinstance(data, ProductListing):
        return data
    platform_str = data.get("platform", "general").lower()
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.GENERAL

    return ProductListing(
        listing_id=str(data.get("listing_id", "TEMP-001")),
        platform=platform,
        title=data.get("title", ""),
        description=data.get("description", ""),
        category=data.get("category", "general"),
        price=data.get("price"),
        original_price=data.get("original_price"),
        attributes=data.get("attributes", {}),
        images_text=data.get("images_text", []),
    )


@tool
def scan_listing(listing: Dict[str, Any]) -> List[Dict[str, Any]]:
    """扫描电商商品 Listing (标题、详情、属性、图片文字) 中存在的违规词与合规风险。

    Args:
        listing: 商品数据字典，需包含 title、description、platform (taobao/pdd/ebay/general) 等字段。

    Returns:
        违规证据项列表，每个证据包含 category、severity、trigger_pattern、location、context_snippet 与 explanation。
    """
    model = _ensure_listing_model(listing)
    violations = _global_engine.scan_listing(model)
    return [v.model_dump() for v in violations]
