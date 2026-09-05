"""
Filename: chunker.py
Description: 基于 Markdown 章节与法条条款粒度感知的合规文档切分器。
Author: ListingGuard Team
"""

import re
from pathlib import Path
from typing import List

from src.models.enums import Platform
from src.rag.schemas import RegulationChunk


class RegulationChunker:
    """条款感知文档切分器，将法律与平台规范 Markdown 准确拆解为条款级切片。"""

    @staticmethod
    def infer_scope_from_path(filepath: Path) -> str:
        """根据规章路径推断其效力范畴 (internal / external / national)。

        Args:
            filepath (Path): 文件路径。

        Returns:
            str: 规章范围。
        """
        path_str = str(filepath).lower().replace("\\", "/")
        if "/internal/" in path_str or "internal" in filepath.name.lower():
            return "internal"
        if "/national/" in path_str or "national" in filepath.name.lower() or "advertising_law" in path_str or "ecommerce_law" in path_str:
            return "national"
        return "external"

    @staticmethod
    def infer_platform_from_filename(filepath: Path) -> Platform:
        """根据规章文件路径或文件名推断对应的电商平台。

        Args:
            filepath (Path): 文件路径。

        Returns:
            Platform: 平台枚举。
        """
        path_str = str(filepath).lower().replace("\\", "/")
        if "taobao" in path_str:
            return Platform.TAOBAO
        elif "pdd" in path_str:
            return Platform.PDD
        elif "ebay" in path_str:
            return Platform.EBAY
        return Platform.GENERAL

    @classmethod
    def chunk_markdown_file(cls, filepath: Path) -> List[RegulationChunk]:
        """解析切分单个合规 Markdown 文档。

        Args:
            filepath (Path): 文件路径。

        Returns:
            List[RegulationChunk]: 生成的条款切片列表。
        """
        if not filepath.exists():
            return []

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        platform = cls.infer_platform_from_filename(filepath)
        scope = cls.infer_scope_from_path(filepath)

        lines = content.splitlines()
        doc_title = filepath.stem
        current_chapter = "总则/概览"
        current_article = ""
        current_article_lines: List[str] = []
        chunks: List[RegulationChunk] = []
        chunk_idx = 1

        def flush_article():
            nonlocal chunk_idx, current_article, current_article_lines
            if current_article and current_article_lines:
                body = "\n".join(current_article_lines).strip()
                if body:
                    safe_stem = re.sub(r"[^\w]+", "_", filepath.stem).upper()
                    chunk_id = f"REG-{platform.value.upper()}-{safe_stem}-{chunk_idx:03d}"
                    chunks.append(
                        RegulationChunk(
                            chunk_id=chunk_id,
                            doc_name=doc_title,
                            platform=platform,
                            scope=scope,
                            chapter=current_chapter,
                            article=current_article,
                            content=body,
                            metadata={
                                "source_file": str(filepath.name),
                                "platform": platform.value,
                                "scope": scope,
                                "chapter": current_chapter,
                                "article": current_article
                            }
                        )
                    )
                    chunk_idx += 1
            current_article_lines = []

        for line in lines:
            stripped = line.strip()
            # 匹配一级大标题 (文档名)
            if stripped.startswith("# ") and not stripped.startswith("## "):
                doc_title = stripped[2:].strip()
            # 匹配二级标题 (章节)
            elif stripped.startswith("## ") and not stripped.startswith("### "):
                flush_article()
                current_chapter = stripped[3:].strip()
                current_article = ""
            # 匹配三级标题 (具体条款)
            elif stripped.startswith("### "):
                flush_article()
                current_article = stripped[4:].strip()
            else:
                if current_article:
                    current_article_lines.append(line)
                elif stripped and not stripped.startswith("---"):
                    # 属于前言或章节说明
                    current_article_lines.append(line)

        flush_article()
        return chunks

    @classmethod
    def chunk_directory(cls, dir_path: Path) -> List[RegulationChunk]:
        """批量切分指定目录下的所有 Markdown 合规法规文件（支持多层子目录递归扫描）。

        Args:
            dir_path (Path): 规章文件目录。

        Returns:
            List[RegulationChunk]: 全量切片集合。
        """
        all_chunks: List[RegulationChunk] = []
        for file in sorted(dir_path.rglob("*.md")):
            file_chunks = cls.chunk_markdown_file(file)
            all_chunks.extend(file_chunks)
        return all_chunks
