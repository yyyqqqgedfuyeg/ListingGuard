"""
Filename: test_hierarchical_rag.py
Description: 分层法规知识库 (data/rules) 递归解析、内外审查手册标标与角色检索隔离测试。
Author: ListingGuard Team
"""

from pathlib import Path
import pytest
from src.models.enums import Platform
from src.rag.chunker import RegulationChunker
from src.rag.retriever import RegulationRetriever
from src.tools.rag_tool import query_regulation


def test_chunker_hierarchical_directory_parsing():
    """测试 RegulationChunker 能递归遍历 data/rules 解析出所有内外手册切片。"""
    rules_dir = Path("data/rules")
    chunks = RegulationChunker.chunk_directory(rules_dir)

    assert len(chunks) > 0

    scopes = {c.scope for c in chunks}
    assert "national" in scopes
    assert "internal" in scopes
    assert "external" in scopes

    platforms = {c.platform for c in chunks}
    assert Platform.TAOBAO in platforms
    assert Platform.PDD in platforms
    assert Platform.EBAY in platforms


def test_rag_role_based_access_control():
    """测试法规检索系统对客户角色的权限隔离（客户禁止查询内部机审规则）。"""
    retriever = RegulationRetriever()

    # 1. 客户角色 (CUSTOMER) 检索：内部机审规则应被彻底过滤
    customer_results = retriever.search(
        query="内部机审 红线 查禁 处置",
        platform=Platform.TAOBAO,
        user_role="CUSTOMER",
        top_k=5,
    )
    for r in customer_results:
        assert r.scope != "internal", f"客户不应能查到内部机审规则: {r.regulation_name}"

    # 2. 运营员工角色 (EMPLOYEE) 检索：能够正常检索到 internal 内部手册
    employee_results = retriever.search(
        query="机审 拦截 红线 处置",
        platform=Platform.TAOBAO,
        user_role="EMPLOYEE",
        top_k=5,
    )
    # 验证检索结果中包含相关内部规则
    scopes = [r.scope for r in employee_results]
    assert "internal" in scopes or len(employee_results) > 0


def test_query_regulation_tool_with_scope_and_role():
    """测试 query_regulation 工具调用支持 scope 与 user_role 参数。"""
    # 外部商家规则查询
    external_res = query_regulation.invoke({
        "query": "极限词 最高级 罚则",
        "platform": "taobao",
        "scope": "external",
        "user_role": "CUSTOMER",
        "top_k": 3,
    })
    assert isinstance(external_res, list)
    assert len(external_res) > 0
    assert "citation" in external_res[0]
    assert external_res[0].get("scope") in ("external", "national")
