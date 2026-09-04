"""
Filename: test_rag.py
Description: RAG 条款级法规知识检索与混合索引单元测试套件。
Author: ListingGuard Team
"""

from pathlib import Path
import pytest

from src.models.enums import Platform
from src.rag.chunker import RegulationChunker
from src.rag.indexer import RegulationIndexer
from src.rag.retriever import RegulationRetriever
from src.tools.rag_tool import query_regulation


@pytest.fixture(scope="module")
def rag_indexer():
    """模块级 RAG 索引器 fixture。"""
    indexer = RegulationIndexer()
    return indexer


@pytest.fixture(scope="module")
def rag_retriever(rag_indexer):
    """模块级 RAG 检索器 fixture。"""
    return RegulationRetriever(indexer=rag_indexer)


def test_chunker_parses_all_regulations():
    """验证切分器能正确提取法规文档中的章节与具体条款。"""
    reg_dir = Path(__file__).resolve().parent.parent / "data" / "regulations"
    chunks = RegulationChunker.chunk_directory(reg_dir)
    assert len(chunks) >= 10

    # 验证切片包含广告法核心条款
    articles = [c.article for c in chunks]
    assert any("第九条" in a for a in articles)
    assert any("第十七条" in a for a in articles)
    assert any("条款 1.1" in a for a in articles)


def test_retriever_advertising_law_extreme_words(rag_retriever):
    """验证检索极限词条款能够高分命中广告法第九条。"""
    results = rag_retriever.search("商品宣传使用国家级、最佳、全网第一极限词", top_k=3)
    assert len(results) > 0
    top_chunk = results[0].chunk
    assert "广告法" in top_chunk.doc_name
    assert "第九条" in top_chunk.article or "绝对化" in top_chunk.article


def test_retriever_taobao_feedback_manipulation(rag_retriever):
    """验证限定淘宝平台检索好评返现，准确命中淘宝评价管理细则。"""
    results = rag_retriever.search(
        query="带图好评返现 加微信返红包 扣分处罚",
        platform=Platform.TAOBAO,
        top_k=3
    )
    assert len(results) > 0
    citations = [r.chunk.article for r in results]
    assert any("评价管理" in a or "虚假评价" in a for a in citations)


def test_retriever_ebay_vero_ip(rag_retriever):
    """验证限定 eBay 平台检索品牌词碰瓷，准确命中 VeRO 规则。"""
    results = rag_retriever.search(
        query="like Apple Rolex replica counterfeit trademark misuse",
        platform=Platform.EBAY,
        top_k=3
    )
    assert len(results) > 0
    assert any("VeRO" in r.chunk.doc_name or "VeRO" in r.chunk.chapter or "Trademark" in r.chunk.article for r in results)


def test_query_regulation_tool():
    """验证 LangChain Tool 接口 query_regulation 的正常调用与字典输出。"""
    tool_output = query_regulation.invoke({
        "query": "非药品普通食品宣传抗癌治病消炎",
        "platform": "taobao",
        "top_k": 2
    })
    assert isinstance(tool_output, list)
    assert len(tool_output) > 0
    item = tool_output[0]
    assert "regulation" in item
    assert "snippet" in item
    assert "score" in item
