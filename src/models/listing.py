"""
Filename: listing.py
Description: 商品 Listing 结构体模型定义，支持多平台标准化入参及属性扩展。
Author: ListingGuard Team
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from src.models.enums import Platform


class ProductListing(BaseModel):
    """商品上架信息模型（Listing）。

    包含商品基本信息、标题、商品详情文案、类目、价格以及多平台特有属性。
    """
    listing_id: str = Field(description="商品唯一标识 ID")
    platform: Platform = Field(default=Platform.GENERAL, description="目标电商平台")
    title: str = Field(description="商品上架标题")
    description: str = Field(default="", description="商品主详情、规格及营销卖点说明文案")
    category: str = Field(default="general", description="商品品类，如 美妆个护、食品保健、3C数码、服饰箱包")
    price: Optional[float] = Field(default=None, description="销售标价（单位：元或美元）")
    original_price: Optional[float] = Field(default=None, description="划线原价/参考价")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="商品结构化属性键值对（如品牌、产地、功效、材质）")
    images_text: List[str] = Field(default_factory=list, description="商品主图及详情图 OCR 识别出的文字内容列表")

    def full_text(self) -> str:
        """拼接完整的商品文本用于文本扫描。

        Returns:
            str: 拼接标题、详情及属性文本的长字符串。
        """
        parts = [f"标题: {self.title}", f"详情: {self.description}"]
        if self.attributes:
            attr_str = " | ".join([f"{k}: {v}" for k, v in self.attributes.items()])
            parts.append(f"属性: {attr_str}")
        if self.images_text:
            parts.append("图片文字: " + " ".join(self.images_text))
        return "\n".join(parts)
