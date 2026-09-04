"""
Filename: retriever.py
Description: 基于倒数排名融合 (RRF) 与平台过滤的混合检索器 (Hybrid Regulation Retriever)。
Author: ListingGuard Team
"""

from typing import Dict, List, Optional
from src.models.enums import Platform
from src.rag.indexer import RegulationIndexer
from src.rag.schemas import RegulationChunk, RetrievalResult


class RegulationRetriever:
    """合规法规知识库混合检索器。"""

    def __init__(self, indexer: Optional[RegulationIndexer] = None):
        """初始化混合检索器。

        Args:
            indexer (Optional[RegulationIndexer], optional): 索引器实例。
        """
        self.indexer = indexer or RegulationIndexer()

    def search(
        self,
        query: str,
        platform: Optional[Platform] = None,
        top_k: int = 3,
        rrf_k: int = 60
    ) -> List[RetrievalResult]:
        """执行密集向量与 BM25 稀疏混合检索并使用 RRF 进行排名融合。

        Args:
            query (str): 检索自然语言查询词或违规描述。
            platform (Optional[Platform], optional): 限定电商平台（会自动包含通用法律）。
            top_k (int, optional): 返回的最相关条款数量。默认为 3。
            rrf_k (int, optional): RRF 平滑常数。默认为 60。

        Returns:
            List[RetrievalResult]: 排序后的检索结果。
        """
        if not query or not self.indexer.chunks:
            return []

        chunk_map: Dict[str, RegulationChunk] = {c.chunk_id: c for c in self.indexer.chunks}

        # 1. 密集向量检索
        dense_results = self.indexer.collection.query(
            query_texts=[query],
            n_results=min(top_k * 4, len(self.indexer.chunks))
        )

        dense_ranks: Dict[str, int] = {}
        if dense_results and "ids" in dense_results and dense_results["ids"]:
            for rank, cid in enumerate(dense_results["ids"][0], start=1):
                dense_ranks[cid] = rank

        # 2. 稀疏 BM25 检索
        sparse_ranks: Dict[str, int] = {}
        if self.indexer.bm25:
            tokens = self.indexer.tokenize(query)
            if tokens:
                bm25_scores = self.indexer.bm25.get_scores(tokens)
                scored_indices = sorted(
                    range(len(bm25_scores)),
                    key=lambda i: bm25_scores[i],
                    reverse=True
                )
                for rank, idx in enumerate(scored_indices[: top_k * 4], start=1):
                    cid = self.indexer.chunks[idx].chunk_id
                    sparse_ranks[cid] = rank

        # 3. 收集所有候选 ID
        candidate_ids = set(dense_ranks.keys()).union(set(sparse_ranks.keys()))

        # 4. RRF 评分融合与平台过滤
        scored_results: List[RetrievalResult] = []
        for cid in candidate_ids:
            chunk = chunk_map.get(cid)
            if not chunk:
                continue

            # 平台过滤：若指定平台，只保留该平台专属规则或通用国家法律
            if platform and platform != Platform.GENERAL:
                if chunk.platform != platform and chunk.platform != Platform.GENERAL:
                    continue

            d_rank = dense_ranks.get(cid, 999)
            s_rank = sparse_ranks.get(cid, 999)

            # 计算 RRF 分数
            rrf_score = (1.0 / (rrf_k + d_rank)) + (1.0 / (rrf_k + s_rank))

            scored_results.append(
                RetrievalResult(
                    chunk=chunk,
                    score=rrf_score,
                    dense_rank=d_rank if d_rank != 999 else None,
                    sparse_rank=s_rank if s_rank != 999 else None,
                    retrieval_method="hybrid_rrf"
                )
            )

        # 按 RRF 得分降序排序
        scored_results.sort(key=lambda r: r.score, reverse=True)
        return scored_results[:top_k]
