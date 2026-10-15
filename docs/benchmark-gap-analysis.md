# 对标顶尖技能与主流 SAST：差距清单与取舍

> 2026-10-14 ｜ 两路取证：① 精读本机 `superpowers@6.3.0` 14 个技能（writing-skills /
> test-driven-development / systematic-debugging / verification-before-completion /
> subagent-driven-development / dispatching-parallel-agents 等）；
> ② 联网调研 Semgrep / CodeQL / Joern / Gitleaks / Trivy / OSV / SARIF 官方口径 /
> Anthropic skills 仓库与 2025-2026 AI 审计基准。
> 每条结论后面标了出处；没读到的不写。

## 一、六个维度的对照

| 维度 | 顶尖语料怎么做 | 我们怎么做 | 差在哪 |
|---|---|---|---|
| 入口与披露 | 每技能独立目录，`using-superpowers` 当强制索引；token 预算**分档硬校验**（常驻 <200 词、其他 <500 词，`wc -w` 量）；description 只写触发条件，并附 A/B 实证"写了工作流会让 agent 少做一轮审查" | 单入口 211 行 + 19 分册 + `lookup.py` 检索；预算是 warn 不是 error | 无分档硬上限；触发只能靠 description 匹配（实测 2/19），他们靠 SessionStart 强注入 |
| 纪律强制 | Iron Law 框 + 反合理化表 + 红旗，**明写"改写/同义词/暗示同样适用"**；verification 五步门函数、"Skip any step = lying"；但**全是文档，无机器闸** | 同款三件套 **＋** 机器闸（`validate_skill` / `preflight --strict` / `ship_check` 进 CI） | 我们缺"改写同禁"这句范围声明；缺把"必验证"写成可执行的五步门 |
| 测试与评测 | 技能即 TDD；压力场景 ≥3 压叠加；**meta-testing**（失败后反问"怎么写才让正确答案一目了然"）；**micro-test**：无指导对照、每变体 ≥5 次、方差当指标、**"对照不失败就别写这条规则"** | 红测 7 场景双组、触发 24 条两轮、任务评测 5 项、审计靶场量化 | 缺 meta-test 一问；缺"≥5 次重复 + 方差"的措辞 micro-test；我们多次"基线无区分度"却仍保留规则，与他们的准则相反 |
| 子代理编排 | 完整状态机：每任务 fresh implementer + 双判 reviewer、**diff 落成文件不外灌上下文**、5 轮修复环 + 熔断、ledger 抗压缩、按复杂度选模型、四态各有处置 | 入口一段：返回契约三件 + 独立核验 | 缺状态分派处置、修复环上限/熔断、ledger 恢复、diff-as-file 脚本 |
| 工具与代码质量 | 脚本极少而专（`review-package`、`find-polluter.sh`），核心价值是**用文件传产物保护上下文**；脚本无自测、无 CI | 13 个纯标准库脚本 + 60 条 unittest + CI 六闸（含性能预算与靶场复跑） | 只有"上下文卫生"这一件他们更好 |
| 审计工具链 | Semgrep `mode: taint` + sources/sinks/sanitizers/**propagators** 四元组、`options` 调保守度；误报抑制三层：行内 `# nosemgrep`、`.semgrepignore`、规则 options；Gitleaks `--baseline-path` 只报新增；Trivy `.trivyignore` 带**原因与过期时间**；Joern 用 CPG（AST+CFG+PDG）解跨函数可达 | 规则四元组已有（缺 propagators）、`--baseline` 只报新增已实现、SARIF 2.1.0 导出、独立验证五项 | **没有行内/路径级豁免机制**（业界标配）；没有 propagator 声明；无 AST（已知） |

## 二、我们反而更强的六条（不许被对标劝退）

1. **脚本可靠性**：60 条 unittest + CI 六闸 + 性能护栏——顶尖语料的脚本没有自测，也没有 CI。
2. **量化安全验收带诚实边界**：靶场 16/16、误报 0/18、干净仓库 69 文件误报 14→0、
   内存曲线，以及"自建语料有出题人偏置"的自陈——两个语料库都没有对应物。
3. **跨平台预算工程是实测出来的**：1024 静默丢弃 / 1536 截断 / 299 清单可见，三阈值分别
   由真实客户端验证；他们只有一个 `wc -w`。
4. **机器防漂移**：README 计数、分册骨架契约、分册必须登记进路由词表，全是硬校验。
5. **红测记录不粉饰**：明写"基线未红、当前环境无区分度"，而不是删掉不利场景。
6. **反幻觉验证层**：出报告前重新打开文件核五项、位置对不上直接丢弃并计数——
   主流 SAST 不做这件事，因为它们不需要防"模型编造行号"。

## 三、本轮落地（按 ROI 排序，全部零依赖）

| 轮 | 动作 | 依据 |
|---|---|---|
| B2 | **行内豁免 `jiangzuo:ignore RULE-ID 理由` + `.jiangzuoignore`**，且**没写理由就不生效**，报告单列"已豁免 N 条（含理由）" | Gitleaks `gitleaks:allow`、Trivy 带原因的 `.trivyignore`、Semgrep `# nosemgrep`；我们此前完全没有豁免出口，误报只能靠改规则 |
| B3 | SARIF 按 GitHub 必填口径自检；**撤回"baselineCommit/suppressions"式说法**（GitHub 不消费），指纹匹配对齐"ruleId+路径一致才算同一条" | GitHub SARIF 支持文档、`fingerprints.ts` |
| B4 | `--osv osv.json` 离线导入依赖建议，替换 6 条手写样例（数据不入库，只给下载指引） | OSV 记录格式与 `--offline` 实践 |
| B5 | 子代理编排：四态处置 + 修复环熔断 + ledger + **`review_packet.py`（diff 落文件）** | subagent-driven-development 状态机 |
| B6 | 铁律补"改写/暗示同禁"、"必验证"改成五步门函数；evals 增 micro-test（无指导对照、≥5 次、方差）与 meta-test 一问 | verification-before-completion、writing-skills 的 micro-test 节 |

## 四、明确不做的事

- **不引 AST/tree-sitter**：零依赖是硬约束，代价（同名函数串味、模块级靠伪作用域）已公开写在
  分册与验收记录里。业界解法是 Joern 的 CPG，那条路要引依赖，与技能定位冲突。
- **不把 OSV 全量数据提交进仓库**：体积与时效都不合适；只做导入通道。
- **不做流程图渲染**（graphviz 依赖）：ASCII 决策树已够用，superpowers 用流程图是因为它有渲染链。
- **不为了"检出率更高"放宽规则**：CodeQL/Semgrep 公开实测误报率 68.2%/74.8%，
  我们的 0/18 是靠"干净仓库也要 0 误报"这条反约束换来的，放宽等于放弃差异化。
