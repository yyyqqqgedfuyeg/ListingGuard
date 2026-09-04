"""
Filename: rewriter_node.py
Description: 智能合规文案改写节点，驱动自省迭代与文案优化。
Author: ListingGuard Team
"""

from typing import Any, Dict
from src.agent.state import ComplianceAgentState
from src.tools.rewrite_tool import rewrite_compliant


def rewriter_node(state: ComplianceAgentState) -> Dict[str, Any]:
    """对存在违规的 Listing 生成合规优化版本。

    Args:
        state (ComplianceAgentState): 当前图状态。

    Returns:
        Dict[str, Any]: 状态更新字典。
    """
    listing = state["listing"]
    diag = state.get("initial_diagnosis") or {}
    violations = diag.get("violations", [])
    current_iter = state.get("iteration", 0) + 1

    # 如果初检原本就是 0 风险，直接保留原标题和详情
    if not violations:
        return {
            "rewritten_title": listing.get("title", ""),
            "rewritten_description": listing.get("description", ""),
            "iteration": current_iter,
            "is_compliant": True
        }

    # 执行智能改写
    rewrite_res = rewrite_compliant.invoke({
        "listing": listing,
        "violations": violations
    })

    return {
        "rewritten_title": rewrite_res.get("rewritten_title", listing.get("title", "")),
        "rewritten_description": rewrite_res.get("rewritten_description", listing.get("description", "")),
        "iteration": current_iter
    }
