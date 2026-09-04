"""
Filename: file_tools.py
Description: 文件系统操作核心工具集。
Author: Risk-Aware Agent Team
"""

from pathlib import Path
from typing import Optional
from src.tools.base import risk_tool
from src.tools.schemas import EditFileArgs, ListDirArgs, ReadFileArgs, WriteFileArgs


@risk_tool("read_file", args_schema=ReadFileArgs, permission="direct")
def read_file(file_path: str, start_line: Optional[int] = None, end_line: Optional[int] = None) -> str:
    """读取指定路径文件的文本内容，支持指定起止行号切片展示。

    Args:
        file_path (str): 目标文件的绝对路径或相对路径。
        start_line (Optional[int], optional): 起始行号 (1-indexed，包含)。默认为 None。
        end_line (Optional[int], optional): 结束行号 (1-indexed，包含)。默认为 None。

    Returns:
        str: 带有行号的文件文本内容，或错误提示。
    """
    try:
        path = Path(file_path).resolve()
        if not path.exists():
            return f"❌ 错误: 文件不存在 -> {path}"
        if not path.is_file():
            return f"❌ 错误: 目标路径不是有效文件 -> {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()

        total_lines = len(lines)
        if total_lines == 0:
            return f"📄 文件为空: {path}"

        start_idx = max(1, start_line) if start_line is not None else 1
        end_idx = min(total_lines, end_line) if end_line is not None else total_lines

        if start_idx > total_lines:
            return f"❌ 错误: start_line ({start_idx}) 超出文件最大行数 ({total_lines})"

        output_lines = []
        for i in range(start_idx - 1, end_idx):
            output_lines.append(f"{i + 1:4d}: {lines[i].rstrip()}")

        return (
            f"📄 文件: {path} (显示第 {start_idx} 至 {end_idx} 行，共 {total_lines} 行):\n"
            + "\n".join(output_lines)
        )
    except Exception as e:
        return f"❌ 读取文件发生异常: {str(e)}"


@risk_tool("write_file", args_schema=WriteFileArgs, permission="user_confirm")
def write_file(file_path: str, content: str, overwrite: bool = True) -> str:
    """创建新文件或覆盖写入文本内容。若父目录不存在将自动递归创建。

    Args:
        file_path (str): 目标文件的绝对路径或相对路径。
        content (str): 要写入的完整文本内容。
        overwrite (bool, optional): 若文件已存在是否允许覆盖。默认为 True。

    Returns:
        str: 写入成功提示或错误原因。
    """
    try:
        path = Path(file_path).resolve()
        if path.exists() and not overwrite:
            return f"❌ 错误: 文件已存在且 overwrite=False -> {path}"

        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return f"✅ 成功写入文件 ({len(content)} 字符) -> {path}"
    except Exception as e:
        return f"❌ 写入文件发生异常: {str(e)}"


@risk_tool("edit_file", args_schema=EditFileArgs, permission="user_confirm")
def edit_file(file_path: str, target_content: str, replacement_content: str) -> str:
    """在已有文件中定位匹配的目标文本片段并进行精准替换。

    Args:
        file_path (str): 目标文件路径。
        target_content (str): 需要被替换的目标文本片段。
        replacement_content (str): 替换后的新文本片段。

    Returns:
        str: 替换操作执行反馈。
    """
    try:
        path = Path(file_path).resolve()
        if not path.exists():
            return f"❌ 错误: 文件不存在 -> {path}"

        with open(path, "r", encoding="utf-8", errors="replace") as f:
            full_text = f.read()

        if target_content not in full_text:
            return f"❌ 错误: 在文件中未找到指定的 target_content，未做任何修改。"

        count = full_text.count(target_content)
        new_text = full_text.replace(target_content, replacement_content, 1)

        with open(path, "w", encoding="utf-8") as f:
            f.write(new_text)

        return f"✅ 成功替换 1 处匹配文本 (共发现 {count} 处匹配) -> {path}"
    except Exception as e:
        return f"❌ 修改文件发生异常: {str(e)}"


@risk_tool("list_dir", args_schema=ListDirArgs, permission="direct")
def list_dir(directory_path: Optional[str] = None, max_depth: int = 2) -> str:
    """列出指定目录下的文件和子目录结构清单，支持设置遍历深度。

    Args:
        directory_path (Optional[str], optional): 目标目录路径。若为 None 则默认查看当前工作目录。
        max_depth (int, optional): 最大遍历深度（默认为 2）。

    Returns:
        str: 格式化的目录结构清单。
    """
    try:
        target_dir = Path(directory_path).resolve() if directory_path else Path.cwd().resolve()
        if not target_dir.exists():
            return f"❌ 错误: 目录不存在 -> {target_dir}"
        if not target_dir.is_dir():
            return f"❌ 错误: 目标路径不是目录 -> {target_dir}"

        results = [f"📁 目录路径: {target_dir}"]

        def _scan(current_path: Path, current_depth: int, prefix: str):
            if current_depth > max_depth:
                return
            try:
                entries = sorted(current_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
            except PermissionError:
                results.append(f"{prefix}└── [无权限访问]")
                return

            for idx, entry in enumerate(entries):
                is_last = (idx == len(entries) - 1)
                connector = "└── " if is_last else "├── "
                sub_prefix = "    " if is_last else "│   "

                if entry.name in (".git", "__pycache__", ".pytest_cache", ".venv", "venv", ".idea"):
                    continue

                if entry.is_dir():
                    results.append(f"{prefix}{connector}📁 {entry.name}/")
                    _scan(entry, current_depth + 1, prefix + sub_prefix)
                else:
                    size_kb = entry.stat().st_size / 1024
                    results.append(f"{prefix}{connector}📄 {entry.name} ({size_kb:.1f} KB)")

        _scan(target_dir, 1, "")
        return "\n".join(results)
    except Exception as e:
        return f"❌ 遍历目录发生异常: {str(e)}"
