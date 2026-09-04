"""
Filename: graph.py
Description: 基于 LangGraph 的电商商品上架合规自省闭环状态机构建与执行引擎。
Author: ListingGuard Team
"""

from typing import Any, Dict, Optional
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from src.agent.nodes import (
    diagnose_node,
    report_node,
    rewriter_node,
    scanner_node,
    verifier_node,
)
from src.agent.state import ComplianceAgentState
from src.models.report import ComplianceReport


def _should_continue_after_scan(state: ComplianceAgentState) -> str:
    """初检后的分支判断路由。

    如果初检 0 违规，直接跳至报告输出；否则进入法理诊断与改写阶段。
    """
    diag = state.get("initial_diagnosis") or {}
    if diag.get("total_risks", 0) == 0:
        return "report"
    return "diagnose"


def _should_continue_after_verify(state: ComplianceAgentState) -> str:
    """复检后的自省回路分支判断路由。

    如果二次验证通过或已达到最大迭代轮次，则结束迭代输出终审报告；
    否则循环回退至 rewriter 节点继续自省改写。
    """
    is_compliant = state.get("is_compliant", False)
    iteration = state.get("iteration", 0)
    max_iter = state.get("max_iterations", 3)

    if is_compliant or iteration >= max_iter:
        return "report"
    return "rewriter"


def build_compliance_agent_graph() -> CompiledStateGraph:
    """构建并编译 ListingGuard 闭环自省状态图。

    工作流阶段：
    [START] -> [scanner] -(有风险)-> [diagnose] -> [rewriter] -> [verifier]
                     |                                               |
                  (0风险)                                     (已合规/超上限)
                     |                                               |
                     v                                               v
                 [report] <------------------------------------------+
                     |
                   [END]

    Returns:
        CompiledStateGraph: 编译后的 LangGraph 状态图实例。
    """
    workflow = StateGraph(ComplianceAgentState)

    # 1. 注册核心功能节点
    workflow.add_node("scanner", scanner_node)
    workflow.add_node("diagnose", diagnose_node)
    workflow.add_node("rewriter", rewriter_node)
    workflow.add_node("verifier", verifier_node)
    workflow.add_node("report", report_node)

    # 2. 编排工作流拓扑
    workflow.add_edge(START, "scanner")

    workflow.add_conditional_edges(
        "scanner",
        _should_continue_after_scan,
        {
            "report": "report",
            "diagnose": "diagnose"
        }
    )

    workflow.add_edge("diagnose", "rewriter")
    workflow.add_edge("rewriter", "verifier")

    workflow.add_conditional_edges(
        "verifier",
        _should_continue_after_verify,
        {
            "report": "report",
            "rewriter": "rewriter"
        }
    )

    workflow.add_edge("report", END)

    return workflow.compile()


def run_compliance_guard(
    listing: Dict[str, Any],
    max_iterations: int = 3
) -> ComplianceReport:
    """统一高阶 API：执行单件商品 Listing 的全流程合规扫描、诊断、自省改写与报告生成。

    Args:
        listing (Dict[str, Any]): 商品数据字典。
        max_iterations (int, optional): 最大改写自省迭代轮次。默认为 3。

    Returns:
        ComplianceReport: 结构化合规终审报告对象。
    """
    app = build_compliance_agent_graph()
    initial_state: ComplianceAgentState = {
        "listing": listing,
        "initial_diagnosis": None,
        "rewritten_title": None,
        "rewritten_description": None,
        "secondary_diagnosis": None,
        "is_compliant": False,
        "iteration": 0,
        "max_iterations": max_iterations,
        "report": None,
        "messages": []
    }

    final_state = app.invoke(initial_state)
    report_dict = final_state.get("report") or {}
    return ComplianceReport(**report_dict)
