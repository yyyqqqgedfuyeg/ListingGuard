"""
Filename: tui.py
Description: 基于 Rich 的 ListingGuard 现代化交互式终端运营控制台。
Author: ListingGuard Team
"""

import json
import os
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from src.agent.graph import run_compliance_guard
from src.models.enums import Platform

console = Console()


def print_banner():
    """打印项目 ASCII Banner 与版本信息。"""
    banner_text = (
        "[bold cyan] _     _     _   _             ____                     _ [/bold cyan]\n"
        "[bold cyan]| |   (_)___| |_(_)_ __   __ _|  _ \\ _   _  __ _ _ __ __| |[/bold cyan]\n"
        "[bold cyan]| |   | / __| __| | '_ \\ / _` | | | | | | |/ _` | '__/ _` |[/bold cyan]\n"
        "[bold cyan]| |___| \\__ \\ |_| | | | | (_| | |_| | |_| | (_| | | | (_| |[/bold cyan]\n"
        "[bold cyan]|_____|_|___/\\__|_|_| |_|\\__, |____/ \\__,_|\\__,_|_|  \\__,_|[/bold cyan]\n"
        "[bold cyan]                         |___/                            [/bold cyan]\n"
        "[bold white]🛡️ 电商商品上架合规运营智能体 (ListingGuard) v1.0[/bold white]\n"
        "[dim]支持平台: 淘宝 / 天猫 | 拼多多 | eBay 跨境 | 全网合规自省闭环[/dim]"
    )
    console.print(Panel(banner_text, border_style="cyan", expand=False))


def display_report(report):
    """在终端格式化呈现合规审查报告。"""
    console.print("\n[bold green]===== 🛡️ 合规审核终审报告 =====[/bold green]")

    # 基本信息表格
    table = Table(title=f"商品详情 - [{report.platform.value.upper()}] {report.original_listing.listing_id}")
    table.add_column("字段", style="cyan", width=16)
    table.add_column("内容", style="white")

    table.add_row("原始标题", report.original_listing.title)
    table.add_row("商品类目", report.original_listing.category)
    table.add_row("初检风险总数", f"[bold red]{report.initial_diagnosis.total_risks} 项[/bold red]")
    table.add_row("最高风险等级", f"[bold red]{report.initial_diagnosis.max_severity.value}[/bold red]")
    table.add_row("自省优化轮次", f"{report.iteration_count} 轮")
    table.add_row("终审合规状态", "[bold green]✅ 完全合规通过[/bold green]" if report.is_compliant else "[bold red]⚠️ 存在残留风险[/bold red]")

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
        title="✨ 智能合规优化文案 (保留营销转化力)",
        border_style="green"
    )
    console.print(rewrite_panel)


def main():
    """TUI 主运行循环。"""
    print_banner()

    data_dir = Path(__file__).resolve().parent.parent.parent / "data" / "listings"

    # 加载样例商品
    sample_files = {
        "1": ("淘宝商品真实违规样本 (美妆/数码/个护)", data_dir / "taobao_listings.json"),
        "2": ("拼多多真实违规样本 (食品滋补/日用)", data_dir / "pdd_listings.json"),
        "3": ("eBay 跨境真实侵权/受限样本 (3C/手表)", data_dir / "ebay_listings.json"),
    }

    console.print("\n[bold]请选择检测模式或样本集:[/bold]")
    for key, (desc, _) in sample_files.items():
        console.print(f"  [cyan]{key}[/cyan]. {desc}")
    console.print("  [cyan]4[/cyan]. 自定义输入商品信息并检测")
    console.print("  [cyan]q[/cyan]. 退出")

    choice = Prompt.ask("\n请输入选项", choices=["1", "2", "3", "4", "q"], default="1")
    if choice == "q":
        console.print("[dim]感谢使用 ListingGuard，再见！[/dim]")
        return

    if choice in ["1", "2", "3"]:
        _, fpath = sample_files[choice]
        if not fpath.exists():
            console.print(f"[red]未找到样本文件: {fpath}[/red]")
            return
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
    else:
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


if __name__ == "__main__":
    main()
