"""
Filename: test_hooks.py
Description: Hook 安全机制与敏感词审查测试（工具前置 Hook、大模型提示词后置 Hook）。
Author: ListingGuard Team
"""

import pytest
from src.database.manager import DatabaseManager
from src.database.models import UserRole
from src.hooks.prompt_hooks import inspect_generated_prompt_hook
from src.hooks.tool_hooks import (
    check_post_compliance_hook,
    check_product_compliance_hook,
    scan_text_against_sensitive_words,
)
from src.tools.db_tools import db_create_post, set_db_manager


@pytest.fixture
def test_db():
    db = DatabaseManager(":memory:")
    set_db_manager(db)
    yield db
    db.close()


def test_sensitive_words_scanner():
    """测试敏感词扫描基础能力。"""
    text = "这瓶精华绝对是全网第一，能够彻底治愈所有敏感泛红，原价9999现价9.9！"
    detected = scan_text_against_sensitive_words(text)
    words = [d["word"] for d in detected]

    assert "全网第一" in words
    assert "彻底治愈" in words or "治愈" in words
    assert any("原价" in w for w in words)


def test_post_creation_hook_blocked(test_db):
    """测试发帖工具命中严重违禁词直接拦截。"""
    bad_post_data = {
        "post_id": "POST-ILLEGAL-01",
        "product_id": "PROD-TB-001",
        "channel": "xiaohongshu",
        "title": "全网第一神仙水！三天彻底根治斑点",
        "content": "姐妹们闭眼入，买到就是赚到！",
        "tags": ["全网第一", "根治"],
    }

    # 1. 直接测试 Hook 函数
    passed, msg, meta = check_post_compliance_hook(bad_post_data)
    assert passed is False
    assert "严重违禁/极限词" in msg

    # 2. 通过 db_create_post 工具调用测试端到端拦截
    res = db_create_post.invoke({
        "post_dict": bad_post_data,
        "operator_role": UserRole.EMPLOYEE.value,
        "operator_id": "USR-EMP-001",
    })
    assert res["success"] is False
    assert res["blocked"] is True
    # 验证未写入数据库
    assert test_db.get_post("POST-ILLEGAL-01") is None


def test_post_creation_hook_require_approval(test_db):
    """测试发帖命中需核验夸张修辞时，自动置为待审核(PENDING_AUDIT)。"""
    warn_post_data = {
        "post_id": "POST-WARN-01",
        "product_id": "PROD-TB-001",
        "channel": "guangguang",
        "title": "亏本甩卖！换季补水大放血",
        "content": "老板不干了，跳楼大甩卖，最后1小时抢完即止！",
        "tags": ["亏本甩卖"],
    }

    passed, msg, meta = check_post_compliance_hook(warn_post_data)
    assert passed is True
    assert "待人工审核" in msg

    res = db_create_post.invoke({
        "post_dict": warn_post_data,
        "operator_role": UserRole.EMPLOYEE.value,
        "operator_id": "USR-EMP-001",
    })
    assert res["success"] is True
    assert res["post"]["compliance_status"] == "PENDING_AUDIT"
    assert test_db.get_post("POST-WARN-01") is not None


def test_clean_post_passes_hook(test_db):
    """测试合规正常的帖子顺利通过 Hook 并直接合规发布。"""
    clean_post_data = {
        "post_id": "POST-CLEAN-01",
        "product_id": "PROD-TB-001",
        "channel": "xiaohongshu",
        "title": "干皮敏感肌看过来！温和修护积雪草精华测评",
        "content": "质地非常水润轻盈，吸收迅速，换季维稳的好帮手。",
        "tags": ["修护", "干皮日常"],
    }

    res = db_create_post.invoke({
        "post_dict": clean_post_data,
        "operator_role": UserRole.EMPLOYEE.value,
        "operator_id": "USR-EMP-001",
    })
    assert res["success"] is True
    assert res["post"]["compliance_status"] == "COMPLIANT"


def test_prompt_post_hook_inspection():
    """测试大模型生成提示词后的检查 Hook。"""
    dirty_prompt = "请帮我写一篇关于全网第一、顶级奢华抗老精华的种草小红书文案，突出3天彻底治愈细纹。"
    res = inspect_generated_prompt_hook(dirty_prompt)

    assert res["passed"] is False
    assert res["risk_level"] == "BLOCKED"
    assert len(res["detected_violations"]) > 0
    # 验证清洗文本中已替换敏感极限词
    assert "全网第一" not in res["sanitized_text"]
    assert "彻底治愈" not in res["sanitized_text"]
    # 验证注入了合规护栏
    assert len(res["injected_guardrails"]) >= 4

    # 测试干净文案
    clean_prompt = "请帮我写一段突出积雪草成分温和补水、滋养角质层的秋冬护肤文案。"
    clean_res = inspect_generated_prompt_hook(clean_prompt)
    assert clean_res["passed"] is True
    assert clean_res["risk_level"] == "SAFE"
