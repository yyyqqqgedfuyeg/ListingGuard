"""
Filename: tool_hooks.py
Description: 数据库写操作与高危工具前置拦截 Hook：敏感词/夸大宣传前置审查与管理员删除二次确认。
Author: ListingGuard Team
"""

from typing import Any, Dict, List, Optional, Tuple

from src.database.manager import DatabaseManager
from src.database.models import UserRole
from src.hooks.sensitive_loader import SensitiveWordEntry, SensitiveWordsRegistry


class ToolComplianceError(Exception):
    """工具前置合规拦截异常。"""
    pass


def scan_text_against_sensitive_words(text: str) -> List[Dict[str, Any]]:
    """使用敏感词文档库扫描文本中的违规词汇。

    Args:
        text (str): 待检查的文本内容。

    Returns:
        List[Dict[str, Any]]: 命中的违规详情列表。
    """
    if not text:
        return []

    entries = SensitiveWordsRegistry.get_entries()
    detected = []
    seen_words = set()

    for entry in entries:
        if entry.word in text and entry.word not in seen_words:
            seen_words.add(entry.word)
            detected.append({
                "word": entry.word,
                "category": entry.category,
                "severity": entry.severity,
                "recommended_replacement": entry.replacement,
                "reason": entry.reason,
            })

    return detected


def check_post_compliance_hook(post_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """在创建或修改商品种草/推广帖子前的拦截 Hook。

    检查帖子标题、正文及标签中是否存在极限词、夸大宣传、虚假医疗或价格欺诈。
    - 若命中 BLOCK 级别（如“全网第一”、“彻底治愈”）：直接拦截不允许创建，返回 False；
    - 若命中 REQUIRE_APPROVAL / WARNING 级别（如“跳楼大甩卖”、“独一无二”）：允许写入但必须强制将状态标记为 PENDING_AUDIT；
    - 若无违规：放行通过。

    Args:
        post_data (Dict[str, Any]): 帖子数据字典，包含 title, content, tags 等。

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]: (是否允许入库, 提示/拦截说明, 审计与风控元数据)
    """
    title = post_data.get("title", "")
    content = post_data.get("content", "")
    tags = post_data.get("tags", [])
    if isinstance(tags, list):
        tags_str = " ".join([str(t) for t in tags])
    else:
        tags_str = str(tags)

    full_post_text = f"{title}\n{content}\n{tags_str}"
    violations = scan_text_against_sensitive_words(full_post_text)

    if not violations:
        return True, None, {"risk_score": 0.0, "flagged_violations": []}

    blocked_violations = [v for v in violations if v["severity"] == "BLOCK"]
    approval_violations = [v for v in violations if v["severity"] == "REQUIRE_APPROVAL"]

    # 1. 存在严重违规 BLOCK
    if blocked_violations:
        viol_names = [v["word"] for v in blocked_violations]
        error_msg = f"发帖前置合规拦截：检测到严重违禁/极限词或虚假宣传词汇【{', '.join(viol_names)}】，违反《广告法》及平台规范，已自动阻断发布。"
        return False, error_msg, {
            "risk_score": 0.95,
            "blocked_words": viol_names,
            "flagged_violations": violations,
            "recommended_action": "BLOCK",
        }

    # 2. 存在中度风险 REQUIRE_APPROVAL
    if approval_violations:
        viol_names = [v["word"] for v in approval_violations]
        warn_msg = f"发帖合规预警：检测到可能存在夸大修辞或需核验促销用语【{', '.join(viol_names)}】，已自动将帖子标记为待人工审核(PENDING_AUDIT)。"
        return True, warn_msg, {
            "risk_score": 0.70,
            "warning_words": viol_names,
            "flagged_violations": violations,
            "recommended_action": "REQUIRE_APPROVAL",
        }

    # 3. 仅有轻度提示
    return True, None, {
        "risk_score": 0.30,
        "flagged_violations": violations,
        "recommended_action": "WARNING",
    }


def check_product_compliance_hook(product_data: Dict[str, Any]) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """在创建或修改商品前的拦截 Hook。

    Args:
        product_data (Dict[str, Any]): 商品数据。

    Returns:
        Tuple[bool, Optional[str], Dict[str, Any]]: (是否允许入库, 说明, 审计元数据)
    """
    title = product_data.get("title", "")
    desc = product_data.get("description", "")
    full_text = f"{title}\n{desc}"

    violations = scan_text_against_sensitive_words(full_text)
    if not violations:
        return True, None, {"risk_score": 0.0, "flagged_violations": []}

    blocked = [v for v in violations if v["severity"] == "BLOCK"]
    if blocked:
        viol_names = [v["word"] for v in blocked]
        return False, f"商品上架合规拦截：商品标题或详情包含违禁词【{', '.join(viol_names)}】，禁止录入。", {
            "risk_score": 0.95,
            "blocked_words": viol_names,
            "flagged_violations": violations,
        }

    approval = [v for v in violations if v["severity"] == "REQUIRE_APPROVAL"]
    if approval:
        viol_names = [v["word"] for v in approval]
        return True, f"商品合规预警：包含待核验宣传用语【{', '.join(viol_names)}】，商品已置为待审核(PENDING_AUDIT)。", {
            "risk_score": 0.65,
            "flagged_violations": violations,
            "force_status": "PENDING_AUDIT",
        }

    return True, None, {"risk_score": 0.20, "flagged_violations": violations}


def enforce_admin_double_confirmation(
    operator_role: UserRole | str,
    action_type: str,
    target_id: str,
    confirm_token: Optional[str],
    db_manager: DatabaseManager,
    operator_id: str = "ADMIN",
) -> Dict[str, Any]:
    """高危删除动作的 RBAC 角色鉴权与管理员二次确认 Hook。

    逻辑：
    1. 若角色不是 ADMIN：立即阻断，返回权限不足；
    2. 若未提供 confirm_token：生成一次性二次确认令牌并入库，阻断直接删除，向管理员下发确认请求；
    3. 若提供了 confirm_token：校验 Token 是否合法有效并立即作废（一次性消费），核验成功放行执行物理删除。

    Args:
        operator_role (UserRole | str): 操作人角色
        action_type (str): 操作类型，如 delete_product / delete_post
        target_id (str): 目标删除实体 ID
        confirm_token (Optional[str]): 二次确认防伪凭据
        db_manager (DatabaseManager): 数据库管理器实例
        operator_id (str): 操作人 ID

    Returns:
        Dict[str, Any]: 拦截或确认校验结果字典
    """
    role_str = operator_role.value if hasattr(operator_role, "value") else str(operator_role)
    if role_str.upper() != UserRole.ADMIN.value:
        return {
            "success": False,
            "status": "PERMISSION_DENIED",
            "message": f"权限不足：操作人角色为 [{role_str}]，高危删除操作 [{action_type}] 严格仅限系统超级管理员(ADMIN)操作。",
        }

    # 尚未提供二次确认 Token -> 生成确认令牌并拦截本次调用
    if not confirm_token or not confirm_token.strip():
        req = db_manager.create_confirmation_request(
            action_type=action_type,
            target_id=target_id,
            requested_by=operator_id,
            ttl_seconds=300,
        )
        # 记录审计日志
        db_manager.log_action(
            entity_type="confirmation",
            entity_id=target_id,
            action="confirm_request_generated",
            operator_id=operator_id,
            operator_role=UserRole.ADMIN,
            details={"action_type": action_type, "token": req.token, "expires_at": req.expires_at},
        )
        return {
            "success": False,
            "status": "CONFIRMATION_REQUIRED",
            "message": (
                f"高危操作拦截二次确认：正在尝试物理删除目标 [{action_type}: {target_id}]！"
                f"此操作不可逆。系统已生成管理员专属确认防伪凭证，请核对目标后携带 confirm_token 重新提交调用该工具以完成真正删除。"
            ),
            "confirm_token": req.token,
            "target_id": target_id,
            "action_type": action_type,
            "expires_at": req.expires_at,
        }

    # 已提供二次确认 Token -> 核验并消费
    ok, verify_msg = db_manager.verify_and_consume_token(
        token=confirm_token.strip(),
        action_type=action_type,
        target_id=target_id,
    )

    if not ok:
        return {
            "success": False,
            "status": "INVALID_TOKEN",
            "message": f"二次确认凭据核验失败：{verify_msg}",
        }

    # 二次确认核验成功
    return {
        "success": True,
        "status": "CONFIRMED",
        "message": f"管理员二次确认核验通过，准予执行删除 [{action_type}: {target_id}]。",
    }
