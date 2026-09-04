"""
Filename: tool.py
Description: 华夏通商银行规章知识检索工具 (query_rag)，支持只读 RBAC 状态注入与条款级精准溯源。
Author: Risk-Aware Agent Team
"""

from typing import Annotated, Any, Dict, Optional
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import InjectedState

from src.tools.base import RiskAwareTool
from src.tools.rag.retriever import HybridRAGRetriever
from src.tools.rag.schemas import RAGQueryInput

# 单例缓存全局检索器
_GLOBAL_RETRIEVER: Optional[HybridRAGRetriever] = None


def get_default_retriever() -> HybridRAGRetriever:
    """获取或初始化全局默认混合检索器单例。

    Returns:
        HybridRAGRetriever: 检索器单例。
    """
    global _GLOBAL_RETRIEVER
    if _GLOBAL_RETRIEVER is None:
        _GLOBAL_RETRIEVER = HybridRAGRetriever()
    return _GLOBAL_RETRIEVER


def _extract_user_role(
    state: Optional[Dict[str, Any]],
    config: Optional[RunnableConfig],
    fallback_role: Optional[str] = None,
) -> str:
    """从运行时上下文注入安全鉴权后的用户角色。

    按优先级逐级尝试从鉴权状态或配置中解析用户角色：
    1. LangGraph State 的 context['user_role']
    2. LangGraph State 的 metadata['user_role']
    3. RunnableConfig 的 configurable['user_role']
    4. 单元测试或直接调用传入的 fallback_role (若存在)
    5. 最严格安全降级: 'PUBLIC' (完全杜绝未授权提权)

    Args:
        state (Optional[Dict[str, Any]]): 状态机状态。
        config (Optional[RunnableConfig]): 运行时配置。
        fallback_role (Optional[str]): 备选角色。

    Returns:
        str: 经规范化的用户角色 (如 'TELLER', 'PUBLIC')。
    """
    if state and isinstance(state, dict):
        ctx = state.get("context")
        if isinstance(ctx, dict) and ctx.get("user_role"):
            return str(ctx["user_role"]).strip().upper()

        meta = state.get("metadata")
        if isinstance(meta, dict) and meta.get("user_role"):
            return str(meta["user_role"]).strip().upper()

    if config and isinstance(config, dict):
        cfg = config.get("configurable")
        if isinstance(cfg, dict) and cfg.get("user_role"):
            return str(cfg["user_role"]).strip().upper()

    if fallback_role:
        return str(fallback_role).strip().upper()

    return "PUBLIC"


def _query_rag_func(
    query: str,
    state: Annotated[Optional[Dict[str, Any]], InjectedState] = None,
    config: Optional[RunnableConfig] = None,
    _role: Optional[str] = None,
) -> str:
    """华夏通商银行规章制度与业务参数知识检索。

    向知识库查询各项金融规章制度、存款贷款基准挂牌利率、信贷审批授权限额、
    风险五级分类与计提拨备要求、反洗钱合规以及柜面业务处理流程标准。

    Args:
        query (str): 自然语言查询问题，例如“三年期定期存款挂牌利率是多少”、“支行长审批个人贷款额度上限”。
        state (Optional[Dict[str, Any]], optional): LangGraph 上下文状态（自动注入）。
        config (Optional[RunnableConfig], optional): 运行时配置（自动注入）。
        _role (Optional[str], optional): 测试或直接调用时指定角色，模型调用时不可篡改。

    Returns:
        str: 格式化的制度条款内容与 [来源: 《文档名》(Doc_ID) 章节] 精准溯源标签。
    """
    user_role = _extract_user_role(state, config, fallback_role=_role)
    retriever = get_default_retriever()
    results = retriever.retrieve(query=query, user_role=user_role, top_k=3)
    return retriever.format_retrieval_output(results=results, user_role=user_role)


# 构建暴露给 Agent 的标准只读安全工具
query_rag: RiskAwareTool = RiskAwareTool.from_function(
    func=_query_rag_func,
    name="query_rag",
    description=(
        "华夏通商银行规章制度与业务参数知识检索工具。"
        "可查询存贷款利率、信贷审批分级授权限额、五级分类标准、柜面业务规程及反洗钱合规等条款。"
        "输入为自然语言问题 query，系统自动结合当前角色身份执行权限过滤，并返回带溯源标签的规章条文。"
    ),
    args_schema=RAGQueryInput,
    permission="direct",
    return_direct=False,
)
