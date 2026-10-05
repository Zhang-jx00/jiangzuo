# 更新日志

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

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
