"""
Filename: bash_tool.py
Description: 系统 Shell/Bash 命令行执行工具。
Author: Risk-Aware Agent Team
"""

import subprocess
from pathlib import Path
from typing import Optional

from src.tools.base import risk_tool
from src.tools.schemas import BashArgs


@risk_tool("bash", args_schema=BashArgs, permission="user_confirm")
def bash(command: str, cwd: Optional[str] = None, timeout: int = 30) -> str:
    """在系统终端中执行 shell / bash 命令行指令，并返回执行结果 (包含退出码、标准输出和标准错误)。

    Args:
        command (str): 要执行的终端命令（不能为空）。
        cwd (Optional[str], optional): 命令执行的工作目录。默认为当前工作目录。
        timeout (int, optional): 命令超时时间（秒）。默认为 30 秒。

    Returns:
        str: 包含执行状态、标准输出与标准错误的结构化文本。
    """
    try:
        work_dir = str(Path(cwd).resolve()) if cwd else str(Path.cwd().resolve())

        process = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=work_dir,
        )

        output_parts = [
            f"💻 执行命令: `{command}`",
            f"📁 工作目录: {work_dir}",
            f"🚦 退出码 (Exit Code): {process.returncode}",
        ]

        if process.stdout and process.stdout.strip():
            output_parts.append(f"📤 标准输出 (stdout):\n{process.stdout.rstrip()}")

        if process.stderr and process.stderr.strip():
            output_parts.append(f"⚠️ 标准错误 (stderr):\n{process.stderr.rstrip()}")

        if process.returncode == 0 and not process.stdout.strip() and not process.stderr.strip():
            output_parts.append("✨ (命令执行成功，无任何输出)")

        return "\n".join(output_parts)

    except subprocess.TimeoutExpired:
        return f"❌ 命令执行超时 (超过 {timeout} 秒): `{command}`"
    except Exception as e:
        return f"❌ 执行命令发生异常: {str(e)}"
