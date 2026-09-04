# P0 主项目：`agent-risk-gate` 核心中间件与 `risk-aware-agent` 双场景智能体实施计划

严格对照安永科技风险、摩尔线程 Agent 工程师与 AI 产品专员的 JD 要求，以**模块化 Monorepo** 架构推进 P0 主项目研发。

---

## 一、架构设计与 Monorepo 目录规划

```
e:/求职/
├── packages/
│   └── agent-risk-gate/              # [独立核心包] LangGraph 原生声明式低延迟风控中间件 (PyPI 规格)
│       ├── pyproject.toml            # 独立打包配置 (支持 pip install -e .)
│       ├── src/
│       │   └── agent_risk_gate/
│       │       ├── __init__.py
│       │       ├── core/
│       │       │   ├── engine.py     # L1/L2 规则执行引擎
│       │       │   ├── schema.py     # 策略 Pydantic Schema
│       │       │   └── parser.py     # YAML 策略解析器
│       │       ├── decorators/
│       │       │   ├── idempotent.py # 工具执行幂等性装饰器
│       │       │   └── risk.py       # @risk_protected 工具装饰器
│       │       └── langgraph/
│       │           └── node.py       # create_risk_gate_node() 图中间件
│       └── tests/                    # 单元测试 (pytest)
│           ├── test_engine.py
│           ├── test_idempotency.py
│           └── test_langgraph_node.py
│
├── risk-aware-agent/                 # [主应用] 双场景工业级风险感知智能体
│   ├── .env.example                  # 多模型配置模板 (OpenAI / DeepSeek / Qwen / Ollama)
│   ├── requirements.txt
│   ├── app.py                        # Streamlit 交互主入口 (红绿灯卡片/HITL审批/RAG溯源)
│   ├── configs/
│   │   ├── finance_policy.yaml       # 金融合规风控策略 (信贷/调额/越权拦截)
│   │   └── ecommerce_policy.yaml     # 电商治理风控策略 (广告法/大额券/群发)
│   ├── data/
│   │   ├── finance_knowledge/        # 金融信贷与合规规章 Markdown 条款
│   │   └── ecommerce_knowledge/      # 电商平台规则与营销合规 Markdown 手册
│   ├── src/
│   │   ├── agent/
│   │   │   ├── state.py              # ExtendedAgentState 定义
│   │   │   ├── graph.py              # LangGraph 状态机编排 (条件分支/HITL/Checkpointer)
│   │   │   └── context.py            # 动态 Context 装配与 Prompt 管理
│   │   ├── tools/
│   │   │   ├── finance_tools.py      # 金融模拟工具 (调额、数据导出、信贷规章查询)
│   │   │   └── ecommerce_tools.py    # 电商模拟工具 (营销文案生成、优惠券、全量群发)
│   │   ├── rag/
│   │   │   ├── hybrid_search.py      # BM25 + Dense 混合检索器
│   │   │   └── citation.py           # Chunk 级条款溯源高亮器
│   │   └── observability/
│   │       └── audit_logger.py       # 结构化审计记录器 (支持导出与 Langfuse 映射)
│   └── tests/
│       ├── test_finance_workflow.py  # 金融场景全链路测试 (含恶意注入与越权拦截)
│       └── test_ecommerce_workflow.py# 电商场景全链路测试
```

---

## 二、模块实施细节与功能规范

### 1. `packages/agent-risk-gate` 核心包
- **L1 Query 预检**：内置常用 Prompt 越狱（Jailbreak）模式与对抗注入正则匹配，毫秒级过滤。
- **L2 工具参数引擎**：解析 YAML 策略文件中的 `field`, `operator` (`>`, `<`, `==`, `in`, `contains`), `action` (`PASS`, `BLOCK`, `REQUIRE_APPROVAL`)。
- **幂等性保障**：实现 `@idempotent_tool`，基于 `SHA256(func_name + sorted_args + context_id)` 拦截重复调用并返回状态缓存。
- **LangGraph 节点适配**：提供 `create_risk_gate_node(policy_path)` 供 StateGraph 无缝挂载。

### 2. `risk-aware-agent` 主应用核心链路
- **金融合规场景**：
  - 工具：`query_credit_rule`、`mock_adjust_credit_limit`（参数含 `new_limit`, `reason`, `skip_approval`）、`mock_export_customer_data`。
  - 拦截重点：`skip_approval == True` 强制 `BLOCK`；`new_limit > 100,000` 触发 `REQUIRE_APPROVAL` (HITL)。
- **电商治理场景**：
  - 工具：`generate_marketing_copy`（违禁词过滤）、`mock_issue_coupon`（`discount_rate < 0.5` 触发审批）、`mock_broadcast_push`（受众 > 10,000 拦截）。
- **RAG 混合检索与引用**：
  - 本地 Markdown 规章切割，保留条款 ID 与小节名。
  - 基于 `rank_bm25` + 密集向量实现混合打分，输出 `[来源: 《商业银行授信指引》第12条]` 精确标注。
- **持久化与 HITL**：
  - 使用 `SqliteSaver` 保存各 `thread_id` 状态。
  - 触发 `interrupt()` 挂起，Streamlit 前端弹出审批卡片，主管审批后通过 `Command(resume=...)` 恢复。

### 3. Streamlit 可视化 UI
- **双场景切换 Tab**：一键切换“金融合规与审计”与“电商运营与治理”。
- **风险决策指示灯**：绿色（安全通过）、黄色（人机审批挂起）、红色（高危拦截）。
- **RAG 溯源侧边栏/卡片**：展示模型引用来源与相似度得分。
- **审计日志流面板**：实时刷新审计流水（Trace ID, 触发规则, 参数指纹, 审批人）。

---

## 三、验证计划

### 1. 自动化测试 (`pytest`)
- `packages/agent-risk-gate` 核心逻辑测试覆盖率 ≥ 90%。
- `risk-aware-agent` 场景集成测试：
  - 验证正常合规操作顺利执行并完成。
  - 验证注入攻击与越权操作被成功拦截 (BLOCK)。
  - 验证大额操作成功触发 HITL 中断并在模拟审批后恢复。
  - 验证重复提交触发幂等缓存拦截。

### 2. 本地交互验证
- 运行 `streamlit run risk-aware-agent/app.py`，分别跑通金融与电商两个典型交互链路。
