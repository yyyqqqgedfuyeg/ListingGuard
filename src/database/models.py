"""
Filename: models.py
Description: ListingGuard 电商合规数据库模型，涵盖用户角色(RBAC)、商品、营销种草帖子、合规审计日志与二次确认凭据。
Author: ListingGuard Team
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.enums import Platform


class UserRole(str, Enum):
    """用户角色权限枚举 (RBAC)。"""
    ADMIN = "ADMIN"          # 系统管理员：全权操作，拥有高危删除执行与二次确认审核权限
    EMPLOYEE = "EMPLOYEE"    # 平台/运营审核员工：可查看内外规章、审核商品与帖子、触发合规检查
    CUSTOMER = "CUSTOMER"    # 客户/商家卖家：仅可访问外部公开规则与自有商品帖子，无敏感操作权限


class ProductStatus(str, Enum):
    """商品生命周期状态。"""
    DRAFT = "DRAFT"                      # 草稿待提交
    PENDING_AUDIT = "PENDING_AUDIT"      # 待合规审核（命中风险预警或人工质检）
    APPROVED = "APPROVED"                # 审核通过已上架
    REJECTED = "REJECTED"                # 违规驳回下架
    OFFLINE = "OFFLINE"                  # 商家主动下架


class PostStatus(str, Enum):
    """商品关联推广/种草帖子合规状态。"""
    DRAFT = "DRAFT"                      # 草稿
    PENDING_AUDIT = "PENDING_AUDIT"      # 待人工合规复核
    COMPLIANT = "COMPLIANT"              # 合规发布
    FLAGGED = "FLAGGED"                  # 存在违规风险已标红/拦截


class User(BaseModel):
    """系统用户模型。"""
    user_id: str = Field(description="用户唯一 ID，如 USR-ADMIN-001")
    username: str = Field(description="用户名/登录账号")
    role: UserRole = Field(description="用户角色：ADMIN / EMPLOYEE / CUSTOMER")
    display_name: str = Field(default="", description="显示名称或昵称")
    email: str = Field(default="", description="联系邮箱")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")


class Product(BaseModel):
    """商品数据库实体模型。"""
    product_id: str = Field(description="商品唯一编号，如 PROD-TB-001")
    platform: Platform = Field(default=Platform.TAOBAO, description="所属电商平台")
    title: str = Field(description="商品标题")
    description: str = Field(default="", description="商品详细文案与卖点")
    category: str = Field(default="general", description="商品类目")
    price: Optional[float] = Field(default=None, description="售价")
    original_price: Optional[float] = Field(default=None, description="划线原价")
    stock: int = Field(default=100, description="库存数量")
    status: ProductStatus = Field(default=ProductStatus.DRAFT, description="商品状态")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="商品结构化属性")
    images: List[str] = Field(default_factory=list, description="商品图片链接或存储路径")
    created_by: str = Field(default="", description="创建人用户 ID")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="更新时间")


class Post(BaseModel):
    """与商品关联的种草、推广及营销帖子实体模型。"""
    post_id: str = Field(description="帖子唯一编号，如 POST-001")
    product_id: str = Field(description="关联商品编号，关联 products 表")
    channel: str = Field(default="xiaohongshu", description="投放渠道，如 xiaohongshu / guangguang / weibo / tiktok")
    title: str = Field(description="帖子标题")
    content: str = Field(default="", description="帖子正文或种草文案")
    tags: List[str] = Field(default_factory=list, description="宣传标签或话题 tag")
    compliance_status: PostStatus = Field(default=PostStatus.DRAFT, description="合规状态")
    risk_score: float = Field(default=0.0, description="风险量化评分 (0.0~1.0)")
    flagged_violations: List[Dict[str, Any]] = Field(default_factory=list, description="命中的违规详情记录列表")
    author_id: str = Field(default="", description="创作者/发布人 ID")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="创建时间")
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="更新时间")


class AuditLog(BaseModel):
    """合规操作与审计日志模型。"""
    log_id: str = Field(description="日志唯一编号")
    entity_type: str = Field(description="实体类型: product / post / confirmation")
    entity_id: str = Field(description="实体编号")
    action: str = Field(description="操作动作: create / update / delete / audit / flag / confirm_request")
    operator_id: str = Field(description="操作人 ID")
    operator_role: UserRole = Field(description="操作人角色")
    details: Dict[str, Any] = Field(default_factory=dict, description="详细上下文或变更差异")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="审计时间")


class ConfirmationRequest(BaseModel):
    """高危动作二次确认申请单（管理员双重确认凭据）。"""
    token: str = Field(description="一次性确认防伪令牌")
    action_type: str = Field(description="高危动作类型，如 delete_product / delete_post")
    target_id: str = Field(description="目标删除对象 ID")
    requested_by: str = Field(description="申请人用户 ID")
    status: str = Field(default="PENDING", description="凭证状态: PENDING / CONFIRMED / EXPIRED / CANCELLED")
    expires_at: str = Field(description="过期失效时间")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="申请生成时间")
