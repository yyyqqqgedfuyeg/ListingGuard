"""
Filename: prompt_hooks.py
Description: 大模型生成提示词与营销文案后的后置检查 Hook，扫描敏感词、极限词并注入合规护栏约束。
Author: ListingGuard Team
"""

from typing import Any, Dict, List, Optional

from src.hooks.sensitive_loader import SensitiveWordsRegistry
from src.hooks.tool_hooks import scan_text_against_sensitive_words


def inspect_generated_prompt_hook(
    text_or_prompt: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """大模型生成提示词或文案后的后置审查 Hook。

    功能：
    1. 敏感词深度扫描：依据 data/rules/sensitive_words.md 词库，检查大模型生成的提示词或商品文案是否含有极限词、虚假医疗宣称、价格欺诈等；
    2. 合规清洗建议：自动映射并生成安全无违规的合规修改替代版本 (sanitized_text)；
    3. 安全护栏自动注入：若检测到风险倾向，自动生成注入式的 Prompt Guardrail 约束指令，供下一次提示词迭代或下游节点规避违规。

    Args:
        text_or_prompt (str): LLM 生成的提示词、营销文案或指令文本。
        context (Optional[Dict[str, Any]]): 关联上下文，如所属平台 (taobao/pdd/ebay)、目标品类等。

    Returns:
        Dict[str, Any]: 审查报告，包含通过状态、风险等级、检出敏感词、清洗后文本及推荐注入护栏。
    """
    if not text_or_prompt or not text_or_prompt.strip():
        return {
            "passed": True,
            "risk_level": "SAFE",
            "detected_violations": [],
            "suggested_replacements": {},
            "sanitized_text": text_or_prompt,
            "injected_guardrails": [],
            "audit_report": "提示词为空，无合规风险。",
        }

    violations = scan_text_against_sensitive_words(text_or_prompt)
    replacement_map = SensitiveWordsRegistry.get_replacement_map()

    # 生成安全替换版本
    sanitized_text = text_or_prompt
    suggested_replacements = {}
    for v in violations:
        word = v["word"]
        rep = v.get("recommended_replacement") or replacement_map.get(word, "优质推荐")
        suggested_replacements[word] = rep
        sanitized_text = sanitized_text.replace(word, rep)

    blocked = [v for v in violations if v["severity"] == "BLOCK"]
    approval = [v for v in violations if v["severity"] == "REQUIRE_APPROVAL"]

    # 动态组装合规护栏指令
    injected_guardrails = [
        "【电商合规红线提示】必须严格遵守《中华人民共和国广告法》及各平台入驻规范：",
        "1. 严禁使用'全网第一'、'最好'、'顶级'、'100%'等绝对化极限词；",
        "2. 非药品医疗器械严禁宣称'治愈'、'根治'、'降三高'等医疗功效；",
        "3. 严禁使用'虚构原价'、'跳楼大甩卖'等误导消费者的虚假促销价格宣称；",
        "4. 严禁在文案中诱导'好评返现'或引导站外私下交易。",
    ]

    if blocked:
        risk_level = "BLOCKED"
        passed = False
        blocked_words = [v["word"] for v in blocked]
        report = (
            f"提示词后置拦截：文本中检出严重违禁词汇 [{', '.join(blocked_words)}]，"
            f"直接违反法律红线，必须进行合规替换后方可使用。"
        )
    elif approval:
        risk_level = "WARNING"
        passed = True
        warn_words = [v["word"] for v in approval]
        report = (
            f"提示词合规预警：文本中检出可能引起夸大营销争议的用语 [{', '.join(warn_words)}]，"
            f"建议采纳合规替代词以降低平台限流风险。"
        )
    elif violations:
        risk_level = "WARNING"
        passed = True
        report = "提示词包含轻微优化提示用语，整体风险可控。"
    else:
        risk_level = "SAFE"
        passed = True
        report = "提示词通过合规安全审查，未检出敏感违禁词汇。"

    return {
        "passed": passed,
        "risk_level": risk_level,
        "detected_violations": violations,
        "suggested_replacements": suggested_replacements,
        "sanitized_text": sanitized_text,
        "injected_guardrails": injected_guardrails,
        "audit_report": report,
    }
