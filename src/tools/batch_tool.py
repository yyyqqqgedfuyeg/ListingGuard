"""
Filename: batch_tool.py
Description: 批量商品 Listing 批量扫描与合规大盘统计分析工具。
Author: ListingGuard Team
"""

from typing import Any, Dict, List
from langchain_core.tools import tool

from src.models.listing import ProductListing
from src.rules.engine import RuleEngine
from src.tools.scan_tool import _ensure_listing_model

_global_engine: RuleEngine = RuleEngine()


@tool
def batch_scan(listings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """批量扫描多个商品 Listing，统计合规达标率、高风险拦截数与风险类目分布。

    Args:
        listings: 待扫描商品列表，每项为一个商品字典。

    Returns:
        批量扫描汇总报告字典，包含 total_scanned、passed_count、failed_count、compliance_rate 及各商品摘要。
    """
    total = len(listings)
    if total == 0:
        return {
            "total_scanned": 0,
            "passed_count": 0,
            "failed_count": 0,
            "compliance_rate": 1.0,
            "details": []
        }

    passed = 0
    failed = 0
    risk_distribution: Dict[str, int] = {}
    details: List[Dict[str, Any]] = []

    for item in listings:
        model: ProductListing = _ensure_listing_model(item)
        diagnosis = _global_engine.diagnose_listing(model)

        is_passed = diagnosis.total_risks == 0
        if is_passed:
            passed += 1
        else:
            failed += 1
            for v in diagnosis.violations:
                cat = v.category.value
                risk_distribution[cat] = risk_distribution.get(cat, 0) + 1

        details.append({
            "listing_id": model.listing_id,
            "platform": model.platform.value,
            "title": model.title,
            "total_risks": diagnosis.total_risks,
            "max_severity": diagnosis.max_severity.value,
            "is_compliant": is_passed
        })

    rate = round(passed / total, 4)

    return {
        "total_scanned": total,
        "passed_count": passed,
        "failed_count": failed,
        "compliance_rate": rate,
        "risk_category_distribution": risk_distribution,
        "details": details
    }
