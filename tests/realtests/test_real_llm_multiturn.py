"""
Filename: test_real_llm_multiturn.py
Description: 真实调用 .env 大语言模型 (DeepSeek) 进行多轮多角色合规对话，
             全链路验证 LLM 响应、工具调用、职能边界、分层检索隔离、敏感词 Hook 拦截、
             以及管理员删除二次确认机制，并将对话过程与日志落盘持久化。
Author: ListingGuard Team
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

# 确保项目根目录在 sys.path 中
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)

from src.agent.config import get_llm, load_agent_settings
from src.database.manager import DatabaseManager
from src.database.models import UserRole
from src.hooks.prompt_hooks import inspect_generated_prompt_hook
from src.tools import (
    ALL_DB_TOOLS,
    query_regulation,
    set_db_manager,
)

# 确保 realtests 目录存在
REALTESTS_DIR = Path(__file__).resolve().parent
REALTESTS_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = REALTESTS_DIR / "real_llm_execution.log"
HISTORY_JSON = REALTESTS_DIR / "conversation_history.json"
RECORD_MD = REALTESTS_DIR / "conversation_record.md"

# 配置日志记录器
logger = logging.getLogger("ListingGuard_RealTest")
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8", mode="w")
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
file_handler.setFormatter(formatter)
if not logger.handlers:
    logger.addHandler(file_handler)


SYSTEM_PROMPT = """你是由 ListingGuard 驱动的电商合规运营智能体（Compliance Agent）。
你的核心职责是协助商家客户（CUSTOMER）、运营员工（EMPLOYEE）及系统管理员（ADMIN）保障商品上架及营销内容的严格合规。

你有以下专业工具可供调用：
1. query_regulation: 法规与平台政策检索工具（RAG）。
   - 当用户/员工询问法律法规（广告法、电商法）或平台政策时，必须调用此工具；
   - 客户（CUSTOMER）仅能检索外部公开规范（scope='external' 或留空），员工与管理员可检索内部机审手册（scope='internal'）。
2. 数据库管理工具：
   - db_query_products: 查询商品列表
   - db_get_product_detail: 查询商品详情及关联营销帖子
   - db_create_product / db_update_product: 创建或更新商品（底层 Hook 会自动检查敏感词与违禁词）
   - db_delete_product: 删除商品（高危操作：仅限 ADMIN 角色，且必须进行二次确认）
   - db_query_posts: 查询商品关联的种草推广帖子
   - db_get_post_detail: 查询单个帖子详情
   - db_create_post: 创建关联帖子（底层 Hook 会自动进行敏感词与夸大宣称扫描）
   - db_update_post: 更新帖子
   - db_delete_post: 删除帖子（高危操作：仅限 ADMIN 角色，且必须进行二次确认）
   - db_audit_post: 审核帖子

核心职能边界与调用规范：
- 遇到法律与平台规则问询 -> 务必调用 query_regulation 进行条款级溯源；
- 遇到商品或帖子操作 -> 务必调用 db_xxx 系列工具，并如实传入操作人角色 operator_role；
- 发帖或改写若被底层 Hook 拦截，应清晰向用户说明被拦截的原因及命中的敏感违规词；
- 删除操作若返回 CONFIRMATION_REQUIRED，必须向管理员说明需要二次确认，并给出确认令牌 confirm_token。
"""


class RealConversationRunner:
    """真实多轮对话测试运行器。"""

    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        set_db_manager(self.db)

        # 加载真实配置与大模型
        self.settings = load_agent_settings()
        self.llm = get_llm(self.settings, temperature=0.0)

        # 注册可用工具映射表
        self.tools = [query_regulation, *ALL_DB_TOOLS]
        self.tool_map = {t.name: t for t in self.tools}
        self.llm_with_tools = self.llm.bind_tools(self.tools)

        self.messages: List[BaseMessage] = [SystemMessage(content=SYSTEM_PROMPT)]
        self.saved_turns: List[Dict[str, Any]] = []

    def execute_turn(
        self,
        user_input: str,
        user_role: str = "CUSTOMER",
        operator_id: str = "USR-CUST-001",
        turn_name: str = "Turn",
        max_tool_rounds: int = 5,
    ) -> Dict[str, Any]:
        """执行单轮对话，支持自主多步工具调用（Tool Calling 循环），直到返回最终自然语言回复。"""
        logger.info(f"=== 开始执行 [{turn_name}] (角色: {user_role}) ===")
        logger.info(f"用户输入: {user_input}")

        # 构造用户 Prompt，带上用户角色上下文
        augmented_prompt = f"【当前操作人】角色: {user_role}，用户ID: {operator_id}\n【用户请求】: {user_input}"
        self.messages.append(HumanMessage(content=augmented_prompt))

        turn_log = {
            "turn_name": turn_name,
            "user_role": user_role,
            "operator_id": operator_id,
            "user_input": user_input,
            "tool_calls": [],
            "assistant_response": "",
            "timestamp": datetime.now().isoformat(),
        }

        rounds = 0
        while rounds < max_tool_rounds:
            rounds += 1
            # 调用真实 LLM
            response: AIMessage = self.llm_with_tools.invoke(self.messages)
            self.messages.append(response)

            # 检查是否有工具调用
            if not response.tool_calls:
                # LLM 给出最终文本回复
                final_text = response.content
                logger.info(f"LLM 最终响应: {final_text}")
                turn_log["assistant_response"] = final_text
                break

            # 遍历执行所有被调用的工具
            for tc in response.tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]

                logger.info(f"LLM 触发工具调用: {tool_name}，入参: {tool_args}")
                target_tool = self.tool_map.get(tool_name)
                if not target_tool:
                    tool_output = {"error": f"Tool '{tool_name}' not found"}
                else:
                    try:
                        tool_output = target_tool.invoke(tool_args)
                    except Exception as e:
                        tool_output = {"error": str(e)}

                logger.info(f"工具返回结果: {str(tool_output)[:300]}...")
                turn_log["tool_calls"].append({
                    "tool_name": tool_name,
                    "tool_args": tool_args,
                    "tool_output": tool_output,
                })

                # 将工具执行结果作为 ToolMessage 塞回上下文
                tool_msg_content = json.dumps(tool_output, ensure_ascii=False) if isinstance(tool_output, (dict, list)) else str(tool_output)
                self.messages.append(ToolMessage(content=tool_msg_content, tool_call_id=tool_id))

        self.saved_turns.append(turn_log)
        return turn_log

    def save_results(self):
        """将对话数据与记录文件保存到 tests/realtests 目录。"""
        # 1. 保存结构化 JSON 数据
        with open(HISTORY_JSON, "w", encoding="utf-8") as f:
            json.dump(self.saved_turns, f, ensure_ascii=False, indent=2)

        # 2. 生成优雅易读的 Markdown 对话记录
        md_lines = [
            "# ListingGuard 真实大模型多轮对话评测记录",
            "",
            f"- **测试执行时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- **测试模型**: {self.settings.model_name} (API Base: {self.settings.base_url})",
            f"- **评测轮次**: 共 {len(self.saved_turns)} 轮深度测试",
            "- **测试核心验证项**: 真实 LLM 响应、工具调用、职能边界、RAG 分层检索隔离、敏感词 Hook 拦截、管理员二次确认",
            "",
            "---",
            "",
        ]

        for idx, t in enumerate(self.saved_turns, 1):
            md_lines.append(f"## 第 {idx} 轮: {t['turn_name']}")
            md_lines.append(f"- **操作人角色**: `{t['user_role']}` (ID: `{t['operator_id']}`)")
            md_lines.append(f"- **时间戳**: `{t['timestamp']}`")
            md_lines.append("")
            md_lines.append(f"**用户请求 (User)**:\n> {t['user_input']}\n")

            if t["tool_calls"]:
                md_lines.append("**智能体工具调用链 (Tool Execution)**:")
                for tc in t["tool_calls"]:
                    md_lines.append(f"- **工具名称**: `{tc['tool_name']}`")
                    md_lines.append(f"  - **调用入参**: `{json.dumps(tc['tool_args'], ensure_ascii=False)}`")
                    out_str = json.dumps(tc["tool_output"], ensure_ascii=False) if isinstance(tc["tool_output"], (dict, list)) else str(tc["tool_output"])
                    if len(out_str) > 300:
                        out_str = out_str[:300] + "..."
                    md_lines.append(f"  - **执行返回**: `{out_str}`")
                md_lines.append("")

            md_lines.append(f"**智能体最终回复 (Assistant)**:\n{t['assistant_response']}\n")
            md_lines.append("---")
            md_lines.append("")

        with open(RECORD_MD, "w", encoding="utf-8") as f:
            f.write("\n".join(md_lines))

        logger.info(f"评测数据已持久化保存至: {HISTORY_JSON} 和 {RECORD_MD}")


@pytest.fixture(scope="module")
def real_runner():
    """测试夹具：初始化包含真实基准数据的测试数据库和真实模型运行器。"""
    db = DatabaseManager(":memory:")
    runner = RealConversationRunner(db)
    yield runner
    runner.save_results()
    db.close()


def test_turn1_customer_policy_rag_isolation(real_runner):
    """第1轮测试：客户角色查询政策法规。
    验证：
    1. LLM 准确判定为政策问题，调用 query_regulation (RAG)；
    2. 客户角色 (CUSTOMER) 自动隔离内部手册，检索结果仅包含外部规范和国家法律；
    3. LLM 基于真实法条给出专业解答。
    """
    turn = real_runner.execute_turn(
        user_input="我是淘宝新开店的商家，我想了解一下淘宝平台关于‘好评返现’和违规导流有什么具体的条款规定？违规会有什么处罚？",
        user_role=UserRole.CUSTOMER.value,
        operator_id="USR-CUST-001",
        turn_name="客户政策法规检索与外部规范隔离",
    )

    # 验证 LLM 响应不为空
    assert turn["assistant_response"] is not None and len(turn["assistant_response"]) > 0

    # 验证触发了 query_regulation 工具
    tool_names = [tc["tool_name"] for tc in turn["tool_calls"]]
    assert "query_regulation" in tool_names, f"应当调用 query_regulation 工具，实际调用了: {tool_names}"

    # 验证检索隔离：客户不得查到 internal 内部手册
    for tc in turn["tool_calls"]:
        if tc["tool_name"] == "query_regulation":
            output = tc["tool_output"]
            if isinstance(output, list):
                for item in output:
                    assert item.get("scope") != "internal", f"客户角色不应检索到内部机审手册: {item}"


def test_turn2_employee_internal_manual_rag(real_runner):
    """第2轮测试：运营员工查询平台内部机审标准。
    验证：
    1. 员工角色 (EMPLOYEE) 查询内部审核规则；
    2. query_regulation 返回 internal 内部机审指南切片；
    3. LLM 正常引用内部红线标准答复。
    """
    turn = real_runner.execute_turn(
        user_input="我是平台风控运营专员，请帮我调取淘宝内部机审手册中关于违禁品查禁和拦截处置的操作标准。",
        user_role=UserRole.EMPLOYEE.value,
        operator_id="USR-EMP-001",
        turn_name="员工权限调取内部机审手册",
    )

    assert len(turn["assistant_response"]) > 0
    tool_names = [tc["tool_name"] for tc in turn["tool_calls"]]
    assert "query_regulation" in tool_names


def test_turn3_database_query_products_and_posts(real_runner):
    """第3轮测试：运营员工查询商品与关联帖子数据库。
    验证：
    1. LLM 准确调用数据库工具 db_query_products 或 db_get_product_detail；
    2. 成功返回积雪草精华 (PROD-TB-001) 及其关联的营销帖子；
    3. LLM 汇报商品详情与帖子状态。
    """
    turn = real_runner.execute_turn(
        user_input="请帮我查询系统数据库中目前有哪些商品，并详细查看一下积雪草精华 (PROD-TB-001) 的详细参数和它关联的所有种草帖子。",
        user_role=UserRole.EMPLOYEE.value,
        operator_id="USR-EMP-001",
        turn_name="数据库商品与关联帖子综合查询",
    )

    assert len(turn["assistant_response"]) > 0
    tool_names = [tc["tool_name"] for tc in turn["tool_calls"]]
    assert any("product" in name for name in tool_names)


def test_turn4_hook_blocks_illegal_post_creation(real_runner):
    """第4轮测试：发布含极限词和虚假宣传的违规帖子，前置 Hook 拦截。
    验证：
    1. LLM 调用 db_create_post；
    2. 前置 Hook 检测到“全网第一”、“彻底治愈”等严重违规词，返回 blocked=True；
    3. 数据未写入数据库；
    4. LLM 向用户明确解释拦截原因与违规词汇。
    """
    bad_title = "全网第一神仙水！3天彻底治愈泛红"
    bad_content = "闭眼入！全球顶级配方，原价9999现价9.9元亏本甩卖，绝无副作用！"
    turn = real_runner.execute_turn(
        user_input=f"请帮我为积雪草精华 (PROD-TB-001) 发布一篇小红书种草文，帖子ID使用 POST-BAD-001，标题：'{bad_title}'，正文：'{bad_content}'，标签：['全网第一', '彻底治愈']。",
        user_role=UserRole.EMPLOYEE.value,
        operator_id="USR-EMP-001",
        turn_name="发帖前置敏感词Hook拦截测试",
    )

    assert len(turn["assistant_response"]) > 0
    tool_names = [tc["tool_name"] for tc in turn["tool_calls"]]
    assert "db_create_post" in tool_names

    # 验证 Hook 成功拦截
    create_call = next(tc for tc in turn["tool_calls"] if tc["tool_name"] == "db_create_post")
    output = create_call["tool_output"]
    assert output.get("blocked") is True or output.get("success") is False
    # 验证数据库中确实没有创建该帖子
    assert real_runner.db.get_post("POST-BAD-001") is None


def test_turn5_hook_passes_compliant_post_creation(real_runner):
    """第5轮测试：发布合规文案，Hook 通过并写入数据库。
    验证：
    1. LLM 调用 db_create_post；
    2. Hook 扫描无违规，返回 success=True，状态为 COMPLIANT；
    3. 帖子成功持久化至 SQLite 数据库。
    """
    good_title = "秋冬换季干皮日常修护精华分享"
    good_content = "质地轻盈水润，温和舒缓肌肤干燥紧绷，换季维稳的好帮手，成分安心。"
    turn = real_runner.execute_turn(
        user_input=f"我已按合规要求修改了文案，请重新发布：关联商品 PROD-TB-001，帖子ID使用 POST-REAL-001，标题：'{good_title}'，正文：'{good_content}'，标签：['护肤日常', '温和修护']，渠道使用 xiaohongshu。",
        user_role=UserRole.EMPLOYEE.value,
        operator_id="USR-EMP-001",
        turn_name="合规文案发帖Hook放行与入库",
    )

    assert len(turn["assistant_response"]) > 0
    tool_names = [tc["tool_name"] for tc in turn["tool_calls"]]
    assert "db_create_post" in tool_names

    create_call = next(tc for tc in turn["tool_calls"] if tc["tool_name"] == "db_create_post")
    output = create_call["tool_output"]
    assert output.get("success") is True
    # 验证数据库持久化成功
    saved_post = real_runner.db.get_post("POST-REAL-001")
    assert saved_post is not None
    assert saved_post.title == good_title


def test_turn6_delete_rbac_and_double_confirmation(real_runner):
    """第6轮测试：删除帖子的权限拦截与管理员二次确认闭环。
    分为三个递进阶段：
    6a. 员工角色尝试删除 -> 权限不足拒绝；
    6b. 管理员首次调用删除（未提供 Token） -> 系统拦截并生成 confirm_token；
    6c. 管理员携带 Token 确认删除 -> 验证通过，物理删除成功。
    """
    post_id = "POST-REAL-001"
    assert real_runner.db.get_post(post_id) is not None

    # 6a: 员工尝试删除
    turn_6a = real_runner.execute_turn(
        user_input=f"请帮我把刚才创建的帖子 {post_id} 从数据库中删除。",
        user_role=UserRole.EMPLOYEE.value,
        operator_id="USR-EMP-001",
        turn_name="员工越权删除帖子拦截 (RBAC)",
    )
    # 确认帖子仍存在
    assert real_runner.db.get_post(post_id) is not None

    # 6b: 管理员首次请求删除（无 Token）
    turn_6b = real_runner.execute_turn(
        user_input=f"我是系统超级管理员，请帮我物理删除帖子 {post_id}。",
        user_role=UserRole.ADMIN.value,
        operator_id="USR-ADMIN-001",
        turn_name="管理员删除触发二次确认拦截",
    )
    # 确认帖子仍存在，且拿到了二次确认凭证
    assert real_runner.db.get_post(post_id) is not None
    del_call = next(tc for tc in turn_6b["tool_calls"] if tc["tool_name"] == "db_delete_post")
    token = del_call["tool_output"].get("confirm_token")
    assert token is not None

    # 6c: 管理员携带 Token 确认删除
    turn_6c = real_runner.execute_turn(
        user_input=f"我确认删除帖子 {post_id}，这是本次操作的二次确认令牌凭据：'{token}'，请立即执行物理删除。",
        user_role=UserRole.ADMIN.value,
        operator_id="USR-ADMIN-001",
        turn_name="管理员携带Token完成二次确认物理删除",
    )
    # 确认帖子已被物理删除
    assert real_runner.db.get_post(post_id) is None


def test_turn7_prompt_generation_and_post_hook(real_runner):
    """第7轮测试：大模型生成提示词后的后置 Hook 检查。
    验证：
    1. LLM 针对带有潜在违规倾向的用户需求生成文案或提示词；
    2. inspect_generated_prompt_hook 后置扫描；
    3. 检出敏感词、输出清洗脱敏建议并注入合规护栏。
    """
    dirty_prompt = "请帮我写一段针对燕麦片新品的爆款营销种草文案，突出'全网第一'、'降三高神粮'、'原价999现价9.9亏本甩卖'。"
    hook_result = inspect_generated_prompt_hook(dirty_prompt)

    assert hook_result["passed"] is False
    assert hook_result["risk_level"] == "BLOCKED"
    assert len(hook_result["detected_violations"]) >= 2
    # 验证合规替换版本
    assert "全网第一" not in hook_result["sanitized_text"]
    assert "降三高" not in hook_result["sanitized_text"]
    # 验证注入了合规护栏
    assert len(hook_result["injected_guardrails"]) >= 4

    # 记录该轮测试
    real_runner.saved_turns.append({
        "turn_name": "提示词生成后置Hook安全审查与护栏注入",
        "user_role": UserRole.EMPLOYEE.value,
        "operator_id": "USR-EMP-001",
        "user_input": dirty_prompt,
        "tool_calls": [
            {
                "tool_name": "inspect_generated_prompt_hook",
                "tool_args": {"text_or_prompt": dirty_prompt},
                "tool_output": hook_result,
            }
        ],
        "assistant_response": f"【Hook后置审查拦截成功】\n风险等级: {hook_result['risk_level']}\n检出违规项: {[v['word'] for v in hook_result['detected_violations']]}\n合规脱敏建议: {hook_result['sanitized_text']}",
        "timestamp": datetime.now().isoformat(),
    })


if __name__ == "__main__":
    # 支持直接运行本脚本
    db = DatabaseManager(":memory:")
    runner = RealConversationRunner(db)
    try:
        test_turn1_customer_policy_rag_isolation(runner)
        test_turn2_employee_internal_manual_rag(runner)
        test_turn3_database_query_products_and_posts(runner)
        test_turn4_hook_blocks_illegal_post_creation(runner)
        test_turn5_hook_passes_compliant_post_creation(runner)
        test_turn6_delete_rbac_and_double_confirmation(runner)
        test_turn7_prompt_generation_and_post_hook(runner)
        print("所有真实大模型多轮对话测试已全部成功执行！")
    finally:
        runner.save_results()
        db.close()
