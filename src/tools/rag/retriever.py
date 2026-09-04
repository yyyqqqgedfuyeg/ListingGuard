"""
Filename: retriever.py
Description: 华夏通商银行 RAG 混合检索器，集成 RBAC 密级前置过滤、Dense+BM25 双轨召回与 RRF 融合排序。
Author: Risk-Aware Agent Team
"""

import os
import pickle
from typing import Any, Dict, List, Optional
import chromadb
import jieba

from src.tools.rag.indexer import EmbeddingProvider
from src.tools.rag.schemas import (
    DocumentChunk,
    RetrievalResult,
    SecurityLevel,
    get_allowed_security_levels,
)


class HybridRAGRetriever:
    """具备 RBAC 严格隔离的混合检索器 (Chroma Dense + BM25 Sparse)。"""

    def __init__(
        self,
        persist_dir: str = "data/chroma_db",
        bm25_path: str = "data/bm25_index.pkl",
        collection_name: str = "hcb_regulations",
        embedding_provider: Optional[EmbeddingProvider] = None,
        dense_weight: float = 0.5,
        bm25_weight: float = 0.5,
        rrf_k: int = 60,
    ):
        """初始化混合检索器。

        Args:
            persist_dir (str): ChromaDB 持久化存储路径。
            bm25_path (str): BM25 序列化文件路径。
            collection_name (str): 集合名称。
            embedding_provider (Optional[EmbeddingProvider]): 向量模型提供者。
            dense_weight (float): 稠密向量权重。默认为 0.5。
            bm25_weight (float): 稀疏 BM25 权重。默认为 0.5。
            rrf_k (int): RRF 平滑常数。默认为 60。
        """
        self.persist_dir = persist_dir
        self.bm25_path = bm25_path
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider or EmbeddingProvider()
        self.dense_weight = dense_weight
        self.bm25_weight = bm25_weight
        self.rrf_k = rrf_k

        # 初始化连接 ChromaDB
        self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(name=self.collection_name)

        # 加载 BM25 稀疏模型
        self.bm25_model = None
        self.chunks_map: Dict[str, DocumentChunk] = {}
        self.bm25_chunks: List[DocumentChunk] = []
        self._load_bm25_index()

    def _load_bm25_index(self):
        """从本地加载 BM25 索引。"""
        if os.path.exists(self.bm25_path):
            with open(self.bm25_path, "rb") as f:
                data = pickle.load(f)
            self.bm25_model = data.get("bm25_model")
            raw_chunks = data.get("chunks", [])
            self.bm25_chunks = [DocumentChunk(**c) for c in raw_chunks]
            self.chunks_map = {c.chunk_id: c for c in self.bm25_chunks}

    def retrieve(
        self,
        query: str,
        user_role: str = "PUBLIC",
        top_k: int = 3,
    ) -> List[RetrievalResult]:
        """执行带 RBAC 密级过滤的混合检索。

        Args:
            query (str): 自然语言查询问题。
            user_role (str, optional): 调用者的身份角色。默认为 'PUBLIC'。
            top_k (int, optional): 返回的最相关切片数量。默认为 3。

        Returns:
            List[RetrievalResult]: 排序后的检索结果列表。
        """
        if not query or not query.strip():
            return []

        # 1. 计算当前角色被授权的密级集合 (RBAC 前置过滤核心)
        allowed_levels = get_allowed_security_levels(user_role)
        if not allowed_levels:
            return []

        # 2. Chroma 稠密向量检索 (带 where 过滤)
        dense_ranked_ids: List[str] = []
        dense_scores_map: Dict[str, float] = {}

        if len(allowed_levels) == 1:
            where_clause = {"security_level": allowed_levels[0]}
        else:
            where_clause = {"security_level": {"$in": allowed_levels}}

        try:
            query_embedding = self.embedding_provider.embed_query(query)
            # 扩大候选集至 40，确保充分覆盖相关切片
            fetch_k = min(max(top_k * 10, 40), max(self.collection.count(), 1))
            chroma_res = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=fetch_k,
                where=where_clause,
                include=["metadatas", "documents", "distances"],
            )

            if chroma_res and chroma_res["ids"] and chroma_res["ids"][0]:
                for idx, chunk_id in enumerate(chroma_res["ids"][0]):
                    dist = chroma_res["distances"][0][idx] if chroma_res["distances"] else 1.0
                    sim = 1.0 / (1.0 + max(dist, 0.0))
                    dense_ranked_ids.append(chunk_id)
                    dense_scores_map[chunk_id] = sim
        except Exception as e:
            print(f"[RAG Retriever] Chroma 检索发生异常: {e}")

        # 3. BM25 稀疏检索 (带 RBAC 过滤)
        bm25_ranked_ids: List[str] = []
        bm25_scores_map: Dict[str, float] = {}

        if self.bm25_model and self.bm25_chunks:
            query_tokens = list(jieba.cut_for_search(query))
            scores = self.bm25_model.get_scores(query_tokens)

            # 过滤并排序
            valid_candidates = []
            for idx, score in enumerate(scores):
                chunk = self.bm25_chunks[idx]
                if chunk.security_level in allowed_levels and score > 0:
                    valid_candidates.append((chunk.chunk_id, float(score)))

            valid_candidates.sort(key=lambda x: x[1], reverse=True)
            for chunk_id, score in valid_candidates[: fetch_k * 2]:
                bm25_ranked_ids.append(chunk_id)
                bm25_scores_map[chunk_id] = score

        # 4. 混合得分融合 (结合 MinMax 归一化得分与 RRF 排序增益)
        all_candidate_ids = set(dense_ranked_ids) | set(bm25_ranked_ids)
        if not all_candidate_ids:
            return []

        # 归一化 Dense 得分
        max_dense = max(dense_scores_map.values()) if dense_scores_map else 1.0
        min_dense = min(dense_scores_map.values()) if dense_scores_map else 0.0
        dense_range = max_dense - min_dense if max_dense > min_dense else 1.0

        # 归一化 BM25 得分
        max_bm25 = max(bm25_scores_map.values()) if bm25_scores_map else 1.0
        min_bm25 = min(bm25_scores_map.values()) if bm25_scores_map else 0.0
        bm25_range = max_bm25 - min_bm25 if max_bm25 > min_bm25 else 1.0

        combined_scores: Dict[str, float] = {}
        for cid in all_candidate_ids:
            raw_dense = dense_scores_map.get(cid, min_dense)
            norm_dense = (raw_dense - min_dense) / dense_range

            raw_bm25 = bm25_scores_map.get(cid, 0.0)
            norm_bm25 = (raw_bm25 - min_bm25) / bm25_range if raw_bm25 > 0 else 0.0

            rank_dense = dense_ranked_ids.index(cid) + 1 if cid in dense_ranked_ids else 80
            rank_bm25 = bm25_ranked_ids.index(cid) + 1 if cid in bm25_ranked_ids else 80
            rrf_gain = (self.dense_weight / (self.rrf_k + rank_dense)) + (
                self.bm25_weight / (self.rrf_k + rank_bm25)
            )

            # 顶级稀疏关键词命中奖励 (在精确命中专业条款和利率表时提升权重)
            sparse_top_bonus = 0.25 if rank_bm25 == 1 else (0.15 if rank_bm25 <= 3 else 0.0)

            combined_scores[cid] = (
                0.6 * (self.dense_weight * norm_dense + self.bm25_weight * norm_bm25)
                + 0.25 * (rrf_gain * 30.0)
                + sparse_top_bonus
            )

        # 按综合得分降序排序候选切片并执行动态自适应截断 (P0 级优化：过滤低置信度边缘噪声)
        sorted_all = sorted(all_candidate_ids, key=lambda x: combined_scores[x], reverse=True)
        if not sorted_all:
            return []

        top_score = combined_scores[sorted_all[0]]
        selected_cids: List[str] = []

        # 动态门槛策略：
        # 1. 至少保留 2 个切片（保障基础事实召回覆盖率）
        # 2. 最多保留 top_k 个切片（默认 3）
        # 3. 若后续切片得分断崖式下跌 (score < top_score * 0.60 或 score < prev_score * 0.65)，自动截断尾部边缘噪声
        for i, cid in enumerate(sorted_all[:top_k]):
            score = combined_scores[cid]
            if i >= 2 and len(selected_cids) >= 2:
                prev_score = combined_scores[selected_cids[-1]]
                if score < top_score * 0.60 or score < prev_score * 0.65:
                    break
            selected_cids.append(cid)

        results: List[RetrievalResult] = []
        for cid in selected_cids:
            chunk = self.chunks_map.get(cid)
            if not chunk:
                continue

            # 构建精确的溯源标签
            citation = f"[来源: 《{chunk.title}》({chunk.doc_id}) {chunk.section}]"
            results.append(
                RetrievalResult(
                    chunk=chunk,
                    dense_score=dense_scores_map.get(cid, 0.0),
                    sparse_score=bm25_scores_map.get(cid, 0.0),
                    combined_score=combined_scores[cid],
                    citation_tag=citation,
                )
            )

        return results

    def format_retrieval_output(self, results: List[RetrievalResult], user_role: str) -> str:
        """将检索结果渲染为适合 LLM 阅读与引用的规整文本。

        Args:
            results (List[RetrievalResult]): 检索结果列表。
            user_role (str): 查询者角色。

        Returns:
            str: 格式化的 Markdown 结果文本。
        """
        if not results:
            allowed_levels = get_allowed_security_levels(user_role)
            return (
                f"【知识检索通知】未检索到与您查询相关的内容，或相关规章超出您的授权密级权限范围。\n"
                f"（当前角色: {user_role}，最高许可密级: {max(allowed_levels, default='C1_PUBLIC')}）"
            )

        formatted_parts: List[str] = [
            f"### 华夏通商银行规章知识检索结果 (查询角色: {user_role}，命中 {len(results)} 条条款)\n"
        ]

        for idx, item in enumerate(results, 1):
            chunk = item.chunk
            formatted_parts.append(
                f"#### [{idx}] {item.citation_tag}\n"
                f"- **规章密级**: `{chunk.security_level}` | **归口部门**: {chunk.department or '全行'}\n"
                f"- **相关度评分**: {item.combined_score:.4f}\n"
                f"- **条款正文**:\n```markdown\n{chunk.content}\n```\n"
            )

        formatted_parts.append(
            "> **合规引述规范提示**：在回答用户提问时，必须严格忠实于上述正文内容，保留具体数值（如利率、期限、审批限额），并在结论后标注对应的 [来源: 《文档名》(Doc_ID) 章节] 条款溯源标签。"
        )

        return "\n".join(formatted_parts)
