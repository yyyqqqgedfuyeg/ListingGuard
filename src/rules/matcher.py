"""
Filename: matcher.py
Description: 高性能文本模式匹配器，支持不区分大小写、正则与上下文句子截取。
Author: ListingGuard Team
"""

import re
from typing import List, Optional, Tuple


class TextMatcher:
    """提供精准匹配与敏感词命中定位的工具类。"""

    @staticmethod
    def extract_context_snippet(text: str, match_start: int, match_end: int, window: int = 30) -> str:
        """根据匹配起止下标截取周围上下文句子片段。

        Args:
            text (str): 待截取完整文本。
            match_start (int): 关键词命中起始索引。
            match_end (int): 关键词命中结束索引。
            window (int, optional): 上下文延伸字符数。默认为 30。

        Returns:
            str: 格式化的上下文截取片段。
        """
        start = max(0, match_start - window)
        end = min(len(text), match_end + window)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(text) else ""
        return f"{prefix}{text[start:end].strip()}{suffix}"

    @classmethod
    def search_pattern(
        cls,
        text: str,
        pattern: str,
        is_regex: bool = False
    ) -> List[Tuple[str, int, int, str]]:
        """在文本中检索模式词并返回所有匹配结果及上下文。

        Args:
            text (str): 待检索文本。
            pattern (str): 敏感模式或关键词。
            is_regex (bool, optional): 是否作为正则表达式处理。默认为 False。

        Returns:
            List[Tuple[str, int, int, str]]: 列表项为 (命中词, start_idx, end_idx, context_snippet)。
        """
        if not text or not pattern:
            return []

        results: List[Tuple[str, int, int, str]] = []
        try:
            if is_regex:
                regex_obj = re.compile(pattern, re.IGNORECASE)
            else:
                regex_obj = re.compile(re.escape(pattern), re.IGNORECASE)

            for match in regex_obj.finditer(text):
                start, end = match.span()
                matched_str = match.group()
                snippet = cls.extract_context_snippet(text, start, end)
                results.append((matched_str, start, end, snippet))
        except Exception:
            # 防御性回退：普通子串匹配
            lower_text = text.lower()
            lower_pat = pattern.lower()
            idx = lower_text.find(lower_pat)
            while idx != -1:
                end = idx + len(pattern)
                snippet = cls.extract_context_snippet(text, idx, end)
                results.append((text[idx:end], idx, end, snippet))
                idx = lower_text.find(lower_pat, end)

        return results
