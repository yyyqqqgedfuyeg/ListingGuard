"""
Filename: engine.py
Description: 电商商品上架合规规则判定核心引擎，负责多字段扫描、风险归因与诊断生成。
Author: ListingGuard Team
"""

from typing import List, Optional
from pathlib import Path

from src.models.enums import Platform, Severity
from src.models.listing import ProductListing
from src.models.violation import ViolationItem
from src.models.diagnosis import DiagnosisResult
from src.rules.loader import RuleLoader, RuleDefinition
from src.rules.matcher import TextMatcher


class RuleEngine:
    """电商合规规则执行引擎。"""

    def __init__(self, rules_dir: Optional[Path] = None):
        """初始化规则引擎。

        Args:
            rules_dir (Optional[Path], optional): 规则配置文件所在目录。默认为 None。
        """
        self.rules_dir = rules_dir

    def scan_listing(self, listing: ProductListing) -> List[ViolationItem]:
        """对给定的商品 Listing 进行全量合规规则扫描。

        Args:
            listing (ProductListing): 待检测的商品 Listing。

        Returns:
            List[ViolationItem]: 检测到的违规证据列表。
        """
        rules: List[RuleDefinition] = RuleLoader.load_rules_for_platform(
            platform=listing.platform,
            rules_dir=self.rules_dir
        )

        violations: List[ViolationItem] = []
        seen_keys = set()
        violation_counter = 1

        # 扫描目标字段定义：(字段名称, 字段文本内容)
        targets = [
            ("title", listing.title),
            ("description", listing.description),
        ]

        if listing.attributes:
            attr_text = " | ".join([f"{k}: {v}" for k, v in listing.attributes.items()])
            targets.append(("attributes", attr_text))

        if listing.images_text:
            img_text = " ".join(listing.images_text)
            targets.append(("images_text", img_text))

        for location, text in targets:
            if not text:
                continue

            for rule in rules:
                for pattern in rule.patterns:
                    matches = TextMatcher.search_pattern(
                        text=text,
                        pattern=pattern,
                        is_regex=rule.is_regex
                    )

                    for matched_str, start, end, snippet in matches:
                        # 避免同一字段中完全重复的 pattern 产生冗余报警
                        dedup_key = (rule.rule_id, location, matched_str.lower(), snippet)
                        if dedup_key in seen_keys:
                            continue
                        seen_keys.add(dedup_key)

                        violations.append(
                            ViolationItem(
                                violation_id=f"VIO-{listing.listing_id}-{violation_counter:03d}",
                                category=rule.category,
                                severity=rule.severity,
                                trigger_pattern=matched_str,
                                location=location,
                                context_snippet=snippet,
                                cited_regulation=rule.cited_regulation,
                                explanation=rule.explanation or rule.description,
                                suggestion=rule.suggestion,
                            )
                        )
                        violation_counter += 1

        return violations

    def diagnose_listing(self, listing: ProductListing) -> DiagnosisResult:
        """执行商品合规诊断，输出聚合后的诊断报告对象。

        Args:
            listing (ProductListing): 待诊断商品 Listing。

        Returns:
            DiagnosisResult: 聚合后的诊断结果。
        """
        violations = self.scan_listing(listing)
        total_risks = len(violations)

        if total_risks == 0:
            return DiagnosisResult(
                listing_id=listing.listing_id,
                total_risks=0,
                max_severity=Severity.WARNING,
                violations=[],
                legal_citations=[],
                can_auto_rewrite=True,
                summary="✅ 商品上架信息初检合格，未发现违反平台规定或广告法的违规项。"
            )

        # 计算最高严重级别
        has_block = any(v.severity == Severity.BLOCK for v in violations)
        has_approval = any(v.severity == Severity.REQUIRE_APPROVAL for v in violations)

        if has_block:
            max_severity = Severity.BLOCK
        elif has_approval:
            max_severity = Severity.REQUIRE_APPROVAL
        else:
            max_severity = Severity.WARNING

        # 收集法条引用列表
        citations = []
        seen_regs = set()
        for v in violations:
            if v.cited_regulation and v.cited_regulation not in seen_regs:
                citations.append({
                    "regulation": v.cited_regulation,
                    "reason": v.explanation,
                    "category": v.category.value
                })
                seen_regs.add(v.cited_regulation)

        summary = (
            f"⚠️ 检测到 {total_risks} 处合规风险 (最高等级: {max_severity.value})。"
            f"主要涉及 {', '.join({v.category.value for v in violations})}。"
        )

        return DiagnosisResult(
            listing_id=listing.listing_id,
            total_risks=total_risks,
            max_severity=max_severity,
            violations=violations,
            legal_citations=citations,
            can_auto_rewrite=True,
            summary=summary
        )
