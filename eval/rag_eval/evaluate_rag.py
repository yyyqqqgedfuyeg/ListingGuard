"""
Filename: evaluate_rag.py
Description: RAG 条款级法规知识检索模块基准评测器 (Hit@K, MRR 及消融实验)。
Author: ListingGuard Team
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.enums import Platform
from src.rag.retriever import RegulationRetriever


def evaluate_rag_benchmark(
    queries_file: Path,
    retriever: RegulationRetriever
) -> Dict[str, Any]:
    """运行 RAG 基准评测并输出详细统计指标。

    Args:
        queries_file (Path): 评测查询基准 JSON 路径。
        retriever (RegulationRetriever): 待测检索器。

    Returns:
        Dict[str, Any]: 评测结果字典，包含 hit@1, hit@3, hit@5, mrr 及各 case 详情。
    """
    with open(queries_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total_queries = len(cases)
    hit_1 = 0
    hit_3 = 0
    hit_5 = 0
    mrr_sum = 0.0
    latencies = []
    details: List[Dict[str, Any]] = []

    for case in cases:
        query = case["query"]
        expected_keywords = case.get("target_article_keywords", [])
        platform_str = case.get("expected_platform", "general")
        try:
            platform = Platform(platform_str)
        except ValueError:
            platform = Platform.GENERAL

        t0 = time.time()
        results = retriever.search(query=query, platform=platform, top_k=5)
        elapsed_ms = (time.time() - t0) * 1000.0
        latencies.append(elapsed_ms)

        hit_rank = None
        for rank, res in enumerate(results, start=1):
            article_text = f"{res.chunk.doc_name} {res.chunk.article} {res.chunk.content}"
            # 判定是否命中目标条款核心关键词
            if any(kw in article_text for kw in expected_keywords):
                hit_rank = rank
                break

        if hit_rank is not None:
            if hit_rank == 1:
                hit_1 += 1
            if hit_rank <= 3:
                hit_3 += 1
            if hit_rank <= 5:
                hit_5 += 1
            mrr_sum += 1.0 / hit_rank
        else:
            mrr_sum += 0.0

        details.append({
            "query_id": case.get("query_id"),
            "query": query,
            "hit_rank": hit_rank,
            "latency_ms": round(elapsed_ms, 2),
            "top_article": results[0].chunk.article if results else "None"
        })

    avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else 0.0

    metrics = {
        "total_queries": total_queries,
        "hit_at_1": round(hit_1 / total_queries, 4),
        "hit_at_3": round(hit_3 / total_queries, 4),
        "hit_at_5": round(hit_5 / total_queries, 4),
        "mrr": round(mrr_sum / total_queries, 4),
        "avg_latency_ms": avg_latency,
        "details": details
    }
    return metrics


if __name__ == "__main__":
    benchmark_path = Path(__file__).resolve().parent.parent / "benchmark" / "golden_rag_queries.json"
    r = RegulationRetriever()
    res = evaluate_rag_benchmark(benchmark_path, r)
    print("RAG Evaluation Results:")
    print(f"Hit@1: {res['hit_at_1'] * 100:.1f}%")
    print(f"Hit@3: {res['hit_at_3'] * 100:.1f}%")
    print(f"Hit@5: {res['hit_at_5'] * 100:.1f}%")
    print(f"MRR:   {res['mrr']:.4f}")
    print(f"Avg Latency: {res['avg_latency_ms']} ms")
