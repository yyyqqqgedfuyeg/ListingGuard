"""
Filename: loader.py
Description: 声明式 YAML 规则文件解析与动态热重载器。
Author: ListingGuard Team
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

from src.models.enums import Platform, RiskCategory, Severity


class RuleDefinition:
    """内部规则定义对象。"""

    def __init__(
        self,
        rule_id: str,
        name: str,
        category: RiskCategory,
        severity: Severity,
        description: str,
        patterns: List[str],
        cited_regulation: Optional[str] = None,
        explanation: str = "",
        suggestion: Optional[str] = None,
        is_regex: bool = False,
    ):
        self.rule_id = rule_id
        self.name = name
        self.category = category
        self.severity = severity
        self.description = description
        self.patterns = patterns
        self.cited_regulation = cited_regulation
        self.explanation = explanation
        self.suggestion = suggestion
        self.is_regex = is_regex

    def __repr__(self) -> str:
        return f"<RuleDefinition id={self.rule_id} name={self.name} severity={self.severity.value}>"


class RuleLoader:
    """规则加载管理器，从 configs/rules 目录加载各平台合规策略。"""

    DEFAULT_RULES_DIR = Path(__file__).resolve().parent.parent.parent / "configs" / "rules"

    @classmethod
    def load_rule_file(cls, filepath: Path) -> List[RuleDefinition]:
        """读取并解析单个 YAML 规则文件。

        Args:
            filepath (Path): YAML 文件路径。

        Returns:
            List[RuleDefinition]: 解析后的规则定义列表。
        """
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or "rules" not in data:
            return []

        rule_defs: List[RuleDefinition] = []
        for r in data["rules"]:
            cat_str = r.get("category", "absolute_claim")
            try:
                category = RiskCategory(cat_str)
            except ValueError:
                category = RiskCategory.ABSOLUTE_CLAIM

            sev_str = r.get("severity", "BLOCK")
            try:
                severity = Severity(sev_str)
            except ValueError:
                severity = Severity.BLOCK

            rule_defs.append(
                RuleDefinition(
                    rule_id=r.get("id", "UNKNOWN"),
                    name=r.get("name", "unnamed_rule"),
                    category=category,
                    severity=severity,
                    description=r.get("description", ""),
                    patterns=r.get("patterns", []),
                    cited_regulation=r.get("cited_regulation"),
                    explanation=r.get("explanation", ""),
                    suggestion=r.get("suggestion"),
                    is_regex=r.get("is_regex", False),
                )
            )

        return rule_defs

    @classmethod
    def load_rules_for_platform(
        cls,
        platform: Platform,
        rules_dir: Optional[Path] = None
    ) -> List[RuleDefinition]:
        """加载适用于指定电商平台的全部合规规则（含通用广告法通用规则）。

        Args:
            platform (Platform): 目标平台 (taobao/pdd/ebay/general)。
            rules_dir (Optional[Path], optional): 自定义规则目录。默认为 None。

        Returns:
            List[RuleDefinition]: 规则集合。
        """
        target_dir = rules_dir or cls.DEFAULT_RULES_DIR
        rules: List[RuleDefinition] = []

        # 1. 始终加载通用《广告法》基础规则
        adv_file = target_dir / "advertising_law.yaml"
        if adv_file.exists():
            rules.extend(cls.load_rule_file(adv_file))

        # 2. 平台专属规则文件映射
        platform_file_map = {
            Platform.TAOBAO: "taobao_rules.yaml",
            Platform.PDD: "pdd_rules.yaml",
            Platform.EBAY: "ebay_rules.yaml",
        }

        specific_filename = platform_file_map.get(platform)
        if specific_filename:
            p_file = target_dir / specific_filename
            if p_file.exists():
                rules.extend(cls.load_rule_file(p_file))

        return rules
