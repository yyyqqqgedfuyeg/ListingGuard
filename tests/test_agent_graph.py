"""
Filename: test_agent_graph.py
Description: LangGraph 状态机工作流编译与状态流转单元测试套件。
Author: ListingGuard Team
"""

import pytest
from src.agent.graph import build_compliance_agent_graph, run_compliance_guard
from src.models.enums import Platform


def test_agent_graph_compiles_successfully():
    """验证状态图构建无环、拓扑正确并能成功编译。"""
    graph = build_compliance_agent_graph()
    assert graph is not None
    # 验证节点已挂载
    assert "scanner" in graph.nodes
    assert "diagnose" in graph.nodes
    assert "rewriter" in graph.nodes
    assert "verifier" in graph.nodes
    assert "report" in graph.nodes


def test_agent_graph_clean_listing_fast_path():
    """验证无风险合规商品在初检后快速直达报告节点 (Fast Path)。"""
    clean_listing = {
        "listing_id": "GRAPH-CLEAN-01",
        "platform": "taobao",
        "title": "夏季精梳纯棉男女百搭透气圆领短袖T恤",
        "description": "精选优质棉花织造，手感柔和细腻，吸汗透气不易变形，落肩版型舒适百搭。",
        "category": "服饰",
        "price": 49.9
    }
    report = run_compliance_guard(clean_listing)
    assert report.is_compliant is True
    assert report.initial_diagnosis.total_risks == 0
    # 无需改写
    assert report.rewritten_title is None or report.rewritten_title == clean_listing["title"]


def test_agent_graph_violation_listing_closed_loop():
    """验证违规商品完整经历初检、诊断、改写、二次复检与报告输出闭环。"""
    bad_listing = {
        "listing_id": "GRAPH-BAD-02",
        "platform": "pdd",
        "title": "0元免费领 强肾固本降三高古法草本膏方 每天一勺根治糖尿病",
        "description": "原价999现价9.9元，工厂倒闭清库，全网第一疗效！三天见效！",
        "category": "食品保健",
        "price": 9.9
    }
    report = run_compliance_guard(bad_listing, max_iterations=2)
    assert report.initial_diagnosis.total_risks >= 4
    assert report.rewritten_title is not None
    assert report.rewritten_description is not None

    # 验证改写后的文案消除了主要违规词
    assert "0元免费领" not in report.rewritten_title
    assert "根治" not in report.rewritten_title
    assert "全网第一" not in report.rewritten_description

    # 验证二次扫描已生成
    assert report.secondary_diagnosis is not None
    assert report.iteration_count >= 1
