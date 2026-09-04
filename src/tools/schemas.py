"""
Filename: schemas.py
Description: 内部核心工具入参的 Pydantic 严格校验模式 (Args Schemas)。
此类属于内部校验机制，不直接暴露在面向 LLM 的工具描述提示词中。
Author: Risk-Aware Agent Team
"""

from typing import Dict, Optional, Type
from pydantic import BaseModel, ConfigDict, Field, model_validator


class ReadFileArgs(BaseModel):
    """读取文件工具参数 Schema。"""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="目标文件的绝对路径或相对路径")
    start_line: Optional[int] = Field(default=None, ge=1, description="起始行号 (1-indexed，包含，必须 >= 1)")
    end_line: Optional[int] = Field(default=None, ge=1, description="结束行号 (1-indexed，包含，必须 >= 1)")

    @model_validator(mode="after")
    def validate_line_range(self) -> "ReadFileArgs":
        if self.start_line is not None and self.end_line is not None:
            if self.start_line > self.end_line:
                raise ValueError(
                    f"start_line ({self.start_line}) 不能大于 end_line ({self.end_line})"
                )
        return self


class WriteFileArgs(BaseModel):
    """写入文件工具参数 Schema。"""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="目标文件的绝对路径或相对路径")
    content: str = Field(..., description="要写入的完整文本内容")
    overwrite: bool = Field(default=True, description="若文件已存在是否允许覆盖")


class EditFileArgs(BaseModel):
    """修改/替换文件工具参数 Schema。"""
    model_config = ConfigDict(extra="forbid")

    file_path: str = Field(..., min_length=1, description="目标文件路径")
    target_content: str = Field(..., min_length=1, description="需要被替换的精确目标文本片段（不能为空）")
    replacement_content: str = Field(..., description="用于替换的新文本片段")


class ListDirArgs(BaseModel):
    """目录遍历工具参数 Schema。"""
    model_config = ConfigDict(extra="forbid")

    directory_path: Optional[str] = Field(default=None, description="要查看的目录路径，默认为当前工作目录")
    max_depth: int = Field(default=2, ge=1, le=10, description="递归遍历的最大深度（1-10 之间）")


class BashArgs(BaseModel):
    """命令行执行工具参数 Schema。"""
    model_config = ConfigDict(extra="forbid")

    command: str = Field(..., min_length=1, description="要执行的终端命令（不能为空）")
    cwd: Optional[str] = Field(default=None, description="命令执行的工作目录，默认为当前工作目录")
    timeout: int = Field(default=30, ge=1, le=300, description="命令超时时间（1-300 秒）")


# 注册内部校验 Schema 字典
TOOL_SCHEMAS: Dict[str, Type[BaseModel]] = {
    "read_file": ReadFileArgs,
    "write_file": WriteFileArgs,
    "edit_file": EditFileArgs,
    "list_dir": ListDirArgs,
    "bash": BashArgs,
}
