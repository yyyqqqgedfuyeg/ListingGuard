"""
Filename: schemas.py
Description: RAG 知识检索系统核心数据结构、RBAC 权限映射矩阵与 Pydantic 校验模型。
Author: Risk-Aware Agent Team
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SecurityLevel(str, Enum):
    """规章密级枚举 (由低至高)"""
    C1_PUBLIC = "C1_PUBLIC"
    C2_INTERNAL = "C2_INTERNAL"
    C3_RESTRICTED = "C3_RESTRICTED"
    C4_CONFIDENTIAL = "C4_CONFIDENTIAL"


class RoleEnum(str, Enum):
    """银行组织角色枚举"""
    PUBLIC = "PUBLIC"
    ALL = "ALL"
    TELLER = "TELLER"
    ACCOUNT_MANAGER = "ACCOUNT_MANAGER"
    BRANCH_HEAD = "BRANCH_HEAD"
    CREDIT_APPROVER = "CREDIT_APPROVER"
    AUDITOR = "AUDITOR"
    CHIEF_RISK_OFFICER = "CHIEF_RISK_OFFICER"
    CREDIT_COMMITTEE = "CREDIT_COMMITTEE"
    EXECUTIVE = "EXECUTIVE"


# RBAC 角色与可访问密级矩阵定义
ROLE_PERMISSIONS_MAP: Dict[str, List[str]] = {
    "PUBLIC": [SecurityLevel.C1_PUBLIC.value],
    "ALL": [SecurityLevel.C1_PUBLIC.value],
    "TELLER": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
    ],
    "ACCOUNT_MANAGER": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
    ],
    "BRANCH_HEAD": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
    ],
    "CREDIT_APPROVER": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
    ],
    "AUDITOR": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
    ],
    "CHIEF_RISK_OFFICER": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
        SecurityLevel.C4_CONFIDENTIAL.value,
    ],
    "CREDIT_COMMITTEE": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
        SecurityLevel.C4_CONFIDENTIAL.value,
    ],
    "EXECUTIVE": [
        SecurityLevel.C1_PUBLIC.value,
        SecurityLevel.C2_INTERNAL.value,
        SecurityLevel.C3_RESTRICTED.value,
        SecurityLevel.C4_CONFIDENTIAL.value,
    ],
}


def get_allowed_security_levels(role: str) -> List[str]:
    """根据给定的角色标识，获取其获准访问的安全密级列表。

    若角色未知或未授权，默认严格降级为最低安全级别 (仅 C1_PUBLIC)，杜绝权限泄露。

    Args:
        role (str): 角色字符串。

    Returns:
        List[str]: 允许读取的密级列表 (如 ['C1_PUBLIC', 'C2_INTERNAL'])。
    """
    normalized_role = (role or "").strip().upper()
    return ROLE_PERMISSIONS_MAP.get(normalized_role, [SecurityLevel.C1_PUBLIC.value])


class DocumentChunk(BaseModel):
    """规章条款切片数据结构。"""
    chunk_id: str = Field(..., description="切片全局唯一标识")
    doc_id: str = Field(..., description="所属原始文档代号 (如 DOC-C2-001)")
    title: str = Field(..., description="文档标题")
    security_level: str = Field(..., description="安全密级 (C1~C4)")
    allowed_roles: List[str] = Field(default_factory=list, description="显式允许的角色列表")
    department: Optional[str] = Field(default=None, description="主责归口部门")
    section: str = Field(default="", description="条款章节标题或条款编号")
    content: str = Field(..., description="条款切片正文内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="额外扩展元数据")


class RetrievalResult(BaseModel):
    """检索命中的单个条款片段与溯源信息。"""
    chunk: DocumentChunk = Field(..., description="命中的文档切片")
    dense_score: float = Field(default=0.0, description="稠密向量相似度得分")
    sparse_score: float = Field(default=0.0, description="BM25 稀疏检索得分")
    combined_score: float = Field(default=0.0, description="综合排序得分 (RRF或加权)")
    citation_tag: str = Field(..., description="条款级溯源标签，如 [来源: 《DOC-C2-002》第3.2条]")


class RAGQueryInput(BaseModel):
    """query_rag 工具的输入参数模型。"""
    query: str = Field(
        ...,
        description="针对华夏通商银行业务制度、利率、审批权限或合规条款的自然语言查询问题",
    )
