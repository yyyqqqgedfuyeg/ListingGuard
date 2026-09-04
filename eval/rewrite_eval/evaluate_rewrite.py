"""
Filename: evaluate_rewrite.py
Description: 文案改写与闭环自省能力基准评测器 (首轮合规率、闭环终审率、迭代轮次与卖点留存度)。
Author: ListingGuard Team
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List
import jieba

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.agent.graph import run_compliance_guard
from src.tools.scan_tool import scan_listing
from src.tools.rewrite_tool import rewrite_compliant
from src.tools.verify_tool import verify_rewrite


def evaluate_rewrite_benchmark(
    cases_file: Path
) -> Dict[str, Any]:
    """对违规案例运行文案改写与自省闭环全流程评测。

    Args:
        cases_file (Path): 评测案例集文件路径。

    Returns:
        Dict[str, Any]: 改写能力各项指标。
    """
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    # 仅选取存在违规项的样本进行改写评测
    violation_cases = [c for c in cases if not c.get("expected_is_compliant", False)]
    total_violation_cases = len(violation_cases)

    if total_violation_cases == 0:
        return {"error": "No violation cases found for rewrite benchmark"}

    first_pass_count = 0
    closed_loop_pass_count = 0
    iteration_counts = []
    retention_scores = []
    details: List[Dict[str, Any]] = []

    for case in violation_cases:
        listing = {
            "listing_id": case["case_id"],
            "platform": case.get("platform", "general"),
            "title": case["title"],
            "description": case.get("description", ""),
            "category": case.get("category", "general")
        }

        # 1. 单独评测单次（首次）改写效果
        vios = scan_listing.invoke({"listing": listing})
        single_rewrite = rewrite_compliant.invoke({"listing": listing, "violations": vios})
        first_verify = verify_rewrite.invoke({
            "original_listing": listing,
            "rewritten_title": single_rewrite["rewritten_title"],
            "rewritten_description": single_rewrite["rewritten_description"]
        })
        if first_verify["is_compliant"]:
            first_pass_count += 1

        # 2. 评测完整 LangGraph 闭环自省流程
        report = run_compliance_guard(listing, max_iterations=3)
        if report.is_compliant:
            closed_loop_pass_count += 1
        iteration_counts.append(report.iteration_count)

        # 3. 计算营销信息与核心词汇留存度 (Jaccard 词重合度)
        orig_words = set(jieba.lcut(listing["title"] + " " + listing["description"]))
        new_words = set(jieba.lcut((report.rewritten_title or "") + " " + (report.rewritten_description or "")))
        intersect = len(orig_words.intersection(new_words))
        union = len(orig_words.union(new_words))
        jaccard = round(intersect / union, 4) if union > 0 else 0.0
        retention_scores.append(jaccard)

        details.append({
            "case_id": case["case_id"],
            "first_pass": first_verify["is_compliant"],
            "closed_loop_pass": report.is_compliant,
            "iterations": report.iteration_count,
            "retention_score": jaccard,
            "rewritten_title": report.rewritten_title
        })

    avg_iterations = round(sum(iteration_counts) / len(iteration_counts), 2) if iteration_counts else 1.0
    avg_retention = round(sum(retention_scores) / len(retention_scores), 4) if retention_scores else 0.0

    return {
        "total_evaluated_cases": total_violation_cases,
        "first_pass_compliance_rate": round(first_pass_count / total_violation_cases, 4),
        "closed_loop_final_compliance_rate": round(closed_loop_pass_count / total_violation_cases, 4),
        "average_iterations": avg_iterations,
        "average_marketing_retention_score": avg_retention,
        "details": details
    }


if __name__ == "__main__":
    benchmark_path = Path(__file__).resolve().parent.parent / "benchmark" / "golden_compliance_cases.json"
    res = evaluate_rewrite_benchmark(benchmark_path)
    print("Rewrite Evaluation Results:")
    print(f"First-Pass Compliance: {res['first_pass_compliance_rate'] * 100:.1f}%")
    print(f"Closed-Loop Final:     {res['closed_loop_final_compliance_rate'] * 100:.1f}%")
    print(f"Avg Iterations:        {res['average_iterations']}")
    print(f"Marketing Retention:   {res['average_marketing_retention_score'] * 100:.1f}%")
