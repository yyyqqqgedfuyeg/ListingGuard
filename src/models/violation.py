"""
Filename: violation.py
Description: 商品合规违规判定实体与证据链结构定义。
Author: ListingGuard Team
"""

from typing import Optional
from pydantic import BaseModel, Field

from src.models.enums import RiskCategory, Severity


class ViolationItem(BaseModel):
    """单个合规违规证据实体。"""
    violation_id: str = Field(description="违规项唯一标识")
    category: RiskCategory = Field(description="风险类别")
    severity: Severity = Field(description="风险严重程度 (BLOCK/REQUIRE_APPROVAL/WARNING)")
    trigger_pattern: str = Field(description="命中的关键词、敏感正则或规则名称")
    location: str = Field(default="title", description="违规位置，如 title, description, attributes")
    context_snippet: str = Field(description="包含违规词的上下文句子或片段")
    cited_regulation: Optional[str] = Field(default=None, description="匹配的法律法规或平台规则条款（如《广告法》第9条）")
    explanation: str = Field(description="违规原因与法理解释")
    suggestion: Optional[str] = Field(default=None, description="合规修改建议或替代词汇")
