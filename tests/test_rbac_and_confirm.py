"""
Filename: test_rbac_and_confirm.py
Description: RBAC 三级角色权限隔离与管理员删除二次确认拦截机制测试。
Author: ListingGuard Team
"""

import pytest
from src.database.manager import DatabaseManager
from src.database.models import UserRole
from src.tools.db_tools import (
    db_create_product,
    db_delete_post,
    db_delete_product,
    db_query_products,
    set_db_manager,
)


@pytest.fixture
def test_db_setup():
    """初始化测试内存数据库并注入工具全局环境。"""
    db = DatabaseManager(":memory:")
    set_db_manager(db)
    yield db
    db.close()


def test_rbac_customer_permission_boundary(test_db_setup):
    """测试普通客户/商家角色权限边界。"""
    # 客户无法直接调用高危创建工具
    res = db_create_product.invoke({
        "product_dict": {
            "product_id": "PROD-HACK",
            "title": "非法提单商品",
            "platform": "taobao",
        },
        "operator_role": UserRole.CUSTOMER.value,
        "operator_id": "USR-CUST-001",
    })
    assert res["success"] is False
    assert "权限不足" in res["message"]

    # 客户无权执行删除商品
    del_res = db_delete_product.invoke({
        "product_id": "PROD-TB-001",
        "operator_role": UserRole.CUSTOMER.value,
        "operator_id": "USR-CUST-001",
    })
    assert del_res["success"] is False
    assert del_res["status"] == "PERMISSION_DENIED"

    # 员工也无权执行物理删除操作
    del_res_emp = db_delete_product.invoke({
        "product_id": "PROD-TB-001",
        "operator_role": UserRole.EMPLOYEE.value,
        "operator_id": "USR-EMP-001",
    })
    assert del_res_emp["success"] is False
    assert del_res_emp["status"] == "PERMISSION_DENIED"


def test_admin_delete_product_double_confirmation(test_db_setup):
    """测试管理员删除商品的二次确认拦截与闭环。"""
    product_id = "PROD-TB-001"

    # 1. 首次调用未传入 confirm_token -> 系统拦截并生成二次确认凭据
    res_step1 = db_delete_product.invoke({
        "product_id": product_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
        "confirm_token": None,
    })

    assert res_step1["success"] is False
    assert res_step1["status"] == "CONFIRMATION_REQUIRED"
    assert "二次确认" in res_step1["message"]
    token = res_step1.get("confirm_token")
    assert token is not None
    assert "CONFIRM_DELETE_PRODUCT" in token

    # 确认商品仍安然存在，未被物理删除
    assert test_db_setup.get_product(product_id) is not None

    # 2. 携带错误的 Token 再次调用 -> 依然拦截
    res_fake = db_delete_product.invoke({
        "product_id": product_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
        "confirm_token": "FAKE_INVALID_TOKEN_123",
    })
    assert res_fake["success"] is False
    assert res_fake["status"] == "INVALID_TOKEN"
    assert test_db_setup.get_product(product_id) is not None

    # 3. 管理员携带合法的 confirm_token 再次调用 -> 验证通过，物理删除成功
    res_step2 = db_delete_product.invoke({
        "product_id": product_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
        "confirm_token": token,
    })
    assert res_step2["success"] is True
    assert res_step2["status"] == "DELETED"
    assert test_db_setup.get_product(product_id) is None

    # 4. 二次使用已被消费的 Token -> 拦截，防止重放
    res_reuse = db_delete_product.invoke({
        "product_id": product_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
        "confirm_token": token,
    })
    assert res_reuse["success"] is False


def test_admin_delete_post_double_confirmation(test_db_setup):
    """测试管理员删除营销帖子的二次确认机制。"""
    post_id = "POST-001"
    assert test_db_setup.get_post(post_id) is not None

    # 1. 未带 Token 触发拦截并获取 Token
    res1 = db_delete_post.invoke({
        "post_id": post_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
    })
    assert res1["status"] == "CONFIRMATION_REQUIRED"
    token = res1["confirm_token"]

    # 2. 携带 Token 确认删除
    res2 = db_delete_post.invoke({
        "post_id": post_id,
        "operator_role": UserRole.ADMIN.value,
        "operator_id": "USR-ADMIN-001",
        "confirm_token": token,
    })
    assert res2["success"] is True
    assert res2["status"] == "DELETED"
    assert test_db_setup.get_post(post_id) is None
