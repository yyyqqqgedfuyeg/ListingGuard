"""
Filename: db_tools.py
Description: 供大模型与合规系统调用的数据库操作工具集，集成 RBAC 鉴权、敏感词 Hook 拦截及管理员删除二次确认。
Author: ListingGuard Team
"""

import json
from typing import Any, Dict, List, Optional
from langchain_core.tools import tool

from src.database.manager import DatabaseManager
from src.database.models import (
    Post,
    PostStatus,
    Product,
    ProductStatus,
    UserRole,
)
from src.hooks.tool_hooks import (
    check_post_compliance_hook,
    check_product_compliance_hook,
    enforce_admin_double_confirmation,
)
from src.models.enums import Platform

_global_db_manager: Optional[DatabaseManager] = None


def get_db_manager() -> DatabaseManager:
    """获取或初始化全局数据库管理器单例。"""
    global _global_db_manager
    if _global_db_manager is None:
        _global_db_manager = DatabaseManager()
    return _global_db_manager


def set_db_manager(manager: DatabaseManager):
    """设置全局数据库管理器（常用于测试环境注入内存库）。"""
    global _global_db_manager
    _global_db_manager = manager


# ==================== 商品管理工具 (Product Tools) ====================


@tool
def db_query_products(
    category: Optional[str] = None,
    platform: Optional[str] = None,
    status: Optional[str] = None,
    operator_role: str = "CUSTOMER",
) -> List[Dict[str, Any]]:
    """查询商品列表，支持按类目、平台及上架状态进行多条件筛选。

    Args:
        category: 商品类目，如 美妆个护、食品保健、3C数码、服饰箱包。
        platform: 电商平台，可选 'taobao'、'pdd'、'ebay'。
        status: 商品状态，可选 'APPROVED'、'PENDING_AUDIT'、'REJECTED'、'DRAFT'。
        operator_role: 调用方角色，'ADMIN' / 'EMPLOYEE' / 'CUSTOMER'。

    Returns:
        匹配的商品摘要信息列表。
    """
    db = get_db_manager()
    # 客户角色默认仅可查已审核上架(APPROVED)商品，员工与管理员可查全部
    target_status = status
    if operator_role.upper() == UserRole.CUSTOMER.value and not status:
        target_status = ProductStatus.APPROVED.value

    products = db.list_products(category=category, platform=platform, status=target_status)
    return [p.model_dump() for p in products]


@tool
def db_get_product_detail(
    product_id: str,
    operator_role: str = "CUSTOMER",
) -> Dict[str, Any]:
    """查询指定商品的完整详情，包含基本参数、结构化属性以及所有关联的种草推广帖子。

    Args:
        product_id: 商品唯一编号，如 'PROD-TB-001'。
        operator_role: 调用人角色。

    Returns:
        包含商品详细信息及关联营销帖子列表的复合字典。
    """
    db = get_db_manager()
    product = db.get_product(product_id)
    if not product:
        return {"success": False, "message": f"未找到编号为 [{product_id}] 的商品"}

    # 关联查询帖子
    posts = db.list_posts(product_id=product_id)
    # 若为客户角色，过滤掉被标红违规的帖子
    if operator_role.upper() == UserRole.CUSTOMER.value:
        posts = [p for p in posts if p.compliance_status != PostStatus.FLAGGED]

    data = product.model_dump()
    data["associated_posts"] = [p.model_dump() for p in posts]
    return {"success": True, "product": data}


@tool
def db_create_product(
    product_dict: Dict[str, Any],
    operator_role: str = "EMPLOYEE",
    operator_id: str = "USR-EMP-001",
) -> Dict[str, Any]:
    """新增商品上架信息（前置触发敏感词与绝对化宣传 Hook 拦截）。

    Args:
        product_dict: 待创建商品字典，包含 product_id, platform, title, description, category, price 等。
        operator_role: 操作人角色（仅限 EMPLOYEE 或 ADMIN 执行录入）。
        operator_id: 操作人 ID。

    Returns:
        创建结果与合规审计信息。
    """
    if operator_role.upper() not in (UserRole.EMPLOYEE.value, UserRole.ADMIN.value):
        return {"success": False, "message": "权限不足：普通客户无权直接调用商品创建工具，需通过商家端提审。"}

    # 1. 触发前置 Hook 扫描敏感词与违规
    passed, hook_msg, audit_meta = check_product_compliance_hook(product_dict)
    if not passed:
        return {
            "success": False,
            "blocked": True,
            "message": hook_msg,
            "audit_meta": audit_meta,
        }

    db = get_db_manager()
    # 确定初始状态
    initial_status = ProductStatus.DRAFT
    if audit_meta.get("force_status") == "PENDING_AUDIT":
        initial_status = ProductStatus.PENDING_AUDIT
    elif product_dict.get("status"):
        try:
            initial_status = ProductStatus(product_dict["status"])
        except ValueError:
            initial_status = ProductStatus.DRAFT

    platform_val = Platform(product_dict.get("platform", "taobao"))
    product = Product(
        product_id=product_dict["product_id"],
        platform=platform_val,
        title=product_dict["title"],
        description=product_dict.get("description", ""),
        category=product_dict.get("category", "general"),
        price=product_dict.get("price"),
        original_price=product_dict.get("original_price"),
        stock=product_dict.get("stock", 100),
        status=initial_status,
        attributes=product_dict.get("attributes", {}),
        images=product_dict.get("images", []),
        created_by=operator_id,
    )

    created = db.create_product(product)
    db.log_action(
        entity_type="product",
        entity_id=created.product_id,
        action="create",
        operator_id=operator_id,
        operator_role=operator_role,
        details={"status": created.status.value, "hook_note": hook_msg},
    )

    return {
        "success": True,
        "message": f"商品 [{created.product_id}] 创建成功" + (f" ({hook_msg})" if hook_msg else ""),
        "product": created.model_dump(),
    }


@tool
def db_update_product(
    product_id: str,
    update_dict: Dict[str, Any],
    operator_role: str = "EMPLOYEE",
    operator_id: str = "USR-EMP-001",
) -> Dict[str, Any]:
    """修改商品信息（前置触发敏感词审查 Hook）。

    Args:
        product_id: 商品编号。
        update_dict: 待更新字段字典。
        operator_role: 操作人角色。
        operator_id: 操作人 ID。

    Returns:
        更新结果及状态。
    """
    if operator_role.upper() not in (UserRole.EMPLOYEE.value, UserRole.ADMIN.value):
        return {"success": False, "message": "权限不足：普通客户无权修改商品信息。"}

    # 1. 触发前置 Hook
    passed, hook_msg, audit_meta = check_product_compliance_hook(update_dict)
    if not passed:
        return {
            "success": False,
            "blocked": True,
            "message": hook_msg,
            "audit_meta": audit_meta,
        }

    db = get_db_manager()
    if audit_meta.get("force_status") == "PENDING_AUDIT":
        update_dict["status"] = ProductStatus.PENDING_AUDIT

    updated = db.update_product(product_id, update_dict)
    if not updated:
        return {"success": False, "message": f"商品 [{product_id}] 不存在"}

    db.log_action(
        entity_type="product",
        entity_id=product_id,
        action="update",
        operator_id=operator_id,
        operator_role=operator_role,
        details={"updates": list(update_dict.keys()), "hook_note": hook_msg},
    )

    return {
        "success": True,
        "message": f"商品 [{product_id}] 更新成功" + (f" ({hook_msg})" if hook_msg else ""),
        "product": updated.model_dump(),
    }


@tool
def db_delete_product(
    product_id: str,
    operator_role: str = "ADMIN",
    operator_id: str = "USR-ADMIN-001",
    confirm_token: Optional[str] = None,
) -> Dict[str, Any]:
    """删除商品及其关联的全部营销帖子（高危操作：严格限制 ADMIN 角色，且必须执行管理员二次确认）。

    首次调用未传入 confirm_token 时，系统将生成确认令牌并中断删除；
    管理员携带有效的 confirm_token 再次调用时，方可真正执行物理删除。

    Args:
        product_id: 目标删除商品编号。
        operator_role: 操作人角色，必须为 'ADMIN'。
        operator_id: 管理员 ID。
        confirm_token: 二次确认防伪凭证。

    Returns:
        包含二次确认令牌提示或删除完成状态的字典。
    """
    db = get_db_manager()

    # 检查商品是否存在
    prod = db.get_product(product_id)
    if not prod:
        return {"success": False, "message": f"商品 [{product_id}] 不存在，无需删除"}

    # 触发二次确认 Hook
    confirm_res = enforce_admin_double_confirmation(
        operator_role=operator_role,
        action_type="delete_product",
        target_id=product_id,
        confirm_token=confirm_token,
        db_manager=db,
        operator_id=operator_id,
    )

    if not confirm_res["success"]:
        return confirm_res

    # 二次确认通过，执行物理删除
    deleted = db.delete_product(product_id)
    if deleted:
        db.log_action(
            entity_type="product",
            entity_id=product_id,
            action="delete",
            operator_id=operator_id,
            operator_role=UserRole.ADMIN,
            details={"title": prod.title, "confirm_token": confirm_token},
        )
        return {
            "success": True,
            "status": "DELETED",
            "message": f"管理员二次确认通过：商品 [{product_id}] 及其全部关联帖子已成功从数据库中物理删除。",
            "deleted_product_id": product_id,
        }

    return {"success": False, "message": "删除失败，数据库未受影响"}


# ==================== 关联帖子管理工具 (Post Tools) ====================


@tool
def db_query_posts(
    product_id: Optional[str] = None,
    channel: Optional[str] = None,
    compliance_status: Optional[str] = None,
    operator_role: str = "CUSTOMER",
) -> List[Dict[str, Any]]:
    """查询商品关联的种草推广与社交媒体营销帖子。

    Args:
        product_id: 指定商品 ID，如 'PROD-TB-001'。
        channel: 推广渠道，如 xiaohongshu / guangguang / weibo / tiktok / instagram。
        compliance_status: 合规状态，可选 'COMPLIANT'、'PENDING_AUDIT'、'FLAGGED'、'DRAFT'。
        operator_role: 调用方角色。

    Returns:
        帖子列表。
    """
    db = get_db_manager()
    posts = db.list_posts(
        product_id=product_id,
        channel=channel,
        compliance_status=compliance_status,
    )
    # 客户角色过滤掉 FLAGGED 违规帖子
    if operator_role.upper() == UserRole.CUSTOMER.value:
        posts = [p for p in posts if p.compliance_status != PostStatus.FLAGGED]

    return [p.model_dump() for p in posts]


@tool
def db_get_post_detail(
    post_id: str,
    operator_role: str = "CUSTOMER",
) -> Dict[str, Any]:
    """查询单个营销种草帖子的详细信息及合规风控诊断记录。

    Args:
        post_id: 帖子编号，如 'POST-001'。
        operator_role: 调用方角色。

    Returns:
        帖子详情与风控记录。
    """
    db = get_db_manager()
    post = db.get_post(post_id)
    if not post:
        return {"success": False, "message": f"未找到编号为 [{post_id}] 的帖子"}

    return {"success": True, "post": post.model_dump()}


@tool
def db_create_post(
    post_dict: Dict[str, Any],
    operator_role: str = "EMPLOYEE",
    operator_id: str = "USR-EMP-001",
) -> Dict[str, Any]:
    """创建商品关联的营销种草帖子（前置触发敏感词、极限词及夸大修辞检查 Hook）。

    - 若包含严重违规词（如绝对化用语、虚假疗效），Hook 直接拦截禁止发布；
    - 若包含轻中度夸大修辞，自动将帖子状态置为待审核 (PENDING_AUDIT) 并记录违规标签；
    - 无风险文案直接通过发布。

    Args:
        post_dict: 帖子内容字典，必须包含 post_id, product_id, title, content 等字段。
        operator_role: 操作人角色。
        operator_id: 操作人 ID。

    Returns:
        创建成功数据或 Hook 拦截详细原因。
    """
    db = get_db_manager()

    # 校验关联商品是否存在
    product_id = post_dict.get("product_id")
    if not product_id or not db.get_product(product_id):
        return {"success": False, "message": f"关联商品 [{product_id}] 不存在，无法创建关联帖子"}

    # 1. 触发发帖前置 Hook
    passed, hook_msg, audit_meta = check_post_compliance_hook(post_dict)
    if not passed:
        # 严重违规直接拦截阻断
        return {
            "success": False,
            "blocked": True,
            "message": hook_msg,
            "audit_meta": audit_meta,
        }

    # 确定帖子状态
    status = PostStatus.COMPLIANT
    if audit_meta.get("recommended_action") == "REQUIRE_APPROVAL":
        status = PostStatus.PENDING_AUDIT
    elif post_dict.get("compliance_status"):
        try:
            status = PostStatus(post_dict["compliance_status"])
        except ValueError:
            status = PostStatus.DRAFT

    post = Post(
        post_id=post_dict["post_id"],
        product_id=product_id,
        channel=post_dict.get("channel", "xiaohongshu"),
        title=post_dict["title"],
        content=post_dict.get("content", ""),
        tags=post_dict.get("tags", []),
        compliance_status=status,
        risk_score=audit_meta.get("risk_score", 0.0),
        flagged_violations=audit_meta.get("flagged_violations", []),
        author_id=operator_id,
    )

    created = db.create_post(post)
    db.log_action(
        entity_type="post",
        entity_id=created.post_id,
        action="create",
        operator_id=operator_id,
        operator_role=operator_role,
        details={
            "product_id": product_id,
            "status": created.compliance_status.value,
            "hook_message": hook_msg,
        },
    )

    return {
        "success": True,
        "message": f"帖子 [{created.post_id}] 创建成功" + (f" ({hook_msg})" if hook_msg else ""),
        "post": created.model_dump(),
    }


@tool
def db_update_post(
    post_id: str,
    update_dict: Dict[str, Any],
    operator_role: str = "EMPLOYEE",
    operator_id: str = "USR-EMP-001",
) -> Dict[str, Any]:
    """修改帖子文案（前置触发敏感词与夸大宣称 Hook 审查）。

    Args:
        post_id: 帖子编号。
        update_dict: 待更新字段。
        operator_role: 操作人角色。
        operator_id: 操作人 ID。

    Returns:
        更新结果或拦截说明。
    """
    # 1. 触发前置 Hook
    passed, hook_msg, audit_meta = check_post_compliance_hook(update_dict)
    if not passed:
        return {
            "success": False,
            "blocked": True,
            "message": hook_msg,
            "audit_meta": audit_meta,
        }

    db = get_db_manager()
    if audit_meta.get("recommended_action") == "REQUIRE_APPROVAL":
        update_dict["compliance_status"] = PostStatus.PENDING_AUDIT
        update_dict["risk_score"] = audit_meta.get("risk_score", 0.7)
        update_dict["flagged_violations"] = audit_meta.get("flagged_violations", [])

    updated = db.update_post(post_id, update_dict)
    if not updated:
        return {"success": False, "message": f"帖子 [{post_id}] 不存在"}

    db.log_action(
        entity_type="post",
        entity_id=post_id,
        action="update",
        operator_id=operator_id,
        operator_role=operator_role,
        details={"updates": list(update_dict.keys()), "hook_message": hook_msg},
    )

    return {
        "success": True,
        "message": f"帖子 [{post_id}] 更新成功" + (f" ({hook_msg})" if hook_msg else ""),
        "post": updated.model_dump(),
    }


@tool
def db_delete_post(
    post_id: str,
    operator_role: str = "ADMIN",
    operator_id: str = "USR-ADMIN-001",
    confirm_token: Optional[str] = None,
) -> Dict[str, Any]:
    """删除营销帖子（高危操作：严格限制 ADMIN 角色，且必须执行管理员二次确认）。

    首次调用未传入 confirm_token 时返回确认令牌与拦截说明；
    二次携带有效令牌方可完成删除。

    Args:
        post_id: 待删除帖子 ID。
        operator_role: 操作人角色，必须为 'ADMIN'。
        operator_id: 管理员 ID。
        confirm_token: 二次确认凭据。

    Returns:
        执行结果字典。
    """
    db = get_db_manager()
    post = db.get_post(post_id)
    if not post:
        return {"success": False, "message": f"帖子 [{post_id}] 不存在，无需删除"}

    # 触发二次确认 Hook
    confirm_res = enforce_admin_double_confirmation(
        operator_role=operator_role,
        action_type="delete_post",
        target_id=post_id,
        confirm_token=confirm_token,
        db_manager=db,
        operator_id=operator_id,
    )

    if not confirm_res["success"]:
        return confirm_res

    deleted = db.delete_post(post_id)
    if deleted:
        db.log_action(
            entity_type="post",
            entity_id=post_id,
            action="delete",
            operator_id=operator_id,
            operator_role=UserRole.ADMIN,
            details={"title": post.title, "confirm_token": confirm_token},
        )
        return {
            "success": True,
            "status": "DELETED",
            "message": f"管理员二次确认通过：帖子 [{post_id}] 已成功物理删除。",
            "deleted_post_id": post_id,
        }

    return {"success": False, "message": "删除失败，数据库未受影响"}


@tool
def db_audit_post(
    post_id: str,
    decision: str,
    operator_role: str = "EMPLOYEE",
    operator_id: str = "USR-EMP-001",
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """人工合规审核帖子（仅限 EMPLOYEE 与 ADMIN 角色操作）。

    Args:
        post_id: 帖子编号。
        decision: 审核决定，可选 'APPROVE' (标记为 COMPLIANT) 或 'REJECT' (标记为 FLAGGED)。
        operator_role: 审核人角色。
        operator_id: 审核人编号。
        notes: 审核批注或整改要求说明。

    Returns:
        审核处理结果。
    """
    if operator_role.upper() not in (UserRole.EMPLOYEE.value, UserRole.ADMIN.value):
        return {"success": False, "message": "权限不足：普通客户无权执行人工合规审核。"}

    db = get_db_manager()
    post = db.get_post(post_id)
    if not post:
        return {"success": False, "message": f"帖子 [{post_id}] 不存在"}

    if decision.upper() == "APPROVE":
        new_status = PostStatus.COMPLIANT
        new_score = 0.0
    elif decision.upper() == "REJECT":
        new_status = PostStatus.FLAGGED
        new_score = max(post.risk_score, 0.85)
    else:
        return {"success": False, "message": f"未知的审核指令 [{decision}]，必须为 APPROVE 或 REJECT"}

    updated = db.update_post(
        post_id,
        {
            "compliance_status": new_status,
            "risk_score": new_score,
        },
    )

    db.log_action(
        entity_type="post",
        entity_id=post_id,
        action="audit",
        operator_id=operator_id,
        operator_role=operator_role,
        details={"decision": decision, "notes": notes or ""},
    )

    return {
        "success": True,
        "message": f"帖子 [{post_id}] 审核完成，状态变更为 [{new_status.value}]",
        "post": updated.model_dump() if updated else None,
    }
