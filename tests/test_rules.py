"""
Filename: test_rules.py
Description: 电商合规规则引擎与业务模型单元测试套件。
Author: ListingGuard Team
"""

import pytest
from src.models.enums import Platform, RiskCategory, Severity
from src.models.listing import ProductListing
from src.rules.engine import RuleEngine
from src.rules.loader import RuleLoader


@pytest.fixture
def rule_engine():
    """初始化规则引擎 fixture。"""
    return RuleEngine()


def test_clean_listing_no_violations(rule_engine):
    """测试合规商品无任何违规检出。"""
    listing = ProductListing(
        listing_id="PROD-001",
        platform=Platform.TAOBAO,
        title="夏季纯棉短袖T恤男女同款透气休闲百搭圆领半袖",
        description="选用精梳棉面料，触感柔软亲肤，吸汗透气不易起球，经典版型设计舒适百搭。",
        category="服饰箱包",
        price=59.9
    )
    violations = rule_engine.scan_listing(listing)
    assert len(violations) == 0

    diagnosis = rule_engine.diagnose_listing(listing)
    assert diagnosis.total_risks == 0
    assert "✅" in diagnosis.summary


def test_taobao_feedback_manipulation(rule_engine):
    """测试淘宝好评返现行为检测与拦截。"""
    listing = ProductListing(
        listing_id="PROD-TB-002",
        platform=Platform.TAOBAO,
        title="新款高保真蓝牙无线耳机",
        description="音质出众，带图好评返5元红包，加微信返更多优惠！",
        category="3C数码"
    )
    violations = rule_engine.scan_listing(listing)
    assert len(violations) >= 1
    categories = [v.category for v in violations]
    assert RiskCategory.FEEDBACK_MANIPULATION in categories

    # 验证判定为严重违规 BLOCK
    diagnosis = rule_engine.diagnose_listing(listing)
    assert diagnosis.max_severity == Severity.BLOCK
    assert any("淘宝网市场管理" in str(v.cited_regulation) for v in violations)


def test_pdd_deceptive_promotion_and_medical_claims(rule_engine):
    """测试拼多多价格欺诈与虚假医疗宣称检测。"""
    listing = ProductListing(
        listing_id="PROD-PDD-003",
        platform=Platform.PDD,
        title="0元免费领 老树野生肉桂养生代用茶",
        description="原价999现价9.9元，工厂倒闭清库，每天一杯降三高降血糖，三天见效根治糖尿病！",
        category="食品保健"
    )
    violations = rule_engine.scan_listing(listing)
    assert len(violations) >= 3

    categories = {v.category for v in violations}
    assert RiskCategory.PRICE_FRAUD in categories
    assert RiskCategory.FALSE_EFFICACY in categories

    diagnosis = rule_engine.diagnose_listing(listing)
    assert diagnosis.max_severity == Severity.BLOCK


def test_ebay_vero_ip_infringement(rule_engine):
    """测试 eBay 跨境知识产权与品牌碰瓷侵权违规检测。"""
    listing = ProductListing(
        listing_id="PROD-EB-004",
        platform=Platform.EBAY,
        title="Luxury Watch like Apple Rolex replica waterproof quartz wristwatch",
        description="1:1 replica design, high quality leather strap inspired by Chanel style.",
        category="Watches"
    )
    violations = rule_engine.scan_listing(listing)
    assert len(violations) >= 2
    for v in violations:
        assert v.category == RiskCategory.IP_INFRINGEMENT
        assert v.severity == Severity.BLOCK
        assert "VeRO" in str(v.cited_regulation)


def test_advertising_law_universal_extreme_words(rule_engine):
    """测试《广告法》第九条极限词与绝对化用语通用拦截。"""
    listing = ProductListing(
        listing_id="PROD-GEN-005",
        platform=Platform.GENERAL,
        title="全网第一顶级美白淡斑精华液 100%纯天然 永久有效",
        description="独一无二的独家配方，全网最佳效果，彻底清除色斑不反弹。",
        category="美妆护肤"
    )
    violations = rule_engine.scan_listing(listing)
    hit_patterns = {v.trigger_pattern for v in violations}
    assert "第一" in hit_patterns or "全网第一" in hit_patterns or "顶级" in hit_patterns
    assert "100%纯天然" in hit_patterns or "永久有效" in hit_patterns

    diagnosis = rule_engine.diagnose_listing(listing)
    assert diagnosis.total_risks >= 3
    assert len(diagnosis.legal_citations) >= 1
