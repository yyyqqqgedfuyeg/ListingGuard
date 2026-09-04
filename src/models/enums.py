"""
Filename: enums.py
Description: 电商商品合规运营智能体枚举体系，定义电商平台、风险等级及违规类型。
Author: ListingGuard Team
"""

from enum import Enum


class Platform(str, Enum):
    """支持的电商与跨境电商平台枚举。"""
    TAOBAO = "taobao"          # 淘宝 / 天猫
    PDD = "pdd"                # 拼多多
    EBAY = "ebay"              # eBay 跨境电商
    GENERAL = "general"        # 通用电商 / 独立站


class Severity(str, Enum):
    """风险判定等级枚举。"""
    BLOCK = "BLOCK"                          # 严重违规：直接拦截禁止上架（如违禁品、严重违法虚假疗效、侵权）
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"    # 中度风险：需人工审核或整改后确认（如资质要求、夸大营销词）
    WARNING = "WARNING"                      # 轻度提示：建议优化文案提升合规性与转化率


class RiskCategory(str, Enum):
    """合规风险分类枚举。"""
    ABSOLUTE_CLAIM = "absolute_claim"              # 极限词 / 绝对化用语 (如: 全网第一, 最佳, 100%纯天然)
    FALSE_EFFICACY = "false_efficacy"              # 虚假宣传 / 医疗功效宣称 (如: 治愈, 根治, 降三高)
    PRICE_FRAUD = "price_fraud"                    # 价格欺诈 / 虚假促销 (如: 虚构原价, 跳楼大甩卖)
    PROHIBITED_GOODS = "prohibited_goods"          # 禁限售商品及成分 (如: 违禁化学品, 军警装备, 盗版软件)
    IP_INFRINGEMENT = "ip_infringement"            # 知识产权侵权 / VeRO违规 (如: 仿冒假货, 碰瓷大牌, 品牌词堆叠)
    FEEDBACK_MANIPULATION = "feedback_manipulation"# 操纵评价 (如: 好评返现, 加微信退款)
    QUALIFICATION_MISSING = "qualification_missing"# 资质与认证缺失 (如: 无FDA/CE认证宣称出口, 无食品生产许可证)
