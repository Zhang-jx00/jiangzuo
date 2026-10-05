# 设计依据与调研来源

> 将作 v0.1.0 开发期间完成的一轮系统调研：**155+ 独立来源、25 个高星技能仓库深析**（star 数为 2026-10 实测）。
> 本文件沉淀"哪个结论来自哪里、落在了技能的哪个文件"，让每条规则可追溯，也方便后续更新调研。

## 一、关键结论 → 来源 → 技能落点（映射表）

| # | 结论 | 来源 | 落点 |
|---|---|---|---|
| 1 | 技能价值的 65.7% 来自"程序性锚定"（稳定工作流防跑偏），仅 4.5% 来自知识注入；技能池过大命中率暴跌（5→100 个时 29.6%→3.3%） | arXiv 2608.14036《Demystifying Agent Skills》（8135 次实验） | 整体设计：薄入口+分册；内核是流程纪律而非知识堆砌 |
| 2 | description 是触发的唯一依据，超 1024 字符技能被直接丢弃；公式 = 做什么 + 何时用 + 用户真实措辞 | agentskills.io 规范；Anthropic 官方最佳实践 | SKILL.md frontmatter；evals/trigger-tests.md |
| 3 | "太简单不用走流程"是技能失效首因（superpowers Issue #54 实测） | obra/superpowers | SKILL.md「逃生口封死」；description 的"无论任务大小" |
| 4 | 铁律 + 反合理化对照表是被 295k★ 仓库验证的纪律写法 | obra/superpowers（verification-before-completion、systematic-debugging） | SKILL.md 铁律、反合理化表；debugging.md 四阶段 |
| 5 | 单向棘轮 + 分级硬门防"过度流程"与"静默跳步"双向失败 | obra/superpowers（Spike/Bounded/Architectural） | SKILL.md L0–L4 分级门 |
| 6 | 计划落盘对抗长任务遗忘（benchmark 96.7%、盲测 A/B 3/3） | OthmanAdi/planning-with-files（27.3k★） | SKILL.md 落盘约定；task-plan.md |
| 7 | EARS 句式验收标准（当…系统应…）可验证、不含糊 | Kiro 官方文档（Requirements→Design→Tasks 门禁） | requirements.md 验收标准三件套 |
| 8 | SDD 流程的批评："止步于实现，缺 review/verify 后段" | martinfowler.com（Böckeler）；ThoughtWorks Tech Radar（SDD=Assess） | 将作补齐后段：code-review/testing/docs-delivery |
| 9 | 确定性操作用脚本，判断类用指令；脚本零 token 加载 | Anthropic 官方最佳实践；agentskills.io/scripts | scripts/ 四件套；各分册"机器层+人工层"分工 |
| 10 | 引用保持一层深，分册不再互相嵌套阅读链 | agentskills.io 规范 | 渐进式披露结构；validate_skill.py 校验项 |
| 11 | 技能必须自包含（引用技能外路径是高星仓库踩过的坑） | addyosmani/agent-skills Issue #361 | 全部资源在技能目录内，相对路径引用 |
| 12 | 技能供应链是真实攻击面（3984 个技能审计：36.8% 有安全问题，13.4% critical） | Snyk ToxicSkills；OWASP Agentic Skills Top 10（AST01） | 脚本纯标准库、不联网、可审计；README 兼容性说明 |
| 13 | 简历型技能（"你有 20 年经验"人设宣言）是社区最痛恨的反模式 | Reddit r/ClaudeAI 高赞批评帖 | 全文无人设宣言，只有可执行规则 |
| 14 | 团队经验应回写技能形成闭环，但需人工审查（不安全轨迹也会被沉淀） | Archer continuous-learning；arXiv 2605.23899 | learnings.md 回写机制；docs-delivery.md |
| 15 | 先建评测再写技能（eval-first），触发准确率目标 ≥90% | Anthropic 工程博客；掘金实战指南 | evals/ 三件套 |

## 二、官方规范与文档

- agentskills.io — Agent Skills 开放标准（name/description 约束、<500 行、三级渐进式披露）
- platform.claude.com — Anthropic《Agent Skills 最佳实践》（自由度三档、description 公式、反模式清单）
- code.claude.com/docs/en/skills — 技能安装位置与扩展字段
- docs.openclaw.ai/tools/skills — OpenClaw 技能系统（加载优先级、token 预算）
- agentskills.io/skill-creation/{optimizing-descriptions, evaluating-skills, using-scripts} — 触发优化与评测官方专页

## 三、高星技能仓库（25 个实测，节选前 10）

| 仓库 | Star | 借鉴点 |
|---|---|---|
| obra/superpowers | 295.4k | 铁律/反合理化表/单向棘轮/计划落盘/红测方法论 |
| mattpocock/skills | 276.5k | 小而可组合、反对接管流程 |
| affaan-m/ECC | 273.2k | research-first 纪律 |
| anthropics/skills | 179.7k | 渐进式披露、资源打包、官方 description 写法 |
| addyosmani/agent-skills | 101.4k | 六阶段 SDLC、slash 命令映射、自包含教训 |
| Leonxlnx/taste-skill | 92.7k | 反 AI 味清单 |
| tt-a1i/archify | 77.8k | 架构可视化 |
| OthmanAdi/planning-with-files | 27.3k | 三文件落盘规划 + hook 注入 |
| Nutlope/hallmark | 29.6k | 反 slop 设计 |
| VoltAgent/awesome-agent-skills | 35.2k | 跨平台兼容矩阵 |

## 四、学术实证

- arXiv 2608.14036 — Demystifying Agent Skills（程序性锚定 65.7%；技能池稀释效应）
- arXiv 2601.01293 — SWE-Skills-Bench（49 个公开 SWE 技能仅 7 个显著有效——自建技能必须自带评测）
- arXiv 2605.23899 — From Raw Experience to Skill Consumption（自我沉淀的质量与风险）
- OWASP Agentic Skills Top 10 — AST01 恶意技能风险

## 五、社区方法论（节选）

- Simon Willison《Claude Skills are awesome…》— 渐进披露省 token 的经典阐述
- 掘金《Claude Skill 开发实战指南》— 触发率 90% 等量化验收
- 掘金《官方 Skills 构建完全指南》— 三级测试、五大实战模式
- 知乎《Skill 不就是 prompt 吗？》— "Prompt 是建议、代码才是命令"
- Reddit r/ClaudeAI — 简历型技能批评、25 条使用技巧
- ThoughtWorks / martinfowler.com — SDD 的冷静分析与"止步过早"批评

## 六、更新约定

- 技能大版本更新（major/minor）时复查上表结论是否仍然成立
- 新增结论请同步追加映射表行，注明来源与落点，保持可追溯
