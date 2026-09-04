"""
Filename: indexer.py
Description: 法规知识库双路索引管理器（Chroma 密集向量 + BM25 稀疏词频索引）。
Author: ListingGuard Team
"""

import hashlib
import os
import re
from pathlib import Path
from typing import List, Optional
import jieba
from rank_bm25 import BM25Okapi
import chromadb
from chromadb.api.types import Documents, EmbeddingFunction, Embeddings

from src.models.enums import Platform
from src.rag.chunker import RegulationChunker
from src.rag.schemas import RegulationChunk


class LocalHashEmbeddingFunction(EmbeddingFunction):
    """离线轻量级语义哈希向量嵌入函数，保证在无外部网络或未配 API Key 时稳定运行。"""

    def __init__(self, dim: int = 128):
        self.dim = dim

    def name(self) -> str:
        return "local_hash_embedding"

    def get_config(self) -> dict:
        return {"dim": self.dim}

    def __call__(self, input: Documents) -> Embeddings:
        embeddings: Embeddings = []
        for text in input:
            vec = [0.0] * self.dim
            words = jieba.lcut(text.lower())
            for word in words:
                word_clean = word.strip()
                if not word_clean:
                    continue
                # 利用 MD5 分桶哈希计算固定维度权重
                h = int(hashlib.md5(word_clean.encode("utf-8")).hexdigest(), 16)
                idx = h % self.dim
                sign = 1.0 if ((h >> 8) & 1) == 1 else -1.0
                vec[idx] += sign

            # L2 归一化
            norm = sum(x * x for x in vec) ** 0.5
            if norm > 1e-6:
                vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


class RegulationIndexer:
    """合规法规与平台规则索引构建与维护器。"""

    DEFAULT_REGULATIONS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "regulations"

    def __init__(
        self,
        collection_name: str = "listing_guard_regulations",
        regulations_dir: Optional[Path] = None,
    ):
        """初始化索引管理器。

        Args:
            collection_name (str, optional): Chroma 集合名称。默认为 "listing_guard_regulations"。
            regulations_dir (Optional[Path], optional): 规章源文件目录。
        """
        self.collection_name = collection_name
        self.regulations_dir = regulations_dir or self.DEFAULT_REGULATIONS_DIR
        self.chunks: List[RegulationChunk] = []

        # 1. 初始化 Chroma 客户端
        self.chroma_client = chromadb.Client()
        self.embedding_fn = LocalHashEmbeddingFunction(dim=128)
        self.collection = self.chroma_client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}
        )

        # 2. 初始化 BM25 数据
        self.bm25: Optional[BM25Okapi] = None
        self.tokenized_corpus: List[List[str]] = []

        # 3. 执行全量加载与索引
        self.build_index()

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """对中英文混合文本进行分词与归一化。

        Args:
            text (str): 输入文本。

        Returns:
            List[str]: 分词结果列表。
        """
        if not text:
            return []
        cleaned = re.sub(r"[^\w\u4e00-\u9fa5]+", " ", text.lower())
        tokens = jieba.lcut(cleaned)
        return [t.strip() for t in tokens if t.strip()]

    def build_index(self):
        """扫描 regulations 目录并构建 Chroma 密集向量与 BM25 稀疏索引。"""
        if not self.regulations_dir.exists():
            return

        self.chunks = RegulationChunker.chunk_directory(self.regulations_dir)
        if not self.chunks:
            return

        # 1. 灌装 Chroma
        ids = [c.chunk_id for c in self.chunks]
        documents = [f"{c.doc_name} {c.chapter} {c.article}\n{c.content}" for c in self.chunks]
        metadatas = [
            {
                "chunk_id": c.chunk_id,
                "doc_name": c.doc_name,
                "platform": c.platform.value,
                "article": c.article,
                "chapter": c.chapter
            }
            for c in self.chunks
        ]

        # 如果集合已有数据先清理
        existing_count = self.collection.count()
        if existing_count > 0:
            self.chroma_client.delete_collection(self.collection_name)
            self.collection = self.chroma_client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_fn,
                metadata={"hnsw:space": "cosine"}
            )

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        # 2. 灌装 BM25
        self.tokenized_corpus = [self.tokenize(doc) for doc in documents]
        self.bm25 = BM25Okapi(self.tokenized_corpus)
