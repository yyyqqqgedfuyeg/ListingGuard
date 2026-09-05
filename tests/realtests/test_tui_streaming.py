"""
Filename: test_tui_streaming.py
Description: 测试 TUI 用户输入内容时的真实大语言模型流式输出与合规后置审查。
Author: ListingGuard Team
"""

import os
import sys
from pathlib import Path
from typing import List

# 确保项目根目录在 sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from src.ui.tui import stream_llm_compliance_response
from src.agent.graph import run_compliance_guard


def test_tui_llm_streaming_output_live():
    """测试 TUI 用户输入自定义内容时，LLM 能够正常分块流式输出。"""
    user_input = "请问在小红书宣传淘宝护肤品时，使用‘全网第一’和‘彻底根治痘痘’会有什么合规风险？请给出一段简短合规的替代文案。"

    received_chunks: List[str] = []

    def chunk_collector(token: str):
        received_chunks.append(token)

    # 真实触发流式交互
    full_text, hook_report, chunk_count = stream_llm_compliance_response(
        user_input=user_input,
        user_role="EMPLOYEE",
        on_chunk=chunk_collector,
        temperature=0.2,
    )

    # 1. 验证流式分块正常到达
    assert chunk_count > 1, f"应当接收到多个流式分块，实际只收到: {chunk_count}"
    assert len(received_chunks) == chunk_count
    assert "".join(received_chunks) == full_text

    # 2. 验证回复内容充实完整且切题
    assert len(full_text) > 50
    assert "广告法" in full_text or "极限词" in full_text or "医疗" in full_text

    # 3. 验证后置 Hook 正常运作
    assert "risk_level" in hook_report
    assert "sanitized_text" in hook_report


def test_tui_custom_listing_detection_flow():
    """测试 TUI 模式4 (自定义输入商品信息并检测闭环)。"""
    custom_listing = {
        "listing_id": "TUI-CUSTOM-001",
        "platform": "taobao",
        "title": "全网第一顶级草本美白修护霜",
        "description": "富含积雪草成分，彻底根治肌肤暗沉，原价999现价9.9亏本甩卖！",
        "category": "美妆个护",
    }

    report = run_compliance_guard(custom_listing)

    # 验证初检检出违规
    assert report.initial_diagnosis.total_risks > 0
    # 验证经过自省改写后消除违规
    assert report.is_compliant is True
    assert "全网第一" not in report.rewritten_title
    assert "彻底根治" not in report.rewritten_description


if __name__ == "__main__":
    print("=== 开始执行 TUI 输入与 LLM 流式输出实测 ===")
    test_tui_llm_streaming_output_live()
    print("✓ test_tui_llm_streaming_output_live 测试通过！")
    test_tui_custom_listing_detection_flow()
    print("✓ test_tui_custom_listing_detection_flow 测试通过！")
    print("所有 TUI 流式与自省测试执行完毕！")
