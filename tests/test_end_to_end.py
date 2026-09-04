"""
Filename: test_end_to_end.py
Description: 跨平台 (淘宝/拼多多/eBay) 真实商品合规审核端到端系统集成测试。
Author: ListingGuard Team
"""

import json
from pathlib import Path
import pytest
from src.agent.graph import run_compliance_guard


@pytest.fixture
def dataset_dir():
    return Path(__file__).resolve().parent.parent / "data" / "listings"


def test_e2e_taobao_real_listings(dataset_dir):
    """端到端测试淘宝真实商品样本。"""
    tb_file = dataset_dir / "taobao_listings.json"
    assert tb_file.exists()

    with open(tb_file, "r", encoding="utf-8") as f:
        listings = json.load(f)

    for item in listings:
        report = run_compliance_guard(item)
        assert report.report_id.startswith("RPT-")
        assert report.platform.value == "taobao"

        if item.get("is_compliant_ground_truth") is True:
            # 原本合规的商品应直接判定为合规
            assert report.is_compliant is True
            assert report.initial_diagnosis.total_risks == 0
        else:
            # 违规商品初检必有违规项
            assert report.initial_diagnosis.total_risks > 0
            # 必须生成改写方案
            assert report.rewritten_title is not None


def test_e2e_pdd_real_listings(dataset_dir):
    """端到端测试拼多多真实商品样本。"""
    pdd_file = dataset_dir / "pdd_listings.json"
    assert pdd_file.exists()

    with open(pdd_file, "r", encoding="utf-8") as f:
        listings = json.load(f)

    for item in listings:
        report = run_compliance_guard(item)
        assert report.platform.value == "pdd"
        if item.get("is_compliant_ground_truth") is False:
            assert report.initial_diagnosis.total_risks > 0


def test_e2e_ebay_crossborder_listings(dataset_dir):
    """端到端测试 eBay 跨境真实商品样本。"""
    ebay_file = dataset_dir / "ebay_listings.json"
    assert ebay_file.exists()

    with open(ebay_file, "r", encoding="utf-8") as f:
        listings = json.load(f)

    for item in listings:
        report = run_compliance_guard(item)
        assert report.platform.value == "ebay"
        if item.get("is_compliant_ground_truth") is False:
            assert report.initial_diagnosis.total_risks > 0
