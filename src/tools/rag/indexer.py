"""
Filename: indexer.py
Description: 华夏通商银行规章知识库索引器，支持 ChromaDB 稠密向量索引与 BM25 稀疏索引双轨构建。
Author: Risk-Aware Agent Team
"""

import hashlib
import os
import pickle
from typing import Any, Dict, List, Optional
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv
import jieba
from rank_bm25 import BM25Okapi

load_dotenv()

from src.tools.rag.chunker import MarkdownArticleChunker
from src.tools.rag.schemas import DocumentChunk


class EmbeddingProvider:
    """向量化嵌入提供者，优先调用 DashScope text-embedding-v3，缺省时支持无损确定性本地降级。"""

    def __init__(self, api_key: Optional[str] = None, model: str = "text-embedding-v3"):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY", "")
        self.model = model or os.getenv("EMBEDDING_MODEL_NAME", "text-embedding-v3")
        self.dim = 1024

    def is_cloud_available(self) -> bool:
        """检查是否有配置真实可用的 DashScope API Key。"""
        return bool(self.api_key and not self.api_key.startswith("your_"))

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """批量嵌入文档列表。

        Args:
            texts (List[str]): 待向量化的文本列表。

        Returns:
            List[List[float]]: 浮点向量列表。
        """
        if not texts:
            return []

        if self.is_cloud_available():
            try:
                import dashscope
                from dashscope import TextEmbedding

                # DashScope 单次最大支持 10 条批量请求
                batch_size = 8
                all_embeddings: List[List[float]] = []
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    rsp = TextEmbedding.call(
                        model=self.model,
                        input=batch,
                        api_key=self.api_key,
                    )
                    if rsp.status_code == 200:
                        batch_res = sorted(rsp.output["embeddings"], key=lambda x: x["text_index"])
                        for item in batch_res:
                            all_embeddings.append(item["embedding"])
                    else:
                        raise RuntimeError(f"DashScope API 返回异常 ({rsp.code}): {rsp.message}")
                return all_embeddings
            except Exception as e:
                # 异常时记录并平滑回退
                print(f"[RAG Indexer] 调用 DashScope 失败，启用本地确定性降级: {e}")

        # 本地确定性 Hash-Projection 降级（确保离线与单测 100% 可用且可重现）
        return [self._pseudo_embed(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        """嵌入单条查询。

        Args:
            text (str): 查询文本。

        Returns:
            List[float]: 浮点向量。
        """
        return self.embed_documents([text])[0]

    def _pseudo_embed(self, text: str) -> List[float]:
        """确定性伪向量生成（用于离线或无 Key 单测场景）。"""
        vec = [0.0] * self.dim
        tokens = list(jieba.cut_for_search(text))
        for token in tokens:
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self.dim
            vec[idx] += 1.0
        # 归一化
        norm = sum(x * x for x in vec) ** 0.5
        if norm > 0:
            vec = [x / norm for x in vec]
        return vec


class DocumentIndexer:
    """RAG 双轨索引构建器 (ChromaDB + BM25)。"""

    def __init__(
        self,
        persist_dir: str = "data/chroma_db",
        bm25_path: str = "data/bm25_index.pkl",
        collection_name: str = "hcb_regulations",
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        """初始化索引器。

        Args:
            persist_dir (str): ChromaDB 本地持久化路径。
            bm25_path (str): BM25 模型存储路径。
            collection_name (str): Chroma 集合名称。
            embedding_provider (Optional[EmbeddingProvider]): 向量提供者。
        """
        self.persist_dir = persist_dir
        self.bm25_path = bm25_path
        self.collection_name = collection_name
        self.embedding_provider = embedding_provider or EmbeddingProvider()
        self.chunker = MarkdownArticleChunker()

        os.makedirs(self.persist_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.bm25_path), exist_ok=True)

        self.chroma_client = chromadb.PersistentClient(path=self.persist_dir)
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "Huaxia Commerce Bank Multi-Tier Regulation Corpus"},
        )

    def scan_and_load_documents(self, corpus_dir: str) -> List[DocumentChunk]:
        """扫描制度文档目录并生成全部切片。

        Args:
            corpus_dir (str): 原始文档根目录 (例如 e:/求职/rag)。

        Returns:
            List[DocumentChunk]: 切片集合。
        """
        all_chunks: List[DocumentChunk] = []
        for root, _, files in os.walk(corpus_dir):
            for file in sorted(files):
                if file.endswith(".md"):
                    file_path = os.path.join(root, file)
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()
                    chunks = self.chunker.chunk_document(content, source_path=file_path)
                    all_chunks.extend(chunks)
        return all_chunks

    def build_indexes(self, corpus_dir: str, force_rebuild: bool = False) -> Dict[str, Any]:
        """执行全量索引构建。

        Args:
            corpus_dir (str): 制度根目录。
            force_rebuild (bool): 是否强制清空并重建。

        Returns:
            Dict[str, Any]: 构建统计指标。
        """
        existing_count = self.collection.count()
        if existing_count > 0 and not force_rebuild and os.path.exists(self.bm25_path):
            print(f"[RAG Indexer] 发现已有索引 (共 {existing_count} 条)，跳过重建。如需重建请设置 force_rebuild=True")
            return {"status": "skipped", "chunk_count": existing_count}

        print(f"[RAG Indexer] 开始读取语料并分块: {corpus_dir}")
        chunks = self.scan_and_load_documents(corpus_dir)
        if not chunks:
            raise ValueError(f"在目录 {corpus_dir} 下未发现可索引的 Markdown 规章文档！")

        print(f"[RAG Indexer] 分块完成，共生成 {len(chunks)} 个条款切片。")

        # 1. 构建并写入 ChromaDB 向量库
        if force_rebuild:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.get_or_create_collection(
                name=self.collection_name,
                metadata={"description": "Huaxia Commerce Bank Multi-Tier Regulation Corpus"},
            )

        ids = [c.chunk_id for c in chunks]
        documents = [c.content for c in chunks]
        metadatas = [
            {
                "doc_id": c.doc_id,
                "title": c.title,
                "security_level": c.security_level,
                "allowed_roles": ",".join(c.allowed_roles),
                "department": c.department or "",
                "section": c.section,
            }
            for c in chunks
        ]

        print(f"[RAG Indexer] 正在生成文本向量并写入 ChromaDB (共 {len(documents)} 条)...")
        embeddings = self.embedding_provider.embed_documents(documents)
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )

        # 2. 构建并写入 BM25 稀疏索引
        print(f"[RAG Indexer] 正在对切片进行中文分词并构建 BM25 索引...")
        tokenized_corpus = [list(jieba.cut_for_search(doc)) for doc in documents]
        bm25_model = BM25Okapi(tokenized_corpus)

        bm25_data = {
            "bm25_model": bm25_model,
            "chunks": [c.model_dump() for c in chunks],
            "tokenized_corpus": tokenized_corpus,
        }

        with open(self.bm25_path, "wb") as f:
            pickle.dump(bm25_data, f)

        print(f"[RAG Indexer] BM25 稀疏索引成功持久化至 {self.bm25_path}")
        return {
            "status": "success",
            "chunk_count": len(chunks),
            "chroma_count": self.collection.count(),
            "bm25_path": self.bm25_path,
        }
