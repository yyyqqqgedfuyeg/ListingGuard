"""
Filename: diagnosis.py
Description: 商品 Listing 合规诊断聚合分析结果实体。
Author: ListingGuard Team
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field

from src.models.enums import Severity
from src.models.violation import ViolationItem


class DiagnosisResult(BaseModel):
    """商品 Listing 综合合规诊断报告对象。"""
    listing_id: str = Field(description="对应的商品 ID")
    total_risks: int = Field(default=0, description="命中违规项总数")
    max_severity: Severity = Field(default=Severity.WARNING, description="全局最高风险等级")
    violations: List[ViolationItem] = Field(default_factory=list, description="违规项详情列表")
    legal_citations: List[Dict[str, Any]] = Field(default_factory=list, description="通过 RAG 检索匹配的权威法规及条款信息")
    can_auto_rewrite: bool = Field(default=True, description="是否支持大模型自动化改写修复")
    summary: str = Field(default="", description="合规诊断综述")
