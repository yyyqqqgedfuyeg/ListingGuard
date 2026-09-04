"""
Filename: report_node.py
Description: 终审报告汇总节点，组装 ComplianceReport 并生成审计记录。
Author: ListingGuard Team
"""

from datetime import datetime
from typing import Any, Dict
import uuid
from src.agent.state import ComplianceAgentState
from src.models.enums import Platform, Severity
from src.models.listing import ProductListing
from src.models.report import ComplianceReport
from src.models.diagnosis import DiagnosisResult


def report_node(state: ComplianceAgentState) -> Dict[str, Any]:
    """汇总各阶段检测与改写产物，生成标准化合规审查报告。

    Args:
        state (ComplianceAgentState): 当前图状态。

    Returns:
        Dict[str, Any]: 状态更新字典。
    """
    listing_raw = state["listing"]
    platform_str = listing_raw.get("platform", "general").lower()
    try:
        platform = Platform(platform_str)
    except ValueError:
        platform = Platform.GENERAL

    orig_listing = ProductListing(
        listing_id=str(listing_raw.get("listing_id", "UNKNOWN")),
        platform=platform,
        title=listing_raw.get("title", ""),
        description=listing_raw.get("description", ""),
        category=listing_raw.get("category", "general"),
        price=listing_raw.get("price"),
        original_price=listing_raw.get("original_price"),
        attributes=listing_raw.get("attributes", {}),
        images_text=listing_raw.get("images_text", [])
    )

    init_diag_raw = state.get("initial_diagnosis") or {}
    sec_diag_raw = state.get("secondary_diagnosis")

    is_compliant = state.get("is_compliant", False)
    if init_diag_raw.get("total_risks", 0) == 0:
        is_compliant = True
    elif sec_diag_raw and sec_diag_raw.get("total_risks", 0) == 0:
        is_compliant = True

    report_id = f"RPT-{platform.value.upper()}-{uuid.uuid4().hex[:8].upper()}"

    report = ComplianceReport(
        report_id=report_id,
        platform=platform,
        original_listing=orig_listing,
        initial_diagnosis=DiagnosisResult(**init_diag_raw) if init_diag_raw else DiagnosisResult(
            listing_id=orig_listing.listing_id,
            total_risks=0,
            max_severity=Severity.WARNING
        ),
        rewritten_title=state.get("rewritten_title"),
        rewritten_description=state.get("rewritten_description"),
        secondary_diagnosis=DiagnosisResult(**sec_diag_raw) if sec_diag_raw else None,
        is_compliant=is_compliant,
        iteration_count=state.get("iteration", 0),
        created_at=datetime.now().isoformat()
    )

    return {
        "report": report.model_dump()
    }
