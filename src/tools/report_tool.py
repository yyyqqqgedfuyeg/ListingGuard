"""
Filename: report_tool.py
Description: 合规审查报告导出工具，支持生成 Markdown 与 JSON 格式的专业合规报告。
Author: ListingGuard Team
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from langchain_core.tools import tool

from src.models.report import ComplianceReport


@tool
def export_report(
    report_data: Dict[str, Any],
    export_format: str = "markdown",
    output_path: Optional[str] = None
) -> str:
    """将商品合规审核结果导出为结构化报告（支持 markdown 与 json 格式）。

    Args:
        report_data: ComplianceReport 报告数据字典。
        export_format: 导出格式，可选 'markdown' 或 'json'，默认为 'markdown'。
        output_path: 可选保存至本地文件的绝对路径。

    Returns:
        导出的报告文本内容。
    """
    try:
        report = ComplianceReport(**report_data)
        if export_format.lower() == "json":
            content = json.dumps(report.model_dump(), ensure_ascii=False, indent=2)
        else:
            content = report.to_markdown()
    except Exception:
        # 防御性字典格式化
        if export_format.lower() == "json":
            content = json.dumps(report_data, ensure_ascii=False, indent=2)
        else:
            content = f"# 🛡️ ListingGuard 合规审核简报\n```json\n{json.dumps(report_data, ensure_ascii=False, indent=2)}\n```"

    if output_path:
        path_obj = Path(output_path)
        path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(path_obj, "w", encoding="utf-8") as f:
            f.write(content)

    return content
