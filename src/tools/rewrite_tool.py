"""
Filename: rewrite_tool.py
Description: 智能商品文案合规改写工具，剔除违规风险同时保留高转化营销卖点。
Author: ListingGuard Team
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import tool

from src.tools.scan_tool import _ensure_listing_model

# 规则替换安全同义词字典 (用于离线降级与确定性兜底)
COMPLIANCE_SUBSTITUTIONS = {
    # 极限词替换
    "全网第一": "热销口碑优选",
    "销量第一": "热销推荐",
    "全网最佳": "备受好评",
    "顶级": "高品质",
    "极品": "优选精选",
    "极致": "匠心呈现",
    "第一": "前沿推荐",
    "最": "十分",
    "独一无二": "别具匠心",
    "100%纯天然": "精选植物萃取成分",
    "永久有效": "长效持久",
    "彻底清除": "深层净澈",
    # 医疗功效替换为普通护理/营养描述
    "消炎": "舒缓修护屏障",
    "降三高": "日常营养滋补",
    "降血糖": "草本清新回甘",
    "根治": "温和调理养护",
    "治愈": "贴心呵护",
    "三天见效": "循序渐进呵护",
    "七天暴瘦": "健康轻盈体态",
    "不节食月瘦20斤": "均衡膳食好搭档",
    "强肾固本": "日常草本滋补",
    "排毒养颜神效": "轻盈舒畅好状态",
    # 价格欺诈与违规噱头
    "0元免费领": "限时拼单特惠",
    "不要钱白送": "超值拼购尝鲜",
    "工厂倒闭清库": "源头工厂直营直供",
    "老板跑路清仓": "精选换季回馈",
    "原价": "日常建议价",
    # 评价操纵
    "好评返现": "",
    "带图好评返": "",
    "好评返红包": "",
    "加微信返": "",
    # 迷信宣称
    "大师开光": "传统非遗匠作",
    "辟邪保平安": "吉祥祈福雅意",
    "招财转运": "寓意吉祥如意",
    # 跨境 VeRO 与受限
    "like Apple": "Compatible with Apple",
    "Apple style": "Minimalist Modern Aesthetic",
    "Rolex replica": "Classic Mechanical Luxury Design",
    "Gucci style": "Fashionable Stripe Pattern",
    "Chanel inspired": "Elegant Quilted Motif",
    "1:1 replica": "Custom Precision Craftsmanship",
    "high power laser 10000mw": "Class 2 Presentation Pointer <= 5mW",
    "burning laser pointer": "Office Presentation Pointer",
}


def _heuristic_rule_rewrite(title: str, description: str) -> Dict[str, str]:
    """使用合规替代词库对违规文案进行启发式安全改写。

    Args:
        title (str): 原标题。
        description (str): 原详情。

    Returns:
        Dict[str, str]: 改写后的 {"rewritten_title": ..., "rewritten_description": ...}。
    """
    new_title = title
    new_desc = description

    for bad_pat, safe_rep in COMPLIANCE_SUBSTITUTIONS.items():
        # 正则不区分大小写安全替换
        pattern = re.compile(re.escape(bad_pat), re.IGNORECASE)
        new_title = pattern.sub(safe_rep, new_title)
        new_desc = pattern.sub(safe_rep, new_desc)

    # 清理可能产生的双空格或断句瑕疵
    new_title = re.sub(r"\s+", " ", new_title).strip()
    new_desc = re.sub(r"\s+", " ", new_desc).strip()

    return {
        "rewritten_title": new_title,
        "rewritten_description": new_desc,
        "method": "heuristic_substitutions"
    }


@tool
def rewrite_compliant(
    listing: Dict[str, Any],
    violations: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """智能改写商品 Listing 标题与详情，在完全消除违规风险的同时保留核心营销卖点与转化率。

    Args:
        listing: 商品数据字典，包含 title、description、category 等。
        violations: 之前扫描检出的违规项列表（可选）。

    Returns:
        改写结果字典，包含 rewritten_title、rewritten_description 与 explanation。
    """
    model = _ensure_listing_model(listing)
    title = model.title
    desc = model.description

    # 如果有配置 LLM API Key 则优先调用大模型改写
    api_key = os.getenv("OPENAI_API_KEY") or os.getenv("DEEPSEEK_API_KEY")
    if api_key and api_key != "your_openai_or_deepseek_api_key_here":
        try:
            from src.agent.config import get_llm
            llm = get_llm(temperature=0.3)
            system_prompt = (
                "你是一位拥有十年经验的资深电商合规与爆款文案运营总监。\n"
                "你的任务是为商家修改违规商品文案。\n"
                "要求：\n"
                "1. 坚决剔除所有极限词(最/第一/100%纯天然/永久)、虚假医疗功效(降三高/消炎/根治)、价格欺诈(0元送/原价/清仓倒闭)及品牌侵权(like/replica)；\n"
                "2. 深度保留原商品的核心材质规格、技术参数、受众人群与核心营销卖点，语言通顺且具备高转化吸引力；\n"
                "3. 仅以合法的 JSON 格式返回，包含字段: 'rewritten_title' 和 'rewritten_description'。"
            )
            user_msg = (
                f"【商品类目】: {model.category}\n"
                f"【原标题】: {title}\n"
                f"【原详情】: {desc}\n"
                f"【检出违规项】: {json.dumps(violations or [], ensure_ascii=False)}\n"
                "请返回优化后的合规文案 JSON:"
            )
            response = llm.invoke([
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_msg)
            ])
            text = response.content.strip()
            # 尝试提取 JSON
            json_match = re.search(r"\{.*\}", text, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                return {
                    "rewritten_title": data.get("rewritten_title", title),
                    "rewritten_description": data.get("rewritten_description", desc),
                    "method": "llm_creative_rewrite"
                }
        except Exception:
            # 发生异常时平滑降级至启发式安全改写
            pass

    # 兜底：启发式安全改写
    res = _heuristic_rule_rewrite(title, desc)
    return res
