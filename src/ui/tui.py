"""
Filename: tui.py
Description: 基于 Rich 的 ListingGuard 现代化交互式终端运营控制台，支持自定义输入、实时 LLM 流式输出与合规自省闭环。
Author: ListingGuard Team
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from langchain_core.messages import HumanMessage, SystemMessage
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from src.agent.config import get_llm
from src.agent.graph import run_compliance_guard
from src.hooks.prompt_hooks import inspect_generated_prompt_hook
from src.models.enums import Platform

console = Console()

STREAMING_SYSTEM_PROMPT = """你是由 ListingGuard 驱动的资深电商合规运营与文案专家。
你的任务是协助商家与运营人员分析文案合规风险、解答电商平台政策，并创作兼具高转化力与 100% 合规的优质文案。
要求：
1. 坚决规避绝对化极限词（如全网第一、顶级、最好）、虚假医疗宣称（如降三高、彻底根治）、价格欺诈（如虚构原价、跳楼甩卖）及违规导流；
2. 给出客观严谨的合规分析与法理依据；
3. 如果用户要求改写，提供通顺、吸引力强且完全合规的替代方案；
4. 语言专业、精炼。
"""


def print_banner():
    """打印项目 ASCII Banner 与版本信息（无 emoji，风格整洁专业）。"""
    banner_text = (
        "[bold cyan] _     _     _   _             ____                     _ [/bold cyan]\n"
        "[bold cyan]| |   (_)___| |_(_)_ __   __ _|  _ \\ _   _  __ _ _ __ __| |[/bold cyan]\n"
        "[bold cyan]| |   | / __| __| | '_ \\ / _` | | | | | | |/ _` | '__/ _` |[/bold cyan]\n"
        "[bold cyan]| |___| \\__ \\ |_| | | | | (_| | |_| | |_| | (_| | | | (_| |[/bold cyan]\n"
        "[bold cyan]|_____|_|___/\\__|_|_| |_|\\__, |____/ \\__,_|\\__,_|_|  \\__,_|[/bold cyan]\n"
        "[bold cyan]                         |___/                            [/bold cyan]\n"
        "[bold white]电商商品上架合规运营智能体 (ListingGuard) v1.0[/bold white]\n"
        "[dim]支持平台: 淘宝 / 天猫 | 拼多多 | eBay 跨境 | 全网合规自省闭环 | LLM 实时流式响应[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def stream_llm_compliance_response(
    user_input: str,
    user_role: str = "EMPLOYEE",
    on_chunk: Optional[Callable[[str], None]] = None,
    temperature: float = 0.3,
) -> Tuple[str, Dict[str, Any], int]:
    """核心流式交互函数：通过 .env 大语言模型进行实时流式输出，并自动触发后置 Hook 检查。

    Args:
        user_input (str): 用户输入的咨询或待改写文案。
        user_role (str): 当前操作人角色。
        on_chunk (Optional[Callable[[str], None]]): 每收到一个流式分块时的回调函数。
        temperature (float): 采样温度。

    Returns:
        Tuple[str, Dict[str, Any], int]: (完整拼接回复文本, 后置 Hook 审查报告, 接收到的分块总数)
    """
    llm = get_llm(streaming=True, temperature=temperature)
    messages = [
        SystemMessage(content=STREAMING_SYSTEM_PROMPT),
        HumanMessage(content=f"【操作人角色】: {user_role}\n【用户需求】: {user_input}"),
    ]

    collected_chunks: List[str] = []
    chunk_count = 0

    for chunk in llm.stream(messages):
        content = chunk.content or ""
        if content:
            chunk_count += 1
            collected_chunks.append(content)
            if on_chunk:
                on_chunk(content)
            else:
                sys.stdout.write(content)
                sys.stdout.flush()

    if not on_chunk:
        sys.stdout.write("\n")
        sys.stdout.flush()

    full_response = "".join(collected_chunks)

    # 触发后置 Prompt Hook 检查
    hook_report = inspect_generated_prompt_hook(full_response)

    return full_response, hook_report, chunk_count


def display_report(report):
    """在终端格式化呈现合规审查终审报告。"""
    console.print("\n[bold green]===== 合规审核终审报告 =====[/bold green]")

    # 基本信息表格
    table = Table(title=f"商品详情 - [{report.platform.value.upper()}] {report.original_listing.listing_id}")
    table.add_column("字段", style="cyan", width=16)
    table.add_column("内容", style="white")

    table.add_row("原始标题", report.original_listing.title)
    table.add_row("商品类目", report.original_listing.category)
    table.add_row("初检风险总数", f"[bold red]{report.initial_diagnosis.total_risks} 项[/bold red]")
    table.add_row("最高风险等级", f"[bold red]{report.initial_diagnosis.max_severity.value}[/bold red]")
    table.add_row("自省优化轮次", f"{report.iteration_count} 轮")
    table.add_row("终审合规状态", "[bold green][PASS] 完全合规通过[/bold green]" if report.is_compliant else "[bold red][WARN] 存在残留风险[/bold red]")

    console.print(table)

    # 违规证据明细
    if report.initial_diagnosis.violations:
        vio_table = Table(title="初检命中违规项与法理归因")
        vio_table.add_column("严重级别", style="red", width=12)
        vio_table.add_column("违规分类", style="yellow", width=16)
        vio_table.add_column("命中特征/词", style="bold red", width=16)
        vio_table.add_column("援引法规及条款", style="blue")
        vio_table.add_column("修改建议", style="green")

        for v in report.initial_diagnosis.violations:
            vio_table.add_row(
                v.severity.value,
                v.category.value,
                v.trigger_pattern,
                v.cited_regulation or "《广告法》通用规则",
                v.suggestion or "删除或替换为中性表述"
            )
        console.print(vio_table)

    # 合规改写对比
    rewrite_panel = Panel(
        f"[bold green]合规改写标题:[/bold green]\n{report.rewritten_title or '无需修改'}\n\n"
        f"[bold green]合规改写详情:[/bold green]\n{report.rewritten_description or '无需修改'}",
        title="智能合规优化文案 (保留营销转化力)",
        border_style="green"
    )
    console.print(rewrite_panel)


def interactive_chat_mode():
    """交互式智能合规问答与文案改写循环（支持实时流式输出）。"""
    console.print("\n[bold green]进入交互式智能合规对话模式 (已启用大模型实时流式输出)[/bold green]")
    console.print("[dim]输入您的问题或待改写文案，输入 'exit' 或 'quit' 返回主菜单。[/dim]\n")

    role = Prompt.ask("请选择您的操作身份", choices=["EMPLOYEE", "CUSTOMER", "ADMIN"], default="EMPLOYEE")

    while True:
        try:
            user_input = Prompt.ask(f"\n[{role}] 请输入内容")
        except (KeyboardInterrupt, EOFError):
            break

        if not user_input.strip():
            continue
        if user_input.strip().lower() in ("exit", "quit", "q", "back"):
            console.print("[dim]退出交互式对话模式。[/dim]")
            break

        console.print(f"\n[bold cyan]ListingGuard 智能体回复 (实时流式):[/bold cyan]")
        full_text, hook_res, chunks_received = stream_llm_compliance_response(
            user_input=user_input,
            user_role=role,
        )

        console.print(f"[dim](本次输出完成，共接收到 {chunks_received} 个流式数据分块)[/dim]")

        # 若后置 Hook 发现风险，给出醒目提示
        if hook_res.get("risk_level") == "BLOCKED":
            console.print(f"[bold red][Hook后置拦截] 警告：回复中文本包含违规风险词汇：{hook_res.get('detected_violations')}[/bold red]")
        elif hook_res.get("risk_level") == "WARNING":
            console.print(f"[bold yellow][Hook后置提醒] 提示：回复中包含需关注的表述。[/bold yellow]")


def main():
    """TUI 主运行循环。"""
    print_banner()

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "listings"

    sample_files = {
        "1": ("淘宝商品真实违规样本 (美妆/数码/个护)", data_dir / "taobao_listings.json"),
        "2": ("拼多多真实违规样本 (食品滋补/日用)", data_dir / "pdd_listings.json"),
        "3": ("eBay 跨境真实侵权/受限样本 (3C/手表)", data_dir / "ebay_listings.json"),
    }

    while True:
        console.print("\n[bold]请选择检测模式或功能入口:[/bold]")
        for key, (desc, _) in sample_files.items():
            console.print(f"  [cyan]{key}[/cyan]. {desc}")
        console.print("  [cyan]4[/cyan]. 自定义输入商品信息并执行闭环自省检测")
        console.print("  [cyan]5[/cyan]. 交互式智能合规问答与改写 (大模型实时流式输出)")
        console.print("  [cyan]q[/cyan]. 退出")

        choice = Prompt.ask("\n请输入选项", choices=["1", "2", "3", "4", "5", "q"], default="1")
        if choice == "q":
            console.print("[dim]感谢使用 ListingGuard，再见！[/dim]")
            break

        if choice in ["1", "2", "3"]:
            _, fpath = sample_files[choice]
            if not fpath.exists():
                console.print(f"[red]未找到样本文件: {fpath}[/red]")
                continue
            with open(fpath, "r", encoding="utf-8") as f:
                listings = json.load(f)

            console.print(f"\n[bold]已加载 {len(listings)} 个样例商品，选择要审核的商品:[/bold]")
            for idx, item in enumerate(listings, start=1):
                console.print(f"  [cyan]{idx}[/cyan]. [{item.get('category')}] {item.get('title')[:40]}...")

            sub_choice = Prompt.ask("输入序号", default="1")
            try:
                target_idx = int(sub_choice) - 1
                selected_listing = listings[target_idx]
            except Exception:
                selected_listing = listings[0]

            with console.status("[bold green]正在执行闭环合规扫描与自省改写...[/bold green]", spinner="dots"):
                report = run_compliance_guard(selected_listing)
            display_report(report)

        elif choice == "4":
            title = Prompt.ask("请输入商品标题")
            desc = Prompt.ask("请输入商品详情文案")
            platform_str = Prompt.ask("目标电商平台 (taobao/pdd/ebay/general)", default="taobao")
            selected_listing = {
                "listing_id": "CUSTOM-001",
                "platform": platform_str,
                "title": title,
                "description": desc,
                "category": "自定义商品"
            }
            with console.status("[bold green]正在执行闭环合规扫描与自省改写...[/bold green]", spinner="dots"):
                report = run_compliance_guard(selected_listing)
            display_report(report)

        elif choice == "5":
            interactive_chat_mode()


if __name__ == "__main__":
    main()
