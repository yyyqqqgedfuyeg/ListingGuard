"""
Filename: report.py
Description: 商品上架合规审核终审报告实体，支撑多轮自省对比与审计回溯。
Author: ListingGuard Team
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from src.models.diagnosis import DiagnosisResult
from src.models.enums import Platform
from src.models.listing import ProductListing


class ComplianceReport(BaseModel):
    """商品上架终审合规报告。"""
    report_id: str = Field(description="报告唯一序列号")
    platform: Platform = Field(description="审核目标平台")
    original_listing: ProductListing = Field(description="原始待审商品信息")
    initial_diagnosis: DiagnosisResult = Field(description="初次扫描与法规溯源诊断结果")
    rewritten_title: Optional[str] = Field(default=None, description="合规改写后的商品标题")
    rewritten_description: Optional[str] = Field(default=None, description="合规改写后的商品详情文案")
    secondary_diagnosis: Optional[DiagnosisResult] = Field(default=None, description="改写后二次验证诊断结果")
    is_compliant: bool = Field(default=False, description="改写后最终是否合规通过")
    iteration_count: int = Field(default=0, description="自省迭代与改写重试轮数")
    user_action: Optional[str] = Field(default=None, description="用户人机协同处理行为 (APPROVED/REJECTED/MANUALLY_EDITED)")
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat(), description="报告生成时间")

    def to_markdown(self) -> str:
        """导出为格式化 Markdown 报告。

        Returns:
            str: 格式优美的审核报告文本。
        """
        status_badge = "✅ **已通过合规审核**" if self.is_compliant else "⚠️ **存在未解决风险**"
        lines = [
            f"# 🛡️ ListingGuard 商品上架合规审查报告",
            f"- **报告编号**: `{self.report_id}`",
            f"- **目标电商平台**: `{self.platform.value.upper()}`",
            f"- **生成时间**: `{self.created_at}`",
            f"- **最终合规状态**: {status_badge}",
            f"- **迭代优化轮次**: `{self.iteration_count}` 轮",
            "",
            "## 1. 原始商品信息",
            f"- **原始标题**: {self.original_listing.title}",
            f"- **商品类目**: {self.original_listing.category}",
            f"- **初检违规项总数**: `{self.initial_diagnosis.total_risks}` 个 (最高等级: `{self.initial_diagnosis.max_severity.value}`)",
            "",
            "### 命中违规项明细与法条溯源:",
        ]

        if not self.initial_diagnosis.violations:
            lines.append("*(未检测到明显违规项)*")
        else:
            for idx, v in enumerate(self.initial_diagnosis.violations, start=1):
                lines.append(
                    f"{idx}. **[{v.severity.value}] {v.category.value}** - 触发词/特征: `{v.trigger_pattern}`\n"
                    f"   - **上下文片段**: \"{v.context_snippet}\"\n"
                    f"   - **援引法规**: {v.cited_regulation or '暂无关联法条'}\n"
                    f"   - **法理说明**: {v.explanation}\n"
                    f"   - **优化建议**: {v.suggestion or '去除或替换为合规中性词汇'}"
                )

        lines.extend([
            "",
            "## 2. 智能合规优化文案 (保留营销卖点)",
            f"- **合规改写标题**: {self.rewritten_title or '无需修改'}",
            f"- **合规改写详情**: {self.rewritten_description or '无需修改'}",
            "",
            "## 3. 二次闭环扫描验证",
        ])

        if self.secondary_diagnosis:
            lines.append(f"- **二次复检违规数**: `{self.secondary_diagnosis.total_risks}` 个")
            if self.secondary_diagnosis.violations:
                for v in self.secondary_diagnosis.violations:
                    lines.append(f"  - ⚠️ 残留风险: `{v.trigger_pattern}` ({v.explanation})")
            else:
                lines.append("- ✨ **二次扫描 0 风险检出，满足上架合规要求！**")
        else:
            lines.append("- *(无需二次扫描)*")

        return "\n".join(lines)
