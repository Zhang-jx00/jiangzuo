# 更新日志

所有显著变更记录于此。格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本遵循语义化版本。

## [0.16.0] - 2026-10-14

审计链第③环：**声明式规则引擎**（升级清单第 5 项）——规则从"写在代码里的正则常量"
变成可加载、可合并、可版本化的数据。

### 新增

- **`scripts/audit_rules.py`**：加载/校验/合并/导出版本。校验含字段完备性、severity 只认五级
  （critical/high/medium/low/info）、kind 只认四类（taint/pattern/dependency/auth_gap）、
  kind 专属约束（taint 必须同时有 sinks+sources，dependency 必须有 advisory）、
  语言名必须在语言表里（否则规则永远不会命中也不报错），以及**每条正则当场编译**。
- **`scripts/audit-rules/`（内置 30 条）**：injection.json 10 条污点规则（SQL/命令/代码执行/
  反序列化/路径穿越/SSRF/开放重定向/模板注入，含 sources·sinks·sanitizers 三段）+
  webapp.json 20 条（XSS、硬编码密钥、弱哈希、不安全随机、关证书校验、CORS 过宽、调试上线、
  错误回显、**敏感路由未见鉴权标记**、水平越权嫌疑、上传无限制、日志打敏感值、Cookie 属性、
  CSRF，以及 6 条依赖建议）。每条带 CWE/OWASP/修复示例/复测点——报告的八栏内容由规则供给。
- **合并语义**：同 id 用户覆盖内置、去重只留一条；`rules_version` = 规则原文集合的 sha1，
  并进解析器版本，作为增量缓存键的一部分。
- **`unless_present` 语义**：命中 sink 后在邻近 N 行内找"补救证据"（白名单、净化库、属主条件），
  找不到才报——把"水平越权/上传限制"这类**缺失型**问题做成了可机读的判据。

### 修的真缺陷

- **手写 JSON 正则转义写坏 51 条模式**：第一版 injection 规则里一处 `\(` 让整份 JSON 解析失败，
  我随后用一个"批量修转义"脚本去救，反而把所有合法 `\\b` 二次加倍成 `\\(literal)`，
  51 条模式编译不过。做法退回"从内层重新生成整份规则文件 + 当场编译校验"，
  并把**"每条正则必须编译通过"固化成 `--validate` 的硬项**。
  教训：坏数据要重生成，不要就地打补丁；写进纪律的规矩必须变成机器判据，否则照样复发。

### 验证

- 红→绿配对：5 条规则测试先全红后全绿（`--validate` 输出 30 条 / RULES-OK；
  坏 severity、未知 kind、缺字段都要点名规则 id 并退出码 1；同 id 去重且版本变化）。
- 全量 40 tests OK、`validate_skill.py` 通过（脚本计数同步为 11）、CI 四连命令本地全绿。


审计链第②环：**项目侦察与全仓地图**（升级清单第 2 项）——流水线开头先出地图，再谈扫描。

### 新增

- **`scripts/audit_map.py`**：一次遍历产出语言分布、入口（文件名约定 + 启动语句双路）、
  HTTP 路由（FastAPI/Flask/Django/Express/Nest/Spring/Laravel/Gin/Rails）、
  鉴权边界、依赖与锁文件、环境变量名、外部连接点（**已剥凭证与路径**）。
  复用 `project_scan.py` 的 `FRAMEWORK_HINTS`/`LOCKFILES`/`MANIFESTS` 判定（复用阶梯第 2 级：
  仓库里已有同类实现，不造第二遍），并以上游 `index_sha1` 记录溯源。
- **`auth=false` 的措辞纪律**：地图只说"本文件内未见鉴权标记"，`summary.note` 里写死这句——
  全局中间件、网关、别处注册的装饰器它看不见。把它当证据用是审计的头号误报源。

### 修的真缺陷（都是测试逼出来的，不是自测发现的）

- **路由模式用简写语言名 `js` 比较**，而 `auditlib` 的语言名是 `javascript`/`typescript`——
  Express 路由整批漏识别。改成"每条模式自带适用语言集合"。
- **地图被自己的产物污染**：`--json` 落在被扫目录内时，第二次扫描会读到第一次的地图文件，
  `map_sha1` 随运行次数漂移。修法两条并行：产物从索引里排除；数据文件
  （json/yaml/md）不参与环境变量/连接点/鉴权边界抽取。
- **stderr 未转 UTF-8**：Windows GBK 控制台下中文报错信息变成乱码，测试里的
  "目录不存在"断言直接读不出。`auditlib` 现在同时 reconfigure stdout/stderr。
- 依赖抽取只在清单文件上拼全文，源码一律逐行扫——不再"为抽依赖把每个源文件拼成大字符串"。

### 验证

- 红→绿配对：6 条新测试先全红（6 failures）后全绿——覆盖语言/入口、五条路由的文件:行、
  鉴权标记（含 Java 注解分行）、依赖与锁文件、**地图可复现**、缺目录退出码 2。
- 本仓库自扫 0.58 秒；全量 35 tests OK（新增 6 条 + 前两轮 6 条）、
  `validate_skill.py` 通过（README 脚本计数同步为 10）、`preflight --all --strict` PASS。


## [0.14.0] - 2026-10-14

全项目审计链第①环：**文件索引与忽略模块**（升级清单第 3 项）。先盘点后动手——差距分析见
`docs/security-audit-gap-analysis.md`（R1，只读通读 SKILL.md/scripts/references/CHANGELOG 全史/CI）。

### 新增

- **`scripts/audit_index.py`**：给整个仓库出一份**可复现**清单（路径/字节/内容 sha1/语言）。
  按路径排序；git 可用时用 `git ls-files --exclude-standard` 取 git 的忽略判定（语义最准），
  git 不在时退回内置 gitignore 解析器。输出 `index_sha1` 作为可复现性的**断言对象**，不是装饰。
- **`scripts/auditlib.py`**：审计链共享库。gitignore 语义子集（嵌套 `.gitignore` 越深越优先、
  `!` 取反、目录型模式命中目录本身与内部、`*` 不跨 `/`、`**` 跨）、内置依赖/构建目录黑名单、
  二进制按 NUL 探测、**按行流式读取**（不再 `read().splitlines()` 整文件进内存）、
  单行超长截断留痕、`redact()` 密钥脱敏（报告带命中行原文，不脱敏等于把新漏洞写进交付物）。
- **跳过要留痕**：二进制/超限/不可读文件进 `skipped` 明细并计数，最多列 200 条后汇总——
  静默丢文件是审计工具最坏的失效模式（"扫过了"是假的）。

### 设计取舍

- 工具自己写出的产物（`--json/--md` 落在被扫目录内时）从清单里排除：否则"第二次扫结果变了"
  会直接毁掉可复现性，而这个可复现性正是增量缓存的键。
- `.gitignore`/`.dockerignore`/`.npmrc`/`.pypirc` 这类隐藏点文件**默认纳入**（密钥泄露高发区），
  其余点文件跳过并计数。
- `project_scan.py`/`preflight.py` 行为**一字未改**，新链是挂接不是替换（兼容与渐进条款）。

### 验证

- 红→绿配对：新增 6 条测试先**全红**（`can't open file audit_index.py`，6 failures），
  实现后 6/6 OK——覆盖可复现性、忽略规则含取反、跳过留痕、无绝对路径泄露、
  **哈希跟随内容**（内容哈希不进键则增量缓存是假的）、语言映射。
- 本仓库自扫：61 个文件 / 0.3 MB，两次运行 `index_sha1` 完全相同（`1fb0fa45…`），0.76 秒。
- 回归：`validate_skill.py` 通过（README 计数与实物同步为 9 个脚本）、全量 unittest 绿。



## [0.13.0] - 2026-10-14

一次以**响应成本**为对象的审查：技能"跑得快不快"取决于两件事——每次触发要付多少常驻 token，以及能不能一步命中该读的那本分册。全部实测，不估。

### 修复的真缺陷

- **检索层对自然短语失明**：`lookup.py` 早期要求空格分开的同义词，agent 传"数据库迁移回滚"这类真实措辞直接"无命中"，只能整册载入——路由失败 = token 白花。实测 top-1 命中率 **0/17 = 0%**。
- **`BOOKLET_ALIASES` 定义了却从没参与打分**：一份白写的路由词表；且新分册 `self-evolution.md` 没登记，检索层永远看不见它。

### 新增 / 变更

- **两段式检索**（lookup.py）：整词优先；落空才把中文串切成 2-gram 重试，并加两道精度闸——① 切词命中要求**至少 2 个不同词**命中同一分册，② 丢掉"哪本都有"的高 df 泛词（否则"不存在的词"会靠"存在"两字命中任意分册）。实测把这条改坏的用例又抓回来一次（`xyzzy不存在的词` 恢复为无命中、退出码 1）。
- **别名加权**：路由词表命中一次 +4 分，比正文碰巧出现更可信；补齐 `testing`（金字塔/覆盖率/分层）与 `self-evolution` 的别名。
- **validate 第 8 项**：每本分册必须登记进 `BOOKLET_ALIASES`——"加了分册忘了登记"这种漂移只能机器拦。
- **入口正文 5112 → 4991 tokens（−121，债还清）**：删的都是重复表述——术语表指针（正文已就地定义）、沟通协议"给选项带建议"（HARD-GATE 已规定每问给 2-3 个选项＋推荐）、红旗"共同解法"一句（小节标题已写明回到第一步）。CONTRIBUTING 的登记数字同步更新。
- 无命中时的失败路径更诚实：打印实际尝试过的词，而不是只让人"换同义词"。

### 实测结果

| 指标 | 修复前 | 修复后 |
|---|---|---|
| 自然短语 top-1 命中率 | 0/17 = 0% | **17/17 = 100%** |
| 入口正文 tokens | 5112（超目标 2.2%） | **4991（达标）** |
| 脚本耗时（各 3 次取最小） | — | lookup 0.27s / validate 0.31s / preflight 0.36s / project_scan 0.29s / evolve_report 0.41s（Python 启动占大头，无瓶颈） |

- 测试 21 → **23 全绿**：新增 `TestRouting`（17 例自然短语路由 + 1 例"分册未登记词表必须点名"的红测）。**路由命中率从此是回归项，不是口头承诺。**
- validate 10 项 0 错 0 警；preflight `--strict` 退出 0；`ship_check --level L1` SHIP-OK。

### 评测资产清理（不影响技能本体）

`eval-runs` 126MB → 5.9MB：删除 113MB 应用库备份；27 份运行副本转为 `results/run-evidence/<arm>/`（`status.txt` + `changes.patch` + 未跟踪文件原件 + verify-log），源码副本与数据库可凭夹具重建，故不再留存。

## [0.12.0] - 2026-10-14

给技能装上**自进化**：有证据就改、改了必验证、验证就退得回去——并且把"只加不减"当成头号失败模式来防。

### 新增

- **`references/self-evolution.md`（第 18 本分册）**：六道闸门 观测 → 归因 → 假设 → 最小变异 → 验证 → 记账；规则的**四条生命周期出口**（升级为硬约束 / 保持 WATCH / 退役 / 合并，"不知道算不算数"不是出口）；膨胀控制硬指标（入口超目标必须等量删除、每加 3 条正向规则配 1 条反向"什么时候不要做 X"、逐行问"删掉这行 agent 的行为会变吗"）；变异安全与**回滚条件**（回归变红 / 红测判别力消失 / 新规则被用来给不合理行为背书 → 立即回滚并记账）；三条不可交给自进化的边界（安全边界、用户授权、事实）。
- **`scripts/evolve_report.py`**：只读采集六类信号——learnings 的高置信度未升级项 / 重复主题 / 格式漂移，技术债规模与老化，评测集的失效标记（未红·无区分度·不通过），git 改动热度（反复改的分册＝规则没写清），入口预算，分册规模。输出按证据排序的候选清单＋配额提醒。**不修改任何文件，不自动改技能。**
- **`templates/evolution-log.md`**：进化账本。一行一个假设，结论只允许 `KEEP` / `ROLLBACK` / `WATCH`；**没记账的变更视为未发生**；失败的变异必须回账——"扔掉等于白踩一次"。

### 变更

- SKILL.md 阶段路由新增一行指向 self-evolution.md；同时删掉与 README 重复的 agentskills.io 合规说明。**入口正文 5112 tokens，与 v0.11.0 持平**（一增一减，没有净增债务）。
- README 计数同步为 18 分册 / 14 模板 / 7 脚本，按需成本更正为 ~28K tokens——由 validate 第 7 项机器核对（本次正是它抓出我漏改的两处"17 本分册"）。

### 回归

- 测试 18 → **21 全绿**。新增 3 个 evolve 用例，其中一个是**精确度回归**：任务描述里的"哪些作废（搜索逻辑）"不得被当成评测失效信号——这条要求来自我第一版真的误报后的回修（把宽泛的 `作废` 收窄为"臂/运行/波次/本轮…作废"）。
- validate 9 项 0 错 0 警；preflight `--strict` 退出 0；`ship_check --level L1` SHIP-OK；`evolve_report.py` 自跑本仓库产出 7 项真候选（含"入口超预算 112 tokens"与"SKILL.md 最近 40 提交改了 12 次"）。

## [0.11.0] - 2026-10-14

把"自己审自己"从心态变成可执行协议。源：addyosmani/agent-skills 的 `doubt-driven-development` 与 `code-simplification` 原文精读（溯源 research-notes #39）。

### 新增

- **自疑循环**（code-review.md）：CLAIM（一句**可证伪**的主张 + 为什么重要）→ EXTRACT（拆成可观测预测）→ DOUBT（专找未言明的假设 / 没处理的边界 / 隐藏耦合与共享状态，"假定作者过度自信"——包括你自己）→ RECONCILE（逐条跑命令对账）→ **STOP**（下一轮只剩琐碎发现即停；**满 3 轮交回用户，不自己死磕第 4 轮**）。
- **发现分类按序取一**（同节表格）：契约误读 > 有效且可执行 > 有效但属取舍 > 噪音。先命中先归类——取舍类进 ADR/技术债而不是硬改，噪音记录后丢弃而不是逐条回应。
- **交付报告 §0 主张**（delivery-report.md）：主张 / 为什么重要 / 推翻它需要什么 / 我实际跑了什么来推翻它。
- **删除三查**（refactor-performance.md）：Chesterton 的篱笆（说不出它为什么存在就不要删，`git blame` / `git log -L` 查原始上下文）＋ **500 行阈值**（预计触及 >500 行先写 codemod，不手改，脚本要可重跑且不动测试期望）。

### 变更

- `ship_check.py` 的报告检查从"四问＋阶梯"扩为"**主张**＋四问＋阶梯"——缺可证伪主张直接 SHIP-BLOCKED。红/绿实测：报告无主张 → `✘ 交付报告 r.md 缺：主张（可证伪）`，exit 1；补上主张后 SHIP-OK。

### 回归

- 18 用例全绿（其中绿测夹具因新增字段先红一次，改夹具后复绿——证明这条要求真的在起作用，不是装饰）。
- validate 10 项 0 错 0 警；preflight `--strict` 退出 0；`ship_check --level L1` SHIP-OK。
- **入口正文零增长**（仍 5112 tokens）：本版全部改动落在分册与模板，没有挤占常驻上下文。

## [0.10.0] - 2026-10-14

把"收尾五步"里能机械核对的部分做成一道**交付闸门**——对标 addyosmani/agent-skills 的 `definition-of-done.md` 与 mattpocock/skills 的"提交前必过 /code-review"（溯源 research-notes #37–#38）。

### 新增

- **`scripts/ship_check.py` 交付闸门**：一条命令核完 ①测试通道（自动识别并**执行** pytest/unittest/npm/cargo/go/make，识别不到时 L2/L3 判失败——"没测过"不等于"测不了"）② preflight ③交付报告四问＋**复用阶梯停在第几级** ④试验残留（`_probe*`/`_verify*`/`*.log`/`*.tmp`/`scratch/` 等）⑤项目常驻标准 ⑥若目录本身是技能仓库则加跑结构校验。输出逐项结论＋下一步指令，`RESULT: SHIP-OK / SHIP-BLOCKED`，退出码 0/1 可接 CI。只读不写文件。
- **`templates/definition-of-done.md` 项目常驻标准**：与单次验收标准叠加的常驻门槛（测试命令、构建命令、契约同步、回滚、报告、无残留），并明确"只有用户可豁免，且必须写进剩余风险"。onboarding 第 11 步负责建立，摸底标准新增一条。
- **README 计数一致性检查**（validate_skill.py 第 7 项）：README 声明的脚本/模板/分册数量与磁盘实物不符即警告——本仓库曾把"4 个脚本"写错两个版本，靠人记得改不如机器盯着。
- **CI 接入闸门**：`.github/workflows/validate.yml` 新增 `ship_check.py --level L1` 一步。
- **自我约束**：`.gitignore` 改为 `docs/jiangzuo/*` + 例外 `constitution.md`，本仓库公开自己的常驻标准——做不到就别拿去要求别人的项目。

### 变更

- 交付收尾由 5 步收敛为 4 步：报告与文档同步合并，第 3 步统一走闸门（preflight 仍在闸门内，可单独跑）。
- `templates/delivery-report.md` 新增"复用阶梯：停在第 N 级"字段与"交付闸门"证据行（闸门会检查这两处）。
- README 脚本清单补回 `lookup.py` 与 `ship_check.py`，计数改为实际的 6 脚本 / 13 模板。

### 回归

- 新增 6 个测试（4 个闸门红/绿配对 + 2 个 README 计数红/绿），套件 12 → **18 用例全绿**。
- validate 10 项 0 错 0 警；preflight RESULT PASS；`ship_check --level L1` → SHIP-OK（2 项警告为交付报告与 L2 门槛，符合技能仓库定位）。
- 入口正文 5112 tokens（v0.8.0 为 5060，**净增 52**）：已压缩交付收尾、自净细则、L3 流程行、沟通协议首条等四处表述来抵销，仍超 5K 目标 2.2%——这笔债写进 CONTRIBUTING 作为下一版任务，不靠调高目标数字掩盖。

## [0.9.0] - 2026-10-14

任务评测 5 项双臂实跑收口，外加两路未覆盖过的高星竞品精读（DietrichGebert/ponytail 163k★、garrytan/gstack 136k★）。溯源见 docs/research-notes.md #35–#36。

### 新增

- **复用阶梯**（design.md 新节 + 入口 ③ 后动手）：写任何新代码前按七级优先序往下走——必须存在吗 → 仓库里已有 → 标准库 → 框架/平台原生 → 已装依赖 → 一行 → 才写最小实现；且**"停在第几级"必须成文**，给不出这一行就是没走。同时钉死边界：阶梯只裁"要不要写/写多少"，**不削减**输入校验、错误处理、安全、无障碍。
- **必测清单**（testing.md）：带**分支 / 循环 / 解析 / 金额 / 权限 / 并发**的逻辑，改动至少留下一条能失败的测试——把"关键逻辑"从感觉变成可核对的清单。
- **本次不碰（冻结清单）**（templates/task-plan.md + code-review.md 新小节「必要性与范围」）：计划里列出冻结路径与理由，收尾用 `git diff --name-only` 核对没越界；审查时新增代码无复用阶梯结论、已有实现被重写、依赖未经同意 → 打回。
- **自净纪律**（SKILL.md 文件落盘约定 + 交付收尾第 1 步）：为验证临时建的探针脚本、副本库、抓包日志不属于过程文档——用完当场删除，并在验证记录里留一行"已删清单"；接手者只应看到产物，不该看到脚手架。

### 变更

- 交付收尾由 4 步扩为 5 步（"自净"前置）；交付报告需附复用阶梯停在第几级。

### 评测收口（实测结论，非文档改动）

- 任务评测 5 项的双臂运行（10 份副本、独立磁盘取证）已回填 `evals/task-evals.md` 记录表：技能的可复现增益集中在**该问时问**（任务 2/4 两臂方向相反）、**证据与留痕**（verify-log 5/5 vs 3/5、档案只在绿臂）、**范围纪律与自净**；在"能不能做对"层面与本环境强模型基线拉不开差距（根因定位、迁移回滚、性能达标、调用链定位四项两臂同分）。
- 记有一条取证自纠：10-07 曾误判某臂"编造优化结果"，实为在其文件写入完成之前取样——并发写者未收尾时不得据"看不到"下结论。

## [0.8.0] - 2026-10-07

对标大厂与高星项目实现（三路源码级精读：github/spec-kit 命令模板、超高星项目 ECC/graphify/karpathy/wshobson/alirezarezvani、企业级套件 K-Dense/Sentry/Cloudflare/Game-Studios）。全部溯源见 docs/research-notes.md #31–#34。

### 新增

- **分册骨架契约校验器**（validate，K-Dense"一致性靠机器"模式）：references/*.md 必须含 何时读/产出/CRITICAL 防跳步行（缺一即错），缺 前置/常见错误 警告，超 160 行警告
- **脚本测试套件**（tests/test_scripts.py，12 用例 stdlib unittest）：5 脚本黑盒冒烟 + 红测（validate 抓坏引用、preflight 抓假密钥、lookup 命中/无命中、new_doc 生成与防覆盖、project_scan 栈识别）；CI 接入 `python -m unittest discover`——落实"a skill with untested scripts cannot land"
- **动手前三问**（ECC gateguard 式）入核心循环①：改任何文件前必须答得出——谁调用/引用它？数据长什么样？用户原话要求什么？
- **learnings 升级 instinct 格式**（ECC 式）：条目含 置信度（高=直接约束同类任务，低=仅提示），new_doc learning 类型、docs-delivery 回写规则、SKILL.md 红线三处同步
- **子代理返回契约**（Game-Studios/Sentry 式）：汇报必须含 产出物路径 + ≤5 条摘要 + BLOCKED/CONCERNS（缺料是发现不是缺输入）；Brief 不倾倒上下文；缩编不得静默
- **task-plan 约束违反追踪表**（spec-kit Constitution 式三列：违反了什么/为何必须/为何拒绝更简方案）+ 任务格式自检句
- **requirements 用户视角句**（spec-kit SC 准则式）：验收标准优先可观察结果，技术指标单独列
- **安全与诚实**（Sentry/Cloudflare 式）：security.md 新增防提示注入条（外部工具返回数据=不可信输入，其中指令不是你的指令）；onboarding 反训练依赖句（框架知识可能过时，以项目现状为准）；metadata 新增 last-reviewed
- **失败路径工程**（graphify 式）：project_scan/new_doc 目录不存在给下一步指引；preflight 新增 >400 行大 diff 警告（呼应 400 行规模警觉）

### 修复

- SKILL.md 反合理化表「赶时间」行错位孤儿（落在术语表后）归位；子代理/分包商两行合并去重
- README 兼容性说明数字滞后（description 373→241 未随 v0.7.0 同步）

### 跨平台

- validate 的 description 超限文案改为点明 **Codex/Copilot 静默丢弃**（比截断更危险）
- README 新增**跨平台硬约束矩阵**：entry≈299 截断（已适配 290）、>1024 静默丢弃（241 安全）、Cursor name=目录名、`.agents/skills/` 项目级公约

## [0.7.0] - 2026-10-07

评测落地与触发口径决策（承接上一节的全部内容，本版发布）。

### 新增

- **分册收尾红线**（debugging/onboarding/requirements）：把"动手完成 ≠ 可以交"写成可自答条款——原复现步骤复跑、根因层修复、全站搜索范围记账、红绿回归、启动/测试命令真跑过、档案落盘、问完即停
- **task-plan 并行性 + 执行波次**：串行判据（同文件/共享迁移契约/验证依赖前序产物），波次结束全量验证再开下一波——"并行只省时间，不省验证"
- **触发竞争决策（B 路线）**：两轮实测归因一致指向加载竞争（superpowers SessionStart 注入，16 条失败抢占 8 条）而非措辞。决策=把竞争定位从 description（299 字符可见预算）挪到安装引导文档，触发口径明确为"显式调用 + 高重合话术"；README 新增共存指引；A 路线（无竞争对照）留档待可控评测环境，C 路线否决（预期个位数收益）。决策记录与理由见 evals/trigger-tests.md
- **README** 新增「与其他流程技能共存」安装指引

### 评测基线（如实记录）

- 触发：两轮真实会话 24 条话术，6/24 → 7/24（正例 2/19、反例 5/5 零误触发），未达 ≥90%——竞争归因与决策见上
- 红测：S2 模糊需求 / S6 中途改需求 / S7 擅自调用其他技能 = 有效判别（基线红、有技能臂守住）；S1/S3/S4/S5 基线未红，保留为回归哨兵

## [0.6.0] - 2026-10-05

对标世界顶尖技能的**实现级**升级。三路精读：Anthropic 官方重型技能源码（docx/pptx/pdf/canvas-design/web-artifacts-builder）、社区大小对照（ui-ux-pro-max 679 行 / frontend-design 55 行）、顶尖方法论技能全文（superpowers/addyosmani/mattpocock 核心技能）。全部改动溯源见 docs/research-notes.md #28–#30。

### 门控与循环（取自顶尖方法论技能）

- HARD-GATE 升级为 **STOP YOUR TURN**：提问即本回合结束，不边问边做（addyosmani 句式）
- 新增**小歧义裁决权**：不影响目标/范围/验收的小分叉自行裁决并记账 `Ruling: 决定—理由—错了的代价`；按已批准计划连续执行，不在任务间问"要继续吗"；只允许四类事停下（不可逆/安全敏感/工作区外副作用/计划全坏）——"裁决而非停摆"
- 纪律红线顶部新增**优先级链**：用户当前指令 > 本技能 > 默认习惯（防技能与用户指令打架）

### 防跳步与反偏差（取自官方重型技能）

- 17 本分册统一首行：**CRITICAL：读完全册再动手；步骤按顺序执行，不得跳步**（forms.md 范式）
- code-review 审查心法新增"**假定有问题**：第一次零发现=没认真找；收尾前至少完成一轮找问题→修复→复验"（pptx QA 范式）
- code-review 新增**证据矩阵**：什么算验证证据（本回合命令输出/原症状测试通过/VCS diff）vs 什么不算（"看着没问题"/测试曾经绿过/子代理汇报/构建通过）

### 调试升级（取自 systematic-debugging / mattpocock）

- 定位阶段：**先列 3-5 个排序假设**，单假设会锚定；每个假设必须可证伪（说不出预测就丢弃）
- 修复阶段：**失败熔断 ≥3 规则**——同一问题第 3 次修复仍失败，停下质疑前提（复现可靠吗/假设错了吗/该升级给人），继续盲试是沉没成本

### 性能与检索（取自检索式知识库模式的中文适配）

- 新增 **scripts/lookup.py**：`python scripts/lookup.py <关键词>` 在 17 本分册中按加权子串检索（标题×3/清单×2），输出命中分册+≤3 行摘录（截断 120 字符），为找一条规则不再整册载入。实测三组关键词（迁移回滚/越权/根因排查）全部命中正确分册
- 四个脚本 docstring 统一补充**"会做 / 不会做"边界**（官方 pack.py Auto-repair 范式）：明确 RESULT PASS ≠ 审查通过等

### 去重与瘦身（单一清单原则）

- 反合理化表删除 2 行与红旗信号重复的条目（同一内容不出现两份——巨型技能通病）
- 装载即用/落盘约定/沟通协议/不适用区块两两去重；正文净增内容（门控+裁决+元规则+lookup 索引）与会话式压缩相抵，正文维持 ~5.1K tokens 预算内
- templates/task-plan.md 步骤升级为**三元组**：动作 → 运行 → 预期（writing-plans 的 Run/Expected 范式）

### 未采纳（精读后明确拒绝）

- docx 式 590 行单文件巨石（分册+条件路由更优）、canvas-design 式情感化施压（工程任务要可验证规则）、superdesign 式远程 URL 正文（离线即瘫）、ui-ux-pro-max 式入口镜像分册（双份维护负债）

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
