"""
Filename: evaluate_scanner.py
Description: 规则扫描引擎精确率、召回率、F1 分数及吞吐量基准评测器。
Author: ListingGuard Team
"""

import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Set

root_dir = Path(__file__).resolve().parent.parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from src.models.enums import Platform
from src.models.listing import ProductListing
from src.rules.engine import RuleEngine


def evaluate_scanner_benchmark(
    cases_file: Path,
    engine: RuleEngine
) -> Dict[str, Any]:
    """运行规则扫描评测，统计准确率、召回率、F1 值及吞吐率。

    Args:
        cases_file (Path): 标注案例集文件路径。
        engine (RuleEngine): 待评测规则引擎。

    Returns:
        Dict[str, Any]: 评测指标字典。
    """
    with open(cases_file, "r", encoding="utf-8") as f:
        cases = json.load(f)

    total_cases = len(cases)
    binary_correct = 0

    category_stats: Dict[str, Dict[str, int]] = {}

    t0 = time.time()
    for case in cases:
        platform_str = case.get("platform", "general")
        try:
            platform = Platform(platform_str)
        except ValueError:
            platform = Platform.GENERAL

        model = ProductListing(
            listing_id=case["case_id"],
            platform=platform,
            title=case["title"],
            description=case.get("description", ""),
            category=case.get("category", "general")
        )

        violations = engine.scan_listing(model)
        detected_categories: Set[str] = {v.category.value for v in violations}
        expected_categories: Set[str] = set(case.get("expected_categories", []))

        # 1. 二分类指标（是否合规）
        is_actually_compliant = len(expected_categories) == 0
        predicted_compliant = len(detected_categories) == 0
        if is_actually_compliant == predicted_compliant:
            binary_correct += 1

        # 2. 统计各违规类别的 TP, FP, FN
        all_cats = detected_categories.union(expected_categories)
        for cat in all_cats:
            if cat not in category_stats:
                category_stats[cat] = {"tp": 0, "fp": 0, "fn": 0}

            in_pred = cat in detected_categories
            in_gold = cat in expected_categories

            if in_pred and in_gold:
                category_stats[cat]["tp"] += 1
            elif in_pred and not in_gold:
                category_stats[cat]["fp"] += 1
            elif not in_pred and in_gold:
                category_stats[cat]["fn"] += 1

    elapsed = time.time() - t0
    throughput = round(total_cases / elapsed, 1) if elapsed > 0 else 0.0
    binary_accuracy = round(binary_correct / total_cases, 4) if total_cases > 0 else 0.0

    # 计算各类别及宏平均 Precision, Recall, F1
    per_category_metrics = {}
    precisions, recalls, f1s = [], [], []

    for cat, counts in category_stats.items():
        tp = counts["tp"]
        fp = counts["fp"]
        fn = counts["fn"]

        p = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 1.0
        r = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 1.0
        f1 = round(2 * p * r / (p + r), 4) if (p + r) > 0 else 0.0

        per_category_metrics[cat] = {
            "precision": p,
            "recall": r,
            "f1": f1,
            "support": tp + fn
        }
        precisions.append(p)
        recalls.append(r)
        f1s.append(f1)

    macro_p = round(sum(precisions) / len(precisions), 4) if precisions else 1.0
    macro_r = round(sum(recalls) / len(recalls), 4) if recalls else 1.0
    macro_f1 = round(sum(f1s) / len(f1s), 4) if f1s else 1.0

    return {
        "total_cases": total_cases,
        "binary_compliance_accuracy": binary_accuracy,
        "macro_precision": macro_p,
        "macro_recall": macro_r,
        "macro_f1": macro_f1,
        "throughput_listings_per_sec": throughput,
        "category_breakdown": per_category_metrics
    }


if __name__ == "__main__":
    benchmark_path = Path(__file__).resolve().parent.parent / "benchmark" / "golden_compliance_cases.json"
    e = RuleEngine()
    res = evaluate_scanner_benchmark(benchmark_path, e)
    print("Scanner Evaluation Results:")
    print(f"Binary Accuracy: {res['binary_compliance_accuracy'] * 100:.1f}%")
    print(f"Macro Precision: {res['macro_precision'] * 100:.1f}%")
    print(f"Macro Recall:    {res['macro_recall'] * 100:.1f}%")
    print(f"Macro F1-Score:  {res['macro_f1'] * 100:.1f}%")
    print(f"Throughput:      {res['throughput_listings_per_sec']} listings/sec")
