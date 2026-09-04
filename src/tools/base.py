"""
Filename: base.py
Description: 工具权限管控基础数据结构与装饰器，支持 'direct' (直接放行) 与 'user_confirm' (挂起需用户确认)。
Author: Risk-Aware Agent Team
"""

from typing import Any, Callable, Literal, Optional, Type
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# 工具权限等级类型声明
ToolPermission = Literal["direct", "user_confirm"]


class RiskAwareTool(StructuredTool):
    """扩展 LangChain StructuredTool，内置权限管控元数据字段 (permission)。

    Attributes:
        permission (ToolPermission): 工具权限等级:
            - 'direct': 直接放行执行，不挂起中断；
            - 'user_confirm': 具有状态变更或高危风险，需挂起中断并等待用户二次确认后恢复执行。
    """

    permission: ToolPermission = Field(
        default="direct",
        description="工具权限等级: 'direct' 表示直接放行，'user_confirm' 表示挂起需要前端/终端用户二次确认",
    )


def risk_tool(
    name: str,
    args_schema: Optional[Type[BaseModel]] = None,
    permission: ToolPermission = "direct",
    description: Optional[str] = None,
    return_direct: bool = False,
) -> Callable[[Callable[..., Any]], RiskAwareTool]:
    """带有权限等级声明的核心工具注册装饰器。

    Args:
        name (str): 工具唯一标识名称。
        args_schema (Optional[Type[BaseModel]], optional): 参数校验 Pydantic 模型。默认为 None。
        permission (ToolPermission, optional): 权限等级 ('direct' 或 'user_confirm')。默认为 'direct'。
        description (Optional[str], optional): 工具描述。默认为被修饰函数的 docstring。
        return_direct (bool, optional): 是否直接将工具输出返回给用户。默认为 False。

    Returns:
        Callable[[Callable[..., Any]], RiskAwareTool]: 生成的装饰器函数。
    """

    def decorator(func: Callable[..., Any]) -> RiskAwareTool:
        doc = (description or func.__doc__ or "").strip()
        tool_instance = RiskAwareTool.from_function(
            func=func,
            name=name,
            description=doc,
            args_schema=args_schema,
            return_direct=return_direct,
            permission=permission,
        )

        # 触发工具注册后置 Hook：自动同步元数据至 config/tools.yaml
        try:
            from src.hooks.registe_post import sync_tool_to_yaml_hook

            sync_tool_to_yaml_hook(
                tool_name=name,
                description=doc,
                permission=permission,
            )
        except Exception:
            pass

        return tool_instance

    return decorator

