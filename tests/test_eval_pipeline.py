"""
Filename: test_eval_pipeline.py
Description: 全模块基准评测流水线自动化单元测试。
Author: ListingGuard Team
"""

from pathlib import Path
import pytest
from eval.run_all_evals import run_full_evaluation_pipeline


def test_eval_pipeline_executes_successfully():
    """验证评测流水线能完整走通三阶段基准评测并输出汇总报告。"""
    summary = run_full_evaluation_pipeline()
    assert "rag_evaluation" in summary
    assert "scanner_evaluation" in summary
    assert "rewrite_evaluation" in summary

    # 验证关键指标达标底线
    assert summary["rag_evaluation"]["hit_at_3"] >= 0.90
    assert summary["scanner_evaluation"]["binary_compliance_accuracy"] >= 0.95
    assert summary["rewrite_evaluation"]["closed_loop_final_compliance_rate"] >= 0.90

    # 验证报告文件已生成
    reports_dir = Path(__file__).resolve().parent.parent / "eval" / "reports"
    assert (reports_dir / "eval_summary.json").exists()
    assert (reports_dir / "eval_benchmark_report.md").exists()
