"""
Filename: diagnose_node.py
Description: 合规深度诊断与法规 RAG 条款溯源节点。
Author: ListingGuard Team
"""

from typing import Any, Dict
from src.agent.state import ComplianceAgentState
from src.tools.diagnose_tool import diagnose_violation


def diagnose_node(state: ComplianceAgentState) -> Dict[str, Any]:
    """执行深度合规诊断并关联 RAG 法律条文。

    Args:
        state (ComplianceAgentState): 当前图状态。

    Returns:
        Dict[str, Any]: 状态更新字典。
    """
    listing = state["listing"]
    full_diagnosis = diagnose_violation.invoke({"listing": listing})
    return {
        "initial_diagnosis": full_diagnosis
    }
