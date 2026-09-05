"""
Filename: sensitive_loader.py
Description: 解析 data/rules/sensitive_words.md 文档中的敏感词、违禁词与夸大宣称词库，为 Hook 机制提供配置支撑。
Author: ListingGuard Team
"""

import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class SensitiveWordEntry:
    """敏感词条目定义。"""

    def __init__(
        self,
        word: str,
        category: str,
        severity: str,
        replacement: Optional[str] = None,
        reason: str = "",
    ):
        self.word = word
        self.category = category
        self.severity = severity  # BLOCK / REQUIRE_APPROVAL / WARNING
        self.replacement = replacement
        self.reason = reason

    def __repr__(self) -> str:
        return f"<SensitiveWord word={self.word} sev={self.severity} cat={self.category}>"


class SensitiveWordsRegistry:
    """敏感词文档注册中心，从 Markdown 规范文档动态解析词库。"""

    DEFAULT_DOC_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "rules" / "sensitive_words.md"

    _cached_entries: Optional[List[SensitiveWordEntry]] = None
    _cached_replacements: Optional[Dict[str, str]] = None

    @classmethod
    def load_from_markdown(cls, md_path: Optional[Path] = None) -> List[SensitiveWordEntry]:
        """读取并解析 sensitive_words.md。"""
        doc_file = md_path or cls.DEFAULT_DOC_PATH
        if not doc_file.exists():
            return cls._get_fallback_entries()

        content = doc_file.read_text(encoding="utf-8")
        entries: List[SensitiveWordEntry] = []

        # 正则匹配表格中的行: | 类别 | `词1`、`词2` | **BLOCK...** | `替代词` 或 说明 |
        table_row_pattern = re.compile(
            r"\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|"
        )

        current_category = "general_sensitive"
        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("## "):
                # 记录主分类
                if "绝对化" in line_str or "极限词" in line_str:
                    current_category = "absolute_claim"
                elif "医疗功效" in line_str or "虚假宣传" in line_str:
                    current_category = "false_efficacy"
                elif "价格欺诈" in line_str:
                    current_category = "price_fraud"
                elif "查禁" in line_str or "违禁品" in line_str:
                    current_category = "prohibited_goods"
                elif "夸大" in line_str:
                    current_category = "exaggeration"

            match = table_row_pattern.match(line_str)
            if match:
                col1, col2, col3, col4 = match.groups()
                # 忽略表头与分割线
                if "---" in col1 or "违规类型" in col1:
                    continue

                words_raw = col2
                # 提取被反引号包裹的关键词或者按顿号/逗号切分
                raw_words = re.findall(r"`([^`]+)`", words_raw)
                if not raw_words:
                    raw_words = [w.strip() for w in re.split(r"[、，,]", words_raw) if w.strip()]

                # 解析严重等级
                severity = "BLOCK"
                if "REQUIRE_APPROVAL" in col3 or "人工审核" in col3:
                    severity = "REQUIRE_APPROVAL"
                elif "WARNING" in col3 or "提示" in col3:
                    severity = "WARNING"

                # 解析替代词
                replacements = re.findall(r"`([^`]+)`", col4)
                first_rep = replacements[0] if replacements else None

                for w in raw_words:
                    w = w.strip()
                    if w:
                        entries.append(
                            SensitiveWordEntry(
                                word=w,
                                category=current_category,
                                severity=severity,
                                replacement=first_rep,
                                reason=col4.strip(),
                            )
                        )

        if not entries:
            return cls._get_fallback_entries()

        cls._cached_entries = entries
        return entries

    @classmethod
    def get_entries(cls) -> List[SensitiveWordEntry]:
        """获取所有已加载的敏感词。"""
        if cls._cached_entries is None:
            cls.load_from_markdown()
        return cls._cached_entries or cls._get_fallback_entries()

    @classmethod
    def get_replacement_map(cls) -> Dict[str, str]:
        """获取敏感词 -> 推荐替代词映射字典。"""
        if cls._cached_replacements is not None:
            return cls._cached_replacements

        entries = cls.get_entries()
        rep_map = {}
        for e in entries:
            if e.replacement:
                rep_map[e.word] = e.replacement
            elif e.category == "absolute_claim":
                rep_map[e.word] = "精选好物"
            elif e.category == "false_efficacy":
                rep_map[e.word] = "温和修护"
            elif e.category == "price_fraud":
                rep_map[e.word] = "特惠专享价"
            else:
                rep_map[e.word] = "推荐精选"

        cls._cached_replacements = rep_map
        return rep_map

    @classmethod
    def _get_fallback_entries(cls) -> List[SensitiveWordEntry]:
        """内置默认词库保底。"""
        defaults = [
            ("全网第一", "absolute_claim", "BLOCK", "精选好物"),
            ("顶级", "absolute_claim", "BLOCK", "品质优选"),
            ("最好", "absolute_claim", "BLOCK", "备受好评"),
            ("最佳", "absolute_claim", "BLOCK", "推荐好物"),
            ("100%纯天然", "absolute_claim", "BLOCK", "天然萃取"),
            ("100%有效", "absolute_claim", "BLOCK", "助您改善"),
            ("一秒见效", "exaggeration", "BLOCK", "快速吸收"),
            ("治愈", "false_efficacy", "BLOCK", "改善舒缓"),
            ("根治", "false_efficacy", "BLOCK", "深层呵护"),
            ("降三高", "false_efficacy", "BLOCK", "日常膳食调理"),
            ("降血压", "false_efficacy", "BLOCK", "营养补充"),
            ("降血糖", "false_efficacy", "BLOCK", "均衡营养"),
            ("防癌", "false_efficacy", "BLOCK", "健康养护"),
            ("抗癌", "false_efficacy", "BLOCK", "健康养护"),
            ("药效", "false_efficacy", "BLOCK", "温和呵护"),
            ("跳楼大甩卖", "price_fraud", "REQUIRE_APPROVAL", "限时促销"),
            ("亏本甩卖", "price_fraud", "REQUIRE_APPROVAL", "年终特惠"),
            ("原价9999现价9.9", "price_fraud", "BLOCK", "特惠价格"),
            ("好评返现", "prohibited_goods", "BLOCK", "优质服务"),
            ("高仿", "prohibited_goods", "BLOCK", "经典设计"),
            ("A货", "prohibited_goods", "BLOCK", "精工制造"),
        ]
        return [
            SensitiveWordEntry(word=d[0], category=d[1], severity=d[2], replacement=d[3])
            for d in defaults
        ]
