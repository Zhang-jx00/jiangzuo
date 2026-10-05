# 更新日志

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

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
