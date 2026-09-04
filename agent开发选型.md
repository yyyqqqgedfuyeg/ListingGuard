# 垂类行业 Agent 方案调研 — 电商 / 零售 / 金融 / ERP

## 调研发现：垂类赛道的现状

| 赛道 | GitHub 现有最高⭐ | 竞争状态 | 有无 LangGraph 实现 |
|---|---|---|---|
| 电商多Agent | [multi-agent-ecommerce-system](https://github.com/bcefghj/multi-agent-ecommerce-system) 555⭐ | 有标杆但以推荐系统为主 | 少 |
| 电商内容合规 | [ecommerce-content-review](https://github.com/sdhack/ecommerce-content-review) 2⭐ (规则引擎) | **几乎空白** | 无 |
| Text2SQL Agent | [LangGraph-text2sql-agent](https://github.com/ab1821291660/LangGraph-text2sql-agent) 4⭐ | 零散教程级 | 有但粗糙 |
| 财报分析 Agent | 最高 2⭐ | **完全空白** | 无 |
| 供应链/库存 Agent | 最高 7⭐ | **几乎空白** | 无 |
| 电商客服 LangGraph | 全部 0⭐ | 教程抄写级 | 名义上有 |
| 内容审核 Agent | [multimodal-content-moderation-agent](https://github.com/lixingtao123/multimodal-content-moderation-agent) 1⭐ | **空白** | 有但1⭐ |

---

## 🅵 电商商品上架合规运营 Agent — `ListingGuard`

### 🏔️ 巨人
- [ecommerce-content-review](https://github.com/sdhack/ecommerce-content-review) — 2103条规则×17行业的合规引擎，**但它是纯规则匹配**，不是 Agent
- 各平台违禁词检测小工具（前端正则匹配）

### 你的创新
它们只会说"这个词违规了"，然后呢？**你做的是完整闭环**——检测→诊断为什么违规→自动改写合规版本→再次验证改写结果→输出合规报告。这是一个天然的 **Agent 迭代循环**。

### 为什么需要 Agent 而不是规则引擎？

```
卖家输入: "本店产品效果全网最佳，100%纯天然，永久有效，买到就是赚到"
  ↓
Step 1 - 扫描: 命中 "最佳"(极限词) "100%"(绝对化) "永久"(承诺) → 3处违规
  ↓
Step 2 - 诊断: RAG检索 → [《广告法》第9条] [平台《禁限售商品规则》第3.2节]
  ↓
Step 3 - 改写: 生成合规替代文案
  ↓
Step 4 - 二次验证: 对改写后文案再跑一遍扫描 → 发现仍有隐性违规 → 再改
  ↓
Step 5 - 确认: 最终合规版本 → user_confirm → 用户确认采纳
  ↓
多轮迭代直到通过 ✅
```

### 数据从哪来？（全部公开，唾手可得）

| 数据 | 来源 | 获取难度 |
|---|---|---|
| 《广告法》全文 | 国家法律法规数据库 | ⭐ 复制粘贴 |
| 极限词/违禁词库 | GitHub已有多个开源词库 | ⭐ 直接下载 |
| 淘宝/拼多多平台规则 | 各平台卖家中心公开文档 | ⭐⭐ 复制整理 |
| 模拟商品listing | 随便上淘宝复制几个 or 自己写 | ⭐ 几分钟 |

### 工具集

| 工具 | 说明 | 权限 | 风控角色 |
|---|---|---|---|
| `scan_listing` | 扫描商品标题/详情中的违禁词、极限词、虚假宣传 | `direct` | 🔍 检测 |
| `diagnose_violation` | 对命中项分类(极限词/功效承诺/资质缺失)并匹配法规条款 | `direct` | 📋 诊断 |
| `query_regulation` | RAG检索广告法/平台规则，返回带条款号引用 | `direct` | 📖 溯源 |
| `rewrite_compliant` | 生成合规替代文案（保留营销力） | `direct` | ✏️ 修复 |
| `verify_rewrite` | 对改写结果二次扫描验证 | `direct` | ✅ 验证 |
| `batch_scan` | 批量扫描多个商品listing | `user_confirm` | ⚠️ 需确认 |
| `export_report` | 导出合规审查报告 | `user_confirm` | ⚠️ 需确认 |

### 风控策略（YAML）

```yaml
rules:
  - name: absolute_claim_block
    description: 极限词/绝对化用语直接拦截
    patterns: ["最", "第一", "唯一", "100%", "永久", "万能"]
    action: BLOCK
    
  - name: efficacy_claim_review  
    description: 功效宣传需人工审核
    patterns: ["治愈", "根除", "特效", "祛痘", "减肥"]
    action: REQUIRE_APPROVAL
    
  - name: price_fraud_warning
    description: 价格欺诈话术预警
    patterns: ["原价", "清仓价", "跳楼价", "亏本"]
    action: REQUIRE_APPROVAL
```

### 谁会用？
- **个人卖家**（闲鱼/淘宝/拼多多）——你自己卖个二手东西就能用
- **新媒体运营**——公众号/小红书/抖音文案发布前合规自查
- **中小电商团队**——上架前批量扫描

### JD 对齐
- ✅ **AI产品专员**: 电商场景 + 营销文案 + 违禁词过滤 + Agent工作流 ← **完美命中**
- ✅ **安永**: AI治理 + 合规评估 + RAG条款溯源
- ✅ **摩尔线程**: Agent核心架构 + 工具链集成

---

## 🅶 企业数据安全查询 Agent — `SafeQuery`

### 🏔️ 巨人
- Text2SQL 领域：[Vanna.ai](https://github.com/vanna-ai/vanna) (12k⭐)、各种 Text2SQL Agent
- 数据分析：PandasAI (15k⭐)

### 你的创新
所有 Text2SQL 项目都在解决"怎么把自然语言变成 SQL"，**没有人管生成的 SQL 安不安全**。你做的是行业里缺失的一层——**数据查询的风控网关**：

- `SELECT * FROM users` → 敏感字段（手机号/身份证）自动脱敏
- `DELETE FROM orders` → 直接 BLOCK
- `SELECT ... WHERE 1=1` → 检测注入模式 → BLOCK
- 查询返回 >10万行 → REQUIRE_APPROVAL（防止拖库）

### 为什么需要 Agent？

```
用户: "帮我查一下上个月销量前10的商品以及购买者联系方式"
  ↓
Step 1 - 理解意图: 涉及两张表(orders + customers)，需要JOIN
  ↓
Step 2 - 生成SQL: SELECT p.name, SUM(o.qty), c.phone FROM ...
  ↓
Step 3 - 风控审查: 检测到 c.phone (敏感字段!) 
         → 规则触发 → REQUIRE_APPROVAL: "查询包含客户手机号，是否脱敏展示?"
  ↓
Step 4 - 用户选择脱敏 → 改写SQL: CONCAT(LEFT(c.phone,3),'****',RIGHT(c.phone,4))
  ↓
Step 5 - 执行 → 返回结果 → 结果太多? → 分页展示
  ↓
Step 6 - 用户追问 "按地区分组呢?" → Agent记住上下文 → 修改SQL → 再走一遍风控
```

### 数据从哪来？

| 方案 | 说明 |
|---|---|
| **Kaggle 开源数据集** | [Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) / [Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail) — 导入 SQLite 即可 |
| **自己Mock** | 用 Faker 库生成订单/商品/客户数据，5分钟搞定 |
| **本地 SQLite** | 零配置，requirements.txt 不用加任何新依赖 |

### 风控规则（核心卖点）

```yaml
rules:
  # 危险操作
  - name: destructive_sql_block
    description: 拦截所有写操作
    patterns: ["DELETE", "DROP", "TRUNCATE", "UPDATE", "INSERT", "ALTER"]
    action: BLOCK
    message: "🚫 检测到数据变更操作，只读模式下禁止执行"

  # 敏感字段脱敏
  - name: pii_field_masking
    description: 个人隐私字段自动脱敏
    sensitive_fields: ["phone", "email", "id_card", "address", "password"]
    action: REQUIRE_APPROVAL
    options: ["脱敏展示", "完整展示(需审批)", "排除该字段"]

  # 大结果集保护
  - name: large_result_protection
    description: 查询结果超过阈值需确认
    field: estimated_rows
    operator: ">"
    threshold: 10000
    action: REQUIRE_APPROVAL
    message: "⚠️ 预估返回 {value} 行，可能造成性能影响，是否继续？"

  # SQL注入检测
  - name: injection_detection
    patterns: ["1=1", "OR TRUE", "UNION SELECT", "--", "/*"]
    action: BLOCK
```

### 谁会用？
- **任何需要查数据库的非技术人员**（运营、产品经理、财务）
- **数据分析师**——快速探索数据，不用担心写出危险SQL
- **企业内部**——给业务团队一个"安全的数据查询入口"

### JD 对齐
- ✅ **安永**: 数据治理 + IT风险控制 + 数据安全合规 + SQL/数据分析 ← **完美命中**
- ✅ **摩尔线程**: Agent架构 + 工具调用 + 多轮交互 + 记忆
- ✅ **AI产品**: 评价指标(查询准确率/脱敏覆盖率)

---

## 🅷 上市公司财报风控分析 Agent — `FinScan`

### 🏔️ 巨人
- 财报分析Agent赛道 GitHub **全是 0-2⭐**，几乎没有能跑的项目
- Warren Buffett / 雪球 / 同花顺的分析逻辑

### 你的创新
不做"帮你读年报"的套壳ChatGPT，做**财务异常风险扫描仪**——像审计师一样自动扫描财报中的红旗信号（应收暴增、毛利率异常、关联交易、商誉减值风险），然后交叉验证，给出风险评级。

### 为什么需要 Agent？

```
用户: "帮我分析一下贵州茅台2024年年报的风险点"
  ↓
Step 1 - 获取数据: 调用工具从公开API/文件读取财务数据
  ↓
Step 2 - 指标计算: 计算关键财务比率(毛利率/资产负债率/应收账款周转率...)
  ↓
Step 3 - 异常检测: 与历史数据纵向对比 + 与行业均值横向对比
         → 发现: 应收账款同比增长45%，远超营收增速(12%) → 🚨 红旗!
  ↓
Step 4 - 深入调查: Agent 自动追问 → 查询关联交易披露 → 发现大额关联方应收
  ↓
Step 5 - RAG检索: 查询会计准则/审计案例中类似模式的含义
  ↓
Step 6 - 风险报告: 生成结构化风险评估 + 投资建议需 user_confirm（免责声明）
```

### 数据从哪来？

| 来源 | 说明 | 获取方式 |
|---|---|---|
| **Tushare / AKShare** | 免费Python库，直接拉A股财务数据 | `pip install akshare` |
| **巨潮资讯网** | 上市公司公告/年报全文 | 公开下载 |
| **东方财富** | 财务指标对比数据 | 公开API |
| **模拟数据** | 自己构造几家"有问题"的公司财报 | Faker + 手工设计 |

### 风控规则（审计视角的红旗检测）

```yaml
risk_flags:
  - name: receivable_growth_mismatch
    description: 应收账款增速远超营收增速
    condition: "receivable_growth_rate > revenue_growth_rate * 2"
    severity: HIGH
    
  - name: goodwill_impairment_risk
    description: 商誉占净资产比例过高
    condition: "goodwill / net_assets > 0.3"
    severity: MEDIUM
    
  - name: cash_flow_divergence
    description: 净利润为正但经营现金流为负（利润质量存疑）
    condition: "net_profit > 0 AND operating_cash_flow < 0"
    severity: HIGH

  - name: related_party_concentration
    description: 关联交易占营收比过高
    condition: "related_party_revenue / total_revenue > 0.3"
    severity: HIGH
```

### 谁会用？
- **个人投资者**——买股票前跑一遍风控扫描
- **财务/审计专业学生**——学习审计思维
- **你自己**——如果你买基金/股票的话

### JD 对齐
- ✅ **安永**: 数字化审计 + 数据分析 + 风险评估 + AI审计工具 ← **高度命中**（这就是安永在做的事）
- ✅ **摩尔线程**: 多步Agent推理 + 工具链
- ✅ **AI产品**: 数据驱动决策 + 评价指标

---

## 🅸 电商客服+订单风控 多Agent 系统 — `ServiceMesh`

### 🏔️ 巨人
- [multi-agent-ecommerce-system](https://github.com/bcefghj/multi-agent-ecommerce-system) 555⭐ — 但聚焦推荐/营销，不含客服
- LangGraph 官方 [customer-support tutorial](https://langchain-ai.github.io/langgraph/tutorials/customer-support/customer-support/)

### 你的创新
LangGraph 教程只演示了单Agent客服。你做**多Agent编排 + 客诉风险分级**：
- Router Agent（意图识别→分发）
- 订单查询 Agent
- 退款/售后 Agent（高危操作，需HITL）
- 投诉升级 Agent（情绪检测→自动升级主管）

### 为什么需要 Agent？
客服天然是多轮对话 + 跨系统操作。一个退款请求要：查订单→验身份→检查退款政策→计算金额→执行退款→发通知——完整的 Agent 循环。

### 数据
Mock 订单数据 + SQLite，用 Faker 生成，5分钟。

### 风控
- 退款金额>500 → `REQUIRE_APPROVAL`
- 同一用户7天内第3次退款 → `BLOCK` + 升级人工
- 检测到客户辱骂/威胁 → 自动切换到安抚话术 + 升级

### JD 对齐
- ✅ **摩尔线程**: **多智能体协作** + 任务规划 + 记忆管理 ← 直接命中加分项
- ✅ **AI产品**: 电商场景 + 用户体验 + 评价指标(解决率/升级率)
- ⬜ 安永: 弱相关

---

## 🅹 零售库存预警与智能补货 Agent — `StockPilot`

### 🏔️ 巨人
- 传统 ERP 库存管理模块（SAP/用友/金蝶）
- [Inventory-Management-Agent](https://github.com/Nithishkumar647397/Inventory-Management-Agent) 7⭐ — 非常粗糙

### 你的创新
ERP 是"你告诉它规则，它执行"。你做的是"**它自己分析数据，发现风险，给你建议**"——Agent 定期扫描库存状态，主动预警滞销/断货/过期风险，并生成补货建议。

### Agent 循环

```
定时触发 / 用户提问: "最近有什么库存风险？"
  ↓
Step 1 - 扫描: 查询全部SKU库存水位 + 近30天销量
  ↓
Step 2 - 分析: 
  → SKU-A 库存只够卖3天 → 断货风险 🔴
  → SKU-B 180天零销量，库存200件 → 滞销风险 🟡
  → SKU-C 临近保质期(剩30天)，库存500件 → 过期风险 🔴
  ↓
Step 3 - 决策: 
  → SKU-A: 建议紧急补货500件 → user_confirm
  → SKU-B: 建议打折清仓 → user_confirm  
  → SKU-C: 建议立即促销+下架预警 → BLOCK(禁止继续进货)
  ↓
Step 4 - 用户确认后执行补货/促销指令
```

### 数据
Kaggle 零售数据集 or Faker 模拟，导入 SQLite。

### 风控
- 补货金额>1万 → `REQUIRE_APPROVAL`
- 库存清零操作 → `BLOCK`
- 补货建议与历史趋势矛盾 → 预警

### JD 对齐
- ✅ **安永**: ERP系统经验 + 数据分析 + 业务风险评估
- ✅ **AI产品**: 场景挖掘 + 指标体系
- ⬜ 摩尔线程: 一般

---

## 综合对比

| 维度 | 🅵 ListingGuard | 🅶 SafeQuery | 🅷 FinScan | 🅸 ServiceMesh | 🅹 StockPilot |
|---|---|---|---|---|---|
| **Agent循环天然性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **风控是核心价值** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **数据可得性** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| **GitHub差异化** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ |
| **安永JD命中** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **摩尔线程JD命中** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| **AI产品JD命中** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| **你自己能用** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ |
| **实现复杂度(低=好)** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| **面试故事感** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

> [!TIP]
> **组合思路**：这些方案不互斥。比如 **🅶 SafeQuery + 🅷 FinScan** 可以组合成"企业数据风控平台"——SafeQuery 管查询安全，FinScan 管财务分析，共享同一套 risk-aware 中间件。

> [!IMPORTANT]
> **和上一轮通用方案的关系**：这些垂类方案可以和上一轮的 🅰️ AgentProbe（红队测试）组合——做完垂类 Agent 后，再用 AgentProbe 去测试它的安全性，形成**攻防闭环**，简历上就是两个项目。

## Open Questions

1. **这些垂类方向里有感觉的吗？** 可以选一个，也可以组合
2. **你倾向偏"安永风格"（审计/合规/数据治理）还是偏"摩尔线程/AI产品风格"（Agent架构/多Agent/电商场景）？** 这决定了侧重点
3. **上一轮的5个通用方案里有没有想和垂类方案组合的？**
