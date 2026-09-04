"""
Filename: chunker.py
Description: 基于 Markdown 标题与法律条款层级的文档感知切分器 (Heading & Article-aware Chunker)。
Author: Risk-Aware Agent Team
"""

import re
from typing import Any, Dict, List, Tuple
import yaml

from src.tools.rag.schemas import DocumentChunk


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """解析 Markdown 文件开头的 YAML Frontmatter 与正文。

    Args:
        content (str): 完整的 Markdown 文件内容。

    Returns:
        Tuple[Dict[str, Any], str]: (元数据字典, 剩余的正文文本)。
    """
    pattern = r"^---\s*\n(.*?)\n---\s*\n"
    match = re.match(pattern, content, re.DOTALL)
    if not match:
        return {}, content.strip()

    frontmatter_raw = match.group(1)
    body = content[match.end():].strip()
    try:
        metadata = yaml.safe_load(frontmatter_raw) or {}
    except Exception:
        metadata = {}
    return metadata, body


class MarkdownArticleChunker:
    """章节与条款感知分块器。

    解析制度文档中的 `##` (章/主要部分) 与 `###` (条/细则小节)，
    确保利率表格、分级授权表格和关键条款在切片中保持完整不被截断。
    """

    def __init__(self, max_chunk_size: int = 2500, chunk_overlap: int = 150):
        """初始化切分器配置。

        Args:
            max_chunk_size (int, optional): 单个切片的最大字符数。默认为 2500，完整容纳金融表格与完整条款。
            chunk_overlap (int, optional): 切片间重叠字符数。默认为 150。
        """
        self.max_chunk_size = max_chunk_size
        self.chunk_overlap = chunk_overlap

    def chunk_document(self, file_content: str, source_path: str = "") -> List[DocumentChunk]:
        """将单一规章 Markdown 文档解析为结构化的 DocumentChunk 列表。

        Args:
            file_content (str): 文档全文内容。
            source_path (str, optional): 来源文件路径。

        Returns:
            List[DocumentChunk]: 生成的切片对象列表。
        """
        metadata, body = parse_frontmatter(file_content)
        doc_id = metadata.get("doc_id", "DOC-UNKNOWN")
        title = metadata.get("title", "未知制度文件")
        security_level = metadata.get("security_level", "C1_PUBLIC")
        allowed_roles = metadata.get("allowed_roles", ["ALL", "PUBLIC"])
        department = metadata.get("department", "")

        chunks: List[DocumentChunk] = []

        # 按章节 (## 或 ###) 划分区块
        # 匹配以 # 开头的各级标题
        lines = body.split("\n")
        current_h2 = ""
        current_h3 = ""
        current_lines: List[str] = []
        chunk_counter = 0

        def flush_current_block():
            nonlocal chunk_counter, current_lines
            text_block = "\n".join(current_lines).strip()
            if not text_block:
                return

            section_desc = current_h3 or current_h2 or "概览"
            # 组合上下文 Header，方便检索模型定位
            context_header = f"【文档】{title} ({doc_id})\n【章节/条款】{section_desc}\n\n"
            full_content = context_header + text_block

            # 若单块未严重超长，直接作为一个独立 chunk 保留完整表格/条款
            if len(full_content) <= self.max_chunk_size:
                chunk_counter += 1
                chunks.append(
                    DocumentChunk(
                        chunk_id=f"{doc_id}_c{chunk_counter:03d}",
                        doc_id=doc_id,
                        title=title,
                        security_level=security_level,
                        allowed_roles=allowed_roles,
                        department=department,
                        section=section_desc,
                        content=full_content,
                        metadata={
                            "source_path": source_path,
                            "h2": current_h2,
                            "h3": current_h3,
                        },
                    )
                )
            else:
                # 若内容超长（如特别大的人民币利率汇总表），按段落适度切分并保留头部
                paragraphs = text_block.split("\n\n")
                sub_lines: List[str] = []
                for p in paragraphs:
                    cand = "\n\n".join(sub_lines + [p])
                    if len(context_header + cand) > self.max_chunk_size and sub_lines:
                        chunk_counter += 1
                        chunks.append(
                            DocumentChunk(
                                chunk_id=f"{doc_id}_c{chunk_counter:03d}",
                                doc_id=doc_id,
                                title=title,
                                security_level=security_level,
                                allowed_roles=allowed_roles,
                                department=department,
                                section=section_desc,
                                content=context_header + "\n\n".join(sub_lines),
                                metadata={
                                    "source_path": source_path,
                                    "h2": current_h2,
                                    "h3": current_h3,
                                },
                            )
                        )
                        sub_lines = [p]
                    else:
                        sub_lines.append(p)

                if sub_lines:
                    chunk_counter += 1
                    chunks.append(
                        DocumentChunk(
                            chunk_id=f"{doc_id}_c{chunk_counter:03d}",
                            doc_id=doc_id,
                            title=title,
                            security_level=security_level,
                            allowed_roles=allowed_roles,
                            department=department,
                            section=section_desc,
                            content=context_header + "\n\n".join(sub_lines),
                            metadata={
                                "source_path": source_path,
                                "h2": current_h2,
                                "h3": current_h3,
                            },
                        )
                    )
            current_lines = []

        for line in lines:
            if line.startswith("## "):
                flush_current_block()
                current_h2 = line.replace("## ", "").strip()
                current_h3 = ""
            elif line.startswith("### "):
                flush_current_block()
                current_h3 = line.replace("### ", "").strip()
            else:
                current_lines.append(line)

        flush_current_block()
        return chunks
