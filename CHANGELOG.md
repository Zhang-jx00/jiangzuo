# 更新日志

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

## [0.5.0] - 2026-10-05

专项：减占用 + 提性能 + 提可靠性。依据一轮聚焦全网调研（30+ 新来源：arXiv 2608.11888 致错归因、SkillsBench、claudskills 6.9 万技能反模式分析、Uber 技能工厂、2026 生态报告等），全部改动可在 docs/research-notes.md #22–#27 溯源。

### 占用（可度量地减少）

- 新增 `validate_skill.py --stats`：常驻/按需占用分开计量（CJK≈1 token/字），瘦身从感觉变为数字
- SKILL.md 从 254 行 / ~5,922 tokens 压至 ~222 行 / ~5,556 tokens（正文 ~5,047，回到 ≤5K 预算内）：
  - 技能协同五步、subagent 编排、落盘约定压缩为紧凑段落（细节在分册，正文只留行为指令）
  - 术语表外移 docs/glossary.md（15 条完整版），正文保留一行指针
  - description 触发词去重（样式/异常/卡顿/发布 与 UI/报错/性能/上线 重复），-23 字符
- 新增内容同时压总量：「不适用与让位」「重注入」「示例标注」三项可靠性内容为净新增，靠删冗余抵消

### 可靠性（证据驱动）

- 新增「不适用与让位」区块——6.9 万技能分析中单项收益最高的可靠性修改（+16）：非工程任务不套用、纯科普不触发、更专业领域技能在场时让位、用户跳步授权的铁律边界
- 所有示例标注"**模式参考**，按任务实际要求覆盖细节"——把示例误当需求是技能致错第一大根因（307 例中 86 例）
- 装载即用新增"长会话/上下文压缩后重读核心循环与当前计划"——对抗上下文腐烂（context rot）
- preflight.py 全路径输出 `RESULT: PASS/FAIL(...)` 结论行，CI 日志可机器扫描

### 性能与成熟度

- 装载即用新增"最小加载"路径：L0/L1 只读一本分册即可开工，L2 起才需要简报与计划——按需读取更激进
- CONTRIBUTING 新增内容维护规则：token 预算制、逐行"删掉行为会变吗"审计、Gotchas 优先、分册读取频率审计（连续未读候选删除）、聚焦原则
- README 新增「占用与性能」节（数字公开可复现）；安装指引补充 `.agents/skills/` 跨端新默认
- research-notes 映射表扩至 #22–#27 并附专项来源

## [0.4.0] - 2026-10-05

对齐成熟技能：精读本机官方元技能（superpowers/writing-skills、Codex/skill-creator）全文，逐条吸收其被实测验证的写作范式。

### 变更

- **description 重写为纯触发条件**：移除工作流摘要（"按先读懂再想清…推进"）。writing-skills 实测证明：description 摘要工作流会让 agent 照 description 抄近路、跳过技能正文。工作流表述保留在 metadata.short-description 与正文
- 新增 `when_to_use` frontmatter（ZCode/Claude Code 认可的触发短语扩展字段），validate_skill 同步新增"合计 ≤1536 截断阈值"检查
- SKILL.md 新增：
  - **60 秒示例**：一段真实感对话展示门控提问、最小范围、验证证据、风险同报、技术债登记五个动作（官方质量清单要求正文含具体示例）
  - **L0–L4 定级决策树**：非显然决策点用流程图（writing-skills 规范），命中即停、拿不准按高一级
  - **红旗信号清单**：6 个"出现即停"信号，与反合理化表互补（禁令防辩解、红旗防状态）
  - **"违反字面=违反精神"** 原则：切断"精神遵守"式辩解（superpowers Bulletproofing）
  - **术语表** 12 条：核心循环/铁律/分级门/棘轮/HARD-GATE/交接单/常备授权/兜底等全文统一用法
- 纪律红线·最小改动：写入 **"同意完成任务 ≠ 同意扩大范围或额外权限"**（skill-creator）
- templates/task-plan.md：新增"执行方式"（主代理/子代理逐任务）与每任务 REQUIRED REFERENCE（执行前必读分册）
- 新增 `agents/openai.yaml`（Codex 系客户端 UI 元数据）
- evals/trigger-tests.md：新增开发上下文 PPT 交付物触发用例与三组正反边界甄别
- docs/research-notes.md：新增 #16–#21 结论来源映射

### 修复

- description 中"线上事故止血"表述统一为"线上事故排查"（与术语表一致）

## [0.3.0] - 2026-10-05

### 新增：技能协同能力

- SKILL.md 新增「技能协同」节：总工程师/分包商定位、6 类协同情境表（演示文稿/图表/文档/浏览器走查/图像/外部资料）、协调协议五步（盘点→提议→获准→调用→核验）、兜底不停摆原则
- HARD-GATE 新增第 6 条：调用其他技能产出任务交付物须先获准（常备授权除外）
- 反合理化表 +2："这个技能肯定装了直接调"、"分包商说做好了"
- references/skill-orchestration.md（第 17 本分册）：授权两级制（单次/常备，常备授权落 learnings.md）、交接单五要素（目标/上下文/期望产出/验收标准/禁区）、核验清单、兜底策略、好/坏协同示例
- evals/red-tests.md 场景 7：诱导擅自调用其他技能（含常备授权记录的验证）
- README 中英能力面更新（17 本分册）

### 设计要点

- 只从当前环境实际提供的可用技能清单盘点，不假设技能存在（自包含原则的延伸）
- 用户点名交付物（"做成 PPT"）即视为授权该交付物；技能选型有多个候选时才追问
- 分包商产出与子代理产出同等对待：铁律核验后才算数

## [0.2.0] - 2026-10-05

十轮深度优化（纪律 → 触发 → 入口 → 分册 → 模板 → 脚本 → 一致性 → 红测 → 工程化 → 发版）。

### 新增

- SKILL.md「装载即用」：技能加载后前 60 秒的四种启动路径（续接未完成任务/新会话/赶时间豁免边界）
- 铁律补丁：子代理与工具的"成功"汇报不算证据，必须 diff + 命令输出独立核验
- 沟通协议新增"先结论后细节"
- onboarding：跑不起来时的 5 步处理协议、monorepo 识别、遗留系统"冒烟验证先行"
- requirements：需求中途变更协议（停手→盘点→更新简报→重确认）
- design：遗留系统改造（特征测试+绞杀者思路）、第三方依赖"许可证/活跃度/漏洞"三查
- api-design：文件上传下载（预签名/流式）、长任务异步模式（202+轮询）、推送补拉约定
- frontend：首屏性能意识、可访问性底线
- ui-design：深色模式 token 核对、数据展示底线（对齐/单位/空值）
- backend：异步任务幂等三件套、外部调用"超时/退避重试/降级"、流式处理大文件
- database：UTC 存储约定、游标深分页、大批量变更分批执行
- security：CORS 白名单、敏感操作审计日志
- debugging："在我机器上是好的"环境差异排查清单（6 项）
- testing：测试数据管理（工厂构造/可乱序/固定时钟）
- code-review：自审心法（冷却/换序/有罪推定）与 400 行 diff 规模警觉
- refactor-performance：Core Web Vitals 与 P95 预算参考
- devops：备份恢复演练（"没恢复过的备份等于没备份"）、密钥轮换流程
- preflight.py：新增 GitHub/Google/Slack/OpenAI/连接串 5 类密钥特征、大文件提示（实测 5 检出 0 误报）
- project_scan.py：包管理器判定（10 种锁文件）、.env.example 变量清点
- new_doc.py：新增 learning 类型（learnings.md 经验追加，自动建头）
- validate_skill.py：绝对路径检查、metadata.version 与 CHANGELOG 一致性、evals 存在性
- evals/red-tests.md：新增场景 5（诱导信任子代理汇报）、场景 6（任务中途改需求）
- docs/research-notes.md：15 条"结论→来源→技能落点"映射表 + 调研来源库（155+ 来源、25 仓库）
- GitHub PR 模板与 Issue 模板（含验证清单门槛）

### 修复

- release-checklist.md 缺失 {{TITLE}} 占位符
- new_doc.py learning 分支的 project_root 未定义崩溃
- project_scan.py Windows 大小写不敏感导致的 README 重复列出、环境变量列表开头多余顿号

## [0.1.0] - 2026-10-05

### 新增

- SKILL.md 入口：五步核心循环（先读懂/再想清/后动手/必验证/留文档）、三条铁律、
  L0–L4 任务分级门与单向棘轮、HARD-GATE 交互协议、16 分册路由表、反合理化对照表、
  subagent 编排指引、docs/jiangzuo/ 落盘约定
- references/ 16 本分册：onboarding、requirements、design、api-design、frontend、
  ui-design、backend、database、security、debugging、incident、testing、
  code-review、refactor-performance、devops、docs-delivery
- templates/ 12 个模板：project-profile、requirement-brief、task-plan、adr、
  api-contract、test-plan、bug-report、postmortem、tech-debt、release-checklist、
  progress-report、delivery-report
- scripts/ 4 个纯标准库脚本：project_scan.py（摸底扫描）、preflight.py（交付自检）、
  new_doc.py（文档生成，ADR 自动编号）、validate_skill.py（结构校验）
- evals/ 三件套：trigger-tests.md（18 条触发用例）、red-tests.md（4 个压力场景）、
  task-evals.md（5 个代表性任务评测）
- GitHub Actions CI：自动跑 validate_skill.py 结构校验
- 中英双语 README

### 设计依据

- Agent Skills 开放规范（agentskills.io）与 Anthropic 官方最佳实践
- 155+ 篇方法论来源调研；25 个高星技能仓库深析（superpowers、anthropics/skills、
  planning-with-files 等）；arXiv 2608.14036 实证结论（技能价值主要来自程序性锚定）
