"""
Filename: verifier_node.py
Description: 二次闭环合规扫描验证节点，评估自省改写效果。
Author: ListingGuard Team
"""

from typing import Any, Dict
from src.agent.state import ComplianceAgentState
from src.tools.verify_tool import verify_rewrite


def verifier_node(state: ComplianceAgentState) -> Dict[str, Any]:
    """对改写后的标题和详情进行复检，判定是否完全清零违规。

    Args:
        state (ComplianceAgentState): 当前图状态。

    Returns:
        Dict[str, Any]: 状态更新字典。
    """
    listing = state["listing"]
    rewritten_title = state.get("rewritten_title") or listing.get("title", "")
    rewritten_desc = state.get("rewritten_description") or listing.get("description", "")

    # 执行二次闭环校验
    res = verify_rewrite.invoke({
        "original_listing": listing,
        "rewritten_title": rewritten_title,
        "rewritten_description": rewritten_desc
    })

    return {
        "is_compliant": res.get("is_compliant", False),
        "secondary_diagnosis": res.get("secondary_diagnosis")
    }
