"""
Filename: schemas.py
Description: 电商合规法律法规 RAG 知识检索系统数据结构契约定义。
Author: ListingGuard Team
"""

from typing import Any, Dict, Optional
from pydantic import BaseModel, Field

from src.models.enums import Platform


class RegulationChunk(BaseModel):
    """法律法规与电商平台规则条款级知识切片。"""
    chunk_id: str = Field(description="切片全局唯一标识")
    doc_name: str = Field(description="法规或官方规范文件名称")
    platform: Platform = Field(default=Platform.GENERAL, description="所属电商平台或通用法律")
    chapter: str = Field(default="", description="所属章节标题")
    article: str = Field(description="具体条款编号与条目标题，例如：'第九条 【广告绝对化用语】'")
    content: str = Field(description="条款全文正文内容")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展元数据")


class RetrievalResult(BaseModel):
    """检索返回的候选法规条款及评分详情。"""
    chunk: RegulationChunk = Field(description="命中的法规条款切片")
    score: float = Field(description="综合相关性得分或 RRF 融合分")
    dense_rank: Optional[int] = Field(default=None, description="密集向量检索排名")
    sparse_rank: Optional[int] = Field(default=None, description="BM25 关键词检索排名")
    retrieval_method: str = Field(default="hybrid_rrf", description="检索算法 (hybrid_rrf/dense/bm25)")

    def to_citation_dict(self) -> Dict[str, Any]:
        """转化为诊断报告使用的精简法条引用字典。

        Returns:
            Dict[str, Any]: 包含条款号、法规名及核心正文引述的字典。
        """
        return {
            "regulation": f"{self.chunk.doc_name} {self.chunk.article}",
            "doc_name": self.chunk.doc_name,
            "article": self.chunk.article,
            "platform": self.chunk.platform.value,
            "score": round(self.score, 4),
            "snippet": self.chunk.content[:200] + ("..." if len(self.chunk.content) > 200 else "")
        }
