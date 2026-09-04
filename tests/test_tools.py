"""
Filename: test_tools.py
Description: ListingGuard 电商合规工具链单元测试套件。
Author: ListingGuard Team
"""

import json
import pytest

from src.models.enums import Platform
from src.tools.scan_tool import scan_listing
from src.tools.diagnose_tool import diagnose_violation
from src.tools.rewrite_tool import rewrite_compliant
from src.tools.verify_tool import verify_rewrite
from src.tools.batch_tool import batch_scan
from src.tools.report_tool import export_report


@pytest.fixture
def sample_taobao_violation_listing():
    return {
        "listing_id": "TEST-TB-01",
        "platform": "taobao",
        "title": "全网第一顶级美白精华液 100%纯天然 永久有效",
        "description": "消炎祛斑根除黑色素，好评返5元红包，带图好评返现10元！",
        "category": "美妆护肤"
    }


def test_scan_listing_tool(sample_taobao_violation_listing):
    """验证 scan_listing 工具能够检出违禁词并输出标准字典结构。"""
    violations = scan_listing.invoke({"listing": sample_taobao_violation_listing})
    assert isinstance(violations, list)
    assert len(violations) >= 3

    patterns = [v["trigger_pattern"] for v in violations]
    assert any("第一" in p or "全网第一" in p for p in patterns)
    assert any("好评返现" in p for p in patterns)


def test_diagnose_violation_tool(sample_taobao_violation_listing):
    """验证 diagnose_violation 工具能够输出法理诊断及综合风险等级。"""
    diag = diagnose_violation.invoke({"listing": sample_taobao_violation_listing})
    assert isinstance(diag, dict)
    assert diag["total_risks"] >= 3
    assert diag["max_severity"] == "BLOCK"
    assert "summary" in diag


def test_rewrite_compliant_tool(sample_taobao_violation_listing):
    """验证 rewrite_compliant 工具能有效替换违规词并生成优化文本。"""
    violations = scan_listing.invoke({"listing": sample_taobao_violation_listing})
    res = rewrite_compliant.invoke({
        "listing": sample_taobao_violation_listing,
        "violations": violations
    })
    assert "rewritten_title" in res
    assert "rewritten_description" in res

    new_title = res["rewritten_title"]
    new_desc = res["rewritten_description"]
    # 验证极限词已被替换剔除
    assert "全网第一" not in new_title
    assert "100%纯天然" not in new_title
    assert "好评返现" not in new_desc


def test_verify_rewrite_tool(sample_taobao_violation_listing):
    """验证 verify_rewrite 工具对改写文案的二次复检能力。"""
    # 构造合规文案测试
    clean_title = "高品质口碑优选美白精华液 精选植物萃取成分 长效持久"
    clean_desc = "深层净澈黑色素，温和舒缓修护肌肤屏障。"

    res = verify_rewrite.invoke({
        "original_listing": sample_taobao_violation_listing,
        "rewritten_title": clean_title,
        "rewritten_description": clean_desc
    })

    assert res["is_compliant"] is True
    assert res["remaining_risks"] == 0


def test_batch_scan_tool(sample_taobao_violation_listing):
    """验证 batch_scan 工具的批量扫描聚合统计能力。"""
    clean_item = {
        "listing_id": "TEST-CLEAN-02",
        "platform": "taobao",
        "title": "纯棉透气男女情侣T恤",
        "description": "精梳棉面料，舒适亲肤，吸汗透气。",
        "category": "服饰"
    }
    batch_res = batch_scan.invoke({"listings": [sample_taobao_violation_listing, clean_item]})
    assert batch_res["total_scanned"] == 2
    assert batch_res["passed_count"] == 1
    assert batch_res["failed_count"] == 1
    assert batch_res["compliance_rate"] == 0.5


def test_export_report_tool(sample_taobao_violation_listing):
    """验证 export_report 工具能够生成 Markdown 与 JSON 报告。"""
    diag = diagnose_violation.invoke({"listing": sample_taobao_violation_listing})
    report_data = {
        "report_id": "RPT-TEST-001",
        "platform": "taobao",
        "original_listing": sample_taobao_violation_listing,
        "initial_diagnosis": diag,
        "rewritten_title": "合规标题测试",
        "rewritten_description": "合规详情测试",
        "is_compliant": True,
        "iteration_count": 1
    }

    md_output = export_report.invoke({"report_data": report_data, "export_format": "markdown"})
    assert "# 🛡️ ListingGuard" in md_output
    assert "RPT-TEST-001" in md_output

    json_output = export_report.invoke({"report_data": report_data, "export_format": "json"})
    parsed = json.loads(json_output)
    assert parsed["report_id"] == "RPT-TEST-001"
