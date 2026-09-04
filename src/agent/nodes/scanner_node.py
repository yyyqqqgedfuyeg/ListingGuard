"""
Filename: scanner_node.py
Description: 商品上架信息合规扫描节点。
Author: ListingGuard Team
"""

from typing import Any, Dict
from src.agent.state import ComplianceAgentState
from src.tools.scan_tool import scan_listing


def scanner_node(state: ComplianceAgentState) -> Dict[str, Any]:
    """对商品 Listing 执行规则与敏感词扫描。

    Args:
        state (ComplianceAgentState): 当前图状态。

    Returns:
        Dict[str, Any]: 状态更新字典。
    """
    listing = state["listing"]
    violations = scan_listing.invoke({"listing": listing})
    is_clean = len(violations) == 0
    return {
        "is_compliant": is_clean,
        "initial_diagnosis": {
            "listing_id": listing.get("listing_id", "UNKNOWN"),
            "total_risks": len(violations),
            "violations": violations,
            "can_auto_rewrite": True
        }
    }
