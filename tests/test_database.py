"""
Filename: test_database.py
Description: SQLite 数据库核心实体、CRUD 与关系测试。
Author: ListingGuard Team
"""

import pytest
from src.database.manager import DatabaseManager
from src.database.models import (
    Post,
    PostStatus,
    Product,
    ProductStatus,
    User,
    UserRole,
)
from src.models.enums import Platform


@pytest.fixture
def test_db():
    """每个测试函数使用全新的内存数据库。"""
    db = DatabaseManager(":memory:")
    yield db
    db.close()


def test_seed_data_loaded(test_db):
    """测试基准种子数据自动初始化成功。"""
    users = test_db.list_users()
    assert len(users) == 3
    roles = {u.role for u in users}
    assert UserRole.ADMIN in roles
    assert UserRole.EMPLOYEE in roles
    assert UserRole.CUSTOMER in roles

    products = test_db.list_products()
    assert len(products) >= 4
    platforms = {p.platform for p in products}
    assert Platform.TAOBAO in platforms
    assert Platform.PDD in platforms
    assert Platform.EBAY in platforms

    posts = test_db.list_posts()
    assert len(posts) >= 5
    # 验证关联商品正确
    assert any(p.product_id == "PROD-TB-001" for p in posts)


def test_product_crud_operations(test_db):
    """测试商品实体完整增删改查。"""
    new_prod = Product(
        product_id="PROD-TEST-999",
        platform=Platform.TAOBAO,
        title="测试合规洗面奶",
        description="温和氨基酸洁面乳，深层洁净不紧绷。",
        category="美妆个护",
        price=69.0,
        original_price=99.0,
        stock=200,
        status=ProductStatus.APPROVED,
        attributes={"brand": "TestBrand", "volume": "150ml"},
        created_by="USR-EMP-001",
    )
    created = test_db.create_product(new_prod)
    assert created.product_id == "PROD-TEST-999"

    # 查询
    fetched = test_db.get_product("PROD-TEST-999")
    assert fetched is not None
    assert fetched.title == "测试合规洗面奶"
    assert fetched.attributes.get("volume") == "150ml"

    # 更新
    updated = test_db.update_product("PROD-TEST-999", {"price": 59.0, "stock": 180})
    assert updated.price == 59.0
    assert updated.stock == 180

    # 物理删除
    deleted = test_db.delete_product("PROD-TEST-999")
    assert deleted is True
    assert test_db.get_product("PROD-TEST-999") is None


def test_post_crud_and_cascade(test_db):
    """测试商品关联帖子的增改查及级联删除。"""
    new_post = Post(
        post_id="POST-TEST-01",
        product_id="PROD-TB-001",
        channel="xiaohongshu",
        title="亲测超好用的积雪草精华！",
        content="质地清爽，换季退红太快了，无限回购！",
        tags=["修护", "干皮必备"],
        compliance_status=PostStatus.COMPLIANT,
        risk_score=0.0,
        author_id="USR-CUST-001",
    )
    created = test_db.create_post(new_post)
    assert created.post_id == "POST-TEST-01"

    # 查询
    fetched = test_db.get_post("POST-TEST-01")
    assert fetched is not None
    assert fetched.tags == ["修护", "干皮必备"]

    # 更新
    updated = test_db.update_post("POST-TEST-01", {"compliance_status": PostStatus.PENDING_AUDIT})
    assert updated.compliance_status == PostStatus.PENDING_AUDIT

    # 级联删除验证：删除主商品后，关联的帖子应自动随之删除
    test_db.delete_product("PROD-TB-001")
    assert test_db.get_product("PROD-TB-001") is None
    assert test_db.get_post("POST-TEST-01") is None
    # 之前 seed 的 POST-001 关联 PROD-TB-001 也应当已被级联删除
    assert test_db.get_post("POST-001") is None


def test_audit_logs_recording(test_db):
    """测试审计日志记录与按实体过滤查询。"""
    log = test_db.log_action(
        entity_type="product",
        entity_id="PROD-TEST-100",
        action="update_price",
        operator_id="USR-EMP-001",
        operator_role=UserRole.EMPLOYEE,
        details={"old_price": 100, "new_price": 88},
    )
    assert log.log_id.startswith("LOG-")
    assert log.entity_id == "PROD-TEST-100"

    logs = test_db.get_audit_logs(entity_id="PROD-TEST-100")
    assert len(logs) == 1
    assert logs[0].details["new_price"] == 88
