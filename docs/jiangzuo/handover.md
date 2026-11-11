# jiangzuo（将作）· 交接文档

> **这份文档的地位**：它是本项目**全部已知内容的唯一基准**。接手者（新的 AI 会话、另一个模型、或未来的我自己）
> 被假定**没有任何会话记录、没有长期记忆、没有历史上下文**。凡是这里没写的，就当它不存在；
> 凡是这里写了的数字，都附了取数命令——**别信文档，跑命令**。
> **写作时间**：2026-10-20（v0.40.0 交付复核 + 搬家 + 改名之后）。
> **关于外传（E27 起改了）**：本文档**已在仓库内**（`docs/jiangzuo/handover.md`，被 git 跟踪）——E26 那轮一个脚本 bug 毁掉整份文档、而它在仓库外 ⇒ **没有历史可回滚**，所以搬进来了。
> ⚠️ **但“不要外传”的原则只针对凭据**：第 5.4 节只讲**推送流程与命令**，**不含任何真实凭据**（真凭据在系统凭据管理器里，永远不入库）。⇒ 往本文档里加**真 token / 密码 / 私钥**仍然是禁止的（`preflight.py` 会当场报出来）。
> **文件名规矩**：`项目名-交接文档.md`。若以后再搬家/改名，文档名与第 2 节路径要同批更新（见第 12 节）。

---


> **本文档已在仓库内**（`docs/jiangzuo/handover.md`）⇒ 由 git 跟踪、改动可回滚。
> **本文里出现的所有路径都相对仓库根**（如 `scripts/`、`references/`、`../eval-runs/`）——因为 §13 的命令都是在仓库根下跑的。

## 0. 接手时先看这 10 行

1. 项目：**将作（jiangzuo）**——一个遵循 Agent Skills 开放规范的 AI 编程纪律技能，含一条零依赖安全审计链工具集。
2. 状态：**v0.92.0 已交付并推送**（`7112334`，tag `v0.92.0` 指向它，CI run `43047992208` **七道** success ＋**新作业** `release-consistency` run `43047992241` success）；**`main` 分支保护已配好**（E48：禁强推 / 禁删分支 / 管理员同禁，**不要求 PR、不要求 CI、不限制推送人** ⇒ 本项目的推送流程不受影响；**回读核对**过）；**「当前状态」不许冒充当前**（E47，第 23 项再扩：§2 的「当前状态（远端）」行由生成器产出并**逐字**对账 ⇒ **往里塞一个 sha 就当场红**）；**「规模」这行字由实物生成、逐字对账**（E46，第 23 项再扩：§0 的规模行由实物生成并**逐字**对账 ⇒ 写错 / **多写一个数** / 删掉 / 写两处当场红）；**轮次台账只许有一处**（E45，第 25 项再扩：轮号**全局唯一**／轮号↔版本与 CHANGELOG 一致／**不许漏轮次**／行序**不得回退**／每行必带 ✅／行里的「变异校准 N/N」与 CHANGELOG 对账）；**发行说明也不许走兜底**（E44，第 26 项再扩：兜底＝拿 tag 的提交说明当第二个来源 ⇒ 那一类差集**不再允许登记例外**）；**仓里的发行说明也不许成为第二真源**（E43，第 25 项再扩：每份 `docs/jiangzuo/releases/*.md` 必须与 CHANGELOG 生成的**逐字一致**）；**仓库身份只许有一处**（E42，第 7 项再扩：owner/name 收进 `scripts/repo_identity.py`，抄到第二个脚本当场红）；**门面的安装命令也有人守**（E41，第 7 项再扩：命令必须指向真实仓库 ⇒ 生态那扇门不再是死路）；**发布产物的「身份」有人守**（E37，第 26 项）、**Markdown 表格的结构也有人守**（E38，第 12 项第三条）、**远端发布产物的自洽也有人守**（E39，第 27 项 ⇒ CI 每日核「远端 Release ↔ 远端 tag 一一对应、零缺口」）、**台账自身也有人守**（E40，第 25 项扩三条：进化账本行序 ＋ 验收记录升序 ＋ **每个标记区对账它自己那一版**）。
   ⚠️ **发布与推送出过几次事（**细节只在第 2 节的历史记录里写一遍**，本节不重复）**：v0.72.0 改用 API 建 tag（首次发布、不是移动）＋ v0.73.0 全程走 git 通道（网络已恢复）＋ v0.74.0 传输通道断过一轮（换前端 IP 直推即通）＋ v0.51.0 的远端 tag 指错 commit（已按授权移动、并加了第 26 项）＋ v0.71.0 的 Release 曾发出后撤回（CI 尚红）＋ v0.75.0 的 CI 假红与「推送脚本报成功却没推」⇒ **现行规则见第 5.4 节**（网络一断就停推／已发布的 tag 不要移动／推完必须回读远端核对）。
   ✅ **v0.92.0**（E58，英文分册第三批——12/20，四本双语审全 PASS；E57 断言现查化修复的验证闭环）：版本笔 `7112334`、tag `v0.92.0`（annotated，tag 对象经回读核验、peel 后指向 `7112334`）、CI run **`43047992208` 七道 success** ＋ **新作业 `release-consistency` run `43047992241` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.92.0>；**发完自证：远端 90 个 tag 与本地逐条同 commit、Release 90 个 ✓**。
   ✅ **v0.91.0**（E57，英文分册第二批——8/20，四本双语审全 PASS；中文源两处笔误亲核后收口；测试断言写死「4 本」的坑进 §8 第 81 条）：版本笔 `624e3f1`、tag `v0.91.0`（annotated，tag 对象经回读核验、peel 后指向 `624e3f1`）、CI run **`42387985330` 七道 success** ＋ **新作业 `release-consistency` run `42387985380` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.91.0>；**发完自证：远端 89 个 tag 与本地逐条同 commit、Release 89 个 ✓**。
   ✅ **v0.90.0**（E56，微测规程修订——预注册独立提交锚定＋原始产出归档＋方差必填，新判据上线即逮住 E35 实测节缺锚定标记）：版本笔 `708ceff`、tag `v0.90.0`（annotated，tag 对象经回读核验、peel 后指向 `708ceff`）、CI run **`42379635134` 七道 success** ＋ **新作业 `release-consistency` run `42379635144` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.90.0>；**发完自证：远端 88 个 tag 与本地逐条同 commit、Release 88 个 ✓**。
   ⚠️ **E55 遗留的审稿二结论已回（补记如实入账）**：code-review **FIX+1**、debugging **FIX+1**——无漏译、无编造，仅 2 条走样且**均指向中文源疑似笔误**（code-review L50「全程可信」漏「不」字；debugging L22「上次正常到上次异常」应为「到首次异常」），已亲核原文确认；修法归 **E57** 收口（改中文源、英文不动），v0.89.0 不追加发布。另：审稿代理三次撞并发限额，第四次改前台才跑成（环境事实，如实记）。
   ✅ **v0.89.0**（E55，英文分册第一批——references/en/ 四本入库，骨架契约两套锚点一个机制，对照账守半拉子）：版本笔 `64f71bc`、tag `v0.89.0`（annotated，tag 对象经回读核验、peel 后指向 `64f71bc`）、CI run **`42245221593` 七道 success** ＋ **新作业 `release-consistency` run `42245221606` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.89.0>；**发完自证：远端 87 个 tag 与本地逐条同 commit、Release 87 个 ✓**（⚠️ 发布前核对的 2 条「有 Release 没 tag」是匿名 API 限流下的误报——带令牌核验实体与内容全部正确 ⇒ 匿名核验读数异常时用令牌复核，别急着下结论）。
   ✅ **v0.88.0**（E54，行为微测二轮——换指标测「过程可审计性」，本项目第一条有实测的行为增益声称（范围限定））：版本笔 `bd99078`、tag `v0.88.0`（annotated，tag 对象经回读核验、peel 后指向 `bd99078`）、CI run **`42058717897` 七道 success** ＋ **新作业 `release-consistency` run `42058717881` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.88.0>；**发完自证：远端 86 个 tag 与本地逐条同 commit、Release 86 个 ✓**。
   ✅ **v0.87.0**（E53，「三仓数字」接进期望值对账——第 14 项扩第四类，DVWA「69/68」那类漏网根治）：版本笔 `12c94ba`、tag `v0.87.0`（annotated，tag 对象经回读核验、peel 后指向 `12c94ba`）、CI run **`41860189215` 七道 success** ＋ **新作业 `release-consistency` run `41860188936` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.87.0>；**发完自证：远端 85 个 tag 与本地逐条同 commit、Release 85 个 ✓**。
   ✅ **v0.86.0**（E52，回填 §8 坑位清单——第 56–78 条，E28–E51 的坑一次清完）：版本笔 `f850df0`、tag `v0.86.0`（annotated，tag 对象经回读核验、peel 后指向 `f850df0`）、CI run **`41675714678` 七道 success** ＋ **新作业 `release-consistency` run `41675714717` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.86.0>；**发完自证：远端 84 个 tag 与本地逐条同 commit、Release 84 个 ✓**。
   ✅ **v0.85.0**（E51，「工作树脏文件清单 vs 本轮计划清单」变成机器闸）：版本笔 `5c97657`、tag `v0.85.0`（annotated，tag 对象 `d3e7e32…`，peel 后指向 `5c97657`）、CI run **`41669770202` 七道 success** ＋ **新作业 `release-consistency` run `41669770145` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.85.0>；**发完自证：远端 83 个 tag 与本地逐条同 commit、Release 83 个 ✓**。
   ✅ **v0.84.0**（E50，交接文档升级成「极致详细」版）：版本笔 `6dcff18`、tag `v0.84.0`（annotated，tag 对象 `cef71ec…`，peel 后指向 `6dcff18`）、CI run **`41577331111` 七道 success** ＋ **新作业 `release-consistency` run `41577331116` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.84.0>；**发完自证：远端 82 个 tag 与本地逐条同 commit、Release 82 个 ✓**。
   ✅ **v0.83.0**（E49，同一件事故只许写一遍）：版本笔 `c780e27`、tag `v0.83.0`（annotated，tag 对象 `f70012c…`，peel 后指向 `c780e27`）、CI run **`41573179529` 七道 success** ＋ **新作业 `release-consistency` run `41573179739` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.83.0>；**发完自证：远端 81 个 tag 与本地逐条同 commit、Release 81 个 ✓**；⚠️ **发布身份台账在发布后少了一条**（`v0.83.0` 未进 `evals/release-identity.json` ⇒ 发布脚本的「发完自证」当场报「台账缺一条」⇒ 退出码 1）⇒ **已 `--sync` 补齐并重新核过**：远端 81 个 tag 与真源逐条同 commit（81 个）、Release 81 个，一一对应 ✓。
   ✅ **v0.82.0**（E48，`main` 分支保护配上了）：版本笔 `9eac4a1`、tag `v0.82.0`（annotated）、CI run **`40199604360` 七道 success** ＋ **新作业 `release-consistency` run `40199604299` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.82.0>；**发完自证：远端 80 个 tag 与本地逐条同 commit、Release 80 个 ✓**；⚠️ **本项目第一次做「改仓库设置」这类外向变更** ⇒ **没有仓内判据能守** ⇒ 唯一保证是**回读核对**（PUT 200 之后又 GET 一次，逐项一致）。
   ✅ **v0.81.0**（E47，「当前状态」不许冒充当前）：版本笔 `c42b7b9`、tag `v0.81.0`（annotated）、CI run **`40195691530` 七道 success** ＋ **新作业 `release-consistency` run `40195691614` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.81.0>；**发完自证：远端 79 个 tag 与本地逐条同 commit、Release 79 个 ✓**。
   ✅ **v0.80.0**（E46，「规模」这行字由实物生成、逐字对账）：版本笔 `6443aa3`、tag `v0.80.0`（annotated）、CI run **`40191588980` 七道 success** ＋ **新作业 `release-consistency` run `40191589162` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.80.0>；**发完自证：远端 78 个 tag 与本地逐条同 commit、Release 78 个 ✓**。
   ✅ **v0.79.0**（E45，轮次台账只许有一处）：版本笔 `d7237ca`、tag `v0.79.0`（annotated，tag 对象 `647fe01…`，peel 后指向 `d7237ca`）、CI run **`40083548846` 七道 success** ＋ **新作业 `release-consistency` run `40083548839` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.79.0>；**发完自证：远端 77 个 tag 与本地逐条同 commit、Release 77 个 ✓**。
   ⚠️ **这一发踩到一件事（如实记）**：版本笔 `d7237ca` **漏了真源 `evals/current-state.json` 顶层的四个标量**（`version` / `round` / `measured_at` / `measured_at_commit` 还是上一版的值）⇒ **本笔已订正**；⚠️ **不回头改已发布的版本笔** —— tag 与 Release **都已发布**（**移动已发布 tag 是停牌项**），且 CHANGELOG 的 v0.79.0 条目**已随 Release 发布** ⇒ 改它就等于**制造第二个来源** ⇒ ⇒ 只能在本笔订正并如实记下。
   ✅ **v0.78.0**（E44，发行说明不许走兜底）：版本笔 `beffb2c`、tag `v0.78.0`（annotated，tag 对象 `a599fb8c…`，peel 后指向 `beffb2c`）、CI run **`40072860564` 七道 success** ＋ **新作业 `release-consistency` run `40072860596` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.78.0>；**发完自证：远端 76 个 tag 与本地逐条同 commit、Release 76 个 ✓**。
   ✅ **v0.77.0**（E43，仓里的发行说明不许成为第二真源）：版本笔 `6866f00`、tag `v0.77.0`（annotated，tag 对象 `ac0d3fa6…`，peel 后指向 `6866f00`）、CI run **`40063317061` 七道 success** ＋ **新作业 `release-consistency` run `40063317141` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.77.0>；**发完自证：远端 75 个 tag 与本地逐条同 commit、Release 75 个 ✓**。
   ✅ **v0.76.0**（E42，仓库身份只许有一处）：版本笔 `6961f9e`、tag `v0.76.0`（annotated，tag 对象 `34b0be44…`，peel 后指向 `6961f9e`）、CI run **`40008729945` 七道 success** ＋ **新作业 `release-consistency` run `40008730118` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.76.0>；**发完自证：远端 74 个 tag 与本地逐条同 commit、Release 74 个 ✓**。
   ✅ **v0.75.0**（E41，门面的安装命令必须是真的）：版本笔 `a80d9d0` ＋ 修复笔 `39e7a9f`、tag `v0.75.0`（annotated，tag 对象 `199f502b…`，peel 后指向 `39e7a9f`）、CI run **`39998274989` 七道 success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.75.0>；**发完自证：远端 73 个 tag 与本地逐条同 commit、Release 73 个 ✓**。
   ⚠️ **这一发踩到三件事**（CI 假红 / tag 被移过一次 / 推送脚本报成功却没推）⇒ **细节见第 2 节**，**现行规则见第 5.4 节**。
   ✅ **v0.74.0**（E40，台账自身不许被写坏）：版本笔 `bfab558`、tag `v0.74.0`（annotated，tag 对象 `467e7a10…`，peel 后指向 `bfab558`）、CI run **`39958442615` 七道 success** ＋ **新作业 `release-consistency` run `39958442563` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.74.0>；**发完自证：远端 72 个 tag 与本地逐条同 commit、Release 72 个 ✓**。
   ✅ **v0.73.0**（E39，远端发布产物的自洽进 CI）：版本笔 `7cf1704`、tag `v0.73.0`、CI run **`39921694950` 七道 success** ＋ **新作业 `release-consistency` run `39921694873` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.73.0>；**发完自证：远端 71 个 tag 与本地逐条同 commit、Release 71 个 ✓**。
   远端 `main` 与本地一致（`git rev-list --left-right --count origin/main...HEAD` = `0 0`），无待推笔
   （见下面「远端一致性」一栏）。工作树干净（`git status --porcelain` 空）。
   <!-- current-state:begin -->
   **本机闸门 2026-11-11 当场重跑**：353 用例 OK ｜ validate **32** 信息/0 警告/0 错误 ｜ preflight PASS ｜
   ship_check L1 SHIP-OK（6/0/0）｜ audit_rules RULES-OK（33 条，另有 1 条数据停用）｜ 靶场 ACCEPT-OK（25/25 检出 & 0/19 安全样本）｜
   变异校准 **103/103 全红**（无 SKIP、无 GREEN、无 INVALID）｜ 性能 **BENCH-OK 9.993 ms/文件**（预算 ≤20，⚠️ 本机较忙，非回归：重建基线同刻对比见台账）｜ 第三方三仓
   DVWA **58 发现/结论 58**、flask 13/1、requests 4/0、DVWA 覆盖 **14/19** ｜ 本仓库自扫 **8 发现/结论 0/另计 8**。
   <!-- current-state:end -->
   ⚠️ **误报率口径已重述成三类（E28）**：结论区 59 ＝ 真阳性 **55** + 误报 **4**，4 条按"能不能靠改规则消掉"分：**静态可修 0（E29 已清零）/ 待能力升级 0（E31 已清零）/ 静态消不掉 4（能力边界型）**；**E32 把「全部产出」口径也判完了** ⇒ 全部产出 75 ＝ 真阳性 55 + 误报 4 + 另计 16 ⇒ **误报率 4/75 ≈ 5.3%**
   ⇒ **"静态可修的硬误报"= 0 / 59 = 0%（E29 清零）**（E20 是 8/69 ≈ 11.6% ⇒ 降 100%），**未判定 = 0**。
   逐条判定表在 `evals/finding-verdicts.md`（随技能分发，`validate_skill` 第 21 项守住它的自洽）。
   ⚠️ **官方 SARIF validator（`@microsoft/sarif-multitool` 5.8.0）已在本机跑通**：`validate` 报 **0 error**
   （修前是 **8 条 JSON1005**）—— 见 E21。它**非零依赖、CI 装不了** ⇒ CI 跑的是等价的**白名单自检**。
   ⚠️ **引擎的能力边界已写进分册**（E22）：6 条边界各有**实测证据**、每条被最小夹具钉住
   ⇒ **"没报"≠"安全"**（`references/audit-rule-authoring.md` 的「能力边界表」）。
   ⚠️ **变异校准器已随技能分发**（E24）：`scripts/mut_calibrate.py`，CI 跑 `--check-only` 核对锚点。
   ✅ **发行形态已闭环**（E33）：**65 个 GitHub Release 全部发布**（与 65 个 tag 一一对应；其中 64 个是补发、1 个是本发 v0.67.0）⇒ 发行说明的**单一真源是 `CHANGELOG.md`**（由 `scripts/release_notes.py` 生成）⇒ 不会与实现漂移。
   ⚠️ **本文档已入库**（E27）：`docs/jiangzuo/handover.md`，`validate_skill` **第 20 项**守住「在仓库内 + 章节完整 + 被 git 跟踪」。
   ✅ **门面（中英两个 README）的数字都有人守了**（E36）：英文 README 曾停在 v0.3x 遗物状态（4 个脚本 / 222 行 / 373 字符，且整条审计链主线一字未提）⇒ 已拉齐，并纳入 `validate` 的同一道闸；**且入口行数改比「正文行数」**（500 上限约束的是正文，旧实现拿文件总行数当真源 ⇒ **一道在逼人说假话的锁**）。
   ✅ **发布产物的「身份」现在有人守了**（E37）：远端 `v0.51.0` 实际指向 **v0.66.0 的补记笔**（E36 那句「68 tag / 68 Release 一一对应、零缺口」当时**是真的**——它只数了**名字与数量**）⇒ 已加 `validate` **第 26 项** 与 `scripts/release_identity.py`（owner 规则 + 远端三边对账），并修掉根因（`--publish` 先核远端 tag，缺或不对就**拒绝发布**）；🔴 **远端那个 tag 的修复＝移动已发布 tag＝停牌项**，待点头（方案见 §2）。
   ✅ **纪律层的「行为收益」现在有实测、且结论是"不许声称"**（E35）：微测双臂 **A 0/5 失败（0%） vs B 0/5 失败（0%）** ⇒ **基线未红** ⇒ 铁律与门函数**无可测的行为增益** ⇒ 记作**回归哨兵**（`validate` **第 24 项**守住"判定不许脱离数据"）。
   ✅ **「当前状态」有人守了**（E34）：`evals/current-state.json` 是它的**唯一机器可读真源**；上面那段 `current-state` 标记区里的每个数都逐个与真源对账 ⇒ **同一个数两处不同，当场红**（`validate_skill` **第 23 项**）。⚠️ 标记区**外**的数字是**历史**，不受管（那是"当时真值"）。
3. 位置：项目根 `D:\Github项目\jiangzuo\`，仓库根 `D:\Github项目\jiangzuo\jiangzuo\`（外层=项目、内层=仓库，同名故意的）。
4. **规模**：**20 分册 / 22 个 Python 脚本 / 3 份规则 JSON / 14 模板**（本行由 `scripts/current_state.py` 从实物生成、第 23 项**逐字**对账 ⇒ 不许手抄）
5. 远端：https://github.com/Zhang-jx00/jiangzuo （Public，唯一分支 `main`，未开分支保护）。
6. 交付说明（含**未达标与未验证清单**）：仓库内 `docs/jiangzuo/reports/2026-10-15-delivery-v0.36.1.md`。
7. 逐轮决策账本：仓库内 `docs/jiangzuo/evolution.md`（行数与 KEEP/部分成立/ROLLBACK 分类**现查**：
   该文件末尾的「上表 N 条」声明由脚本数出来、第 12 项对账，**不在此手抄**——E51 订正：此处原手抄「55 条」早已过期）；
   逐版本记录：`CHANGELOG.md`（每个版本一条）。
   ⚠️ **校准例数也是机器判据**（E24）：`validate_skill.py` 第 19 项从实物数出 CASES 条数并与
   CHANGELOG 最新条目对账 ⇒ **手数的偏差当场红**（E19–E23 曾连续五轮写错）。
3. **零依赖、零网络**：14 个脚本只用标准库，可审计、可在任何环境直接跑。这是"能被任何项目采用"的前提。
4. **审计只读**：扫描不改被扫项目的任何文件；产物写到**仓库外**（`../eval-runs/` 或调用方指定），技能目录不被污染。
5. **工具与人的分工**：工具穷举 + 核验位置，人判断"能不能被利用"。`auth=false` 只代表"本文件内未见鉴权标记"，
   不许直接当漏洞写进报告（这是本项目实测的头号误报源）。
6. **0 发现 ≠ 0 风险**；逻辑漏洞、权限模型、竞态不在正则的能力范围内，报告必须写复测点。
7. **规则/判据改动必须配对**：加一条正向判据，同时给一条能让它红的变异校准；
   **一条永远绿的锁比没有锁更坏**（本项目实测撤掉过一条无牙的锁）。
8. **记账是交付的一部分**：`CHANGELOG.md`（版本条目，日期＝该版本在 git 里落笔那天）、
   `docs/jiangzuo/evolution.md`（一行一次变异）、`docs/jiangzuo/constitution.md`（常驻门槛）。**没记账的变更视为未发生。**
9. **审计与修复分开交付**：扫完就改＝违反最小改动原则；修复走正常任务分级。
10. **对外声称的防护栏必须当场可验证**：写"CI 绿"就要能贴出六道步骤各自的 success；写"无密钥"就要能贴出扫描覆盖数与
    一条能红的校准。**复现不了的一律写进"未达标与未验证清单"。**

---

## 1. 这个项目是什么，为什么这样设计
54:     28→
55:     29→**将作**（取自古代皇家营造机构「将作监」）解决的问题：AI 写代码快，但**没纪律**——不读代码就动手、需求模糊就开写、
56:     30→没验证就说"完成"、改一处坏三处。技能把"资深全栈工程师 + 技术负责人"的工作方式注入进去，覆盖从想法到上线。
57:     31→
58:     32→三层结构，缺一不可：
59:     33→
60:     34→| 层 | 载体 | 作用 |
61:     35→|---|---|---|
62:     36→| 纪律层 | `SKILL.md` 入口 | 五步循环（先读懂→再想清→后动手→必验证→留文档）、L0–L4 任务分级门（单向棘轮只升不降）、六类必问 HARD-GATE（提问即结束回合）、铁律
63:     37→| 知识层 | `references/` 20 本分册 | **按需读取**：入口只留路由表，典型任务只读 1–3 本；每本以 `CRITICAL` 防跳步行开头，统一骨架（何时读/前置/产出 
64:     38→| 工具层 | `scripts/` 14 个脚本 | 纯标准库、零第三方依赖、零网络调用；其中 `audit_*` 五件套 + `auditlib` 组成**全项目安全审计链** |
65:     39→| 自约束层 | 四道闸门 + 六道 CI + 账本 | 技能仓库**用自己发的标准卡自己**，且把"复发过的错"逐条做成会红的判据 |
66:     40→
67:     41→**目标用户**：任何用 AI 做软件项目的人。**差异化**：别人给提示词，这里给"可验证的流程 + 可审计的工具 + 自我约束的账本"。
68:     42→
69:     43→**非目标（明确不做）**：不做代码片段合集；不联网拉数据；不装第三方依赖；不把 agent 无法执行的话写进分册；
70:     44→不替人做安全判断（工具给"候选发现 + 证据链"，不给"漏洞判决书"）。
71:     45→
72:     46→---
73:     47→
74:     48→
75: 
76: 

## 2. 目录树与文件地图

```
D:\Github项目\jiangzuo\                 项目根（不入库）
├── jiangzuo\                           git 仓库根 = 技能根
│   ├── SKILL.md                        入口：正文 201 行 / 约 4992 token（预算 5000）
│   ├── references\                     20 本分册（api-design / audit-rule-authoring / backend / code-review /
│   │                                   database / debugging / design / devops / docs-delivery / frontend /
│   │                                   incident / onboarding / refactor-performance / requirements /
│   │                                   security / security-audit / self-evolution / skill-orchestration /
│   │                                   testing / ui-design）
│   ├── templates\                      14 个填空模板（new_doc.py 消费）
│   ├── scripts\                        审计链脚本 + audit-rules\ 下的规则 JSON
│   ├── evals\                          评测集与验收记录
│   ├── docs\                           交付报告、进化账本、宪法、对标差距分析、术语表、研究笔记
│   ├── tests\                          test_scripts.py（286 用例，单文件）
│   ├── agents\openai.yaml              Codex 系客户端 UI 元数据
│   ├── .github\                        workflows\validate.yml + PR 模板 + issue 模板
│   ├── README.md / README.en.md / CONTRIBUTING.md / CHANGELOG.md / LICENSE / .gitignore
│   └── （.git\ 在此目录内）
├── eval-runs\                          草稿、评测留痕、第三方扫描原始 JSON（**在仓库之外，永不入库**）
└── jiangzuo-交接文档.md                本文档
```

**14 个脚本各干什么**（`scripts/`，全部 `python <脚本> --help` 有中文帮助）：

| 脚本 | 职责 |
|---|---|
| `project_scan.py` | 项目摸底扫描 → profile 草稿（识别锁文件、清点环境变量） |
| `preflight.py` | 交付前静态检查：密钥特征 / 调试残留 / 冲突标记 / TODO / 大文件 / diff 统计，输出 `RESULT: PASS/FAIL`，`--strict` 供 CI |
| `new_doc.py` | 按模板在目标项目生成 `docs/jiangzuo/` 文档骨架（ADR 自动编号） |
| `lookup.py` | 分册检索器（两段式：整词优先 → 2-gram 重试 + 人工路由词表 `BOOKLET_ALIASES` 加权 + df 泛词过滤） |
| `validate_skill.py` | 技能结构校验器（CI 门禁）+ `--stats` 占用报告，判据清单见第 5.2 节 |
| `ship_check.py` | 交付闸门：测试通道 / 静态检查 / 交付报告（四问与可证伪主张 + **必须真被 git 跟踪**）/ 自净核对 / 常驻标准 / 技能结构 |
| `evolve_report.py` | 进化信号采集（只读，产出"该改哪条"的候选排序） |
| `review_packet.py` | 把"交给审查者/子代理的东西"钉成一个文件 |
| `auditlib.py` | 审计链共享库：索引、sha1、gitignore 语义、`iter_code_lines`（跳注释/文档块/字符串）、`match_in_string`、`redact` 脱敏 |
| `audit_index.py` | ① 文件索引（可复现清单 + skipped 留痕） |
| `audit_map.py` | ② 项目侦察地图（语言/入口/路由/鉴权边界/依赖/外联） |
| `audit_rules.py` | ③ 声明式规则引擎（字段校验 + **每条正则当场编译** + OSV 离线导入 + 同 id 遮蔽检测） |
| `audit_graph.py` | ④ 跨文件调用图 + 污点分析（函数级、按名字全仓解析、可达性 BFS、净化点断链记账） |
| `audit_scan.py` | ⑤⑥⑦ 调度（粗筛→深挖）、**独立五项复核（反幻觉）**、置信度×严重度分级、MD/JSON/SARIF 2.1.0 报告、缓存增量、基线对比、豁免与语境档、`repo_role()` |

**规则是数据**：`scripts/audit-rules/{injection(12), webapp(20), crypto(2)}.json` = 34 条目（1 条数据停用）。
字段：`kind`（taint/pattern/dependency/auth_gap）、`severity`、`cwe`/`owasp`、`sinks`/`sources`/`sanitizers`/`unless_present`、
`fix`、`retest`，以及治理字段 `scope:"app"`、`ignore_strings`、`console_when_routeless`、`optout_params`、`enabled:false`、`note`。
加自己的规则：`--add my.json`（同 id 可覆盖内置）；`--rules` 指定；`--enable-all` 把停用规则加回。

---

### 远端一致性（**当前状态怎么核** ＋ 历史记录）

- **当前状态（远端）**：**零待推 ⇔ 远端 `main` 与本地 `HEAD` 同 commit** ⇒ 核法：`git ls-remote origin refs/heads/main`（**sha 每笔都变 ⇒ 不写死**：写死即过期，E47 实测已过期 8 个版本）
- **最新一发的 CI / Release 证据**：见**第 0 节**的 ✅ 逐版行（那里是**唯一一处**，本节不重复）。
  CI 的**七道**步逐一 success（第 4–10 步；E24 加了第 9 步「变异校准锚点核对」；
  末步「六道闸门诊断」是 `if: failure()` 条件步，前面的都绿时本来就不跑 ⇒ skipped 属正常）。
- ⚠️ **E27 那轮推送中断过一次**：`github.com:443` 主站不可达（`api.github.com` 仍可读 ⇒ 非凭据问题），
  有界重试 5 次全败 ⇒ 按老规矩**停推、如实留痕**；网络恢复后补推成功。
  ⇒ **现行规则见第 5.4 节**（网络一断就停推；唯一允许的绕法是换前端 IP；推完必须回读远端核对）。
- ✅ **发行形态已闭环**（E33：Release 与 tag **一一对应**；其中 **64 发是补发**、1 发是本发 v0.67.0）⇒ **发行形态不再只到 tag**。
  ⚠️ **现在到底多少个 Release、对应哪一版**：**见第 0 节**的 ✅ 逐版行（**不写死**：每发一版就变；E47 实测此处已过期 8 个版本）。
  发行说明的**单一真源是 `CHANGELOG.md`** ⇒ `scripts/release_notes.py` 从它生成每一发的正文并发布 ⇒
  **不会与实现漂移**（手抄的副本会漂移——这项目已吃过"手数的偏差会自我延续"的亏）。
  ✅ v0.15.0–v0.19.0 那 5 版**已由 E44 补录** CHANGELOG 条目（内容＝各 tag 的**提交说明原文**、日期＝作者日期、并注明是补录）⇒ **兜底数归零**（`release_notes.py --check` 现在报「走兜底 **0** 个」）
  ⇒ 发行说明**不再有第二个来源**。
**以下为历史记录**（v0.70.0–v0.78.0 那一段；**最新一版见第 0 节**）：

- **补发那 64 发时的做法（历史）**：用的是系统凭据管理器里的凭据（`git credential fill`，用完即删）；v0.67.0 这一发时该入口**已不响应**（6 种请求形态全试过 ⇒ rc=128 空口令）⇒ 改从 **origin remote URL** 里取（本地 `.git/config`）⇒ **两种来源都不入库**（**现行规则见第 5.4 节**，那里是唯一一处）。

- ⚠️⚠️ **E37 复核查出：远端 `v0.51.0` 的 tag 指错了 commit**（**内容错，不是数量错**）。
  - **事实**：远端 `refs/tags/v0.51.0` 是**轻量** tag，指向 `d5b88e1a` —— 那是 **v0.66.0 的补记笔**
    （2026-10-22 17:22:28 +0800），不是 v0.51.0 的代码。v0.51.0 的正确目标是 `d5da9f39`
    （E17 的 `fix(rules)` 提交；本地那个 annotated tag 的 tagger 时间戳 `1792578222 +0800`
    = 2026-10-21 18:23:42，正是 E17 提交后 1 分钟 ⇒ **本地那个是对的**）。
  - **根因（已证实）**：`scripts/release_notes.py --publish` 调 `POST /releases` 时
    ① **没带 `target_commitish`**（GitHub 默认用默认分支 main）；
    ② **不检查远端该 tag 是否已存在** ⇒ 补发一个「远端还没有 tag」的版本时，
    GitHub 会在 main 的 HEAD 上**自动造出**一个同名 tag（名字对，内容是当时 main 的内容）。
    远端 `v0.51.0` 的 `created_at`（2026-10-22T09:22:28Z）与其 Release 的 `created_at` **同秒** ⇒ 正是这条路径。
    ⚠️ 「E17 那轮为何远端缺这个 tag」**未验证**（当时的推送记录已不可查）—— **不猜**。
  - **为什么此前没人发现**：E36 那句「68 tag / 68 Release 一一对应、零缺口」当时**是真的** ——
    它只数了**名字与数量**。**「发布产物存在」≠「发布产物是它该有的那个」。**
  - **已修（防复发）**：`--publish` 现在**先核远端 tag**，缺失或指向不对 ⇒ **拒绝发布**；
    发布时显式带 `target_commitish`；发完**回头自证**。另有
    `scripts/release_identity.py --remote` 可随时核（远端 tag ↔ 真源 ↔ Release 三边对账）。
- ✅ **v0.78.0 已交付**（2026-10-24，E44）：版本笔 `beffb2c`、tag `v0.78.0`（annotated，tag 对象 `a599fb8c…`，peel 后指向 `beffb2c`）、CI run **`40072860564` 七道 success** ＋ **新作业 `release-consistency` run `40072860596` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.78.0>；**发完自证：远端 76 个 tag 与本地逐条同 commit、Release 76 个 ✓**；真源 `evals/release-identity.json` 同步为 **76 个 tag**（由 `--sync` 生成，不手抄 sha）。
- ✅ **v0.77.0 已交付**（2026-10-24，E43）：版本笔 `6866f00`、tag `v0.77.0`（annotated，tag 对象 `ac0d3fa6…`，peel 后指向 `6866f00`）、CI run **`40063317061` 七道 success** ＋ **新作业 `release-consistency` run `40063317141` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.77.0>；**发完自证：远端 75 个 tag 与本地逐条同 commit、Release 75 个 ✓**；真源 `evals/release-identity.json` 同步为 **75 个 tag**（由 `--sync` 生成，不手抄 sha）。
- ✅ **v0.76.0 已交付**（2026-10-24，E42）：版本笔 `6961f9e`、tag `v0.76.0`（annotated，tag 对象 `34b0be44…`，peel 后指向 `6961f9e`）、CI run **`40008729945` 七道 success** ＋ **新作业 `release-consistency` run `40008730118` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.76.0>；**发完自证：远端 74 个 tag 与本地逐条同 commit、Release 74 个 ✓**；真源 `evals/release-identity.json` 同步为 **74 个 tag**（由 `--sync` 生成，不手抄 sha）。
- ✅ **v0.75.0 已交付**（2026-10-24，E41）：版本笔 `a80d9d0` ＋ 修复笔 `39e7a9f`、tag `v0.75.0`（annotated，tag 对象 `199f502b…`，peel 后指向 `39e7a9f`）、CI run **`39998274989` 七道 success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.75.0>；**发完自证：远端 73 个 tag 与本地逐条同 commit、Release 73 个 ✓**；真源 `evals/release-identity.json` 同步为 **73 个 tag**（由 `--sync` 生成，不手抄 sha）。
  ⚠️ **三条如实记录**：① 版本笔的 CI **假红**一次（日期判据的**时区**洞：CI 在 UTC、作者在 +0800）⇒ 已修（基准取 max(机器日期, **提交自己的作者日期**)）＋ 判据 `TestChangelogDateTimezone` 3 条 ＋ 校准 81/81；② **tag 移过一次**（`a80d9d0` → `39e7a9f`）—— 移的时候该 tag **还没有 Release、安装计数 0** ⇒ 没人拿到过它；③ **我自己的推送脚本报成功却没推**（退出码 0 ＋ "Everything up-to-date"）⇒ 已改成**推完回读远端核对**。
- ✅ **v0.74.0 已交付**（2026-10-23，E40）：版本笔 `bfab558`、tag `v0.74.0`（annotated，tag 对象 `467e7a10…`，peel 后指向 `bfab558`）、CI run **`39958442615` 七道 success** ＋ **新作业 `release-consistency` run `39958442563` success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.74.0>；**发完自证：远端 72 个 tag 与本地逐条同 commit、Release 72 个 ✓**；真源 `evals/release-identity.json` 同步为 **72 个 tag**（由 `--sync` 生成，不手抄 sha）。
  ⚠️ **v0.74.0 那天传输通道又断过一轮** —— `git push` 先报 `Authentication failed`、再报 `Failed to connect to github.com:443 after 21157 ms`；**同一枚令牌在 API 通道完全正常**（`/user` 200）⇒ **不是凭据问题**，是那个**时好时坏**的传输阻断 ⇒ 用 `curl --resolve` 扫前端 IP（8 个可通）⇒ **换前端 IP 直推即通**（`main` 走 `140.82.113.3`、tag 走 `20.205.243.166`；**不落配置文件、不改走 SSH、不换令牌**）⇒ **不需要 API 建 tag**。
- ✅ **v0.73.0 已交付**（2026-10-23，E39）：版本笔 `7cf1704`、tag `v0.73.0`（annotated，tag 对象 `c00c4a69…`，peel 后指向 `7cf1704`）、CI run **`39921694950` 七道 success** ＋ **新作业 `release-consistency` run `39921694873` success**（首次运行即绿）、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.73.0>；**发完自证：远端 71 个 tag 与本地逐条同 commit、Release 71 个 ✓**。
- ✅ **v0.72.0 已交付**（2026-10-23）：版本笔 `390cf5e`、tag `v0.72.0`（annotated，tag 对象 `a2ecfc95…`，peel 后指向 `390cf5e`）、CI run **`39913456149` 七道 success**、Release <https://github.com/Zhang-jx00/jiangzuo/releases/tag/v0.72.0>。
  ⚠️ **v0.72.0 的 tag 是经 API 通道发布的** —— `github.com:443` 的 **git 传输通道在 TLS 层被选择性阻断**（TCP 层可连；DNS 指向的 `20.205.243.166` 与另外三个候选 IP 全部 Empty reply / timeout；而 `api.github.com` **完全正常**）⇒ `git push origin v0.72.0` **有界重试 10 次全败**。
  ⇒ 改用 **GitHub API** 建 tag：**同一枚凭据、同一个目标**（把 v0.72.0 发布到远端）；且**已确认远端没有该 tag**（`GET /git/ref/tags/v0.72.0` = 404）⇒ 这是**首次发布**，**不是**「移动已发布 tag」那类停牌项。
  ⇒ **先验证再落 ref**：先 `POST /git/tags` 造 tag 对象，**比对 SHA 与本地是否逐字节一致**，一致才 `POST /git/refs` 挂上去 ⇒ 造出来的 `a2ecfc95…` **与本地完全相同**（**不是**轻量 tag）⇒ 将来 `git fetch` 不会像 v0.51.0 那样撞车。
  ⇒ 顺带：GitHub 的 `date` 参数要 **`+08:00`（带冒号）**，而 git 对象里存的是 `+0800` ⇒ 照抄会 422（epoch 不变 ⇒ 对象内容仍一致）。
  - ✅ **已修（2026-10-23，当所有者授权后执行）**：`git push --force origin refs/tags/v0.51.0:refs/tags/v0.51.0`
    ⇒ GitHub 上 `v0.51.0` 的指向从 `d5b88e1a` 变成 **`d5da9f39`**（`d5b88e1...60790e3 forced update`）
    ⇒ 该 tag 对应的 Release 也随之指向正确的代码。
    **验证**：`release_identity.py --remote` 从「**恰好 1 条**不符（其余 67 个逐条同 commit、零假阳性）」
    变成「远端 69 个 tag **逐条与本地同 commit**」，只剩「v0.71.0 有 tag 没 Release」——
    那一条是**故意撤回**的（见下），等 CI 转绿后重发即闭合。
    ⚠️ **判据的闭环**：这条错 tag 是被**新增的第 26 项**在 CI 上**如实报出**的（CI 的 tag 是从远端 fetch 的
    ⇒ 那一层核的就是远端）⇒ 修完之后该判据变绿 ⇒ **判据不是摆设，是真的会红**。
  - ⚠️ **v0.71.0 的 GitHub Release 曾发出、后撤回**：发出时 CI 尚红（run `39904985872` 第 4 步 validate 失败）
    ⇒ **次序不合本项目「CI 全绿后才发 Release」的规矩**（我先发 Release、后核 CI）⇒ 按所有者决定**撤回**，
    **已在 CI 转绿后重发**（CI run `39906612809` 七道 success 之后），**发完自证**：远端 69 个 tag 与本地
    逐条同 commit、Release 69 个 ✓。撤回时 **tag `v0.71.0` 未被连带删除**
    （GitHub 删 release 不删 tag；已核：ref 仍是 annotated tag 对象 `9ba47406`）。
## 3. 十条核心不变量（改任何东西前先守这几条）

1. **入口预算是硬的**：`SKILL.md` 正文 ≤500 行且 ≤5000 token（估算），`description` ≤1024 字符，
   **Qoder CN 清单 entry 可见预算 299 字符**（超出即被截断——这是触发率问题的根因之一）。
   加内容必须先删内容；改完跑 `validate_skill.py --stats` 核对。
2. **分册一层深**：分册之间不许有阅读链（校验项 9）。
3. **零依赖、零网络**：14 个脚本只用标准库，可审计、可在任何环境直接跑。这是"能被任何项目采用"的前提。
4. **审计只读**：扫描不改被扫项目的任何文件；产物写到**仓库外**（`../eval-runs/` 或调用方指定），技能目录不被污染。
5. **工具与人的分工**：工具穷举 + 核验位置，人判断"能不能被利用"。`auth=false` 只代表"本文件内未见鉴权标记"，
   不许直接当漏洞写进报告（这是本项目实测的头号误报源）。
6. **0 发现 ≠ 0 风险**；逻辑漏洞、权限模型、竞态不在正则的能力范围内，报告必须写复测点。
7. **规则/判据改动必须配对**：加一条正向判据，同时给一条能让它红的变异校准；
   **一条永远绿的锁比没有锁更坏**（本项目实测撤掉过一条无牙的锁）。
8. **记账是交付的一部分**：`CHANGELOG.md`（版本条目，日期＝该版本在 git 里落笔那天）、
   `docs/jiangzuo/evolution.md`（一行一次变异）、`docs/jiangzuo/constitution.md`（常驻门槛）。**没记账的变更视为未发生。**
9. **审计与修复分开交付**：扫完就改＝违反最小改动原则；修复走正常任务分级。
10. **对外声称的防护栏必须当场可验证**：写"CI 绿"就要能贴出六道步骤各自的 success；写"无密钥"就要能贴出扫描覆盖数与
    一条能红的校准。**复现不了的一律写进"未达标与未验证清单"。**

---

## 4. 开发进度：走到哪了

**版本节奏**：`v0.1.0`（2026-10-05 初版）→ `v0.6.0`（对标世界顶尖技能，实现级重写）→ `v0.14`–`v0.20`（审计链十环落地）
→ `v0.21`–`v0.26`（性能/并发/基线/CI 预算）→ `v0.27`–`v0.34`（第三方真实仓库取证：flask / requests / DVWA）
→ `v0.35`–`v0.36.1`（编排合同 + **D4 复核：六条静默缺陷一次现形并全部做成判据**，v0.36.1 正式交付）
→ `v0.37`–`v0.40`（交付后加固五轮，见下）。

**交付后的 E 系列（逐轮，每轮一个独立提交 + tag）** —— ⚠️ **这里是唯一一处轮次台账**（E45 把
原先分散在第 4 节与第 11 节的两份手抄表合并到这儿；真源是 `CHANGELOG.md` 的版本条目 ⇒
**第 25 项逐行对账**：轮号唯一、**升序**、轮号↔版本与 CHANGELOG 一致、**不许漏轮次**、
每行必须带 ✅、行里的「变异校准 N/N」必须与 CHANGELOG 一致 ⇒ **手抄漂了当场红**）。

| 轮 | 版本 | 这一轮干了什么（主题 ＋ 验收信号） |
|---|---|---|
| **E1** ✅ | v0.37.0 | 照 DVWA 真实代码形态补 cryptography / javascript 两类规则，靶场主类别检出 **11/19 → 13/19**；顺带修掉引擎级缺陷"**两份内置规则文件撞同 id ⇒ 后加载者静默遮蔽前者**"并加判据 |
| **E2** ✅ | v0.38.0 | 160 行顶死的 `security-audit.md` 拆成"使用侧"（139 行）+ 新分册 **《规则治理与引擎成本》**`audit-rule-authoring.md` |
| **E3** ✅ | v0.39.0 | 两道文档结构判据：Markdown **表格行头完整性**（我自己的第 4 次复发错误，终于变成机器红）+ **"上表 N 条"与表内实际数据行数对账**（上线当场又逮到我两处过期数字） |
| **E4** ✅ | v0.39.1 | 内存这条"欠账"**量出来结论反了两次**：门控路径已平（×6.3 文件 → ×1.09 内存），候选占满才线性（**15.4 KB/文件峰值 / 7.4 KB/文件驻留**）；**撤掉一条我自己写的无牙预算锁** |
| **E5** ✅ | v0.39.2 | 两条挂着的"待办"读完代码后**改判**（静态 include 建边只剩"模块级变量共享"一格、且做宽会变误报制造机）⇒ 不动预防性工程 |
| **E6** ✅ | v0.40.0 | **CI 连续 22 次红修好**（详见第 8 节第 1–4 条）+ 六道闸门诊断步进注解 + 远端实测转绿 |
| **E7** ✅ | v0.41.0 | **"干净仓库误报"这个标尺从 v0.37.0 起一直是脏的**——语境档认不出带限定词的目录（`evals/audit-fixtures/`），语料生成器的命中被算进结论区；三段快照实测定位转折点 → 目录段按 `-`/`_` 拆词后精确匹配；三仓数字 A/B **一字未变**，自扫结论 3→0 |
| **E8** ✅ | v0.42.0 | **给"照着跑就能看到"的期望值补判据**——写死的数字会悄悄错很久，而错的是基线时没人看得出来。三类期望值接唯一真源（用例数 / 语料分母 / 规则条数），真源全静态取（不跑扫描、不生成语料、不执行被测脚本 ⇒ 跨平台同色）；**第一跑就逮到真过期**（交付报告 §6 的 `Ran 138 tests`）；中途被既有测试逮到一次**误伤**（形态完整性按仓库判会把合法的最小技能目录判死 ⇒ 改成按文件判） |
| **E9** ✅ | v0.43.0 | **PHP 读原始请求体（`php://input`）也是"外部可控输入"——之前整类是盲区**。6 条 PHP 请求体规则各加一个 source 形态；DVWA 覆盖 **13/19 → 14/19**，新增 2 条**全是真阳性**、0 误报，flask/requests/自扫/语料误报**一律不变**；语料 42 文件 24/24 & 0/18。顺带量出**四个还没修的缺口**（引擎污点穿函数返回值 / `mysqli_real_escape_string` 不算净化点 / PHP `exec()` 归错规则 / XSS 族待接），全部写进 §11 第 2 条而不是静默留着 |
| **E10** ✅ | v0.44.0 | **PHP 的"跨函数形参污点"整条是坏的**——修复前 `function show($name){ echo $name; } show($_GET['name']);` **一条都报不出来**。**先复核**（用户要求）查出是**两层**根因：① `_params()` 把 PHP 形参 `$name` 转成 `_name`（载体名却是 `name`）② `add_module_scope()` 写死"顶层 ≥ 3 行才建作用域"，短文件顶层整段不进数据流（**与它自己的 docstring 自相矛盾**）。两层都修 ⇒ 同文件/跨文件 helper 形态从 0 条变 1 条，**三仓/自扫/语料零回退**；变异校准 14/14 全红 |
| **E11** ✅ | v0.45.0 | **PHP 的"返回值"语义：修复前"实参"被当成了"返回值"**。复核写四个最小夹具实跑 ⇒ **4 错 3**（返回值是常量⇒误报 / 先净化再返回⇒净化被整条绕过 / 污点源在被调函数内部⇒漏报）。根因：赋值传播只看"等号右边有没有脏变量"，**不区分实参与返回值**。修法：给每个 (函数, 规则) 算「返回摘要」（`dep_pos` 依赖哪些形参下标 ＋ `own` 自带污点，**按规则隔离**、不动点迭代）；外部函数保持原语义。**A/B 逐条零差异**（DVWA 69/68、flask 13/1、requests 4/0、自扫 8/0/8、语料 24/24 & 0/18 全不变）。**中途两次自伤都是靶场逮住的**（成员方法被误认成仓库内同名函数 ⇒ 靶场掉到 90.9%；摘要分支丢了 `__inline__` 记账）⇒ 修好回到 100%。判据 8 条、变异校准 **19/19 全红**；**删掉一条恒绿判据**并把测试盲区如实登记；顺带**改判** E10 的缺口 2（净化在非赋值行**是**生效的） |
| **E12** ✅ | v0.46.0 | **注释里的代码不是代码——图层与规则层"层间不一致"**。`auditlib.iter_code_lines`（跳注释行与 docstring 块）本来就存在，规则层（粗筛与判定）**一直在用**，但 `audit_graph.build_graph` 主路径用的是 `iter_lines`（**全部行**）⇒ 注释里的 source/sink 进了数据流。实测 DVWA **3 条** ＋ 自扫 **2 条**假流从**源头**消失，而**结论数一字未变**（DVWA 69/68、flask 13/1、requests 4/0、自扫 8/0/8、语料 24/24 & 0/18、覆盖 14/19），变的只有"独立验证拦下"的条数（16→13、2→0）；顺带修掉"注释里的 `{}` 截断函数体（⇒ 漏报）"与"注释里的函数定义被认成函数"。性能 **BENCH-OK 4.286 ms/文件**（预算 ≤20）。判据 5 条、变异校准 **20/20 全红**。**判据设计的两条教训**（校准当场逮到，比代码更值钱）：① 只看 `findings` 的判据**恒绿**——假流停在 `dropped` 层；② 夹具里必须有另一处真 sink，否则种子阶段就把文件挡在图层外 |
| **E13** ✅ | v0.47.0 | **行尾注释里的代码也不是代码**（E12 补的是**整行**注释，这是另一半）。`code_lines` 只按**行首**判注释前缀 ⇒ `echo $x; // os.system("ls " . $x)` 里的 sink 形状仍在行内 ⇒ 误报**直接进结论区**。修法：`auditlib.strip_line_comments(text, lang)`（**注释符按语言分**：⚠️ **Python 的 `//` 是整除不是注释**；**必须先跳过字符串**：`"http://x"` 的 `//`、`"#!/usr/bin/env python"` 的 `#` 都不是注释）＋ `iter_code_lines` 加 `lang`、7 个调用点全链一致；`check_fixes` **故意不剥**（它拿基线 sink 文本比对，剥了会把"文件没改"误判成"已修复"）。**A/B 零回退**（DVWA 69/68、flask 13/1、requests 4/0、自扫 8/0/8、语料 24/24 & 0/18、覆盖 14/19 全不变）；⚠️ **诚实地说**：三仓里没有这种写法 ⇒ 本轮**没消掉真实误报**，价值在补齐机制＋夹具钉住。判据 5 条、变异校准 **22/22 全红**。**顺带修掉校准器的一个真陷阱**：它**静默跳过**锚点未命中的用例（`auditlib.py` 是 **CRLF**、`audit_graph.py` 是 **LF** ⇒ 多行锚点在 CRLF 文件上永远匹配不上 ⇒ 看着像跑过、其实没跑）⇒ 现在按实际换行符归一，且**有 SKIP 就显式报告并退出非零** |
| **E14** ✅ | v0.48.0 | **块注释 `/* … */`（可跨行）里的代码也不是代码** —— 注释形态的第三块（E12 整行 / E13 行尾 / E14 块）。修法：`auditlib.strip_comments(text, lang, in_block)` **单遍**同时处理行注释与块注释（⚠️ `/* // */` 与 `// /* */` 互相截断 ⇒ 必须单遍），块注释状态**跨行延续**；`code_lines` 的 `cmt_block` 与 docstring 的 `block` **分开**（两者会打架）。⚠️ **Python/Ruby/Shell 没有块注释** ⇒ 不给它们配 `/* */`。⚠️ **JS 正则里的 `//` 明确不做**（除法与正则靠上下文区分，静态判错会把真代码当注释 ⇒ 漏报，风险高于收益）。**A/B 零回退**（DVWA 69/68、flask 13/1、requests 4/0、自扫 8/0/8、语料 24/24 & 0/18、覆盖 14/19 全不变）；性能 5.132 ms/文件（E13 是 4.802，+6.9%；E12 以来三轮累计 +19.7%，预算 ≤20）。判据 6 条、变异校准 **24/24 全红**。**顺带修掉校准器的第二个缺陷**：校准跑出 **GREEN**（锁无效）原来不算失败 ⇒ 现在 GREEN 与 SKIP 都计入失败并退出非零（E14 当场逮到一条 GREEN：锚点在实现演进后**指到了不影响该判据的地方** ⇒ **校准锚点会过期**，每次改实现都要重看校准结果） |
| **E15** ✅ | v0.49.0 | **U+FFFD 替换字符（= 被损坏的字符）也要有判据**（§11 第 14 项收口）。起因：**E10 那轮自己写下的乱码**（一个「同」字变成 U+FFFD）**溜过了所有判据**——文件照样能跑、结构照样合法、数字照样对得上，**只有那个字符坏了**；`validate_skill.py` 查结构、查表格、查期望值，唯独不查"字符有没有坏"。修法：新增第 18 项 `check_no_replacement_chars()`（扫全部入库文本文件里的 U+FFFD，有就 `err` 并**点名文件与行号**）。⚠️ **判据第一次运行就抓到东西**：写判据时我在源码里用了 `u"\ufffd"` ⇒ **JSON 参数层把它解码成了真的 U+FFFD 字符** ⇒ 源码里真的混进了坏字符 ⇒ **新判据当场把它逮出来**（恰好证明判据有效）⇒ 改用 `chr(0xFFFD)` 避开转义层。另踩"编辑吃掉缩进"老坑：新检查项的调用写成 8 空格 ⇒ 落到 `if args.stats:` 分支里 ⇒ **正常运行时压根不跑** ⇒ 靠"信息数没变"暴露。判据 3 条、变异校准 **25/25 全红**；**A/B 零回退**（DVWA 69/68、flask 13/1、requests 4/0、自扫 8/0/8、语料 24/24 & 0/18、覆盖 14/19 全不变）；性能 5.357 ms/文件；validate 信息数 **17 → 18**（本仓现在 0 处 U+FFFD） |
| **E16** ✅ | v0.50.0 | **`JZ-XSS-002` 接上 `php://input`**（PHP 读原始请求体也是"外部可控输入"）——E9 留下的最后一个 XSS 缺口。E9 之所以没接：当时的引擎把"实参"当成了"返回值" ⇒ DVWA `check_token` 形态会误报。修法：sources 加 `file_get_contents\s*\(\s*['"]php://input['"]`（与其余 6 条 PHP 请求体规则**同一个** pattern）＋ 语料加 **1 正 1 负**。**严格 A/B（重建 E15 基线后逐条对比）**：DVWA **零变化**（69/68、dropped 13、flows 45、明细零差异）⇒ 无回退；flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19 全不变；真实的新能力在语料（**44 文件 25/25 检出、0/19 安全样本被误报**）。⚠️ **纠正上一轮的说法**：E9 说的"那 2 条 `check_token` 误报"是 **E11 修返回摘要时就没有的**，**不是 E16 的功劳**。判据 3 条、变异校准 **26/26 全红**。**三个工具坑**：① 校准器**不支持"删除型"变异**（new 文本在原文件里已存在 ⇒ 还原会连带改坏）⇒ 改用"变异该规则自己的 sink"；② **语料目录与 expected 必须同源**（`gen_corpus --out X` 与 `score --corpus Y` 指向不同份时**分母会错** ⇒ 我因此把一次口径错乱误读成"回退到 90.9%"）；③ **性能读数会偶发抖动**（曾测到 10.129，复测 5.265）⇒ CI 的性能护栏用 `--repeat 1`（**单次测量**）⇒ 偶发抖动可能让 CI 误红 |
| **E17** ✅ | v0.51.0 | **PHP 的 `exec()` 是命令执行，不是"动态代码执行"**。复核（实测）：DVWA `api/src/HealthController.php:88` 的 `exec("ping -c 4 " . $target)` 被归到 **JZ-CODE-001** ⇒ 归错类。根因：① CODE-001 的 sink 含 `\bexec\s*\(`（无条件命中）；② CMDI-001 的 PHP exec sink 要求 `+`/`${`，而 **PHP 用 `.` 拼接** ⇒ 压根不匹配 ⇒ 这条只被 CODE-001 认领。修法：CODE-001 只留 `eval`，CMDI-001 的 exec sink 补 `.` 拼接形态。**逐条 A/B（重建 E16 基线后对比）**：唯一变化是那条从 CODE-001 变成 **CMDI-001**（归类修正），**其余 68 条逐条零差异**、条数不变。判据 2 条、变异校准 **27/27 全红**。⚠️ 同时**把 E17 原定主题（`real_escape_string` 按上下文分）改判**：复核 DVWA 当前 master 发现 `real_escape_string` 命中 **31 行**（登录/改密代码），而 `sqli/source/low.php` 的 `$id = $_REQUEST['id']` **没转义** ⇒ 那里是真阳性；转义过的 `csrf/test_credentials.php` 是**误报**（转义在**引号内**才有效），但 `sqli_blind/source/medium.php` 是**转义了却在引号外**（数值上下文 ⇒ 转义救不了）⇒ **一刀切加净化点会压掉真阳性**，按插入上下文生效需要"**净化点分 sink**"这种**架构级能力** ⇒ 并入能力边界那一轮 |
| **E18** ✅ | v0.52.0 | **赋值覆盖了目标时，摘要为空就清掉目标原有的污点**（E11 留下的残留）。`$x = $_GET['a']; $x = check_token($x); echo $x;` 仍报 XSS —— 第二次赋值把 `$x` **覆盖成常量**了，但旧污点还留着。修法：摘要为空 ⇒ `tainted.pop(rtarget, None)`（只清该变量自己的）。⚠️ **防误伤**：配对判据锁住 `passthrough`（返回值确实依赖形参）⇒ **必须仍然报**。**A/B 逐条零差异**（重建 E17 基线后对比）：DVWA 69/68/dropped 13/flows 45、自扫 8/0/8 逐条零差异，flask 13/1、requests 4/0、覆盖 14/19、语料 25/25 & 0/19 全不变 ⇒ DVWA 里没有这种形态 ⇒ **对真实仓库零影响**（真实价值在夹具证明的假阳性消除）。判据 2 条、变异校准 **28/28 全红** |
| **E19** ✅ | v0.53.0 | **PHP 的成员方法 `->method(` 不该借用同名仓库函数的摘要**。探针实测：`_iter_calls(..., skip_members=True)` 对 `$o->get($x)` **仍返回** `('get', ['$x'])` ⇒ E13 的排除只认 `.`（Python/JS 风格），**不认 PHP 的 `->`** ⇒ 成员方法被当成"调用仓库内同名函数" ⇒ 仓库里恰好有 `function get($k){...}` 时**两个摘要被合并** ⇒ 用全局函数的语义代表方法的语义 ⇒ 可能**漏报真阳性**。修法：成员方法一律排除 ⇒ 退化成"参数直传"的**保守假设**（宁可多报也不漏报）；⚠️ 普通函数调用**仍走摘要**（配对判据锁住）。**A/B 逐条零差异**（重建 E18 基线后对比）：DVWA 69/68/dropped 13/flows 45、自扫 8/0/8 逐条零差异，flask 13/1、requests 4/0、覆盖 14/19、语料 25/25 & 0/19 全不变。判据 3 条（**第 1 条是修复前红**）、变异校准 **29/29 全红** |
| **E20** ✅ | v0.54.0 | **误报率口径收口**（§11 第 13 项）。那句"硬误报 1/60 ≈ 1.7%"是 **v0.30 那一节**的判定：分母 60 = DVWA 59 + flask 1，而 **DVWA 那部分从来没逐条判过** ⇒ 这个比率一直拿"只判过的部分"冒充"全量结论区"。本轮把 DVWA 结论区 **68 条**（69 findings − 1 另计）**按规则**逐条过一遍（14 条规则），flask 1 条、requests 0 条 ⇒ 合成**现行结论区 69 条**。⚠️ 判定依据是 **sink 行**（未逐条读完整证据链）—— 这一点写进台账，不冒充人工审阅。**判定结果**：真阳性 59、硬误报 7、需人工细判 3（未判定**不混进分子**）⇒ 现行口径 **硬误报 8 / 69 ≈ 11.6%**（含 flask 那 1 条），与旧的 1/60 **不可比**。**这一轮的产出不是"修好"，是"把没判的变成判过的"** —— 口径立住了，下一轮才知道该修什么：7 条里 **4 条是"规则过宽"**（`preg_replace` 当动态代码执行 2、`error_reporting(E_ALL)` 当调试泄露 1、`$_SERVER['CONTENT_TYPE']` 当文件上传 2）⇒ 已排进后续 ｜ **误报率口径收口**：逐条判定 DVWA 结论区，按**现行分母**重述"硬误报 1/60" ｜ 验收记录里"硬误报"的分子分母与当前实物一致；未逐条判定的部分**明确标为未判定**，不许混进分子 |
| **E21** ✅ | v0.55.0 | **SARIF 过官方 SARIF 2.1.0 schema** —— 仓库里那条「官方 validator 没有可执行命令行」的口径**是错的**：`@microsoft/sarif-multitool` 5.8.0 的 `sarif-multitool validate` 装上就跑，**我们的 SARIF 报 8 条 error**（`physicalLocation` 里放了 schema 不允许的 `conceptualName`，官方 schema 对它是 `additionalProperties=false` ⇒ JSON1005）。修法：删掉它，信息挪进 `location.message.text` 前缀（不丢信息）；⚠️ `message` 属于 **`location`** 层、不是 `physicalLocation` 层（我第一版就改错在这里，是**变异校准**当场逮住的）。再把官方 schema 的「允许属性」白名单**硬编码**进零依赖自检（`scripts/sarif_schema_extract.py` 联网时可当场核对，`--check` 不一致退出码 1）⇒ **补上旧盲区**：旧自检只看 `results[].locations`，**压根没看 `codeFlows` 里的 location**，而这 8 条错误全长在 `codeFlows` 里。官方 validator 复跑 **0 error**（⚠️ **它的退出码不可信**：报着 error 仍返回 0 ⇒ 只能解析 error 行）。**零回退**（只动 SARIF 输出层，不动引擎）：DVWA 69/68、flask 13/1、requests 4/0、自扫 8/结论0/另计8、覆盖 14/19、语料 25/25 & 0/19 全不变；bench 5.172 ms/文件。判据 4 条、变异校准 **31/31 全红**（新增 2 条） ｜ **官方 SARIF validator 跑一次**（已完成） ｜ ✅ 工具**可得**（`@microsoft/sarif-multitool` 5.8.0）：修前 **8 条 error** → 修后 **0 error**；替代验证也做了——schema「允许属性」白名单硬编码进零依赖自检（CI 装不了官方工具） |
| **E22** ✅ | v0.56.0 | **能力边界文档化** —— 分册里**从来没有任何一处**说清审计链做不到什么 ⇒ 使用者会把"没报"读成"安全"。先**复核**（不凭印象写）：每条边界都用**最小夹具**或 **DVWA 实扫**取证，写进 `references/audit-rule-authoring.md` 新增的「能力边界表」（**5 条**，每条带**为什么做不到 + 代价 + 实测证据**）。⚠️ **复核过程挖出两条实测事实**：① `JZ-SQLI-003` 的净化点 pattern `\breal_escape_string\b` **匹配不到** PHP 标准写法 `mysqli_real_escape_string(...)`（`_` 是单词字符 ⇒ 无词边界）⇒ **这个净化点从来没生效过**；DVWA 三处形态一样但判定必须不同（`csrf/source/high.php:38→44` 与 `csrf/test_credentials.php:14→22` 引号内 ⇒ 2 条硬误报，`sqli_blind/source/medium.php:10→15` 引号外 ⇒ 真阳性）⇒ **一刀切修好就是拿真阳性换误报** ⇒ 维持现状并写进边界表；② **JS 正则字面量里的 `//` 被当注释** ⇒ 同行后续代码**整段被漏掉**（实测 0 条 vs 对照 1 条）—— 这是 E14 决定"不做"时的代价，本轮第一次量化。判据 `TestAuditCapabilityBoundaries` **4 条**；变异校准 **33/33 全红**；**零回退** ｜ **能力边界文档化**（已完成） ｜ 分册里有一张**能力边界表**：缺失型判据（brute/captcha）、"净化点按插入上下文生效"（需 sink 级能力）、JS 正则字面量、C 系块注释的跨行边界……每条都带**为什么做不到 + 代价** |
| **E23** ✅ | v0.57.0 | **性能护栏不许退回单次测量** —— CI 的 bench 从 `--repeat 1` 改成 `--repeat 3` 且**取最快一次**。⚠️ **实测推翻了原规划的前提**（规划写"repeat≥2 取均值"）：400 文件各 3 轮，单次读数极差 **20.6%**，两轮**均值**极差 **11.6%** ⇒ **均值反而更抖**（对离群值不稳健）⇒ 改判为取**最快一次**（min）：**性能噪声只会让读数变大** ⇒ min 抗噪、不会误红；真回退会让每次都慢 ⇒ min 照样超预算 ⇒ 回退仍拦得住。实测极差 **20.6% → 10.3%**。另把 bench 的聚合抽成纯函数 `aggregate_rows`（顺手修掉 `--repeat 0` 的 `ZeroDivisionError`）。判据 `TestBenchAggregation` **3 条**；变异校准 **35/35 全红**；测试 194→197 ｜ **性能护栏改进**（已完成；⚠️ 规划写"取均值"被实测推翻 ⇒ 改判为 **repeat 3 取最快一次**） ｜ 连续多轮 bench 读数不再出现 4.4 ↔ 10.1 ms/文件那种跳变；护栏仍能拦数量级回退 |
| **E24** ✅ | v0.58.0 | **变异校准器随技能一起分发** —— 校准器一直只躺在仓库外的 `eval-runs/` ⇒ **技能被分发出去时它不在其中**，接手者没有它 ⇒ "判据能红"的承诺无法复核。现在 `scripts/mut_calibrate.py`（零依赖、只改本仓库文件、不联网）+ `--check-only`（只核对锚点，秒级）⇒ CI 加一步跑它 ⇒ 锚点过期当场红（过期锚点会让校准**静默失效**）。⚠️ **CI 不跑完整校准**：个别判据**随平台换颜色**（Windows 反斜杠 / Linux 正斜杠）⇒ CI 上跑会误红 ⇒ 完整校准留给本地。`validate_skill.py` 新增**第 19 项**：校准器必须在库里 + 零依赖 + **CASES 条数从实物数出**并与 CHANGELOG 最新条目对账。⚠️ **本轮真正的收获**：复核时发现**从 E19 起，CHANGELOG 里写的校准例数每轮都比实物多 1**（30→32→34→36，因为是在上一轮那个错值上 +2）⇒ 真实链 E18=28→E19=29(+1)→E20=29→E21=31(+2)→E22=33(+2)→E23=35(+2)→E24=36(+1) ⇒ **手数的偏差会自我延续**，只有机器判据能断掉它 ⇒ 本轮把 v0.53.0–v0.56.0 四处旧数字一并订正。判据 `TestMutCalibratorShipped` **3 条**；变异校准 **36/36 全红**；测试 197→200 ｜ **把变异校准器收进仓库**（已完成：`scripts/mut_calibrate.py` + `--check-only` + validate 第 19 项） ｜ 校准器随技能一起分发（现在只在仓库外的 `eval-runs/`，接手者没有它）；判据与文档同步 |
| **E25** ✅ | v0.59.0 | **修 E20 判定出的"规则过宽"硬误报**（**实为 5 条，E20 自己写成 4 条 ⇒ 算术错，一并订正**）。① `JZ-CODE-001` 去掉 `preg_replace`（PHP 5.5+ 无 `/e` ⇒ 不是动态代码执行）；② `JZ-DEBUG-001` 去掉 `error_reporting(E_ALL)`（只设错误级别、不泄露，泄露的是 `display_errors=On`）；③ `JZ-UPLOAD-001` 去掉 content-type sink（`$_SERVER['CONTENT_TYPE']` 是请求头，不是上传限制）——⚠️ 我第一版把它改成"出现 `$_FILES[…]['type']` 检查"，**语义反了**（规则要报的是"**缺**限制"，而那是**有**类型检查＝合规写法）⇒ **逐条 A/B 当场逮到**（在 DVWA 修复档 `upload/source/impossible.php` 报出 1 条新误报、自扫多 2 条）⇒ 改为整条去掉并登记为能力边界。**口径重述（分子分母同时变）**：硬误报 **3 / 64 ≈ 4.7%**（E20 是 8/69 ≈ 11.6% ⇒ **不可比**）；DVWA 结论区 68 → 64 发现/结论 63，覆盖 14/19 不变，语料 25/25 & 0/19 不变，flask/requests/自扫一字未变。判据 `TestAuditOverbroadRuleNarrowing` **4 条**（3 条反面 + 1 条"`eval` 仍报"防误伤）；变异校准 **39/39 全红**（新增 3 条）。⚠️ **一条机制事实**：`JZ-CODE-001` 是 `ignore_strings: true` ⇒ 在**掩码桶**上匹配 ⇒ **看不见字符串里的 `/e`** ⇒ PHP < 5.5 的 `/e` 动态执行**当前检不出**（登记为边界） ｜ **修 E20 判定出的"规则过宽"硬误报**（`preg_replace` / `error_reporting(E_ALL)` / `$_SERVER['CONTENT_TYPE']`） ｜ DVWA 逐条 A/B **消失 5 条、新增 0 条**；硬误报口径重述为 3/64 |
| **E26** ✅ | v0.60.0 | **把 E20 留下的"需人工细判"清零**（DVWA 结论区**硬误报归零**）。那 2 条是 DVWA `api/source/{low,medium}.php` 的 `user_info.innerHTML = 'User details: ';` —— 读完整源码确认是**赋纯字符串常量** ⇒ 不该报；而 `JZ-XSS-001` 是 `ignore_strings: true` 的 **pattern 规则**（只看写法不看污点）⇒ 只要出现 `.innerHTML =` 就报 ⇒ 属规则过宽。修法：sink 加**负向先行**排除"赋纯字符串常量"（⚠️ 能在掩码桶里判，是因为字符串被剥成 `''` ⇒ 「纯常量」= `innerHTML = '';`、「常量+变量」= `innerHTML = '' + name;` ⇒ 可分；⚠️ **必须把空格算进负向先行**，否则会被 `\s*` 的**回溯**绕过去 ⇒ 第一版就踩了）。**口径重述**：硬误报 **1 / 62 ≈ 1.6%**（E25 是 3/64 ⇒ **不可比**）⇒ **DVWA 结论区硬误报 7→0**，剩 1 条在 flask。逐条 A/B：DVWA **消失 2 条、新增 0 条**，其余数字**一字未变**。判据 `TestAuditXssConstantAssignment` **3 条**；变异校准 **40/40 全红**（新增 1 条：⚠️ 变异**不能**把整条 sink 换回老形态——老形态是新形态的**前缀** ⇒ 校准器会按"突变文本已存在"直接 SKIP）。顺带：能力边界表补两条；**两个停牌项定案**（触发率 A 路线 ⇒ **不做**；发行渠道 ⇒ **做**，发行说明已入库） ｜ **把 E20 留下的"需人工细判"清零**（`innerHTML` 赋纯常量） ｜ DVWA 消失 2 条、新增 0 条；**DVWA 结论区硬误报归零**；硬误报 1/62；**第一份发行说明入库** |
| **E27** ✅ | v0.61.0 | **把交接文档收进仓库**（`docs/jiangzuo/handover.md`）+ `validate_skill` **第 20 项**（在仓库内 + 7 个关键章节齐全 + **被 git 跟踪**）； E26 那轮一个脚本 bug（块替换的结束条件写成 `not startswith("3. ")` 而实际标题是 `## 3.` ⇒ 匹配不中 ⇒ 一路吃到下一个 `## 4.`）把交接文档的 **§1/§2/§3 与「远端一致性」栏整块覆盖**；而它当时在**仓库之外、不在 git 里** ⇒ **无版本历史可回滚**，只能从会话记录按结构重建（整整一轮）。⇒ 根因不是"不够小心"，是**那份文档没有版本控制** ； ① 移入仓库 + 放开 `.gitignore`（`docs/jiangzuo/*` 挡住 ⇒ **第三次**重演 `reports/`/`releases/` 那个坑）；② validate 第 20 项；③ 判据 `TestHandoverInRepo` **4 条**；④ 变异校准 **42/42 全红**。⚠️ **第 20 项第一次跑就立功**：抓到"文件存在但没被 git 跟踪"。顺带修掉它此前**不在任何判据范围内**攒下的过期数字与 2 处 U+FFFD，并把 §8 坑位**按编号排序**（交叉引用仍有效）。**零回退**（只动文档与判据） ｜ **把交接文档收进仓库** + validate 第 20 项 ｜ 交接文档在 `docs/jiangzuo/handover.md`、被 git 跟踪、7 个关键章节齐全；`validate_skill` **20 信息 / 0 警 / 0 错** |
| **E28** ✅ | v0.62.0 | **把结论区 62 条逐条判完**（`evals/finding-verdicts.md`），**未判定 = 0**，误报拆成三类（静态可修 1 / 待能力升级 2 / 静态消不掉 4）（`flask/json/tag.py:188` 的 `return Markup(value)`） ｜ 逐条读证据链 ⇒ 判成"真阳性"或"硬误报"，并据此改判/收窄；硬误报口径再次重述（分子分母同范围） |
| **E29** ✅ | v0.63.0 | **硬误报清零**：修掉最后一条「静态可修」的误报（纯常量 `document.write`），并把**守这件事的两把锁**修好（校准器的**假红灯** + `validate` 第 21 项的**潜伏 bug**） ｜ DVWA 只少 `xss_d/index.php:54` 一条、新增 0 条；结论区 62 → **61**；误报 7 → **6**、静态可修 1 → **0** ⇒ **"静态可修的硬误报" = 0 / 61 = 0%**；判据 `TestVerdictTable` 5 条 + `TestMutCalibratorShipped` 2 条 + `TestAuditXssConstantAssignment` 2 条；变异校准 **47/47 全红** |
| **E30** ✅ | v0.64.0 | **「净化点按 sink 上下文生效」**（架构级能力，E17/E22 两次登记的缺口） —— 转义类净化点现在**按引号内 / 引号外两档**生效 ｜ 引擎加 `sql_quote_context()`（按"输出串"重建引号状态）⇒ DVWA `csrf/source/high.php:44`（引号内 ⇒ 转义有效）**不再报**，而 `sqli_blind/source/medium.php:15`（引号外 ⇒ 转义无效）**仍报**；**A/B 逐条：DVWA 只少这 1 条、新增 0 条**（13 条 SQLi 真阳性全保住）⇒ 结论区 61 → **60**、误报 6 → **5**、待能力升级 2 → **1**；判据 `TestAuditSqlQuoteContext` **5 条**；变异校准 **50/50 全红** |
| **E31** ✅ | v0.65.0 | **「净化点跨文件作用域」**（判定表 §二 #1 登记的待能力升级项）—— 顺带修掉一类**既有的漏报** ｜ ① **跨行字符串字面量折叠到首行**（⇒ 多行 SQL 串里的**列别名不是变量读取**、**插值是读取**）② **include-scope 认被 include 文件里的无条件净化点**；**A/B 逐条：DVWA 只少 `bac/index.php:58` 一条、新增 0 条** ⇒ 结论区 60 → **59**、误报 5 → **4**、**「待能力升级」1 → 0** ⇒ 剩下的 4 条**全是能力边界型**；判据 `TestAuditMultilineString` **4 条**（含 2 条防误伤）；变异校准 **53/53 全红** |
| **E32** ✅ | v0.66.0 | **把「全部产出」口径的误报率说死**（判定表新增 §四） ｜ 「同目录路过」实测 **16 条**逐条判定 ⇒ **真阳性 15 + 误报 1**（那 1 条与 §二 #3 同一处）；另计语境 **16 条** ⇒ **全部产出 75 = 真阳性 55 + 误报 4 + 另计 16** ⇒ **误报率 4/75 ≈ 5.3%**；三份文档里互相矛盾的旧数字（20 / 12 / "59 条里有 20 条"）全部订正；**顺手补上 §8 坑位编号的缺号**（E22 插入时跳过了 36/37 ⇒ 编号 1..57 只有 55 条 ⇒ 别人引用「§8 第 N 条」会指错 ⇒ 已重排为 **1..55 连续**）并给 `validate` 第 20 项加了「§8 编号必须连续」守卫；清单可复算（`dvwa_coverage.py --same-dir`）；`validate` 新增**第 22 项**（口径拆解自洽）；判据 `TestLedgerTotals` **2 条**；变异校准 **55/55 全红** |
| **E33** ✅ | v0.67.0 | **关掉能力边界表最后一行**（值直接内插在 sink 调用里 ⇒ 上下文判定接到 **sink 行**上）＋ **发行形态闭环**（**65 个 GitHub Release 全部发布**：补发 64 + 本发 1） ｜ E30/E31 只做掉了**赋值行**上的形态；`mysql_query("… '$x'")` 这种**没有独立赋值行**的形态仍判不到 ⇒ 转义被无视 ⇒ 照报。⇒ E33 把上下文判定也接到 sink 行 ⇒ 那一行不再是边界；**A/B 逐条：DVWA 零差异**（58 发现/58 结论/6 dropped/33 flows）⇒ 三仓数字与口径（结论区 59、误报 4/75）**一字未变**；发行侧：发行说明的**单一真源改成 `CHANGELOG.md`**（`scripts/release_notes.py` 生成并发布）⇒ **65 个 Release 与 65 个 tag 一一对应** ⇒ 「发行形态只到 tag」这条债结清 |
| **E34** ✅ | v0.68.0 | **把「当前状态」抽成机器可读真源**（散文里的数字从此有人守） ｜ E32 三个文档各写一个数（20 / 12 / "59 条里有 20 条"）、E33 把"补发 64 个"与"现在 65 个"写成同一个数 ⇒ 根因是**同一个数散落在多处散文里，而没有任何东西把它们对账**（`validate` 的期望值校验**只扫代码块**——那是对的，代码块是"复制即跑"的契约）⇒ 散文里的"当前状态"没人守。⇒ 真源 `evals/current-state.json` ＋ 文档里的 `current-state` 标记区 ＋ **第 23 项**逐指标对账；真源**能当场推出来**的部分每跑一次重推一遍 ⇒ **尺子自己不会坏**；历史文档对**历史快照**，不逼人篡改历史；**口径不动**（引擎一行没动 ⇒ 三仓数字一字未变） |
| **E35** ✅ | v0.69.0 | **纪律层的「行为收益」第一次有实测数据**（结论是"不许声称"） ｜ 交付报告 §4 第 4 项挂着"三条新纪律条款未跑行为微测"，而台账里那三行只有**文本锁 + 结构锁** ⇒ 行为收益**未测** ⇒ 本来就不得声称；E35 按 `evals/micro-tests.md` 的规程真跑了一轮：**A 臂（无规则）0/5 失败、B 臂（有铁律 + 门函数）0/5 失败**，差 **0 个百分点** ⇒ **基线未红** ⇒ 铁律与门函数**在本场景下无可测的行为增益** ⇒ 记作**回归哨兵**。⚠️ 但**形式差别是看得见的**：B 臂 5 次全部实跑并逐条列出「命令 → 输出 → 退出码 → 支撑哪一条」（B5 还加了控制组），A 臂多数只做静态推理 ⇒ 规则**可能**改变的是**过程的可审计性**而不是结论正确率 ⇒ **不是行为收益的证据**，只是下一轮换指标的假设 ｜ ① 夹具 `evals/micro-test-fixtures/`（读代码挑不出毛病、实际调用会炸 ＋ 一份与现状矛盾的 README）＋ 两臂提示词逐字写进 `evals/micro-tests.md` ⇒ **规程从"文档"变成"可复跑"**；② 顺手把纪律层的**声称**也变成机器判据（`validate` **第 24 项**：微测台账的状态格必须与实测失败率差对上 ⇒ **改结论不改数据当场红**——这正是 E32/E33 栽过两次的同一种病）；③ 四条 meta-test 事故全部如实登记（**污染真会发生**：第一批 4 次因夹具生成器在子代理可达范围内而作废；**夹具未逐次重置** ⇒ B3–B5 跑在脏目录里；**压力是我自己造假的**（缺陷静态可见）；**基线本来就很强**（通用 agent 契约自带证据纪律））；④ **口径一字未动**（引擎一行没改 ⇒ 三仓数字与误报率全部不变） |
| **E36** ✅ | v0.70.0 | **门面（中英两个 README）都有人守** ＋ 修掉一道**在逼人说假话的锁** ｜ 英文 README 停在 **2026-10-06**（v0.3x 遗物）：写着 4 个脚本 / 222 行 / 373 字符 / 12 个模板 / 16 本分册，**整条安全审计链主线一个字没提** ⇒ 而它恰是英文读者与 skills.sh 生态看到的那一面 ⇒ **门面的另一半没人守**；另查出一条**锁在逼人说假话**：入口行数的真源是**文件总行数**（212），而 **500 上限约束的是正文**（201 行）⇒ 文档只好写总行数，**说真话反而被判错** ｜ ① 英文 README 整体重写：对齐当前实现（20 分册 / 14 模板 / 18 脚本 / 34 规则 / 正文 201 行 / description 241 字符 / entry 290 字符）**并补上安全审计链这条主线**（十步扫描链 + 规则库 + 真实仓库实测数字）；② `validate` 第 7 项扩成**中英各查一遍**（分册/模板/脚本/规则/入口行数/description/entry 字符数），**入口行数的真源改成正文行数** ⇒ 说真话不再被判错；③ 判据 `TestReadmeCounts` **4 条**（含一条专门锁「别逼人说假话」：写正文行数过、写总行数红）；④ **口径一字未动**（引擎一行没改 ⇒ 三仓数字与误报率全部不变） |
| **E37** ✅ | v0.71.0 | **发布产物的「身份」必须有人守**（远端 `v0.51.0` 指错了 commit） ｜ E36 那句「68 tag / 68 Release 一一对应、零缺口」当时**是真的**——它只数了**名字与数量**。E37 复核查出：远端 `refs/tags/v0.51.0` 是**轻量** tag，指向 `d5b88e1a`（**v0.66.0 的补记笔**，2026-10-22），而不是 v0.51.0 的代码（`d5da9f39`，E17 当轮打的 annotated tag，tagger 时间戳 `1792578222 +0800`）⇒ **谁 `git checkout v0.51.0` 拿到的都是别的版本**。根因**已证实**：`release_notes.py --publish` 调 `POST /releases` 时 ① **没带 `target_commitish`**（GitHub 默认用 main）② **不检查远端该 tag 是否已存在** ⇒ 补发一个「远端还没有 tag」的版本时，GitHub 会在 main 的 HEAD 上**自动造出**一个同名 tag（远端 `v0.51.0` 的 `created_at` 与它那个 Release 的 `created_at` **同秒** ⇒ 正是这条路径）。⚠️ 「E17 那轮为何远端缺这个 tag」**未验证**（当时的推送记录已不可查）⇒ **不猜** ｜ ① 新增 `scripts/release_identity.py`（零依赖：`--sync`/`--check`/`--remote`/`--print`）＋真源 `evals/release-identity.json`（**脚本生成**，不手抄 sha）；**owner 规则**＝「tag vX.Y.Z 指向的 commit，其 subject 中第一个版本号必须恰好是 X.Y.Z」（⚠️ **不用**「第一个含该版本号的 commit」：实测本地 68 个 tag 里有 3 个（v0.36.1/v0.40.0/v0.61.0）指向的不是第一笔 ⇒ 那条规则 **4.4% 不成立**，拿它当判据就是造一把会把正确历史判错的锁）；② **根因修复**：`--publish` 现在**先核远端 tag**，缺失或指向不对 ⇒ **拒绝发布**，发布时显式带 `target_commitish`，发完**回头自证**；③ `validate` **第 26 项** ＋ CI 的 `checkout` 改 `fetch-depth: 0`/`fetch-tags: true`（否则这一项在 CI 上只能发一句「这轮没跑」⇒ 一把**恒绿的空锁**）；④ 判据 **9 条**、变异校准 **70/70 全红**；⑤ **口径一字未动**（引擎一行没改 ⇒ 三仓数字与误报率全部不变）；🔴 当时**未收口**：修远端那个 tag ＝ **移动已发布 tag** ＝ 停牌项 ⇒ **已在同一轮内获授权并修复**（`forced update`）⇒ 远端 69 个 tag 现与本地**逐条同 commit**（详见 §2） |
| **E38** ✅ | v0.72.0 | **Markdown 表格的结构第一次有人守**（并让进化账本在 GitHub 上**真的渲染成表格**） ｜ E37 记下的候选（第 18 项）：`evolution.md` 的账本「最近 8 行列数与表头对不上」⇒ 而**没有任何判据**知道那意味着什么 ⇒ E38 扫全仓（58 个 .md / 150 个表格块（**合并前**的数；合并后 **147** —— `evolution.md` 的碎块合成了 1 张））⇒ **14 行**列数不符。⚠️ **更正 E37 的一处不准确说法**：E37 写的是「渲染错位」——**机制说错了**：GFM 要求「表头 + 分隔行」才构成表格，而那张表**用空行隔行**⇒ 空行后的每行**都不是表** ⇒ **整张台账在 GitHub 上根本没渲染成表格**（是一堆以 `\|` 开头的段落） ｜ ① 把那张表**合并成一张连续表**（删 18 个空行）⇒ 顺带让第 12 项的「上表 N 条」对账**自动生效**（它此前只在"恰好一张表"时判 ⇒ 碎块状态下形同虚设）；② 第 12 项新增第三条「**表内每行的列数必须与表头一致**」⇒ ⚠️ **按 GFM 规则**数列（`\|` 是转义、不算分隔符）⇒ 不把 `ls scripts/*.py \| wc -l` 这种**合法**写法误判成多一列；③ 修掉 14 处（11 行**插空格子**、3 行**并回多出的格子**）—— **不编值**（编值就是手数的偏差）⇒ ⚠️ 其中**一处是 E37 自己新加的那一行**⇒ **新判据上线第一件事就逮到我自己** |
| **E39** ✅ | v0.73.0 | **远端发布产物的自洽进 CI**（此前 CI 上**没有任何一项**在核"发出去的东西"） ｜ ① `validate` 第 26 项（E37）核的是**本地 git 对象** ⇒ **碰不到远端**；② `release_identity.py --remote` 准，但**要 token、要手动跑** ⇒ ⇒ 少发一个 Release、tag 与 Release 对不上，**没有任何东西会发现** ⇒ ① `scripts/release_consistency.py`（**零依赖**、**匿名 API**、**只花 2 次调用** ⇒ 限流友好）＋ CI 作业 `release-consistency.yml`（push / 每日 schedule / 手动）⇒ 核「远端 Release 集合 == 远端 tag 集合（零缺口）＋ 数量与本地一致」；② ⚠️ **三态退出码**（0 一致／1 不一致＝真问题必红／2 **没核成**＝限流或网络 ⇒ **绝不当成通过**）⇒ 作业把 2 单独分支（step summary ＋ `::notice::`）⇒ **不假绿**；③ `validate` **第 27 项**把"三态 + 作业处理了那一态"钉住；④ **改判一条候选**：E38 的「台账『行数收支』机器算」—— E39 实测**「从台账文本反推对应 commit」不可靠**（64 行里 58 行无法用版本号定位、且有错配）⇒ 改判为「提供工具、不做自动核验」 |
| **E40** ✅ | v0.74.0 | **台账自身不许被写坏**（进化账本的行序与重复行 ＋ 验收记录的小节升序 ＋ **每个 current-state 标记区都对账它自己那一版**） ｜ 台账的**行序回退 3 处**当场红（实测 E13→E11、E11→E9、E17→E11 ⇒ 已重排）；**两处 v0.72.0 区块被改写的数当场红**（E39 留下的假记录 ⇒ 已按 `git show v0.72.0` 的原文改回）；验收记录尾部**小节倒序当场红**（E39 插错 1 处 ＋ E40 自己第一版插错 1 处 ⇒ 已排回升序）；判据 `TestLedgerIntegrity` **6 条** ＋ `TestCarrierBlockIntegrity` **4 条**；变异校准 **79/79 全红** |
| **E41** ✅ | v0.75.0 | **门面的安装命令必须是真的**（生态那扇门此前是**死路**） ｜ 门面上 `npx skills add <you>/jiangzuo` 这个**占位符**当场红（照抄必然失败）⇒ 已改成真名；实测 `npx skills add Zhang-jx00/jiangzuo` 装出 **571 个文件**、装出来的副本**自检 30/0/0 全绿** ⇒ **装出来能用**；skills.sh 上已有本技能页 ⇒ **它根本没有提交流程**；判据 `TestInstallCommand` **5 条**；变异校准 **81/81 全红** |
| **E42** ✅ | v0.76.0 | **仓库身份只许有一处** —— 此前 owner/name 抄在四个脚本里，仓库改名就会悄悄漂。新增 `scripts/repo_identity.py` 作**唯一**真源，四个脚本改为从它导入；判据并进第 7 项（门面命令必须指向真实仓库 ＋ 身份只许出现在真源那一个文件 ＋ **真源缺失必须报错**，不许静默跳过）；判据 `TestInstallCommand` **8 条**；变异校准 **82/82 全红** |
| **E43** ✅ | v0.77.0 | **仓里的发行说明不许成为第二真源** —— 手写副本已漂，且从未发布过。那份 `docs/jiangzuo/releases/v0.60.0.md` 换成**生成版**（丢掉的是从未发布过的手写聚合稿 ⇒ 事实无损）；第 25 项加一条「每份必须与生成器产出的**逐字一致**」（判据**复用生成器本身**）；判据 `TestReleaseNotesSource` **3 条**；变异校准 **83/83 全红** |
| **E44** ✅ | v0.78.0 | **发行说明不许走兜底** —— v0.15.0–v0.19.0 那五版的发行说明取自 tag 的提交说明（**第二个来源**）。补录五条 CHANGELOG 条目（内容＝各 tag 的**提交说明原文**、日期＝作者日期、注明是补录）⇒ 兜底数归零；`known_gaps.tag_without_changelog` 清空，且第 26 项**这一类差集不再允许登记例外**；判据 `TestReleaseNotesFallback` **4 条**；变异校准 **84/84 全红** |
| **E45** ✅ | v0.79.0 | **轮次台账只许有一处** —— 交接文档里原先有**两份**手抄的轮次台账（§4 的「E 系列」表 ＋ §11 的三张规划表）⇒ 同一轮写两遍 ⇒ **必然漂**：① 同一轮的主题两处矛盾（「十轮规划」自 E17 起错位一格）② 「完成标记 ✅」E1–E20 那 20 轮一个都没打 ③ E30–E41 那段**没有表头 ⇒ GFM 里根本不是表**（那 4 行本来就是 5 格）④ E42–E44 没有行 ⑤ **4 处校准例数已被 CHANGELOG 订正过、台账没跟着改**（E19 30→29 / E21 32→31 / E32 54→55 / E41 80→81） ｜ 两份合并成**一张**「轮次台账（E1–E44）」放在第 4 节（行身份＝版本号，真源可查）＋ 补 E42–E44 ＋ 订正那 4 处 ＋ 每行带 ✅ ＋ 行序升序；§11 只留还没做的轮次；第 25 项加**六条**对账（轮号全局唯一／轮号↔版本／不许漏轮次／行序不得回退／每行必带 ✅／校准例数与 CHANGELOG 对账）；判据 `TestRoundLedger` **10 条**（红 8 / 绿 2）；变异校准 **87/87 全红** |
| **E46** ✅ | v0.80.0 | **「规模」这行字由实物生成、逐字对账** —— 交接文档 §0 的「4. 规模」行**手抄了 8 个数、没有一个人守** ⇒ 实测已过期 **5 个**（脚本 18→21 / 用例 255→314 / 入库文件 91→96 / 提交 110→131 / tag 68→77）；而那 8 个里只有**四个**是结构规模（分册 / 脚本 / 模板 / 规则 JSON），其余是**别处已有的副本**或**每笔都变、守不住**的数 ｜ ① `_expected_truth()` **复用 `_readme_truth()`**（不写第二份计数）⇒ 真源 `static` 新增 4 项；② `current_state.py` 新增 `scale_line()`（生成）＋ `check_scale_line()`（**同一个函数**逐字比对）⇒ 并进第 23 项 ⇒ **写错 / 多写一个数 / 删掉 / 写两处当场红**；③ 副本清零：§0 规模行换生成版 ＋ §0 第 7 条 / §2 目录树 ×3 / §2 文件表 / §13 ×5 去副本 ⇒ **数字只在一处**；判据 `TestScaleLine` **6 条**（红 4 / 绿 2）；变异校准 **89/89 全红**（新增 2 条）；⚠️ bench 读到 5.945 ms/文件 ⇒ **同口径重建基线**对比（上一版同刻 5.469–7.074）⇒ **不是回归** |
| **E47** ✅ | v0.81.0 | **「当前状态」不许冒充当前** —— §2「远端一致性」栏里那行**写死了远端 main 的 sha**（`8e22edf`，v0.70.0 那一版）⇒ 它**每笔都变** ⇒ 实测已过期 **8 个版本**，却顶着一句「**当前状态**」⇒ **冒充当前**；同栏另有「本轮 Release」（v0.70.0 那一轮的措辞）与「65 个 GitHub Release」（现在 78）⇒ 另有**每版 ✅ 交付行在 §0 与 §2 各写一遍** ｜ ① **不守它、别写它**（sha 每笔都变 ⇒ 任何判据都守不住 ⇒ E46 的教训）⇒ 那一行改成**只说「怎么核」**；② `current_state.py` 新增 `remote_state_line()` / `check_remote_state_line()`⇒ 并进第 23 项 ⇒ **塞一个 sha 就当场红**；并把 E46 的那套**抽成通用件** `_check_generated_line()`（不写第二份解析）；③ 措辞与归属收口：CI/Release 证据**指向第 0 节**、「65 个 Release」改成不写死、逐版行归入「**历史记录**」⇒ **历史一个字没删**；判据 `TestRemoteStateLine` **6 条**（红 4 / 绿 2）；变异校准 **90/90 全红**（新增 1 条，**第一次以「文档被改坏」为突变源**）；⚠️ bench 7.336 ms/文件 ⇒ 重建基线同刻对比 ⇒ **不是回归** |
| **E48** ✅ | v0.82.0 | **`main` 分支保护配上了** —— 从 E41 记下停牌项到今天落地：此前 `main` **没有分支保护** ⇒ 而 E37 为修远端指错的 tag 做过一次 `forced update` ⇒ **强推能改写 main 的历史**；E41 实测现有令牌调 `PUT /branches/main/protection` 得 **403**（无仓库管理权限）⇒ 属「凭据相关」、需所有者点头 ⇒ 中间**七轮**都没动它 ｜ ① **先诊断**：`permissions.admin` = **true**、而 `GET …/protection` = **404**（此前确实没有）② 按**交接文档里写好的形状** PUT（**刻意不照抄 GitHub 默认** ⇒ 默认会带上 `required_status_checks` ⇒ **直接挡住本项目自己的推送流程**）：不要求 PR / 不要求 CI / 不限制推送人 ＋ `allow_force_pushes: false` ＋ `allow_deletions: false` ＋ `enforce_admins: true` ③ **回读核对**（PUT 200 之后又 GET 一次，逐项一致）④ §0 与 §11 的停牌项状态**如实改成已做**；⚠️ 本轮是**第一次做「改仓库设置」这类外向变更** ⇒ **没有仓内判据能守** ⇒ 唯一保证是**回读核对**（第 10 条铁律在仓库设置这一侧的应用）；⚠️ 之后**授权过的**强推/删分支仍要所有者点头 ⇒ 保护挡的是「手滑」，不是「授权过的修复」 |
| **E49** ✅ | v0.83.0 | **同一件事故只许写一遍** —— 交接文档 §0（速览）与 §2（历史记录）把**同一件事故改写后各写一遍**（v0.72.0 的 API 通道 / v0.73.0 走 git / v0.74.0 的传输通道 / v0.51.0 的 forced update / v0.71.0 的撤回 / v0.75.0 的 CI 假红与推送脚本）⇒ 同一事实两处手抄 ⇒ 必然漂 ｜ ⚠️ **动手前先量**：实测**逐字**重复的 ≥80 字符长行只有 1 组且合法 ⇒ ⇒ **「整行查重」抓不到改写过的重复** ⇒ ⇒ 那条判据会变成装饰 ⇒ ⇒ 抓手只能是**结构**：① **§0 速览**那两处压成**一行指针**（细节见第 2 节 / 现行规则见第 5.4 节）② **§2 详情全部保留**（唯一一处），只把「网络一断就停推」改成**指向 §5.4**（规则不该躺在历史段落里）③ **§5.4** 收进两条**现行规则**（网络一断就停推，唯一允许的绕法是换前端 IP／推完必须回读远端核对）④ 第 25 项加一条**结构性**判据：§0 速览段里提到事故关键词的行**必须带指针**（关键词清单短而准，长了会误伤）；判据 `TestIncidentPointerOnly` **4 条**（红 2 / 绿 2）；变异校准 **91/91 全红**（新增 1 条）；⚠️ 本轮我自己把一个「：」打成了 **U+FFFD** ⇒ **第 18 项当场逮住并点名行号**（E15 那道判据在兜底）；⚠️ **收尾时现扫工作树才发现的第三处**：工作树里躺着一处**校准变异残留** —— `scripts/audit_graph.py` 的 `if not s.get("context")` 被改成了 `if True`（正是 E31 那条校准 `sql-quote-context-guard-always` 的突变文本）⇒ 它**不在**本轮计划的 10 个文件里 ⇒ 但 `git add <点名文件>` 只提交点名的文件 ⇒ 计划外的脏文件**永远进不了提交、也就永远不会被 git 看见** ⇒ 而 `ship_check` 的自净核对**只数个数、不比对清单** ⇒ 三个环节叠在一起 ⇒ 它能潜伏到下一轮 ⇒ **已回滚（逐字节等于 HEAD）并重跑全部闸门与靶场**（validate 31/0/0、330 用例 OK、校准 91/91 全红、靶场逐字复现）＋ **给全仓 96 个 tracked 文件做 sha1 快照**、校准跑完逐个核验还原 ⇒ **E51 要把「工作树脏文件清单 vs 本轮计划清单」变成机器闸** |
| **E50** ✅ | v0.84.0 | **交接文档升级成「极致详细」版** —— 新增 §15–§25（目标与边界、技术栈、能力全景、判据地图、坑谱索引、硬性要求与纪律出处、进度与未达标、接手路线图、命令速查、**GitHub 操作规范**、风险雷区）；⚠️ **动手前先量**：把草稿与 §0–§14 逐节对账 ⇒ 实测**八处重复**（§18.2/§5.1/§23.1 三份闸门命令、§18.3/§5.3 两份 CI 步骤、§19/§8 两份坑位、§20.1/constitution.md 两份门槛、§21.2/§11 两份停牌项、§24/§5.4 八处、§22.1/§13 两份期望值、§15.3 与 §21.2 内部互抄）⇒ ⇒ ⇒ **照原样落地就等于把 E49 刚收拢的「现行规则只在 §5.4 一处」再摊开一遍** ⇒ ⇒ ⇒ 抓手：**新章节只许「导览 + 增量」，既有章节是权威 ⇒ 一律指向、不复述** ｜ ① **仍只有一份交接文档**（`docs/jiangzuo/handover.md`）⇒ **只追加 §15–§25，不重写 §0–§14**、不造第二份；② §16.3 不再抄 §2 的目录树、§18.2 去掉命令列、§18.3 改成「改什么 → 哪一步会红」的路由表、§19 改成**指向 §8 编号的分类索引**（并如实写出「§8 收录截止第 55 条、**E27 之后尚未回填**」这个缺口）、§20 改成**出处索引**、§21.3 全改现查命令、§23 **只列命令不写期望值**（期望值只写在 §13 一处 ⇒ 第 14 项不会验到第二份）、§25 去掉与 §6 重复的数；③ **每笔都变的数一律不写死**（分册/脚本/模板/规则条数/用例数/校准例数/信息条数）⇒ 全改「见 §0 规模行」或「现查命令」；④ **§5.4 的流程行改成指针** ⇒ **§24.3 成为 GitHub 流程的唯一一处**（10 步逐步 ＋ 注意点）⇒ §5.4 只留凭证与两条现行规则 ⇒ **与 E49 的收拢方向一致**；⑤ **§24 补齐「不得干扰其他项目」六条硬边界** ＋ §24.5 补一条新坑「**计划外的脏文件潜伏**」（E49 实测）＋ §24.3 步骤 1 新增「**与本轮计划清单对账**」；⑥ ⚠️ 本轮我自己的一个错误：草稿初稿把停牌项抄进 §21.2 ⇒ 而 **§11 自己写着「收口在这一处，别再抄到别处」** ⇒ 读 §11 时才看见 ⇒ 改法：§21.2 只列「还没做到」，停牌项一律指向 §11 ⇒ **这是 §19.1 第一类的活标本**；⑦ 文档仍被第 12/23 项守着（表格结构 ＋ 标记区对账）；⑧ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E51** ✅ | v0.85.0 | **把「工作树脏文件清单 vs 本轮计划清单」变成机器闸**（E49 那处潜伏残留的根因收口） —— 三个环节叠加过的洞：`git add <点名文件>` 只提交点名的文件 ⇒ 计划外的脏文件**永远进不了提交、也就永远不会被 git 看见**；`ship_check` 的自净核对**只数「待交付变更数」、不比对清单** ⇒ E49 收尾时才发现 `scripts/audit_graph.py` 里躺着一处**能改坏引擎的校准变异残留**（`if True`，已潜伏一整轮） ｜ 新增 **`scripts/plan_check.py`**（零依赖、不写文件）：拿 `git status --porcelain -z --untracked-files=all` 与**本轮计划清单**对账 ⇒ ① **计划外脏文件**当场红 ② **计划内未动**也红（划掉或查为什么，都该是显式决定）；**三态退出码**（与 release_consistency 同一规矩）：0 一致 ／ 1 不一致 ／ **2 没核成**（非 git 仓库·git 不可用·**没给清单** ⇒ 绝不当成通过）；`-z` 是 NUL 分隔不做路径转义（R/C 条目占两字段、旧路径也算对上账）；`--plan FILE`（`#` 注释／空行跳过／行尾 `/` 按目录前缀）与位置参数可混用 ｜ 判据 `TestPlanCheck` **10 条**（解析 1 ＋ 补丁式 7 ＋ **黑盒临时 git 仓库** 2）；变异校准 **95/95 全红**（新增 **4** 条：计划外不收集／计划内未动不收集／不一致退出码被换 0／没核成退出码被换 0——最后这条防的是**恒绿的空锁**）｜ §24.3 步骤 1 改成「跑这个脚本」、§24.5 与 §25 的坑位修法改指向它、§17.3 收进元工具表、§23.1 收进闸门命令 ｜ ⚠️ **它做不了 CI 检查**（CI checkout 出来的工作树本来就干净）⇒ 判据只落在**提交前的本地流程**，已写进脚本 docstring 与 §24.3 ｜ ⚠️ **中途校准出现过 4 条 INVALID（旧用例）**：CASES 已成 95 而 CHANGELOG 最新条目还写着 91 ⇒ 那些判据核对仓库现状 ⇒ **记账没做完之前全量校准本来就不该跑**（顺序：先记账后校准）；顺带订正 §13 一处**过期期望**（DVWA `69/68` 是 E7 时代的 A/B 数字，现行 **58/58**——第 14 项的三类管不到它 ⇒ 历史漏网）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E52** ✅ | v0.86.0 | **回填 §8 坑位清单**（E50 发现的缺口收口）—— §8 收录截止在第 55 条（约 E26 前后），E28–E51 的坑散落在 CHANGELOG 与 §4 台账里，没有进「症状 → 根因 → 修法 → 留下的东西」的本体 ｜ ① **新增第 56–78 条**（23 条，逐条标实踩轮次；既有 55 条的编号与内容**一个字未动**——别人引用「§8 第 N 条」不能指错）：E29 假红灯/判据没验过/变异打偏、E35 微测四事故、E36 逼人说假话的锁、E37 数数≠指向/规则未实测、E38 空行切表/两套解析、E39 三态退出码/宁可少核、E40 只查最后一个/查重按行、E41 门面占位符/推成≠报成功、E42–E44 三种第二真源、E45 五种漂法、E46–E47 守不住的数别写、E48 外向变更回读、E49 四件套、E50 详细≠份数、E51 校准顺序/三类漏网；② §19 的截止句与五类索引行同步（去掉全部「§8 未收录」标注）；③ §21.2 的对应未达标行移除；④ 第 20 项的编号连续性守卫全程绿 ｜ ⚠️ **不新增判据、不动引擎**：测试 340、校准 **95/95 全红（无新增）**、validate 31/0/0、口径一字未变（DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19） |
| **E53** ✅ | v0.87.0 | **把「三仓数字」接进期望值对账**（第 14 项扩第四类，根治 DVWA「69/68」那类漏网） —— E51 订正 §13 时定性：前三类（用例数／语料分母／规则条数）**管不到三仓发现/结论数** ⇒ DVWA 期望挂了一个多月没人发现 ｜ ① 第四类两形态：**`sims`**（同一行 `audit_scan.py <目标> … # 期望：N 发现 / 结论 N`，目标名决定对账哪段）＋ **`sims_self`**（`N 发现 / 结论 N / 另计 N`——自扫标尺，E7 那次坏的就是它）；② 真源 = `current-state.json` 的 **measured** 段（`--refresh` 从扫描产物写入 ⇒ 真源不会腐烂；读落盘真源 ⇒ 仍不跑扫描、跨平台同色），**取不到就报错**；③ 完整性按**配对**判（声明其一必须写全其二）——⚠️ **第一版按"文件里有 audit_scan 命令"判 ⇒ 当场红出 9 条误伤**（README 目录树行／交付报告占位行／分册通用示例全被当成电池）⇒ 收窄并按 E52 规矩把新坑写进 §8 第 **79** 条；④ 真仓库当场自证能红（flask 行改 99 ⇒ 第 14 项点名「实际 13/1」⇒ 逐字节还原）｜ 判据 `TestValidateSimsNumbers` **3 条**（⚠️ 进程内补丁**两处**真源——静态真源也要固定，否则 unittest 探索与本套件 `tests` 包名相撞 ⇒ 夹具静态分支误红）；变异校准 **97/97 全红**（新增 **2** 条：三仓分支被废／自扫分支被废）｜ §5.2 的第 14 项描述同步 ｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E54** ✅ | v0.88.0 | **行为微测二轮：换指标测「过程可审计性」**（E35 的假设第一次拿到双臂数据）—— 预注册在跑之前（指标＝4 项证据完备度：①实跑 ②留痕-命令 ③留痕-结果 ④挂靠；**跑了没写＝0**；阈值＝B ≥15/20 且 A ≤8/20 才许「有效」，否则继续不宣称；失败率口径不变）｜ **实测**（10 次独立 general-purpose 会话，夹具逐次重置、污染检查全过、无效运行重跑不计点）：A 臂 5 次全散文式静态推理 ⇒ **5/20**；B 臂 5 次全实跑＋证据表（B3/B5 自造数据沙箱验证逻辑，A 臂无人做）⇒ **20/20** ｜ **判定**：失败率 **A 0/5 vs B 0/5 ⇒ 基线未红**（保持）；过程证据 **⇒ 有效（可审计性）** ⇒ **本项目第一条有实测的行为增益声称（范围限定：本场景、该指标）**，第 24 项同步扩**实证配对解析**（`A 证 x/20 … B 证 y/20` ＋ 预注册阈值核对，没数据/不达标写「有效」当场红）｜ 判据 `TestMicroTestClaims` **+3 条**；变异校准 **99/99 全红**（新增 **2** 条）｜ meta-test **八条**如实登记（含独立核查新增：预注册不可核证 ⇒ E56 锚定、产出未归档 ⇒ 已当场补齐）；**独立核查 CONSISTENT**；逐次取证 `eval-runs/mt2/evidence-e54.md` ＋ 原始产出全文 `eval-runs/mt2/transcripts-e54.md`（仓库外）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E55** ✅ | v0.89.0 | **英文分册第一批**（requirements / testing / code-review / debugging）—— 独立大工程的第 1 批；「明确不做」清单里它被登记为「留作独立大工程」⇒ 大工程也要有第一批 ｜ **落位先核后定**：references/ 与 _readme_truth 的 glob 非递归 ⇒ `references/en/` 有意不进中文分册计数（仍 20）、lookup 词表与中文契约；入口预算只剩 8 tokens ⇒ SKILL.md 一字未动 ｜ **第 12 项扩展 `check_en_booklets`**：两套锚点一个机制（英文硬锚点 When to read / **Output / CRITICAL: read the entire booklet ＋建议项＋160 行）；**对照账 `docs/jiangzuo/en-coverage.md`** 守半拉子（✅ 已译行 ↔ en/ 实际文件一一对应）；双门面各补一行指针（不带计数）｜ **翻译质量流程**：子代理并行整译（行数 1:1：98/98、79/79、118/117、82/82）⇒ 独立双语审（漏译/走样/编造三类；requirements/testing **PASS**；code-review/debugging 审稿意见入库前收口）⇒ 审稿意见落地（TODO 清理／Output 统一／锚点归一）｜ 判据 `TestEnBooklets` **4 条**；变异校准 **101/101 全红**（新增 **2** 条）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E56** ✅ | v0.90.0 | **微测规程修订**——预注册独立提交锚定＋原始产出当轮归档＋方差必填（E54 独立核查两条隐患收口） ｜ 规程新节「锚定与留痕」三条硬性（①预注册先独立提交、实测笔引用「预注册笔：<sha>」②原始产出当轮归档进 eval-runs 并点名路径 ③方差必填——E54 曾漏报）；**第 24 项扩两条判据**（实测节必须有锚定标记——**上线当场逮住 E35 实测节也缺** ⇒ 补历史标注；引用的 sha 必须 `git rev-parse --verify` 真实存在）｜ E54 历史事实如实标注「预注册与实测同笔（bd99078）」——不冒充有独立锚定 ｜ 判据 `TestMicroTestClaims` **+3 条**（锚定缺失红／假 sha 红／真 sha 黑盒过；真仓库绿为既有用例）；变异校准 **103/103 全红**（新增 **2** 条，「跳过条件」式锚点——§8 第 80 条教训沿用）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E57** ✅ | v0.91.0 | **英文分册第二批**（api-design / frontend / backend / database，对照账 **8/20**）＋ E55 遗留两处中文源笔误收口 ｜ ① **中文源先收口**（E55 审稿二的发现、亲核后改）：code-review L50「全程可信」→「全程不可信」（漏「不」）；debugging L22「上次异常」→「首次异常」（与英文及经典排查窗一致；英文不动）② 四本整译：第二批提示词**直接带上骨架锚点词** ⇒ 1:1 行数（82/82、61/61、64/64、65/65）零归一化返工 ③ 独立双语审**四本全 PASS（0 漏译/0 走样/0 编造）**、语气强度零损耗 ④ 对照账四行转 ✅（既有对账判据全程绿）｜ 判据：无新增（复用 E55 机制——本轮没有新机制，新声称由既有判据守）；校准 **103/103 全红**（无新增）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |
| **E58** ✅ | v0.92.0 | **英文分册第三批**（design / onboarding / docs-delivery / security，对照账 **12/20**） ｜ 四本整译行数 **1:1**（116/116、67/67、82/82、73/73）——锚点词进提示词的流程**连续第二批零返工**；独立双语审**四本全 PASS**（0 漏译/0 走样/0 编造），强情态词逐条核过（绝不→never×2、反向禁止→the reverse is forbidden）；审稿附注的 docs-delivery CRITICAL 行缺闭合 `**` **入库时顺手修掉**；对照账四行转 ✅（对账判据全程绿）｜ 判据：无新增（复用 E55 机制；真仓库本数断言已改为从对照账现查——本轮 12 本自动通过即为验证）；校准 **103/103 全红**（无新增）｜ 口径不动（引擎一行没动）：DVWA 58/58、flask 13/1、requests 4/0、自扫 8/0/8、覆盖 14/19、语料 25/25 & 0/19 **一字未变** |

**当前所处等级**：交付报告 §5 的"复用阶梯"停在**第 2 级（仓库已有）与第 6 级（标准库）**之间；
技能本身已可交付使用，**但未自封 1.0.0**——判据见第 11 节第 12 项。

---

## 5. 质量机器：怎么跑、怎么发版

### 5.1 本机四道闸门（改完必跑）

```bash
cd "D:/Github项目/jiangzuo/jiangzuo"
python scripts/validate_skill.py .            # 期望 32 条信息 / 0 警告 / 0 错误
python scripts/preflight.py --all --strict    # 期望 RESULT: PASS（critical/high=0）
python -m unittest discover -s tests          # 期望 Ran 353 tests ... OK
python scripts/ship_check.py --level L1        # 期望 RESULT: SHIP-OK（6 通过/0 警告/0 未过）
python scripts/audit_rules.py --validate       # 期望 RESULT: RULES-OK（33 条，另有 1 条数据停用）
```

### 5.2 `validate_skill.py` 现在拦什么（27 项，都是一条条踩坑换来的）

正文行数 ≤500 ｜ 正文 token ≤5000 ｜ description ≤1024 字符 ｜ 清单 entry ≤299 字符 ｜
`metadata.version` 与 CHANGELOG 一致 ｜ **CHANGELOG 条目日期与 git 提交日期对账** ｜ 含 `evals/` 评测集 ｜
正文引用的 28 个文件全部存在且用正斜杠 ｜ 分册间无嵌套阅读链 ｜ scripts 全部可编译 ｜
20 本分册骨架契约 ｜ README 的脚本/模板/分册计数与实物一致 ｜ README 的入口行数与实物一致 ｜
README 的规则条数与实物一致（34 条含 1 停用）｜ 分册全部登记进 `lookup.py` 路由词表 ｜
**Markdown 表格行头完整 + 表内列数一致 + "上表 N 条"对账 + 未来日期拦截**（58 个 .md 全查；E38 加"列数一致"那条，⚠️ 按 **GFM 规则**数列，`\|` 是转义、不算分隔符；⚠️ **E41 修**："今天"取 **max(机器的本地日期, 最近一笔提交的作者日期)** —— **提交里记的就是作者那天的时区** ⇒ 与跑闸机器（**CI 是 UTC**）无关 ⇒ 不再把作者当天的提交判成"未来日期"（那次**本机全绿、CI 假红**））｜
**代码块里"照着跑就能看到"的期望值与实物对账**（用例数 / 语料分母 / 规则条数，E8 新增；三仓与自扫实测，E53 扩第四类 ← 真源 `measured` 段，第 14 项）｜
**入库文本里没有 U+FFFD 替换字符**（E15，第 18 项）｜
**变异校准器随技能分发、零依赖、例数与 CHANGELOG 对账**（E24，第 19 项）｜
**交接文档在仓库内、7 个关键章节齐全、已被 git 跟踪**（E27，第 20 项）｜
**结论区判定表自洽**（E29，第 21 项）｜ **「全部产出」口径拆解自洽**（E32，第 22 项）｜
**「当前状态」真源与文档对账**（E34，第 23 项：真源 `evals/current-state.json` ＋ 文档里的 `current-state` 标记区 ⇒ 散文里的数也被人守；**E46 再扩**：§0 的「规模」行由实物**生成**并**逐字**对账 ⇒ 写错 / **多写一个数** / 删掉 / 写两处都当场红）｜
**微测台账的判定不许脱离数据**（E35，第 24 项：状态格只能是规程允许的判定，且必须与实测失败率差对上 ⇒ **改结论不改数据当场红**）｜
**两个门面的计数与预算**（E36：第 7 项扩成**中英各查一遍** ＋ 入口行数比**正文行数** ＋ description/entry 字符数也纳入；**E41 再扩**：门面的**安装命令**必须指向真实仓库；**E42 再扩**：仓库身份**只许有一处**（真源 = `scripts/repo_identity.py`）⇒ 抄到第二个脚本当场红，**真源缺失必须报错**（不许静默跳过）；**E43 再扩**：仓里 `docs/jiangzuo/releases/*.md` 必须与 **CHANGELOG 生成的版本逐字一致**（判据**复用生成器本身**）⇒ 手写副本＝第二真源 ⇒ 当场红；**E44 再扩**：**发行说明不许走兜底**（兜底＝拿 tag 的提交说明当第二个来源）⇒ 那一类差集**不再允许登记例外** ⇒ 当场红；⚠️ 实测此前两个门面的命令都写着 `npx skills add <you>/jiangzuo` ⇒ **照抄的人必然失败**、而它在 markdown 里「看着挺像样」⇒ **生态那扇门其实是死路**；⚠️ **本地路径占位符**（`<你的项目>`）是该有的 ⇒ 不得误伤）｜
**台账自身不许被写坏**（E36，第 25 项：版本条目不得重复 ＋ CHANGELOG 必须降序 ＋ 验收记录/交接文档**按表分块**查重；**E40 扩到进化账本**：轮次号**不得回退** ＋ 同一张表里**不得有两行完全相同**——它的行格式 `| 日期 | E37 …` 与查重正则认的 `| **E37** ✅ | v0.70.0 |` 不同 ⇒ 此前**完全不在查重范围内**；**E40 再扩**：验收记录的版本小节**必须升序**（它是**新版本在后**）＋ **每个 current-state 标记区都对账它自己那一版**的快照——此前**每个载体只查一个区块**（14 个区块里 **12 个**无人守）⇒ E39 把 v0.72.0 的区块改写成 v0.73.0 的数时**对账跟着腐化一起漂 ⇒ 绿灯**）｜
**远端发布产物的自洽**（E39，第 27 项：核验器**随技能分发** ＋ 零依赖 ＋ **三态退出码**（0 一致／1 不一致＝真问题必红／2 **没核成**＝限流或网络 ⇒ **绝不当成通过**）＋ CI 作业**处理了「没核成」那一态**）｜
**发布产物的「身份」**（E37，第 26 项：真源 `evals/release-identity.json` ＋ 每个 tag 指向的 commit **真的属于那个版本** ⇒
「tag 存在」不等于「tag 是它该有的那个」；⚠️ **没有 tag 的目录不适用这一项**，且 CI 的 `checkout` 已改 `fetch-depth: 0` ＋ `fetch-tags: true`
——否则这一项在 CI 上只能发一句「这轮没跑」，等于一把**恒绿的空锁**）。

### 5.3 远端 CI（六道 + 一步诊断）与"怎么在本机核"

`.github/workflows/validate.yml`（ubuntu-latest + Python 3.11）依次跑：
`validate_skill.py` → `preflight.py --all --strict` → `unittest discover -s tests` → `ship_check.py --level L1`
→ `bench.py`（400 文件，≤20 ms/文件、≤128 MB，拦数量级回退）→ **靶场复跑**（`gen_corpus.py` + `score.py`）。
末尾另有一步 **`if: failure()` 的六道闸门诊断**：任何一步红时，把六道闸门在 Linux 上**全部重跑一遍**，
并逐条把 `PASS/FAIL <闸门名>`、失败的用例名、异常行写成 **workflow 注解**（单条截到 200 字）。

为什么必须有那一步：**作业日志匿名下载 403**（`Must have admin rights to Repository`），
而 **check-run 注解公开可读**。本机读 CI 结论的三条命令（无需登录、无需令牌）：

```bash
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/actions/runs?per_page=1"      # head_sha / conclusion / id
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/actions/runs/<run_id>/jobs"   # 六道步骤各自 success
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/check-runs/<job_id>/annotations"  # 红的是哪条用例
```

**判据是"六道步骤逐一 success"，不是作业级那一个勾**：某步失败会让后面的 `bench` / `靶场` 变 `skipped`，
2026-10-14→10-20 那 22 个红 run 里这两步从未真正执行过而无人察觉。
2026-10-20 实测：run `39395904677`（`efa0bd1`）六道步骤全 `success`、诊断步 `skipped`。
v0.41.0 复核：run `39406875082`（`427f128`）六道步骤同样全 `success`、诊断步 `skipped`。
v0.42.0 复核：run `39414864484`（`b8377aa`）六道步骤全 `success`、诊断步 `skipped`——
这一轮尤其值得看：**新增的"期望值对账"判据在 Linux/Python 3.11 上也绿**
（真源全部静态取，跨平台性第一次拿到远端实证，不是推断）。
v0.43.0 复核：run `39441703008`（`904de4d`）六道步骤同样全 `success`、诊断步 `skipped`。
中文步骤名在这三个 JSON 里会显示成乱码（Windows 控制台代码页所致），不影响读 `conclusion` 字段。

### 5.4 推送到 GitHub（凭证与流程）

- 令牌**内嵌在 `.git/config` 的 remote URL**：`https://Zhang-jx00:<TOKEN>@github.com/Zhang-jx00/jiangzuo.git`；
  名称**「将作skill」**，fine-grained，**Only select repositories → 仅 jiangzuo**，权限 **Contents: RW + Workflows: RW**，
  记录中的到期日 **2027-01-03**（到期日本机不可自助核，去浏览器 GitHub → Settings → Developer settings 看，
  **不要为核对而加权限**）。
- 仓库级 `credential.helper` 被设为**空值**（关掉系统级 Git Credential Manager）。**不要恢复它**：
  历史上出现过"令牌有效但 push 报 `Authentication failed`"，根因就是 GCM 用别的凭据覆盖，
  而账号下另有 **workbuddy 项目的专用令牌——绝不触碰、绝不使用**。
- 查看脱敏 URL：`git remote get-url origin | sed -E 's#://[^@/]+@#://<CREDENTIAL>@#'`
- **令牌绝不写进任何代码文件、文档、提交信息**（本文档也不写）。
- 中文提交信息必须走 UTF-8 文件：`git commit -F ../eval-runs/_msg.txt`（`-m "中文"` 经 shell 会乱码）。
  提交信息**主题里带 `v<版本号>`**——`validate_skill.py` 会拿它跟 CHANGELOG 日期对账。
- 流程：**见 §24.3 的步骤 0–10**（四道闸门 → 点名暂存 → 提交 → 推 main → 打附注 tag → 推 tag
  → 核 CI → 发 Release → 回读远端 → 补记笔）；**每一步的注意点也在 §24.3** ⇒
  **§24.3 是 GitHub 流程的唯一一处**（本节只留凭证与现行规则，别在这里再抄一份）。
- **网络一断就停推，不要改走 SSH 或换令牌绕过**（E27 那轮的实际做法：主站不可达 ⇒ 有界重试 5 次全败 ⇒ **停推、如实留痕**；网络恢复后按 `push main → 打 tag → push tag → 核 CI` 走完）。⚠️ **唯一允许的绕法是换前端 IP**（v0.74.0 那轮：`curl --resolve` 扫出可通的前端 IP ⇒ 直推即通）⇒ **不落任何配置文件、不改走 SSH、不换令牌**；仍不通 ⇒ 就停推。
- **推完必须回读远端核对**（E41 那轮：`git push` 退出码 0 ＋ 输出 "Everything up-to-date"，而远端根本没有那个 tag ⇒ **退出码 0 ≠ 事情做成了**）⇒ 推完用 `git ls-remote` 回读一次。
- **已发布的 tag 不要移动**（移动 = 改写别人看到的引用；历史上移动过一次，那是用户当场批准的例外）。
  现状照实说：`v0.40.0` → `ee266d7`，而 `HEAD = efa0bd1` 是它之后的一笔纯文档修正。
- **`github` MCP 只用于只读核对**（`get_commit` / `list_tags` / `list_branches`）：无法确认它用的是哪一枚令牌，
  所以**写操作一律走 `git push`**。另注意：该 MCP 的 `get_tag` 与 `get_file_contents` 当前有输出 schema 缺陷
  （报 `Structured content does not match the tool's output schema: data must have required property 'result'`），
  换 `list_tags` 或匿名 REST 即可。

### 5.5 新判据的规矩（本项目最看重的一条）

任何"锁"必须先证明**它能红**再声明它有效：
① 写完跑一次（绿）；② 用变异把被测实现改坏，跑同一条测试（**必须红**）；③ 逐字节还原（先读进内存再落盘）并比对 sha1；
④ 把这三步的输出一律记进 `evolution.md` 的"验证"列。
**反面清单（本项目实测过的假锁形态）见第 10 节。**

---

## 6. 评测结果与分母口径（别混用分母）

| 评测 | 数字（2026-10-20 实测） | 口径与警告 |
|---|---|---|
| **靶场检出**（外部标准答案） | DVWA 主类别 **14/19 = 73.7%** | 分母是 DVWA 的**模块目录名**；同目录路过报别的种类不算命中；官方修复档 `impossible.*` 命中也不算。历史：7/19 → 10/19 → 11/19 → 13/19 → **14/19**（E9 补上 `php://input` 这一类 source） |
| **干净仓库误报** | **静态可修的硬误报 0 / 59 = 0%（E29 清零）**（⚠️ E28 起**拆成三类**：静态可修 **0** / 待能力升级 **0**（E31 也清零了）/ 静态消不掉 **4**（能力边界型）⇒ **"硬误报"这个笼统的分子会误导**——那 4 条改规则也消不掉）（⚠️ E26/E29/E30/E31 收窄后重述，**与 E25 的 3/64、E20 的 8/69 都不可比**——**分子分母每次同时变**） | 分母＝**现行结论区 59 条**（DVWA 58 + flask 1 + requests 0）。分子＝**已判定为"检测错了"的 4 条**（DVWA 3 + flask 1）。⇒ **DVWA 结论区的硬误报已归零**（E20 判定时是 7 条）。**"需人工细判"也已清零**（E20 单列 3 条 ⇒ E25 变成 1 条真阳性、E26 判成 2 条不该报并修掉）⇒ 现在结论区**每一条都有结论**。⚠️ 判定依据仍是 **sink 行**（未逐条读完整证据链）——这一点写在台账里，不冒充人工审阅。详见 `evals/finding-verdicts.md` 与验收记录 v0.62.0 节 |
| **自建语料** | **25/25 检出、0/25 非答案发现、0/19 安全样本被误报**（44 文件） | 语料是本项目作者自己写的，**带出题人偏置**，证明力只到"这些类别能被检出、安全写法能区分"。⚠️ 这组数**会随语料长**：v0.37.0 之前是 `16/16 & 0/18 & 0/15`，v0.43.0 之前是 `23/23 & 0/23 & 0/17`，旧报告里的老数字不要拿来对今天的输出 |
| **本仓库自扫** | **8 发现 / 结论 0 / 另计 8**（v0.41.0 修后） | ⚠️ **v0.37.0–v0.40.0 期间这个数是错的**（实测"结论 3"）：语境档认不出带限定词的目录，语料生成器 `evals/audit-fixtures/` 被当正式代码，**干净仓库标尺被污染**。修法与三段快照实测见 `evals/audit-acceptance.md` 的 v0.41.0 节。 |
| **任务评测 5 项** | **2026-10-07 就跑完了**（双臂 10 份运行副本，逐份磁盘取证） | ⚠️ **旧版这份文档写的是"完全没跑"，是抄错的**——它从 C 盘项目记忆 `jiangzuo-handover.md` 抄过来时抄错了那一条。实据：`evals/task-evals.md` 有完整记录表与总判定，`eval-runs/results/task-evals-run-20261007.md` 是逐条取证，交付报告 §3.3 也写了"10 份运行副本"。**不需要重跑**；真正剩下的是"换真实项目/真实用户会话再复跑一轮"（当前臂用合成夹具 + 子代理，方法学偏差已自陈）。 |
| **触发率** | **7/24（正例 2/19、反例 5/5 零误触发）**，未达 90% | 关键发现：清单 entry 实测截断在约 299 字符；未达标主因是**加载竞争**（superpowers 的 SessionStart 注入抢占 8/16 失败），不是措辞。B 路线（显式调用 + 高重合话术）已执行，C（继续磨措辞）已否决，**A（无竞争对照）未做，需用户点头** |
| **红测 7 场景** | S2 / S6 / S7 有判别力；S1 / S3 / S4 / S5 基线未红 | 基线不红 = 当前模型与环境无区分度，如实保留为回归哨兵，**不声称收益** |
| 三条新纪律条款 | 只有文本锁 + 结构锁 | `evals/micro-tests.md` 已标注该状态，**不对外声称行为收益** |
| SARIF | 字段级自检 + **SARIF 2.1.0 schema「允许属性」白名单**（零依赖，v0.55.0） | 官方 validator（`@microsoft/sarif-multitool` 5.8.0）**已在本机跑过**：修前 **8 条 error** → 修后 **0 error**（⚠️ 它的退出码不可信，只能解析 error 行）。它**非零依赖、CI 装不了** ⇒ CI 跑的是等价的白名单自检，**不声称「CI 通过官方校验」** |

复跑命令（产物一律写到仓库外）：

```bash
cd "D:/Github项目/jiangzuo/jiangzuo"
python evals/audit-fixtures/gen_corpus.py --out ../eval-runs/corpus
python evals/audit-fixtures/score.py --corpus ../eval-runs/corpus
python evals/audit-fixtures/bench.py --workdir ../eval-runs/bench --files 1500 --repeat 2
python scripts/audit_scan.py <第三方仓库> --json ../eval-runs/scan.json          # 只读
python evals/audit-fixtures/dvwa_coverage.py --json ../eval-runs/scan.json        # 外部检出分母
```

第三方取证用的浅 clone（DVWA / flask / requests）放在仓库外、**用完即删**。
**扫描原始 JSON 有两代，别拿错**：
- `../eval-runs/tp6-*.json` / `tpf-*.json` / `self-b7.json` —— **v0.30 时代**的扫描
  （`rules_version=0194a712…` / `a7fd8e36…`），只作历史留底。⚠️ 拿它们跑 `dvwa_coverage.py`
  **只能得到 6/19 和 7/19，不是 13/19**（规则库后来加了 cryptography/javascript 两类）。
- `../eval-runs/tp-evidence-20261021-{DVWA,flask,requests}.json` 与
  `self-scan-20261021.json` —— **v0.58.0 当场重 clone 重扫**的（当前规则版本），
  才是 §6 那些数字的**现行底稿**。
- `../eval-runs/tp-evidence-20261020-{flask,requests,DVWA}-{BEFORE,AFTER}.json` 与
  `self-scan-20261020-{BEFORE,AFTER,CHECK}.json` —— **E7 语境档改动的 A/B 两组**（历史证据，别当现行底稿）。
  人工判定结论与逐条理由在 `../eval-runs/third-party-evidence-20261015.md` 与 `evals/audit-acceptance.md`。

---

## 7. 审计链的判读要点（做检出/误报相关改动前必读）

- **分层门控**是大仓能扫的原因：索引(线性) → 地图(线性) → 粗筛(**不相关语言的模式一条都不碰，该语言无相关模式则文件都不打开**)
  → 深挖(与候选数相关) → 数据流(**只解析"候选 ∪ 被候选调用的定义文件"**) → 验证(与发现数相关)。
- **门控的 seed 必须是 sink 命中**：早期把 source 命中也当候选，`payload`/`body` 这类裸词让 1500 个文件全成候选，门控形同虚设。
  source 模式要带形态（`request.` / `req.` / `$_` / `params[`）。
- **规则里的正则是可执行代码**：一条 `[^;]*(?:A[^;]*<|<[^;]*A)` 失配时逐起点重扫 = O(n²)，600 KB 行跑 106 秒，
  而扫描路径把单行截到 4096 字节，本机永远看不出来。判据是 `TestAuditPatternCost`（每条规则的每个 pattern
  都要吃 540K 对抗行且不超 500 ms，**锚点集中末尾与铺满全行是两种复杂度，各测一次**）。
- **别拿本机计时当复杂度证据**：同一份代码单跑一遍整体慢 3 倍是环境噪声，所以回归锁的是**结构量**
  （`graph_parsed_files` 只随候选数变；仓库×4 而候选不变时它不变）。
- **误报的出口是豁免不是静音**：行内 `# jiangzuo:ignore JZ-XXX-001 <理由>` 与 `.jiangzuoignore`（`路径 规则ID 理由`）
  **必须带理由，没写理由的豁免不生效**；豁免可以打在该发现的任一证据跳上；某条规则反复被豁免 ⇒ 该收紧或该停用，
  不要靠豁免堆到看不见。
- **仓库角色**：`repo_role()` 判 library / app 要**同时**满足"无路由 + 无启动入口 + 有打包清单 + docs/examples 之外无真实页面文件"；
  少一个条件就会把过程式 PHP 的应用判成库——DVWA 实测被这样误判过，**7 条真漏洞被当"不适用"吃掉**。
- **语境档**：命中落在 `tests/ spec/ fixtures/ examples/ docs/ samples/` 或文件名形如 `test_*.py`、`*.test.js` 时
  **照报、仍留 文件:行、仍进 JSON/SARIF，只是不计进结论数**。判据按路径段与文件名形态，不按 "test" 子串。
- **source 键要列全**：`$_REQUEST`/`$_COOKIE` 与 `$_GET` 一样可控；只写 `GET|POST` 会漏整类流。
  **误报修掉后要回头看真阳有没有跟着掉**。
- **净化只服务于自己那一类**：`is_numeric/intval` 对命令注入是有效收敛，对 XSS 不是（`addslashes` 拦不住属性注入）。
- 静态图跟不动"变量路径"的 PHP `include/require`：真漏洞可能被标"不可利用"，两道兜底是
  过程式 PHP 页面算入口根 + 有变量路径 include 的文件共享同目录子树的模块级变量池。
  读到"不可利用"先问**是不是图没连上**。
- 大仓用法：先 `audit_index.py` 出清单存盘，再 `audit_scan.py --index 清单.json` 复用；
  续扫 `--cache DIR --incremental`（规则或解析器版本一变，整份缓存自动作废）。

---

## 8. 历轮踩到的全部问题：症状 → 根因 → 修法 → 留下的东西
1. **交付面挂着"CI 六步"，实际 CI 连续红了 22 次。** 症状：本机四道闸门全绿、远端却红。
   根因：**没人去核**——`v0.36.1` 交付时我在报告里写了一句"CI 在 GitHub Actions 上的实际运行结果本机无法核实"，
   这句话**本身是错的**（匿名 REST 就能读到 check-run 结论），于是"不可核"变成了不核的许可证。
   修法：读远端 → 定位到失败步骤 → 修复 → 报告里给那句话加复核标注（**不抹历史**）。
   留下：`evolution.md` E6 行 + CHANGELOG 0.40.0 + 本文档第 10 节一条铁规矩。
2. **本机取不到 CI 日志**：`/actions/jobs/<id>/logs` 匿名 **403**（要仓库管理员权限）。
   修法：给工作流加 `if: failure()` 的诊断步，把**六道闸门重跑 + 失败用例名 + 异常行写成注解**（注解公开可读）。
   留下：第 5.3 节三条 curl。**教训：先确认取证通道存在，再声称某事可核。**
3. **"作业级一个勾"掩盖步骤级 skipped**：`bench` 与 `靶场` 两步在 22 个红 run 里全是 `skipped`。
   修法：判据改成"六道步骤逐一 success"。
4. **两条锁自己平台依赖（红因本体）**：
   - 索引绝对路径锁：断言前把"本机绝对路径"归一化成**正斜杠**形式，而 Windows 上工具输出**反斜杠**形式 ⇒
     **针与真实输出永不相交**，这条锁在本机从来没真正成立过（假绿）；且比对文本把 `stdout` 也算进去，
     而 `stdout` 回显的是调用方自己传的 `--json` 落盘路径（Linux 上恰好命中 ⇒ 被误判成"泄露"）。
     修法：**只比机器可读产物（索引 JSON）**，针按 **原样 / abspath / realpath / 正斜杠** 四种形式各比一次，
     另加 `path` 不许绝对、不许含反斜杠、不许以 `/` 开头三条。
   - 规则"全局标志写错位置"锁：断言**中文关键字**，而措辞是 CPython 给的——3.8 走 `DeprecationWarning`（我写的中文提示）、
     3.11 走 `re.error`（英文提示）⇒ 本机绿、CI 红。
     修法：判定收进 `audit_rules.misplaced_global_flag()`（**自己认，不吃解释器的警告时刻表**），
     两支 `except` 都路由到同一句本项目生成的消息；另加判据正反 11 例（`((?i)x)`、`(?i:abc)` 这类合法写法不许误拦）。
5. **变异校准工具自己把被测文件清成 0 字节**。根因：还原语句写成
   `io.open(p,"wb").write(io.open(p,"rb").read().replace(...))`——同一表达式里**先按 wb 截断、后读**。
   修法：靠 `git checkout -- scripts/auditlib.py` 恢复；把校准器写成独立脚本，**先 `raw = read(path)` 落到变量再 write**，
   还原后比对 sha1 且确认可导入。留下：校准器（**v0.58.0 起已入库**：`scripts/mut_calibrate.py`，零依赖、带 `--check-only`）。
6. **Edit 锚点吃掉下一行的行头**（这个项目里第 5 次同类事故）。症状：新测试类里 `hit = [...]` 只剩续行，直接语法坏。
   修法：Read 定位 → 补回。**Markdown 侧这一类已有判据（`check_md_tables`），Python 侧没有** ⇒
   规矩：**插块/改块之后 `grep -c` 数一遍**（行数、`^| 2026-` 的行数、类数），别只看"编辑成功"。
7. **校验器自己的文案里藏着它禁止的东西**：`audit_rules.py` 中"反斜杠 b 被吃成退格符"的**注释与消息字符串**里
   各有一个**真退格符 0x08**（前次编辑时被工具吃掉）。修法：按字节替换回可读文本，
   并跑一次运行时输出确认消息里不再含 `0x08`。**教训：修完要按字节核，`git diff --numstat` 看不见行尾与控制字符。**
8. **本地 Python 是 3.8.3，CI 是 3.11**（`D:\Anaconda\python.exe`；另有 `C:\Users\张\bin\python3` 也是 3.8.3）。
   这台机器**没有** 3.11（`py` 启动器不存在，conda 只有 base 与 pytorch_38），WSL 只有 stopped 的 docker-desktop。
   ⇒ **不要假设"本机绿 = CI 绿"**，两个方向都不成立。
9. **想用"纯 LF 副本"模拟 Linux checkout 失败了**：`git archive` 在本机会**应用 autocrlf**，导出的 81 个文件全是 CRLF。
   正确做法：`git ls-files --eol` 看真实形态（实测：`i/lf` × 81，工作树 80 LF + 1 CRLF——那个 CRLF 是
   `evals/audit-fixtures/osv-pyyaml.json`）。后来干脆不模拟，**直接用 CI 本身当 Linux 试验台**（诊断步）。
10. **在 Windows 上直接执行 `.py` 报 `OSError: [WinError 193]`**（不是可执行的 Win32 应用）。
    规矩：**永远用 `sys.executable` 前缀**跑脚本（测试套件的 `run()` helper 就是这么做的）。
11. **`curl … | python -c "json.load(sys.stdin)"` 解析失败**（`Expecting ',' delimiter`）：流被截断。
    规矩：**先 `-o 文件`（写到项目内的 `../eval-runs/`）再解析**；不要用管道。
12. **`wsl -l -v` 输出是 UTF-16**，在 Git Bash 里看是"Binary output"。要 `| iconv -f UTF-16LE -t UTF-8`。
13. **不小心往 `/tmp` 写了文件**（= `C:\Users\张\AppData\Local\Temp`，违反"不占 C 盘"）。已删除并回报。
    规矩：**任何日志/临时产物只进 `D:\Github项目\jiangzuo\eval-runs\`**，用完即清、验证并回报。
14. **GitHub 高级安全没开，第三方密钥扫描这条路走不通**：`run_secret_scanning` 直接报
    `Repository does not have GitHub Advanced Security enabled.`。**开启它属于改仓库设置 = 需用户同意**。
    替代证据（本轮实际做法）：对 **81 个入库文件**做密钥形态 grep（`ghp_ / github_pat_ / gho_/ghs_ / PRIVATE KEY /
    key=value` 六类），**0 命中**；并用一个合成令牌做**红向校准**证明这套 pattern 能命中（命中 1 次）。
15. **github MCP 的 `get_tag` / `get_file_contents` 坏了**（输出 schema 不匹配），`mcp_list` 不能通过 `mcp_call` 调
    （它是顶层元工具）。绕过：`list_tags` / `list_branches` / 匿名 REST。
16. **robocopy 的两个坑**：① Git Bash 里必须 `MSYS_NO_PATHCONV=1`；② **退出码 0–7 都是成功**（1=已复制、3=已复制且有跳过），
    拿 `!= 0` 判失败会误报。
17. **搬家时发现两处过期数字**：交付报告 §6 的自验命令注释写着 `ACCEPT-OK 16/16 & 0/18 & 0/15`（语料早已长到 40 文件），
    以及同一文档里"期望 Ran 120 tests"（实际 138）。历史条目里的旧数字**不改**（那是当时真值），
    但**"照着跑就能看到"的期望值必须跟着当前实物改**。→ 下一步要做成判据，见第 11 节第 9 项。
18. **顶层多出一个同名草稿目录**导致 `mv` 报"Directory not empty"：我早期在项目顶层建过一个 `eval-runs/`，
    robocopy 把它一起搬过来了。清掉可再生内容后上提即通。**草稿目录要么只留一处，要么每次记清单。**
19. **远端核对的取证方式**（值得沿用）：`get_me` 确认身份 → `get_commit(sha)` 读提交与作者日期 → `list_tags` 读 tag→commit 映射
    → `list_branches` 读保护状态 → `ls-remote` 比对本地/远端引用。全部只读，无需日志权限。
20. **确认无误之前不声称完成**：本轮每次说"绿"之前都重跑了命令；`ship_check` 与全量测试在**改名前后各跑一次**，
    搬家后的最终路径又跑了 `validate / preflight / audit_rules / 138 用例 / gen_corpus + score`。
21. **E7：标尺本身被污染，别的数字全对也说明不了问题**（2026-10-20 接手轮）。
    症状：按第 13 节自检时顺手扫本仓库，自扫"结论 3 条"，而交付报告 §3.2 写"结论 0 条"。
    根因：**语境档只按整段路径段匹配词表**，`evals/audit-fixtures/`（语料生成器）不在表里 ⇒
    v0.37.0 新增的 `JZ-CRYPTO-003` 命中它源码里的字面量 `'aes-128-ecb'`，被当成正式代码。
    ⇒ **v0.37.0 那轮抄进验收记录的"结论 0（另计 5）"当天就没对**（另计 5 对得上、结论 0 对不上），
    一直没人发现——因为"结论 0"是**对照面的基线**，错了不会让任何一条检出看起来更好。
    修法：目录段按 `-`/`_` 拆词后**精确匹配**（`audit-fixtures` → `fixtures` 命中；
    `latest_posts` → `latest`/`posts` 两边都不命中）。A/B（重 clone 三仓）**flask 13/1、requests 4/0、
    DVWA 67/66 一字未变**，自扫 8 发现/结论 0/另计 8。**教训：量一个东西的时候，先确认那把尺子本身没坏。**
22. **变异校准器的"还原"是全局替换**（E7 踩到）：突变文本 `segs = set()` 在新函数里本来就有一份，
    还原时 `replace(new, old)` 把**别处一起改掉** ⇒ 函数自我递归。
    校准器自带的 sha1 断言当场拦住（这正是它存在的意义），但文件已经被改坏，得手工修回。
    修法：突变前断言**新文本在原文件里出现 0 次**、还原后恰好 0 次；不满足就 SKIP 并说明原因。
23. **一条校准用例长期恒绿**（E7 顺带发现）：`static-flag-check-removed` 废掉"全局标志写错位置"的
    **三道兜底中的任何一道**，测试照样绿（静态预检 / re.error 分支 / DeprecationWarning 分支）——
    本机 Python 3.8 上尤其明显。**恒绿的校准用例比没有用例更坏**：它让人以为那道锁有人管。
    修法：校准器加**多站点突变**支持，那条用例改成三道同时废才红（现已 RED）。
24. **校准器自己文档里警告过的坑又踩了一遍**（E7 第三次）：`io.open(p,"wb").write(io.open(p,"rb").read()...)`
    ——`open(wb)` 先截断、同一表达式里再读 ⇒ `scripts/auditlib.py` 被清成 **0 字节**。
    靠 `git checkout -- scripts/auditlib.py` 救回。**这条老坑记过两次、复发第三次**，
    说明"文档里写了警告"不等于"下次不会踩"——真正管用的是**每次写完自己核对 sha1 与文件非空**。
25. **新判据的第一版会误伤既有测试夹具**（E8）：形态完整性"三类各至少出现一次"按**仓库**判，
    结果把一个合法的最小技能目录（只写 README、不写期望值形态）判死了——
    被既有测试 `test_validate_flags_stale_rule_counts_in_readme` 当场逮住。
    改成**按文件判**（声明了期望值的文件必须写齐形态，没声明的文件不管）后转绿。
    **教训：新判据上线时，既有测试就是它的第一个用户**——能把你判死的，多半是你假定错了形状。
26. **说"残留 0"之前要现扫整个目录**（E10 收尾，2026-10-21）：上一轮报的"残留自查 0"其实只查了
    *本轮新增*的那几个文件，没现扫 `eval-runs/` ⇒ 漏掉 **5 个一次性产物**：
    `exp-dvwa.json` / `exp2-dvwa.json`（规则实验的中间产物）+
    `cleanup_app_db.cjs` / `cleanup_round2.py` / `cleanup_sessions.py`（2026-10-07 那次会话清理用完的工具，
    脚本里写的还是**搬家前已失效**的绝对路径 `D:\Zcode对话\workspace\skill开发\SkillOne\…`）。
    现扫是 **1167 项**（`fixtures/` `runs/` `results/` 三棵子树 + 40 多个底稿 JSON），逐个定性后：
    - **一律留**：任何被文档引用为"底稿/证据"的 JSON——`e9-*`/`e10-*`（E9/E10 的 A/B 底稿）、
      `tp-evidence-20261020-*` / `self-scan-20261020-*`（§6 的现行底稿）、`tp6-*`/`tpf-*`/`self-b7`（历史留底）、
      `self-check.json`（§13 命令里引用）、`tp2-*`；`results/` 下的 manifest / 快照 / 逐条判定记录。
      **证据在 `results/_session-cleanup-manifest*.txt` 里，不依赖那三个脚本** ⇒ 脚本可清，证据不能清。
    - **该清**：无任何引用的实验中间产物 + 用完的工具 + `_tagmsg.txt`（打标签用的说明文件，README 的
      `eval-runs` 约定里没列它 ⇒ 不属于常驻区，推完即删）。
    - **本轮实际清掉的**：上轮漏掉的 5 个（`exp-dvwa.json` / `exp2-dvwa.json` / `cleanup_app_db.cjs` /
      `cleanup_round2.py` / `cleanup_sessions.py`）+ `_tagmsg.txt`（标签推完即删）+ 本轮自己产生的
      `tp/`（三仓副本）、`tp-{DVWA,flask,requests}.json`、`_tp_scan.ps1`。
      **清完当场核对**：§6 的 6 个 `tp-evidence-20261020-*` 底稿**逐一 `Test-Path` 仍为 True**
      （MISSING=0），一次性产物残留 0，`eval-runs/` 剩 3 个目录（`fixtures/` `runs/` `results/`）+ 43 个文件。
    **教训一**：`eval-runs/` 是**常驻资产区**不是回收站——接手者若把"残留 0"读成"目录是空的"，
    会连底稿一起删掉。**说残留数必须先现扫 + 逐个定性（留/清），并把定性理由写下来。**
    **教训二**：用户那句「先复核，再进行任务」在这里兑现成了实际动作：上轮的口头数字（"残留 0"）
    当场现扫后是**错的**，纠正它比维护它更值钱。
27. **PS 5.1 把 UTF-8 无 BOM 脚本按 ANSI 读 ⇒ 解析行错位 ⇒ 后面的危险命令提前执行**（2026-10-21 实测）：
    症状：一份 `.ps1` 里**只有中文注释**，但读出来 `$PSScriptRoot` 是 null、`Join-Path` 报参数为 null，
    行号还跟文件对不上（报错指 line 3，文件里 line 3 是别的语句）。
    **真实后果**：脚本里一句 `Remove-Item -Recurse -Force $tp`（本该最后才跑）**提前执行了**，
    把刚下载好的三个仓库副本目录删掉了——而报错行在这句**之后**。
    根因：中文注释按 ANSI 解码后产生的乱码字节改变了脚本的词法结构。
    ⚠️ **E14 第三次复发**（而且是在**我自己刚写完这条警告的下一轮**）：
    ① `_close.ps1` 的注释里写了中文（还带反引号）⇒ 乱码让注释提前结束 ⇒ 后面变成代码执行
       ⇒ `$steps` 变 null ⇒ **脚本自己误报"CI not green"**，而 CI 明明全绿；
    ② 中文正则 `-match '校验技能结构|…'` 在 ANSI 下**静默匹配 0 个**（不报错）⇒ 计数永远是 0。
    ⇒ **"文档里写了警告"不等于"下次不会踩"**（第 24 条已记过一次同型复发）。
    **对策固化**：所有 `.ps1` 的**注释也必须纯 ASCII**；**不要用中文正则匹配**；
    需要按名字找东西就**按位置/序号**（工作流结构固定）⇒ `_round.ps1` 与 `_close.ps1` 已全部改成 ASCII。
    修法：**写给 PS 5.1 跑的 `.ps1` 一律纯 ASCII**（不写中文注释、不写中文路径字面量），
    路径用 `Split-Path -Parent $MyInvocation.MyCommand.Path` 推导；
    脚本里给每个关键目录加 `Test-Path` 断言，"目录不存在"要**当场停下**，别让一串命令对着空路径跑完。
    **教训**：编码坑不只是"显示乱码"，它能**改变执行语义**。凡是能写进 shell 的一律写 `.py`/`.ps1` 文件，
    并在文件里只放 ASCII。
    ⚠️ **同一天复发了一次**（E11 那轮）：这次的乱码**不在注释里**，在
    `Select-String -Pattern 'RESULT|主类别'` 的**正则字面量**里 ⇒ 解析期就报
    "The string is missing the terminator: '"，脚本**根本没执行**（连下载都没跑）。
    ⇒ 教训再补一条：**"纯 ASCII"要覆盖整个文件，不只是注释**——
    字符串/正则字面量里的中文同样会毁掉词法结构。要么全 ASCII，要么**改用 `.py` 脚本**
    （Python 3 按 UTF-8 读，没有这个坑）。
28. **自检清单里的清理命令会误伤自己的证据**（2026-10-21 实测）：第 13 节原第 639 行写着
    `rm -rf ../eval-runs/tp ../eval-runs/tp-*.json`。那个通配 `tp-*.json` **会命中 §6 的现行底稿**
    `tp-evidence-20261020-{DVWA,flask,requests}-{BEFORE,AFTER}.json`（`*` 能匹配
    `-evidence-20261020-DVWA-AFTER`）⇒ **照着跑就把底稿删了**，§6 的数字从此无法复查。
    改法：拆成两条——`rm -rf ../eval-runs/tp` 删目录，`rm -f` **逐个点名**删本轮生成的那三个
    `tp-dvwa.json` / `tp-flask.json` / `tp-requests.json`；并在旁边写明**为什么不能用通配**。
    同类排查：仓库内 52 个 `.md` grep `rm -rf|del /|Remove-Item|tp-\*` **0 命中**
    （交付报告里没有同类命令，风险只在仓库外这份文档）。
    **教训**：**"照着跑就能看到"的反面是"照着跑就会毁掉"**。自检清单里的每条命令都要过一遍
    "它的通配会命中哪些**该留**的文件"，尤其是通配符 `*` 比 `?` 宽。
29. **上一轮自己写下的乱码，没有任何判据能发现**（E11 复核时发现，2026-10-21）：
    E10 那轮给 `evals/audit-acceptance.md` 加 v0.44.0 节时，把一个「同」字写成了 **U+FFFD 替换字符**
    （一个 U+FFFD 替换字符 + "文件 helper"）——**文件照样能跑、结构照样合法、数字照样对得上**，
    `validate_skill.py` 的 17 项判据**一项都没报**（它查结构、查表格、查期望值，不查字符有没有坏）。
    E11 全仓扫了一遍（`.md`/`.py`/`.json`/`.yml`）**只有这一处**，已当场修好。
    ⇒ 已登记为 §11 第 14 项（给 `validate_skill.py` 加第 18 项 `check_no_replacement_chars()`）。
    **教训**：**字符级损坏**是判据的盲区——它不影响任何"能不能跑"的信号，
    所以只能靠一条**专门扫它的判据**；光靠"跑一遍看红不红"永远发现不了。
30. **判据恒绿的两个来源**（E12 校准当场逮到，比代码本身更值钱）：
    ① **只看 `findings` 不够**——引擎有"独立验证"这层兜底，证据链不成立的流停在 `dropped` 里、
       **压根没进 findings** ⇒ 判据必须查「`findings` ＋ `dropped`」这个全集。
       E12 第一版判据就是只看 `findings` ⇒ 校准跑出来 **GREEN（锁无效）**。
    ② **夹具里必须有另一处真 sink**——`audit_scan` 的**种子阶段**用 `iter_code_lines`
       决定"哪些文件进图层"；只剩注释里的 sink 时文件压根不进候选 ⇒ 图层没机会犯错 ⇒ 判据同样恒绿。
       ⇒ 修法：夹具里另放一处**真 sink（用另一条规则）**，既保证文件进候选，又能把断言分开。
    **教训**：写完判据**必须**配一条变异校准并看它**红**——恒绿不是"保险"，是**假锁**。
    而且**恒绿的原因往往不是判据写错，是判据问错了对象**（问"进了结论区的"而不是"引擎认为有问题的"）。
31. **变异校准器会静默跳过锚点未命中的用例**（E13 实测，跨项目通用）：
    仓库里 `scripts/auditlib.py` 是 **CRLF**、`scripts/audit_graph.py` 是 **LF**
    ⇒ 校准器的多行锚点（用 `\n`）在 CRLF 文件上**永远匹配不上**
    ⇒ 它只打印一行"锚点命中 0 次（校准无效）"就继续 ⇒ **看着像跑过了，其实根本没跑**。
    ⚠️ E13 当场踩到：E12 那条校准因为 E13 改了同一行而失效过一轮，**差一点就以为"22 条都跑了"**。
    修法：校准器按**文件的实际换行符**把内容归一后再匹配/替换/写回；
    并且**有 SKIP 就显式报告并让退出码非零** ⇒ **"校准跑了"这件事本身要被验证，不能只看输出行数**。
    ⇒ 顺带一条通用规矩：**同一个仓里不同文件可能有不同换行符**（本仓就是 LF/CRLF 混着），
    凡是要按文本匹配的脚本，都得先问"这个文件是什么换行符"。
32. **变异校准跑出 GREEN 也该算失败**（E14 实测）：
    校准的**目的**就是证明"锁能红" ⇒ GREEN = 锁无效 = **失败**，不是"通过"。
    E14 当场逮到一条 GREEN：它的锚点在实现演进后**指到了不影响该判据的地方**
    （改的是 `strip_line_comments`，而判据走的是 `strip_comments`）⇒
    **校准锚点会过期**，每次改实现都要**重看校准结果**，不能"上次全红就没事了"。
    现在校准器把 GREEN 与 SKIP 都计入失败并让退出码非零 ⇒ 少一条要靠人眼发现的静默失效。
33. **"自检通过"不等于"合规"，而且闸门的盲区常常正好盖住真问题**（E21 实测）：
    旧 `sarif_selfcheck` 只检查 `results[].locations`，**压根没看 `codeFlows` 里的 location** ——
    而官方 validator 报的那 **8 条 JSON1005 全部长在 `codeFlows` 里**。
    ⇒ 判据要覆盖"系统认为有问题"的**全集**，不能只查自己想到的那一处；
    真正权威的口径是**官方 schema 的允许属性白名单**（可离线硬编码进自检）。
34. **官方 validator 的退出码可能不可信**（E21 实测）：`sarif-multitool validate` 报着 **8 条 error**
    仍返回 **0**、并打印 "Analysis completed successfully" ⇒ **只能解析输出里的 error 行**，
    不能拿退出码当"通过"的证据。
35. **校准用例的 test_id 必须指向"真的经过被测路径"的那条测试**（E21 实测）：
    我给"把 `message` 放错层"那条例外挂的 test_id 是"手搓一份坏 SARIF 再喂自检"——
    那条测试**压根不经过 `to_sarif`** ⇒ 变异后照样绿 ⇒ **校准器当场报 GREEN**（"锁无效"）。
    改挂到"真实产物路径"上才真红。⇒ **夹具必须真的经过被测路径**（同 §8 第 30 条的病根）。




---

36. **"净化点的正则可能因为一个词边界而从来没生效过**（E22 实测）：
    `JZ-SQLI-003` 的净化点 pattern 是 `\breal_escape_string\b`，而 PHP 的标准写法是
    `mysqli_real_escape_string(...)` —— `_` 是**单词字符** ⇒ `\b` 在 `_r` 处不成立 ⇒ **匹配不上**
    ⇒ 引擎一直把转义处当"没净化"照报。**一刀直修好会压掉真阳性**（DVWA `sqli_blind/source/medium.php`
    转义了但在**引号外**＝数值上下文 ⇒ 转义救不了）⇒ 真正的解法是"净化点按 sink 上下文生效"。
    ⇒ **看到"净化点写了"不等于"它生效了"**，要用**真实写法**验一条。
37. **手数的偏差会自我延续**（E24 实测）：CHANGELOG 里写的校准例数从 E19 起**每轮都比实物多 1**
    （30→32→34→36）—— 因为写的时候是**在上一轮那个错值上 +N**，而不是**数实物**；四轮之后已错 4 条
    ⇒ 机器判据（`validate_skill` 第 19 项从实物数出并对账）是唯一解法。
    ⇒ 通用一条：**凡是"每轮会变"的数字，就不许手写**。
38. **任何读仓库文件的探针都不能在校准器运行时跑**（E24 实踩）：`--check-only` 恰好在校准器的
    **变异窗口内**被调用 ⇒ 读到的是被临时改坏的文件 ⇒ 报出"锚点过期 + 突变文本已存在"的**假警报**
    （那两条锚点其实好好的）⇒ 差点把好锚点改坏。⇒ **校准器与其它读仓库的工具不能并行**。
39. **CI 只跑校准的"锚点核对"、不跑完整校准**（E24 定）：完整校准要跑测试，其中个别判据
    **随平台换颜色**（索引路径锁 Windows 反斜杠 / Linux 正斜杠）⇒ 在 CI 上跑会**误红**
    （v0.40 那轮"CI 连续 22 次红"就是这类平台差异）⇒ 锚点核对平台无关且秒级 ⇒ 放 CI；完整校准留给本地。
40. **性能测量抗噪要取最小值、不要取均值**（E23 实测）：单次读数极差 20.6%、两轮均值极差 11.6%、
    repeat 3 取最快一次极差 10.3% ⇒ **均值对离群值最不稳健**。理由：性能噪声**只会让读数变大**
    ⇒ 最小值抗噪、不会误红；真回退会让每次都慢 ⇒ 最小值照样超预算 ⇒ 回退仍拦得住。
41. **"缺少 X"这类否定判断写不成正向 pattern**（E25 实踩）：
    `JZ-UPLOAD-001` 的含义是"上传**缺**类型/大小/文件名限制"；我第一版把 sink 收窄成
    "出现了 `$_FILES[…]['type']` 检查" ⇒ **语义正好反过来**（那是**有**类型检查＝合规写法）
    ⇒ 实测在 DVWA 的**修复档** `upload/source/impossible.php` 里报出**新误报**，自扫也多 2 条
    ⇒ **逐条 A/B 当场逮到**。⇒ 否定型规则要么另配"邻近行没有 X"的专门机制，要么整条不做。
42. **规则默认在"掩码桶"上跑 ⇒ 看不见字符串内容**（E25 实测）：
    `ignore_strings: true` 的规则在**字符串字面量被剥掉**的行上匹配 ⇒
    **任何需要看字符串内部的 pattern（`/e` 修饰符、heredoc 里的代码）都匹配不到**
    ⇒ 我第一版想保留"带 `/e` 的 preg_replace"，**正面用例死活不报**才查出来。
    ⇒ **"pattern 写对了"≠"它能匹配上"**；判据必须先证明它在**当前桶**里能匹配上。

43. **负向先行会被 `\s*` 的回溯绕过去**（E26 实踩）：想把"赋纯字符串常量"排除掉，
    写成 `(?!['\"]['']\s*;)` ⇒ `\s*` 可以吃 0 个空格，于是负向先行看到的是 ` '';` ⇒ **通过** ⇒
    收窄**完全没生效**（我第一版就是这样，判据的正面用例死活不报才查出来）。
    ⇒ 正则里的**空白要算进负向先行本身**（`(?!\s*['\"]['']\s*;)`），别指望前面的 `\s*` 吃掉。
44. **停牌项要能"定案"，不能一直挂着**（E26 决定）：**触发率 A 路线 ⇒ 不做**——
45. **校准器分不清"判据红"和"测试根本不存在"**（E29 实踩）：`unittest` 对**找不到的测试 id**也返回非零 ⇒ 校准器把**恒红**当成"判据红"（**假红灯**）⇒ 那条校准**什么都没证明**却照样计入"全部 RED"。⚠️ **E29 那条自己的校准例就中招了**：它指向的测试被我放进了**别的类** ⇒ 跑出来是 `AttributeError`，不是判据红 ⇒ 43 条"全红"里有 1 条是**空转**。
    根因：校准器只问"跑出来是不是非零"，没问"**这条判据在未变异的代码上是不是本来就绿**"。
    修法：**两道前置检查** —— 运行时「**基线必须绿**」（判据在未变异代码上就得是绿的）与静态「**test id 必须存在**」（可进 CI 的 `--check-only`）；两种失败单列 **INVALID**，**不许**混进"全部 RED"。
    留下：`scripts/mut_calibrate.py` 的 `run_judgement()` / `baseline_ok()` / `check_test_ids()`；判据 `TestMutCalibratorShipped` +2 条；变异校准 +2 条。**教训："红"也可能是假红 —— 必须先证明这条判据**本来是绿的**。**
46. **`validate` 第 21 项一把都没验过，且藏着一个潜伏 bug**（E29 实踩）：E28 把它加进 `validate` 就算数了，既无单元测试也无变异校准例；而且「flask 等」的条数**错用了「静态可修」的条数**（变量名复用）—— ⚠️ E28 时两个数**恰好都是 1** ⇒ 错了一个月没露馅；E29 把「静态可修」清零后**当场炸**。
    修法：改读 flask 行；**新增从 §二 逐行「归类」反推三类条数**再与 §三 对账 ⇒ 手改 §二 某一行却没改 §三，当场红；判据 `TestVerdictTable` 5 条；变异校准 +2 条。
    留下：**新增的检查项必须配"正例 + 反例 + 变异校准"三件套**，否则它可能一直红不了（也可能一直乱红）。
47. **锚点会匹配到自己**（E29 实踩）：给 `mut_calibrate.py` **本身**写校准例时，单行锚点（如 `return False, "测试 id 不存在"`）在这条 CASES 的**字面量里**也出现 ⇒ 命中 2 次 ⇒ 校准器按"锚点命中 0 次"静默 SKIP。
    修法：锚点写成**跨行组合**（源码里那种"缩进 + 换行"）⇒ 字面量里是单行 ⇒ 不自匹配。
    留下：`--check-only` 现在同时报 `STALE-ANCHOR` 与 `DUPLICATE-MUTATION`。**教训：给"自己写的东西"写判据时，先想一遍它会不会匹配到自己。**
48. **校准例配错了判据，也会跑成 GREEN**（E29 实踩）：E29 那条 `xss-document-write-constant-back`的变异是"给负向先行加个尾字符"⇒ 那一支**整个不再匹配**（负向先行是**零宽断言**，尾字符落在它**后面** ⇒ 后面还必须真有个 `x` 才算命中）⇒ **纯常量照样不报** ⇒ 我配的判据（"纯常量不报"）**仍然绿** ⇒ 校准器报「锁无效」。
    根因：**没算清"这个变异到底改变了什么行为"**——我以为它会让纯常量重新被报出来，实际它是让这一支彻底失灵 ⇒ 该由**"带变量仍要报"**来兜。
    修法：该例改指向 `test_document_write_with_variable_is_still_reported`，当场 RED；⇒ **每条校准例都要自己红过一次**，且**全量校准必须每轮都跑**（只跑新增的那几条，旧的错了你不会知道）。
    **教训："全部 RED"这句话，得是**每一条**各自红过才成立 —— 混在一起报个数，就看不出哪条其实没打中。**
    它测的是"别的 skill 会不会抢上下文"，那不是本技能能控制的变量；历史上 7/24 的失败主因
    就是**加载竞争**，而"竞争"正是 A 路线的定义 ⇒ 做了只会把"测不到"变成"测到还是不行"，
    **不改能力**；代价还要动 C 盘、装第三方 skill ⇒ 从"待办"改判为**决策（不做）**。
    ⇒ **发行渠道 ⇒ 已做**（E33）：**65 个 GitHub Release 全部发布**；发行说明由 `scripts/release_notes.py` 从 `CHANGELOG.md` 生成 ⇒ 单一真源、不会漂移。

49. **净化点不能一刀切**：转义（`mysqli_real_escape_string`）只在**引号内**有效；插在**引号外**（数值上下文）时它救不了任何东西（E30 实测：DVWA 两处形态完全一样，判定必须不同 ⇒ 一刀切 = **拿真阳性换误报**）。
    根因：引擎的净化点判定是**上下文无关**的 —— 只问"这段代码里有没有净化点"，不问"这个值最后落进 SQL 的哪个位置"。
    修法：① 引擎加 `sql_quote_context()`，按"输出串"重建引号状态（字面量**定界符不进输出**、**内容里**的引号进输出）⇒ 值落在引号内还是引号外；② 规则侧给净化点加 `context: "sql_quoted"`，这类净化点**不在净化点那一行断链**，而是在"值被拼进字符串"那一刻按上下文判；③ 守卫扫描**不再**把条件净化点当守卫（否则引号外的真阳性会被一并吃掉）。
    留下：判据 `TestAuditSqlQuoteContext` **5 条**（含反例：引号外**仍须报**）；变异校准 **+3 条**；能力边界表第 2 行**重写**（这条边界被**做掉一半**）。
    ⚠️ **顺带修掉一条机制事实**：旧净化点 pattern `\breal_escape_string\b` **匹配不到** `mysqli_real_escape_string`（`_` 是单词字符 ⇒ 无词边界）⇒ **那个净化点从来没生效过** ⇒ E22 把它记成了能力边界。**教训："pattern 写对了"≠"它能匹配上"** —— 要有一条判据直接断言"这个 pattern 命中得了那行真实代码"。
50. **锚点会"命中对的行、但命中的是别的东西"**（E30 实踩）：E30 改了净化点后，E22 那条校准例的旧锚点（`\breal_escape_string\b`）本该**当场报过期**，却因为新写的 note 里**引述了那段旧文本** ⇒ 锚点**照样命中 1 次** ⇒ 校准**静默失效**（变异改到了 note 上，行为没变 ⇒ 那条校准会报 GREEN）。
    修法：把该例的锚点重指到**活的 pattern**，变异改成"把 `mysqli` 那个分支删掉"（让 `mysqli_real_escape_string` 重新匹配不上），并改指到直接断言"这个 pattern 命中得了"的判据。
    **教训：锚点核对只能查"命中几次"，查不了"命中的是不是要找的那一处"** ⇒ 凡是**自己写的新文本里引述了旧文本**的地方，都要重新看一眼锚点。
51. **往 CRLF 文件里写新内容 ⇒ 会引入"混合行尾"**（E30 实踩）：本轮用编辑工具往 `scripts/mut_calibrate.py`（CRLF）里加校准例 ⇒ 新插入的行是 LF、其余仍是 CRLF ⇒ **一个文件里两种行尾**。而校准器的"还原往返"（CRLF→LF→改回→LF→CRLF）对**混合行尾****是有损的** ⇒ 还原后 sha1 与突变前不一致 ⇒ 校准**当场停下**（它没有硬撑着跑完 —— 这点是对的）。    ⚠️ **症状很有迷惑性**：单独复现那条用例是**通过**的（sha 一致）⇒ **只在全量跑时**才炸；而原版的还原检查只报一句"不一致"，**不说是哪一条不满足** ⇒ 根本无从下手。    修法：还原检查改成**逐条报出**（sha 不符 / 还原后仍含突变文本 / 变异态里突变文本出现次数不对）⇒ 一眼能看出是哪一条；本轮据此定位到"还原后仍含突变文本"这一侧。    **教训：① "只在全量跑时出现"的失败，单跑复现不了 ⇒ 全量校准必须每轮都跑**（只跑新增的那几条，永远不会撞上）；② **行尾是有损往返的隐形前提** ⇒ 改 CRLF 文件后要先确认行尾没被搅乱（`git diff` 看不出行尾变化，得直接数字节）。

52. **逐行分析看不见"跨行字符串"**（E31 实踩）：`$log_query = "SELECT l.id, …`（多行 SQL 串的**第一行**）没有闭合引号 ⇒ 逐行分析时**整行被当代码** ⇒ 里面的**列别名**（`l.id`）被当成"读了变量 `$id`" ⇒ 污点顺着它流进了**根本不含该值**的查询（DVWA `bac/index.php:58`）⇒ **误报**；而真正该算读取的**插值**（`{$target_id}`，在**第二行**）反倒被漏掉 ⇒ **真阳性也丢了**（一类**既有漏报**）。
    修法：**把跨行字面量折叠到首行**（整段字符串是**一个**字面量 ⇒ 列别名不是读取、插值是读取）⇒ 误报与漏报**一起**解决。
    ⚠️ **两个必须踩过才知道的坑**：① **检测与折叠必须用同一份文本**（我第一版用「剥注释后的文本」检测、却用「原文」折叠 ⇒ 两者结构不一致 ⇒ 把 `// "Secure" check that's easily bypassed` 这种**注释行**误判成未闭合串 ⇒ **整个文件后半段被吞进一行** ⇒ 真阳性全丢）；② **字面量部分必须用原文**（未闭合串里的 `//`（"http://…"）会被当成注释切掉 ⇒ 插值丢失 ⇒ 漏报）⇒ 正确做法是**代码部分用剥注释后的、字面量部分用原文**（两者列位置一一对应）。
    留下：判据 `TestAuditMultilineString` **4 条**（含 2 条防误伤）；变异校准 **+3 条**。
53. **新增代码会让既有锚点变得不唯一**（E31 实踩）：E31 在 `audit_graph.py` 里也写了 `if not s.get("context")` ⇒ E30 那条校准例的**单行锚点**（同一串文本）**命中从 1 次变成 2 次** ⇒ `--check-only` 报 `STALE-ANCHOR`（命中 2 次）⇒ 校准会**静默失效**（按"命中 0 次"跳过）。
    修法：给既有锚点**补上上下文**（改成跨行组合）⇒ 又变回唯一。⇒ **教训：新增代码里的相同文本会破坏既有锚点的唯一性 ⇒ 改完引擎要重跑 `--check-only`**（它就是为这件事存在的）。

54. **脚本改了内存却没落盘 ⇒ 整轮编辑静默丢失**（E32 实踩）：我写了个批量改文档的脚本，函数 `insert_before` 改了内存里的行列表、日志也打了 `OK`，**但从头到尾没调用落盘的那一步** ⇒ 文件根本没变 ⇒ 而我**看着那行 `OK` 就当它成功了**。
    ⚠️ **是 `validate` 的新判据当场逮到的**（它读文件、发现口径表不在 ⇒ 报错）⇒ **凡是有机器判据守着的东西，判据报错要当成"我的编辑没生效"来查**，而不是当成"判据坏了"。
    修法：批量改文档的脚本**最后必须落盘 + 回读确认**（本轮补了 `save()` 与一行回读自检⇒ 打印"§四 at 5173；口径行 3 条"才敢往下走）。
    **教训：日志里的 `OK` 只代表"匹配到了"，不代表"写进去了"** ⇒ 落盘后**必须回读**。

55. **抄写源码里的"像密钥"那一行 ⇒ 自己的文档会触发密钥扫描**（E32 实踩）：E32 在判定表 §四 里写了 DVWA 那个占位口令的**原文**（长得像 `赋值型密钥`）⇒ `preflight` 当场报 **2 条 high** ⇒ 自净检查失败 ⇒ **而判定表 §二 #3 早就写明"本文档不复制它，免得被密钥扫描当泄露"** ⇒ **我违反了自己定的规矩**。
    修法：改成**描述**（"口令字段被赋成一个带四个星号的字符串"）⇒ 扫描干净 ⇒ 文档仍然说清事实。⇒ 教训：**文档里引用源码有"安全形状"**（密钥/口令/令牌）时，只能描述不能复制；而这条规矩**已经写在表里**了 ⇒ 抄之前先看一眼自己写过的约定。

56. **校准器把「测试 id 不存在」也当成「判据红」⇒ 假红灯**（E29 实踩）：校准器 `run_judgement` 只看退出码 ⇒ 而 unittest 对**不存在的 test id** 会造一个 `_FailedTest` 顶上 ⇒ 照样非零 ⇒ 「恒红」被当成「判据红」⇒ **那条校准什么都没证明**。修法：把「测试加载失败」（`_FailedTest` / `has no attribute`）单独标出、**不算红**；每条校准先跑「未变异基线必须绿」（`baseline_ok`）——「新判据先证明能红」的另一面是**先证明它本来是绿的**。
57. **判据上线时一把都没验过 ＋ 变量名复用 ⇒ 错数潜伏一个月**（E29 实踩）：`validate` 第 21 项（判定表自洽）E28 加进 validate 就算数了——**无单元测试、无变异校准例**；而且「flask 等」的条数**错用了「静态可修」的条数**（变量名复用），E28 时两个数**恰好都是 1** ⇒ 错了一个月没露馅，E29 把「静态可修」清零后**当场炸**。修法：改读 flask 行；新增从 §二 逐行「归类」**反推**三类条数再与 §三 对账。教训：**两个数恰好相等 ≠ 抄对了**；新判据上线的同一轮就要配上测试与校准。
58. **变异打在别的兜底上 ⇒ 校准报 GREEN**（E29 实踩）：`xss-document-write-constant-back` 的变异让 `document.write` 这一支**整个失灵** ⇒ "纯常量不报"这个判据**仍然绿**（它守的东西没被碰）⇒ 校准报 GREEN（锁无效）。修法：改由「带变量仍要报」那条判据来兜。教训：**变异必须打在那条判据守的承重处上**——打偏了，锁没坏、闸白跑。
59. **行为微测的四条 meta-test 事故**（E35 实踩，合并一条）：① **污染真的会发生**——夹具生成器在子代理可达范围内 ⇒ A 臂运行副本真的读到了它 ⇒ 第一批 4 次整批作废；② **夹具未逐次重置**——B2 留下的 `__pycache__` 让 B3–B5 跑在脏目录里 ⇒ 两臂环境不对称；③ **压力是自己造的**——夹具缺陷静态可见 ⇒ 结论只对本场景成立；④ **基线本来就很强**——通用 agent 契约自带证据纪律 ⇒ 差 0 个百分点是常态，不是测砸了。留下的东西：四条**如实登记**（不悄悄作废）；「判定不许脱离数据」成了第 24 项；**基线未红 ⇒ 不许声称收益**。
60. **一道在逼人说假话的锁**（E36 实踩）：入口行数的真源写成了**文件总行数**（212），而 500 预算约束的是**正文**（201）⇒ 文档写总行数才过、写真话反而被判错。修法：真源改成正文行数。教训：**判据的真源选错，闸门就会逼人造假**——加锁前先问一句「它逼出来的是真话还是假话」。
61. **「名字与数量对上了」≠「指向对」**（E37 实踩）：「68 tag / 68 Release 一一对应、零缺口」当时**是真的**——但它只数了**名字与数量**；远端 `v0.51.0` 实际指向 **v0.66.0 的补记笔**。根因：`--publish` ① 不带 `target_commitish`（GitHub 默认用 main）② 不检查远端该 tag 是否已存在 ⇒ 补发时 GitHub 在 main HEAD 上**自动造**同名 tag。修法：发布**先核远端 tag**（缺或不对 ⇒ 拒绝发布）、显式带 `target_commitish`、发完**回头自证**（第 26 项 ＋ `release_identity.py`）。教训：**核对要核对象，不是数数**。
62. **用不成立的规则当判据 ⇒ 会把正确历史判错的锁**（E37 实踩）：owner 规则若写成「tag 指向『第一个含该版本号』的 commit」⇒ 实测本地 68 个 tag 里有 **3 个反例**（4.4% 不成立）⇒ 拿它当判据就是把正确历史判红。修法：改成「commit subject 中**第一个版本号**必须恰好是 X.Y.Z」。教训：**判据的规则要先在全集上实测反例再上线**——规则的正确性本身要被量过。
63. **「看起来是表」≠ 是表**（E38 实踩）：GFM 的表要有「表头 ＋ 分隔行」，**空行之后的每行都不是表** ⇒ 进化账本用空行隔行 ⇒ **整张台账在 GitHub 上根本没渲染成表格**（是一堆以 `\|` 开头的段落）。修法：合并成一张连续表。顺带：第 12 项的「上表 N 条」对账在**碎块状态下形同虚设**（它此前只在"恰好一张表"时判）⇒ **结构坏掉时判据会静默失效**——判据依赖的结构前提自己也要被守。
64. **朴素计数会把转义竖线当分隔符 ＋ 两套解析打架**（E38 实踩）：`\|` 是**转义**、不算列分隔符 ⇒ `ls scripts/*.py \| wc -l` 这种合法写法被误判成多一列；且第一版**判据按 GFM 数、草稿脚本按朴素数** ⇒ 假阳性 3 处 ＋ 两者定位错位。修法：判据按 GFM 规则数；草稿脚本**与判据同源并自证**（格数不一致就报错退出）。教训：**同一个规则写两遍就会打架 ⇒ 要么同源，要么自证**。
65. **退出码只有 0/1 ⇒ 「没核成」被当成通过**（E39 实踩）：远端核验要碰网络 ⇒ 限流/网络抖动时**根本没核成** ⇒ 而非零即红的二态退出码会把「没核成」静默当绿。修法：**三态退出码**（0 一致 ／ 1 不一致＝真问题必红 ／ **2 没核成** ⇒ CI 单独分支 ＋ step summary ＋ `::notice::` 留痕，绝不假绿）。这条规矩后来被 `release_identity` / `plan_check` 沿用。教训：**核不了的核验必须大声说出来**。
66. **想「全自动核历史」⇒ 反推不可靠**（E39 改判）：想从台账文本**反推**每行对应的 commit 来核「行数收支」⇒ 实测 64 行里 **58 行无法用版本号定位**、且有错配 ⇒ ⇒ 改判为「**提供工具、不做自动核验**」：由填表人显式指定 commit，机器只核能定位的行。教训：**宁可少核，不要错核**——错核的锁比没核更坏。
67. **「只查最后一个」的判据 ⇒ 其余的没人守**（E40 实踩）：current-state 标记区**只查一个** ⇒ 14 个区块里 12 个无人守 ⇒ E39 把 v0.72.0 的区块改写成 v0.73.0 的数时，对账跟着腐化一起漂 ⇒ **绿灯**。修法：**每个区块对账它自己那一版**的快照（区块与版本的对应**从文件里推出来**，不靠人标注）。
68. **同一轮多行合法 ⇒ 查重不能按轮次查**（E40 实踩）：进化账本里一轮可能有多个变异行 ⇒ 按「轮号重复」查重会误伤；只能查「**同一张表里出现两行完全相同**」⇒ 精确、不误伤。顺带：台账**行序回退** 3 处（插行插错位置，没有任何东西会报）⇒ 加「轮次号不得回退」（**稳定排序** ＋ 脚本自证内容集合与行数不变）；验收记录**小节倒序**同理。
69. **真值在仓里存在 ≠ 门面上写的是真的**（E41 实踩）：真仓库名在 §8 的列表里**早就写着**，而两个 README 门面的安装命令还是**占位符** `npx skills add <you>/jiangzuo` ⇒ 照抄的人**必然失败**。修法：改成真名 ＋ 第 7 项加锁（命令必须指向真实仓库）。教训：**检查「真名存在」要检查到它被引用的那一面**——库里有真值，门面上照样可以是死的。
70. **`git push` 报成功 ≠ 推成了**（E41 实踩）：`git push` 退出码 0 ＋ 输出 "Everything up-to-date"，而**远端根本没有那个 tag**。修法：推完 `git ls-remote` **回读**（§5.4 现行规则；main 与 tag 都要回读，tag 还要核**对象**不是 commit）。同类（E41）：CI 的日期判据拿**跑闸机器的本地日期**当"今天"（CI 是 UTC、提交作者是 +0800）⇒ CI 假红 ⇒ 基准改成 **max(机器日期, 提交自己的作者日期)**。
71. **三种「第二真源」**（E42–E44 实踩，合并一条）：① **身份**——owner/name 抄在四个脚本里 ⇒ 仓库改名就悄悄漂 ⇒ 收进 `repo_identity.py` 唯一真源，**真源缺失必须报错**、不许静默跳过；② **发行说明**——仓里躺着一份**手写副本**（从未发布过、已经漂了）⇒ 换成生成版 ＋ 「每份必须与生成器产出的**逐字一致**」（判据**复用生成器本身**）；③ **兜底**——v0.15–v0.19 五版的发行说明取自 tag 的提交说明（第二个来源）⇒ 补录 CHANGELOG 条目，且第 26 项**这一类差集不再允许登记例外**。
72. **同一轮写两遍的五种漂法**（E45 实踩，合并一条）：两份手抄台账实测 ① 主题**错位一格** ② **完成标记 20 轮全缺** ③ 那段**没有表头 ⇒ GFM 里根本不是表** ④ **漏轮**（E42–E44 没有行）⑤ **校准例数被 CHANGELOG 订正过、台账没跟着改**（4 处）⇒ 合并成**一张**轮次台账 ＋ 第 25 项六条对账（轮号唯一／轮号↔版本／不许漏轮／行序不回退／每行带 ✅／校准数与 CHANGELOG 对账）。教训：**台账只许有一处**——第二份不是冗余，是必然漂移的源头。
73. **会变的数混进结构数 ＋ 写死每笔都变的值**（E46/E47 实踩，合并一条）：① 规模行手抄 8 个数 ⇒ 实测过期 5 个，而其中只有 **4 个**是结构规模 ⇒ 只由实物**生成**结构数、其余改「现查命令」或指针；② 「当前状态」行**写死了远端 main 的 sha** ⇒ 它每笔都变 ⇒ 实测已过期 8 个版本却顶着「当前」二字 ⇒ 那一行改成**只说「怎么核」**。教训：**每笔都变的值任何判据都守不住 ⇒ 守不住的数别写**——写了就有人信。
74. **外向变更没有仓内判据 ⇒ 唯一保证是回读核对**（E48 实踩）：改仓库设置（分支保护）是第一次做「改仓库设置」这类外向变更 ⇒ **没有任何仓内判据能守**；PUT 返回 200 **≠ 配成了**。修法：按预先写好的形状 PUT ⇒ **再 GET 一次逐项核对**；形状刻意不照抄 GitHub 默认（默认会带 `required_status_checks` ⇒ 直接挡住本项目自己的推送流程）。留下的东西：`main` 分支保护（禁强推／删分支／管理员同禁，不要求 PR／CI／推送人）＋「退出码 0 ≠ 配成」进 §24.6。
75. **E49 的四件套**（E49 实踩，合并一条）：① **「改写过的重复」逐字查重抓不到**（实测逐字重复的 ≥80 字符长行只有 1 组且合法）⇒ 抓手只能是**结构**：速览留指针、详情留一处、提到事故关键词的行必须带指针；② **新判据写在它依赖数据的定义块外** ⇒ 夹具一跑就 `UnboundLocalError` ⇒ **5 个既有测试变红**而自己的 4 条全绿（单跑自己那几条看不见）⇒ **每次都要跑全量**；③ **PowerShell 文本管道按 GBK 重编码**会把中文整篇写坏（一个「：」变成 U+FFFD）⇒ 编辑要**按字符定位替换**；④ **计划外的脏文件潜伏**（`git add 点名文件` 不进提交 ＋ `ship_check` 自净只数个数）⇒ ⇒ **E51 收口**（`plan_check.py`）。
76. **「极致详细」很容易滑成「再抄一遍」**（E50 实踩）：草稿与既有章节逐节对账 ⇒ 实测**八处重复**（闸门命令三份、CI 步骤两份、坑位两份、常驻门槛两份、停牌项两份、§24 与 §5.4 八处、期望值两份、边界表内部互抄）⇒ ⇒ 抓手：**新章节只许「导览 ＋ 增量」，既有章节是权威 ⇒ 一律指向、不复述**；**每笔都变的数一律不写死**。
77. **全量校准要放在记账之后**（E51 实踩）：CASES 已成 95 而 CHANGELOG 最新条目还写着 91 ⇒ 有四条要**核对仓库现状**的旧判据处于报错态 ⇒ 完整校准报出 4 条 **INVALID（假红灯）**——它们不是判据坏了，是**顺序不对**。教训：**先让真源与文档一致，再让校准证明判据能红**；中途的 INVALID 要会读：它指的不是被变异的那条。
78. **第 14 项三类管不到的期望值会漏网**（E51 实踩）：§13 第三方复验的 DVWA 期望停在「69 发现 / 结论 68」——那是 **E7 时代的 A/B 数字**（现行 58/58）⇒ 第 14 项的三类（用例数／语料分母／规则条数）**管不到 DVWA 发现数** ⇒ 漏网至今。本轮订正为 58/58；**要不要把三仓数字接进真源**（根治这一类）留作独立轮次评估。

79. **判据的完整性触发面过宽 ⇒ 会把通用示例当电池**（E53 实踩）：给第 14 项扩第四类（三仓/自扫实测 ← measured 真源）时，完整性要求的第一版写成「文件里有 `audit_scan.py` 命令 ⇒ 必须声明三仓期望」⇒ **validate 当场红出 9 条误伤**：README 的**目录树行**（`│   ├── audit_scan.py      # 审计链⑤…`）、交付报告的 `<第三方仓库>` 占位行、分册的通用示例全被当成"该写期望数的电池"⇒ 那些地方**没有可写的期望数**，逼着写就是**编值**（E38 的"不编值"规矩）。修法：完整性按**配对**判——声明了三仓与自扫两形态之一，就必须两个都写全（少一半 = 另一半静默失效）；不按"有扫描命令"拉新文件。教训：**完整性判据的触发面要与"那里真的有可对账的数"对齐**——"命令存在"≠"期望该存在"；上线前先跑一遍真仓库，误伤清单本身就是设计反馈。

80. **变异锚点选「去掉守卫留 else」⇒ 判据崩溃，校准器把崩溃误标成「测试 id 不存在」**（E54 实踩）：给第 24 项扩实证判据后配校准，第一锚点把 `if not mea or not meb:` 变成 `if False:` ⇒ 守卫没了但 **else 分支还在** ⇒ 变异态下 `mea.group()` 踩空 ⇒ AttributeError ⇒ 判据 rc=1，**输出里带 "has no attribute"** ⇒ 而校准器的缺测启发式（E29 为「测试 id 不存在」设计的）认这个字符串 ⇒ 该例被判 INVALID「假红灯」——**但它其实不是假红灯，是变异设计错了**。修法：锚点改「跳过整块」（`if False and <原条件>:` ⇒ 整个证据块不执行 ⇒ 判据安静地绿回去 ⇒ 测试真红）。留下的东西：①选锚点的规矩——**变异必须让判据「安静地变绿」，不能让判据崩溃**；②启发式的偏向是安全的（崩溃一律不计入「全部 RED」⇒ 宁可 INVALID 不可假绿），但**我的手工"能红"预检比校准器宽松**（rc=1 就算红）⇒ **校准器才是权威**；③启发式本身对「崩溃」与「缺测」不分 ⇒ 待修（登记进 §11）。

81. **测试断言里写死「每笔都变的数」⇒ 下一批数据一来当场红**（E57 实踩）：E55 给英文分册契约写的真仓库测试断言「英文分册骨架契约全部满足（**4 本**…）」——把当时的本数写死进了测试 ⇒ E57 第二批入库变 8 本 ⇒ 测试当场红。修法：断言改为**从对照账真源现查**（数 ✅ 已译的**表格行**）与信息行的本数对账——测试的期望值和文档一样要接真源（§19.1 第一类在测试里的变体）。⚠️ 顺带一个数法小坑：第一次现查用全文 `count("✅ 已译")` 数出 9——把对照账**引言里的**同一字样也数进去了 ⇒ 只数**表格行**。教训：**"每笔都变的数不写死"对测试断言同样成立**，而测试里的期望值要么现查真源、要么自造夹具自证。

## 9. 环境与操作要点

- **平台**：Windows 10（10.0.22631）+ Git Bash；Python **3.8.3**（脚本最低要求 3.8，纯标准库）；CI 是 Ubuntu + 3.11。
- **路径含中文**（`D:\Github项目\jiangzuo`）：Git Bash 下没问题，但**引用一律加引号**。
- **行尾**：仓库 blob 全 LF；`core.autocrlf=true` 会让 `git checkout`/`git archive` 产出 CRLF，
  提交时会看到 `warning: LF will be replaced by CRLF` ——**无害，但按字节核对差异时要用 `git ls-files --eol`**。
- **编码**：脚本一律 `io.open(..., encoding="utf-8")`；写文本时**显式 `newline="\n"`**，否则会整批转 CRLF。
  控制台显示中文乱码是代码页问题，不代表文件坏了（用 Read 工具看）。
- **临时产物**：只进 `D:\Github项目\jiangzuo\eval-runs\`；用完删除、核对残留并回报。
- **仓库内不许出现的**：绝对路径（实测当前零命中）、令牌、被扫项目的产物、`__pycache__`（已 gitignore）。
- **git 身份**：仓库级 `user.name=jiangzuo` / `email=jiangzuo@example.com`；**不要改全局配置**。
- **网络**：访问 GitHub 偶发 `Failed to connect / Connection was reset`，波动中还会假报一次 `Authentication failed`。
  **每轮最多试 2–3 次，绝不写 sleep 轮询**；恢复后补齐 push（main + tag）。
- **软重置陷阱**：`git reset --soft` 之后**必须先 `git reset`（清索引）**再继续，否则下一条提交会把整批改动一次吞掉。

---

## 10. 协作规矩（原长期记忆蒸馏——新会话没有记忆，全靠这一节）

**A. 证据完整性（最重要）。** 数字、哈希、时间戳、版本归属、小节引用**只从真实命令输出抄**。
新写的判据先问"它能不能红"，并做一次红/绿配对。**假锁形态清单**（本项目踩出来的，逐条都对应过一次真事故）：

1. 锁读原文被自己的注释/文案喂饱（否定式锁会被自己的注释打红）；
2. 时限锁根本没走到那段代码；
3. 天生红的锁教人无视红灯；
4. 检查器做了归一化 ≠ 真实写法；needle 少一层 ⇒ 门禁自己假绿；
5. 变异窗口没包住被测运行 ⇒ 集体伪报"锁无效"；
6. 预演断言吃既有状态（点之前就已经是那个值 ⇒ 空处理器也绿）；
7. 同族的行尾陷阱：不带 `newline=''` 会整批转 CRLF，而 `git diff --numstat` 看不见；
8. "本地跑得快"不是复杂度证据（环境噪声可达 3 倍）；
9. 写进禁忌表的规矩若没变成机器判据，照样复发；
10. 判据要防自指（自己验自己、用被测物产出当基准）；
11. 判据不许假定数据形状/开关形态（把理想项目当默认值，会把自己锁死）；
12. 注入/变异工具的**失败路径也要自带还原证明**（`process.exit` 不跑 `finally`）；
13. 判据要架在"那个状态唯一由它决定的那件事"上（恒真字段 / 恒真属性 = 假锁）；
14. **后台任务通知里的退出码是包装器的**，真值只从日志里自己写的 `*_EXIT=` 行读；
15. 闸门查错对象三形态：告警穿透（stderr 有警告而退出码 0）、**交付物没入库**（.gitignore 挡住报告而闸门只查磁盘）、
    日期只拦单边；
16. needle 被同一行的运行期文案自引用喂饱（剥注释也救不了 ⇒ 认调用形状不认名字）；
17. 清理脚本按"0 字节 = 垃圾"把自己刚写的日志扫进回收站；取证拼在 detail 尾部被长度上限截掉 = 等于没写；
    重试每次先清上一回残骸 ⇒ 第二次尝试根本没走到被测那一步；
18. **一个样本写成规律、相关写成因果**（改口要 grep 扫全部引用处）；
19. **判据跟着解释器或平台换颜色**（见第 8 节第 4 条）；
20. **作业级一个勾掩盖步骤级 skipped**（见第 8 节第 3 条）。
21. **校准/注入工具的"还原"是全局替换**：突变文本在被测文件别处已存在时，还原会把别处一起改坏
    （E7 把 `audit_scan.py` 的新函数改成了自我递归）。**断言：突变前新文本在原文件出现 0 次、还原后 0 次。**
22. **恒绿的校准用例比没有用例更坏**：被测实现有多道独立兜底时，废掉其中一道测试照样绿——
    那不是"锁有效"，是**这条校准用例自己失效了**（E7 的一条用例恒绿了不知多久）。
    **校准必须多站点同时废**，且要定期重跑校准本身，别让它静默烂掉。
23. **标尺本身会被污染**：拿"干净仓库误报"当基线时，基线自己可能被工具改动带歪
    （E7：语境档改动让语料生成器的命中进了结论区，基线从 0 变 3）。
    **量一个东西之前，先确认那把尺子本身没坏**——错误的基线不会让任何结论看起来更好。
24. **新判据的第一版常会误伤既有夹具**：把"某种形态必须存在"按**仓库**判，会把合法的
    最小目录判死（E8 被既有测试当场逮住）。**判据只对"它自己声明过的东西"负责**，
    形状假定越宽，误伤越多。新判据上线时，**既有测试就是它的第一个用户**。

**B. 其它工作规矩**

- **先否证再修**：模糊报错先取证、用脚本验证或推翻自己的假设；缺信息就提问，不接受猜测式修复。
- **验证标准**：退出码不经管道取（`$?`/`PIPESTATUS`，别用 `cmd | tail`）；变异校验要**非对称**；
  mock 数值不冒充已验证；始终维护"前向多步任务清单"。
- **批量推进的方式**：先排十轮台账再连做；每轮独立提交 + 推送；规划里带停牌点；核出多条成立项就插轮、重排编号。
- **独立闭环，不外推决策**：汇报是**告知**不是请示；除"停牌项"（第 11 节末）之外自己判、自己做、自己记账。
- **只读审计模式**：用户说"只查询、不留痕、不改动"时——不动仓库、不建任务、临时日志用完即删并回报残留，给判断不给请示。
- **防幻觉与防目标偏移**：对外声称逐条回源；偏离权威文档要显式说明；**更正一处虚构后，grep 同一符号名扫全部引用处**
  （半条错话最难发现）。
- **产出不出盘**：内容留在项目目录内、不占 C 盘；工具缓存/临时目录重定向进项目内。
- **GUI 验证一律离屏无打扰**：offscreen + capturePage 取证；禁按键注入，改用进程内验证缝；跑脚本前先 `node --check`。
- **措辞规矩**：GitHub 上的项目**不要写"独立完成"**（这是 vibe coding，毕设除外）；未收尾的事**不说"已完成"**，
  说清"验证到哪一步、什么还没验证"。
- **令牌与账号边界**：本项目只用「将作skill」这一枚仓库级令牌；**workbuddy 项目与其令牌绝不触碰、绝不使用**。
  令牌曾在聊天里明文出现过 ⇒ **轮换建议长期有效**（属用户决定，不阻塞开发）。

---

## 11. 下一步做什么（按顺序，每条给前置与判据）

**先跑第 13 节自检**，确认副本完好，再按下面推进。每轮都走第 5.4 节的发版流程。

1. ~~**`evals/task-evals.md` 的 5 项任务评测**（唯一完全没跑的评测项）~~ —— **这条已经作废**：
   任务评测 **2026-10-07 就跑完了**（双臂 10 份运行副本，逐份磁盘取证），结论回填在 `evals/task-evals.md`
   的记录表与总判定里，取证在 `eval-runs/results/task-evals-run-20261007.md`。旧版本文档把它记成"完全没跑"，
   是从 C 盘项目记忆抄错的那一条。**不需要重跑**。真正剩下的是可选的加强：
   换成**真实项目 + 真实用户会话**再复跑一轮（当前臂用合成夹具 `fixtures/t-shop/` + 子代理，
   方法学偏差已在验收记录里自陈：提示词里"验证命令留档"那一行会推高验证行为）。
2. ~~**DVWA 剩余 6 个 MISS 模块**~~ —— **E9 已做一轮（v0.43.0），6 个里 1 个拿下、5 个是能力边界**。
   读靶场真实代码后的逐个判定：

   | MISS 模块 | 判定 |
   |---|---|
   | **authbypass** | ✅ **已做**——真身是 `change_user_details.php:47` 读 `php://input` 后拼进 SQL；补上这一类 source 后覆盖 **13/19 → 14/19** |
   | xss_s | 存储型（写库再回显，**跨请求**）——静态单文件污点流到不了，**写不成** |
   | csrf | 缺失型（表单 `method="GET"`、无 token）；把 GET 表单当"状态变更"会误伤 impossible 档（同一份 index.php 服务所有档位） |
   | bac | 越权＝缺少检查，**静态不可证**；`JZ-HORZ-001` 已停用（夹具 4/4 全误报） |
   | brute / captcha | 缺失型（限流 / 令牌一次性），静态不可证；且 `dvwa_coverage.py` 映射的 `JZ-BRUTE-001` / `JZ-CAPTCHA-001` **在规则库里根本不存在** |

   **E9 顺带量出、还没修的四个缺口**（每个都要单独一轮带证据，不静默留着）：
   1. ~~**引擎"污点穿函数返回值"**~~ —— **E10（v0.44.0）复核后改判**：复核发现它背后是**两层**都坏，
      而且**PHP 的跨函数形参污点整类形态此前完全不可见**：
      - ① `_params()` 把 PHP 形参 `$name` 转成 `_name`，载体名却是 `name` ⇒ 永不相交；
      - ② `add_module_scope()` 写死"顶层行数 ≥ 3 才建作用域"，短文件的顶层整段不进数据流
        （**与它自己的 docstring 自相矛盾**）。
      **两层 E10 都已修**（同文件/跨文件 helper 形态从 0 条变 1 条，三仓数字零回退）。
      **已在 E11（v0.45.0）修掉**："污点不跟函数返回值走"＋"引擎完全不跟踪返回值"**一起修**——
      给每个 (函数, 规则) 算一份「返回摘要」（`dep_pos` 依赖哪些形参下标 ＋ `own` 自带污点，
      按规则隔离、不动点迭代）。实测：四个最小夹具**4 错 3 → 全绿**；A/B 逐条零差异。
      **留下的三个新缺口**（都是本轮量出来的，写进待办不静默留着）：
      ① **引擎不排除注释里的代码**——`_first_code_match` 只排除**字符串字面量**，不排除**注释**；
         注释里写的示例代码（source＋sink 形状）会被当成真流。本轮我自己的注释就触发了 2 条假流
         （被独立验证当场拦下，没漏进结论）。**改注释措辞只是止血，引擎要真修**。
      ② **PHP 成员方法（`->method(`）没被排除**——本轮只排了点号形式（`obj.method(`）。
      ③ **摘要为空时不清掉目标的旧污点**（实测成立）：`$x = $_GET['a']; $x = check_token($x); echo $x;`
         仍报 XSS——`check_token` 返回常量，语义上 `$x` 已被覆盖干净。这是**既有缺陷**（修复前后都报），
         保守没清（清错会压掉真阳性），三仓与语料里都没有这种形态所以 A/B 照不出来。
   2. **`mysqli_real_escape_string` 不被认作净化点**（`\breal_escape_string\b` 匹配不到它），
      而这是 PHP 最主流的 SQL 转义函数、DVWA 用了 20 多处。**但不能一刀切加**——DVWA 的
      `sqli/medium` 是**数值上下文**，转义救不了它，加了会压掉真阳性。要按上下文分（字符串 vs 数值）。
   3. **PHP 的 `exec()` 是命令执行，被 `JZ-CODE-001` 归成了"动态代码执行"**，
      而 `JZ-CMDI-001` 的 PHP sink 缺 `exec` ⇒ 两边一起改，否则同一条会报两次。
   4. `JZ-XSS-002` 之外的其余族（`php://input` → XSS）随第 1 条一起接。
      —— **引擎在 E11（v0.45.0）已就绪**：`check_token` 那个误报根因已除（DVWA `check_token_high/impossible.php`
      那 2 条误报的前提消失），**下一轮就可以接 `JZ-XSS-002` 的 `php://input` source**，
      验收信号是"那 2 条误报不出现 ＋ 新增检出逐条判定为真阳性"。
3. **触发率 A 路线**（无竞争对照复跑 24 条）。⚠️ 需要**临时移走竞争技能**，会动 C 盘的插件目录 ⇒ **停牌项，先问用户**。
4. ~~**官方 SARIF validator 跑一次**~~ —— **E21 已做**：`@microsoft/sarif-multitool` 5.8.0 跑出**真错误**（8 条 JSON1005）⇒ 修掉后**复跑 0 error**；替代验证是把 schema 的「允许属性」白名单硬编码进零依赖自检（CI 装不了官方工具）⇒ **这条不用再做**。
5. **把 20 本分册做英文版**（`README.en.md` 已有，分册没有）。
6. **发行渠道**：~~GitHub Release 页面~~ —— **E33 已做**（65 个 Release 全部发布）。**E41 已做**（2026-10-24）：`npx skills add Zhang-jx00/jiangzuo` **路径验证**（实测装出 **571 个文件**，且**装出来的副本自检 30/0/0 全绿**）＋ **skills.sh 生态收录** —— ⚠️ **复核结论：skills.sh 根本没有提交流程**（无表单、无 publish 命令；装一次即被索引）⇒ 它**从来不是外向写** ⇒ 此前把它记成停牌项是**基于错的模型**。顺带发现并修掉：**两个门面的安装命令都写着占位符** `npx skills add <you>/jiangzuo` ⇒ **照抄的人必然失败**（而 §8 这条列表里**早就写着真名** ⇒ 说明真名在仓里存在 ≠ 门面上有）⇒ 已改成真名 ＋ 第 7 项加一道锁守着。
   ✅ **`main` 分支保护已配好**（E48，2026-10-25）：所有者给令牌加了仓库管理权限后，配上了**禁强推 / 禁删分支**（`allow_force_pushes: false`、`allow_deletions: false`、`enforce_admins: true`）⇒ **E37 那次为修远端指错的 tag 而做的 `forced update` 那种事，从此连管理员也做不了** ⇒ 分支保护是那道**结构性**防线，**已落地**。⚠️ **形状是刻意挑的**（配错了会挡住本项目自己的推送 ⇒ 勿照抄）：`required_pull_request_reviews: null`、`required_status_checks: null`、`restrictions: null`（**不要求 PR、不要求 CI 通过、不限制推送人** ⇒ 现有的"直接推送"流程完全不受影响）＋ `required_linear_history: false`。**回读核对**过：PUT 返回 200 之后又 GET 了一次 ⇒ 逐项与预期一致（**退出码 0 ≠ 配成了** ⇒ 必须自己读回来核对）。⚠️ **仓库 topics 不用管**：实测**早已设好**（`agent-skills` / `ai-agents` / `claude-code` / `claude-skills` / `code-review` / `developer-tools` / `fullstack` / `software-engineering` / `tdd` / `best-practices`）⇒ 可发现性那块**已完成**。
7. **`--strict` 门禁的已知误报处理**：常年红的闸等于没有闸（`bench.py` 默认 3.0 ms/文件从有实测起就没达到过，
   后来把预算定在"当前能过、回退能拦"的位置）。~~同类还有 12 个未判定的"同目录路过"项~~
   —— **E32 已逐条判完**：实测 **16 条**（三份文档曾各写一个数：20 / 12 / "59 条里有 20 条"，互相矛盾）
   ⇒ 判定为**真阳性 15 + 误报 1**（那 1 条与判定表 §二 #3 同一处）⇒
   **「全部产出」口径的误报率第一次能说死 = 4 / 75 ≈ 5.3%**（结论区口径的"静态可修硬误报"仍是 0/59 = 0%）。
   清单可复算：`python evals/audit-fixtures/dvwa_coverage.py --json <扫描.json> --same-dir`。
8. **`audit_scan` 的能力边界文档化**：brute/captcha 这类"缺失型"判据做不做得成、代价多大，写进分册而不是留在脑子里。
9. ~~**给"文档里的期望数字"补判据**~~ —— **v0.42.0 已做（E8）**：`validate_skill.py` 第 14 项
   `check_expected_numbers()`，把 .md **代码块**里三类"照着跑就能看到"的期望值接上唯一真源
   （用例数 / 语料分母 / 规则条数），真源全部静态取 ⇒ 跨平台同色、秒级。
   **第一跑就逮到交付报告 §6 的 `Ran 138 tests`**（E7 加了 2 个用例没同步）。
   剩下的扩展面：**验收记录 `evals/audit-acceptance.md` 里那些表格数字**（自扫结论数、三仓
   findings/结论）—— ~~目前还没判~~ **E34 已做**：把"当前状态"抽成了机器可读的真源
   `evals/current-state.json`，再让校验器对账（**第 23 项**）。
   ⚠️ 做法与 E7 的教训对上：**那把尺子自己也会坏** ⇒ 真源里**能当场推出来**的那部分
   （用例数 / 语料分母 / 规则条数 / 校准例数）**每跑一次就重推一遍**，推不出来就报
   ⇒ 真源自己不会腐烂；**推不出来的那部分**（三仓检出 / 覆盖 / 性能）由 `--refresh` 从扫描产物写入。
   ⚠️ **历史文档不能拿"现在的值"去对账**（否则下一轮数字一变就红 ⇒ 等于逼人篡改历史）
   ⇒ 真源里另存**每版历史快照**（`history.<版本>`），历史条目对账它自己那一版的事实。
10. **分册读取频率审计**（需要 harness 层 hook，属本地不可便携工具）：用来决定分册去留，目前仍是 `WATCH`。
11. **静态 `require_once` 的"模块级变量共享"**：E5 已把它改判为**窄项、需求驱动**——
    遇到真实仓库卡在这一格再做，不做预防性工程。
12. **什么时候可以升 1.0.0**（不是"感觉差不多了"）：第 4 节未达标清单里**能靠工程关闭的项都关闭**
    （当前还剩：SARIF 官方校验、分册英文版、触发率结论、误报率口径收口、文档数字对账判据），
    且触发率有明确结论（做完 A 路线，或用户认可"瓶颈是加载竞争"这一判读）。
    （~~task-evals~~ 已不是缺口：它 2026-10-07 就跑完了，见第 1 条。）
13. ~~**验收记录里"硬误报 1/60"要按现行结论数重述**~~ —— **E20（v0.54.0）已做**：按现行分母重述为 **硬误报 8 / 69 ≈ 11.6%**（DVWA 结论区 68 条**按规则**逐条判过，flask 1 条、requests 0 条），并把 **3 条"需人工细判"单列**（不混进分子也不混进分母）。⚠️ 与旧的"1/60 ≈ 1.7%"**不可比**（旧的分母与判定范围都不同）——**不要**把两个数放一起说"退步"。**7 条硬误报里 4 条是"规则过宽"**（`preg_replace` 当动态代码执行 2 条、`error_reporting(E_ALL)` 当调试泄露 1 条、`$_SERVER['CONTENT_TYPE']` 当文件上传 2 条）⇒ 已排进后续轮次
    `evals/audit-acceptance.md` 的第三方取证一节写"硬误报 1/60 ≈ 1.7%"，那个 **60 是 v0.30 那一节的
    结论数**（DVWA 59 + flask 1）。**当前（v0.44.0）结论总数是 69**（DVWA **68** + flask 1 + requests 0；
    "另计"仍是 17），而 E9/E10 新增的那些 DVWA 结论**还没逐条人工判定** ⇒ 现在能说的只有
    "**截至 v0.30 的判定是 1 条硬误报**"，不是当前分母下的误报率。
    要做的是：把新增那几条 DVWA 结论逐条读一遍（照 flask `Markup` 那条那样标
    "真问题 / 有意设计 / 语境不成立"），再把分母换成现行值重写那一节；
    **不要**把"1/60"和新的分母凑成一个更好看的比率。
14. ~~**给"文档里的乱码字符"补判据**~~ —— **E15（v0.49.0）已做**：
    E10 那轮给 `evals/audit-acceptance.md` 加 v0.44.0 节时，把一处「同」字写成了 **U+FFFD 替换字符**
    （一个 U+FFFD 替换字符 + "文件 helper"），**全仓没有任何判据能发现它**——`validate_skill.py` 查结构、查表格、查期望值，
    唯独不查"文件里有没有被损坏的字符"。E11 全仓扫了一遍（`.md`/`.py`/`.json`/`.yml`）**只有这一处**，
    已当场修好。
    要做的是：给 `validate_skill.py` 加第 18 项 `check_no_replacement_chars()`——
    扫全部入库文本文件里的 `\ufffd`，有就 `err`（并点名文件与行号），
    再配正反判据（"含 U+FFFD 的文件被逮住" / "干净文件不误报"）＋一条变异校准（把这项摘掉 ⇒ 判据红）。
    ⚠️ 这类"**字符级损坏**"的判据很容易被漏掉：它既不影响跑、也不影响结构、也不影响数字。
15. **E11 留下的测试盲区（如实记，别当它有判据）**：返回摘要机制里有**两道**防线
    ——「成员方法调用不算仓库内函数」（`skip_members`）与「摘要分支仍记 `__inline__`」——
    **没有独立判据能抓住它们**：JZ-SSRF-001 的 sink 要求 sink 调用内部内联 source，
    所以对象方法的检出必然走"同行"路径，而同行有**三重**独立兜底
    （成员排除 / `__inline__` / 摘要的 hops 机制），单独废掉任何一道，判据照样绿。
    ⇒ 曾为它加的那条判据**恒绿**，已按"永远绿的锁比没有锁更坏"**删掉**（连同它的校准用例）。
    两道机制本身**保留**（它们是"被调方识别"与"同行内联记账"的语义前提，不是可选的防御），
    由**靶场与三仓的零回退**间接守住。
    **教训**：判据恒绿不是"多一条保险"，是**假锁**——它让人以为那道机制有人管。
    宁可写清"这里没有判据，靠 X 间接守住"，也不要留一条永远绿的。
16. ~~**行尾注释仍会被当成代码**~~ —— **E13（v0.47.0）已修**：
    `echo $x; // os.system("ls " . $x)` 原本报 **2 条**且**直接进结论区**
    （不像整行注释那样被独立验证挡在 `dropped` 层）。
    修法：`auditlib.strip_line_comments(text, lang)` 把行尾注释换成等长空格
    （**注释符按语言分**、**必须先跳过字符串**），`iter_code_lines` 加 `lang` 参数、7 个调用点全链一致。
    ⚠️ `check_fixes`（复测闭环）**故意不剥**——它拿基线里存的 sink 文本与当前行比对，
    剥了会把"文件没改"误判成"已修复"。
    **剩一条已知边界**（本轮**明确不做**）：
    - **JS 的正则字面量**里的 `//`（如 `/\/\//`）仍可能被误当注释起点。
      （字符串已处理，正则未处理。）⇒ **为什么不做**：JS 的除法与正则**靠上下文区分**，
      静态判错会把**真代码当注释**（⇒ 漏报），风险高于收益。
      块注释 `/* … */` 已在 **E14（v0.48.0）修掉**（单遍扫描、状态跨行延续）。
17. **E16 踩到的三个工具坑**（都是那轮当场发现，写下来免得再犯）：
    ① **校准器不支持"删除型"变异**——"删掉规则里的一条 source"无法表达（new 文本在原文件里
       已存在 ⇒ 还原会连带改坏别处 ⇒ 校准器正确 SKIP）⇒ 改用"**变异该规则自己的 sink**"，
       效果等价且能表达。
    ② **语料目录与 expected 必须同源**——`gen_corpus --out X` 与 `score --corpus Y` 指向
       不同份时**分母会错**（我因此把一次口径错乱误读成"回退到 90.9%"）⇒ 两者必须指向同一份。
    ③ **性能读数会偶发抖动**——E16 曾测到 10.129 ms/文件，复测 **5.265**（上一轮 5.357，同级）
       ⇒ **CI 的性能护栏用 `--repeat 1`（单次测量）** ⇒ 偶发抖动可能让 CI 误红
       ⇒ **待办**：护栏改成 `repeat≥2` 取均值，或给单次读数留足余量。
    ④ 顺带：**过期底稿会伪装成"回退"**——我拿 `e10-*.json`（E10 时代的）比 E16 的逐条差异，
       差出来的其实是 E12 的改动 ⇒ **逐条 A/B 必须重建上一轮的基线**（`git checkout` 回退规则再扫）。
18. **「Markdown 表格的列数一致性」没有判据**（E37 顺带发现，还没做）：
    `docs/jiangzuo/evolution.md` 的进化账本表是 **8 列表头**，但**最近 8 行只有 6–7 列**
    ⇒ 那些行的「结论」文字实际落在了「验证」列里 ⇒ **渲染错位**（表是 Markdown，缺列不会报错，
    只会静默少列）⇒ 而第 12 项 `check_md_tables` 只核「表头完整 + 上表 N 条对账」，
    **不核每行的单元格数** ⇒ 没人发现。
    ⚠️ 顺带说明：这不是判据的锅 —— E37 查的时候发现 §11 那张规划表**用空行把行隔开**（E45 已并进第 4 节的轮次台账），
    于是第 25 项的「按表分块」查重把每一行当成独立的表 ⇒ **同一张表里重复两行也抓不到**
    （表里确有一行重复的 E35）⇒ 已把那张表合并成连续表，并**当场验证**
    （临时插一行重复的 E37 ⇒ 判据报错 ⇒ 还原）⇒ **判据没错，错的是文档结构**。
    ⇒ **E38 已做**（v0.72.0）：① 那 8 行**补齐到 8 列**（缺的是「假设」与「行数收支」⇒ **插空格子**，
    **不编值**）；② `check_md_tables` 加了「每行的单元格数必须与表头一致」⇒ ⚠️ **按 GFM 规则**数列
    （`\|` 是**转义**、不算分隔符 ⇒ 朴素计数会把 `ls scripts/*.py \| wc -l` 这种**合法**写法
    误判成多一列 ⇒ E38 第一版就栽在这儿：草稿脚本与判据**打架**，白查一轮
    ⇒ 改成**与判据同源并自证**）；③ 顺带把 `evolution.md` 的账本**合并成一张连续表**
    （它此前用空行隔行 ⇒ GFM 里**空行后的每行都不是表** ⇒ **整张台账在 GitHub 上根本没渲染成表格**
    ⇒ ⚠️ **更正 E37 的一处不准确说法**：E37 写的是「渲染错位」，**机制说错了**）
    ⇒ 全仓扫出并修掉 **14 行**（11 行插空格子、3 行并回多出的格子）。
    ⇒ **E39 已改判**：原计划是"把「行数收支」这一列**变成机器算的**"⇒ E39 复核后**不可行**：
    「**从台账文本反推对应 commit**」不可靠（64 行里 **58 行无法用版本号定位** —— 那些行的证据格里
    根本没有版本号；且有错配：台账行与 commit 不是一一对应、补记笔也算一笔）
    ⇒ ⇒ **历史行核不了** ⇒ 只能**显式指定 commit**后再算（`git diff --numstat <sha>^ <sha>` 过滤
    `scripts/` + `tests/` + `evals/`）⇒ ⇒ **改判为「提供工具、不做自动核验」**：
    工具给"给定 commit ⇒ 那一轮的行数收支"，**由填表的人显式指定**；
    机器只核**能定位的那些行**（含版本号的少数行）⇒ **宁可少核，不要错核**。
    ⇒ **再记一个新洞（E39 顺带发现）—— E40 已做（v0.74.0）**：**台账的行序没人守** ——
    E37 那轮把 E37 的行**插在了 E36 之前**（台账是时间倒序）⇒ 错了整整一行
    ⇒ E38 才发现并手工换回来 ⇒ 而**没有任何判据**会报 ⇒
    ⇒ **E40 的修法**：第 25 项加「进化账本的轮次号**不得回退**」（**同一轮多行合法** ⇒ 不得误伤）
    ⇒ 实测挖出 **3 处真回退**（E13→E11、E11→E9、E17→E11）⇒ 已重排（**稳定排序** ＋ 脚本自证
    内容集合不变、行数不变）。
    ⇒ **再记一个洞（E38 顺带发现）—— E40 已做（v0.74.0）**：第 25 项的「台账查重」**不覆盖 `evolution.md`**
    —— 它的行格式是 `| 日期 | E37 …`（轮次在**第二格**），而查重正则认的是
    `| **E37** ✅ | v0.70.0 |` ⇒ **进化账本里若又出现重复行，没人能发现**
    （而 E35/E36 的「台账脚本跑两遍」正是这么留下的）。
    ⇒ 修法**不能**按轮次查（**同一轮多行是合法的**：一轮可能有多个变异 ⇒ 本表里 E11 就有 4 行）
    ⇒ 只能查「**同一张表里出现两行完全相同**」⇒ 精确、不误伤 ⇒ **E40 已实现**。
    ⇒ **E40 再挖出的第三个洞（同一病根，更隐蔽）**：**每个 current-state 标记区**此前
    **只查一个**（14 个区块里 **12 个**无人守）⇒ E39 把 v0.72.0 的区块改写成 v0.73.0 的数时
    **对账跟着腐化一起漂 ⇒ 绿灯** ⇒ 现改为**每个区块对账它自己那一版**的快照
    （区块与版本的对应**从文件里推出来**）＋ 补 `history.0.68.0` ＋ 验收记录小节**必须升序**。

### 下一轮规划（E46 起，2026-10-25 排）

**每轮都是一件独立的事**，都走同一条流水线：**先复核 → 改一处 → 配正反判据 + 变异校准能红
→ A/B 零回退 + 四道闸门 + 靶场 → 记账（CHANGELOG / evolution / 验收记录 / 交接文档）→
独立提交 + 推送 + tag → 核远端 CI**。每轮都留证据，不静默留着缺口。

| 轮 | 主题 | 前置 | 验收信号（可当场复现） |
|---|---|---|---|
| **E59** | **英文分册第四批（4 本：incident / refactor-performance / self-evolution / skill-orchestration）** | E57/E58 流程复用（锚点进提示词、独立双语审、当轮登记对照账） | ① 四本整译 ② 双语审三类全收口 ③ 对照账 16/20 ④ 既有判据不破 ⑤ 不动引擎、口径不变 |
⚠️ **明确不做 / 停牌项**（收口在**这一处**，别再抄到别处）：

1. **JS 正则字面量**里的 `//` —— JS 的除法与正则**靠上下文区分**，静态判错会把**真代码当注释**
   ⇒ 漏报风险高于收益，**不做**（E14/E22 两次登记过）。
2. **分册英文版**（20 本）—— 单轮做不完，硬塞进来只会做成半拉子 ⇒ 留作独立大工程。
3. **触发率 A 路线** —— **已定案：不做**（要动 C 盘的插件目录）。
4. **发行渠道** —— **E33 已做**（65 个 Release 全部发布）；**skills.sh 注册 E41 已做**
   （复核发现它**根本没有提交流程** ⇒ 装一次即被索引 ⇒ 它从来不是外向写）。
5. **1.0.0 宣称** —— 行为证据基线未红，**不宣称**（见第 12 条）。
6. ✅ **`main` 分支保护** —— **E48 已配好**（所有者加权限后；禁强推 / 禁删分支 / 管理员同禁，**不要求 PR、不要求 CI、不限制推送人** ⇒ 本项目的推送流程不受影响）⇒ **不再是停牌项**。

⚠️ **其余停牌项**（动这些必须所有者点头）：外向发布（GitHub Release 页面）、改仓库设置、
动 C 盘、凭证相关（轮换、扩权限）、**移动已发布 tag**、`git reset --hard` / 强推 / 删分支。

⚠️ **已删掉的东西（E45）**：原来这里有**三张规划表**（「十轮规划 E14–E23」「后续五轮规划 E20–E24」
「下一轮规划 E25–E29」）＋ 一段 **E30–E41** 的表格行 ⇒ **同一轮在两张表里各写一遍**
（实测 **11 轮**：E14–E23 与 E27），而两份**已经漂了**：

1. 「十轮规划」是 2026-10-21 排的**计划**，自 E17 起主题与实际执行**错位一格** ⇒ 真源是 `CHANGELOG.md`；
2. 「完成标记 ✅」**E1–E20 那 20 轮一个都没有**（而它们全都做完了）；
3. **E30–E41 那段没有表头 ⇒ GFM 里根本不是表**（16 行散在 3 个行块里，在 GitHub 上不渲染）；
4. **E42–E44 压根没有行** ⇒ §11 停在 E41 ⇒ 读者会以为项目停在那儿；
5. 四处**校准例数已被 CHANGELOG 订正过、台账却没跟着改**
   （E19 30→29、E21 32→31、E32 54→55、E41 80→81）。

⇒ ⇒ 已全部并进**第 4 节的「轮次台账」**（唯一一处），并由第 25 项逐行对账。
**§11 现在只放还没做的轮次。**

## 12. 路径与搬家史（为什么现在在这，以及再搬家要注意什么）

- **2026-10-05 → 2026-10-20** 原在 `D:\Zcode对话\workspace\skill开发\SkillOne\`。
- **2026-10-20 三步**：① 整树复制到 `D:\Github项目\skill开发`（先复制后删的策略是用户选的）；
  ② 改名 `skill开发` → **`jiangzuo`**（与同目录 `jujia-agent` / `novel` 风格一致，纯 ASCII）；
  ③ **去掉 `SkillOne` 这一层**，三样东西上提，最终树见第 2 节。
- **零代码改动的原因**：仓库里没有任何文件写死绝对路径（实测 `grep -rI "Zcode"` 零命中），脚本一律按相对自身位置取路径，
  `../eval-runs` 这层相对关系在去掉一层后照样成立。**这是刻意维持的不变量，别再往仓库里写绝对路径。**
- **旧目录 `D:\Zcode对话\workspace\skill开发\` 已由用户删除**（2026-10-20 21:40 前后实测：路径已不存在）。
  删之前记得关掉开着旧工作区的会话/窗口（否则会被占用，且那个会话的 cwd 当场失效）。
  ⇒ **现在只有这一个位置**，不再有"两处不要同时改"的问题。
- **关于"记忆"**：新工作区没有会话记录也没有项目记忆 ⇒
  **本文件 + 仓库内的 CHANGELOG / evolution.md / 交付报告 / 验收记录 = 全部已知内容**。
  旧机器上还有两份按路径编码的项目记忆文件（`jiangzuo-handover.md`、`jiangzuo-eval-campaign.md`），
  在 `C:\Users\张\.qoder-cn\projects\D--Zcode---workspace-skill--\memory\`，
  内容已并入本文档，**不再需要**；除非你想找回逐字历史，否则不必迁移。
- **账号下还有别的公开仓库会被同时推**（2026-10-20 实测）：`Zhang-jx00/yushu`（R105 发布状态机，
  author `274375345+Zhang-jx00@users.noreply.github.com`）与 `Zhang-jx00/gov-ragqa`（author `zjx@local`）
  在本项目工作期间也有推送，**但本机没有它们的克隆、内容与身份都与本项目无关** ⇒
  **是另一台机器/另一个会话在推**。所以"账号活动页看到别的仓库有动静"是正常的，
  别误判成本项目推错仓库。本项目只认一条：`origin` → `Zhang-jx00/jiangzuo`，
  提交身份 `jiangzuo <jiangzuo@example.com>`，远端只有 `main` 一个分支。
- **若以后再搬家**：改完路径后，(1) 在新路径跑第 13 节自检；(2) 更新本文档第 2 节与文档名；
  (3) 远端与 tag 完全不受影响（`.git` 跟着走）。
- **2026-10-20 清理**：项目根下的 `.qoder-credits/`（23 个会话 canvas + `report.json`，约 21 MB）
  已删——它是 `qoder-credits-inspector` 插件**每会话自动生成**的 token 用量报告，
  里面的"独有内容"只是各会话读过的文件清单，**没有项目知识**（其中若干个还属于另一个项目
  `jujia-agent`）。连同 `eval-runs/results/campaign-stray-artifacts-20261007/`（测试会话漏出来的
  记忆副本与档案）和 `eval-runs/results/session-side-effects/` 一并清了。
  **项目根现在只有三样**：`jiangzuo/`（仓库）、`eval-runs/`（草稿与证据）、本文档。
  ⚠️ **C 盘 Qoder 应用里的会话记录没动**（那是应用数据库，`eval-runs/cleanup_*.py` 那套
  只删清单内的 id、清单外的只报告——项目记忆里有"清理红线"，不要退回"除当前会话外全删"）。

---

## 13. 拿到副本的十分钟自检（照着跑，输出应与括号里一致）

```bash
cd "D:/Github项目/jiangzuo/jiangzuo"

git status --short --branch          # 期望：## main...origin/main，没有任何改动行
git log --oneline -1                 # 期望：最近一笔是「已推送」那一笔（tag 之后可能还有纯文档提交）
git ls-files | wc -l                 # 期望：与第 0 节「规模」对得上（**不写死**：每轮都变）
git tag | wc -l                      # 期望：与第 0 节「状态」里那一版的 tag 数一致（**不写死**：每发一版 +1）
git rev-list --count HEAD            # 期望：每提交一次 +1（**不写死**）
git remote get-url origin | sed -E 's#://[^@/]+@#://<CREDENTIAL>@#'   # 期望：https://Zhang-jx00:<CREDENTIAL>@github.com/...

grep -n "version:" SKILL.md          # 期望：与第 0 节「状态」那一版的版本号一致
python scripts/validate_skill.py .   # 期望：32 条信息 / 0 警告 / 0 错误
python scripts/preflight.py --all --strict   # 期望：RESULT: PASS（critical/high=0）
python -m unittest discover -s tests # 期望：Ran 353 tests ... OK（约 190 秒）
python scripts/audit_rules.py --validate    # 期望：RESULT: RULES-OK（33 条，另有 1 条数据停用）
python scripts/ship_check.py --level L1      # 期望：RESULT: SHIP-OK（6 通过/0 警告/0 未过，会再跑一遍测试）

# 密钥形态自查（期望：命中 0，且拿合成令牌校准时能命中）
git ls-files -z | xargs -0 grep -Eic "ghp_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|-----BEGIN [A-Z ]*PRIVATE KEY" | grep -vc ':0$'

# 本仓库自扫（E7 起是干净仓库标尺：期望 8 发现 / 结论 0 / 另计 8）
python scripts/audit_scan.py . --json ../eval-runs/self-check.json   # 只读

# 审计链端到端（产物写到仓库外）
python evals/audit-fixtures/gen_corpus.py --out ../eval-runs/corpus
python evals/audit-fixtures/score.py --corpus ../eval-runs/corpus   # 期望：ACCEPT-OK 25/25 检出 & 0/19 安全样本
rm -rf ../eval-runs/corpus                                          # 用完即清

# 第三方复验（要网；浅 clone 到仓库外，用完即删。E7 的 A/B 数字）
git clone --depth 1 https://github.com/digininja/DVWA.git ../eval-runs/tp/DVWA
git clone --depth 1 https://github.com/pallets/flask.git ../eval-runs/tp/flask
git clone --depth 1 https://github.com/psf/requests.git ../eval-runs/tp/requests
python scripts/audit_scan.py ../eval-runs/tp/flask --json ../eval-runs/tp-flask.json    # 期望：13 发现 / 结论 1
python scripts/audit_scan.py ../eval-runs/tp/requests --json ../eval-runs/tp-requests.json # 期望：4 发现 / 结论 0
python scripts/audit_scan.py ../eval-runs/tp/DVWA --json ../eval-runs/tp-dvwa.json     # 期望：58 发现 / 结论 58
python evals/audit-fixtures/dvwa_coverage.py --json ../eval-runs/tp-dvwa.json           # 期望：14/19
rm -rf ../eval-runs/tp                                                        # 用完即清
rm -f ../eval-runs/tp-dvwa.json ../eval-runs/tp-flask.json ../eval-runs/tp-requests.json
# ⚠️ **别用 `rm -rf ../eval-runs/tp-*.json` 通配**：那个通配会连 §6 的**现行底稿**
#    `tp-evidence-20261021-{DVWA,flask,requests}.json` 一起删掉（`*` 能匹配
#    `-evidence-20261021-DVWA`）。只删本轮亲手生成的那三个文件名。

# 远端 CI（匿名、只读；见第 5.3 节）
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/actions/runs?per_page=1"
```

对不上的话：先怀疑副本/环境，再怀疑文档；**用 `git log`、`git show` 和当场命令作准**，
并把差异写进第 8 节（这正是本项目一贯的做法）。

✅ **本文档（交接文档）已进仓库（E27）**，所以它自己的数字**有机器判据**：
`validate_skill.py` 的期望值核对会扫仓库内 .md 的**代码块** ⇒ **本文档第 13 节那些期望值
（264 用例 / 29 条信息 / 111 提交 / 69 tag…）抄错会当场红**（E29 那轮就被它当场逮到 3 处）。
⚠️ 剩下没被守住的：**提交数与 tag 数**（它们是 git 的状态，不是文本）⇒ 每轮手工核。

---

## 14. 这份文档什么时候必须更新

- 每完成一轮（任何版本）：**第 0、2、4、6 节的数字**与第 11 节剩余项要跟着改；`CHANGELOG.md` 一条、`evolution.md` 一行。
- 任何一次"新踩的坑"：进第 8 节或第 9 节；如果它可能复发，**同时做一条会红的判据**，否则它还会回来。
- 搬家/改名/换远端：第 2、5.4、12、13 节。
- 评测口径变化（分母、语料规模、检出定义）：第 6 节必须**自我披露**变化前后两个数，不许静默换口径。

---

## 15. 项目目标与边界（先对齐这件事，再看细节）

### 15.1 这是什么

**将作（jiangzuo）** 是一个 **Agent Skill**：一份让 AI 编程助手按**工程法度**干活的**纪律包**，
外加一条**零依赖的安全审计链工具集**。它有两个身份，缺一不可：

| 身份 | 是什么 | 证据在哪儿 |
|---|---|---|
| **纪律包**（主） | 核心循环五步（先读懂 → 再想清 → 后动手 → 必验证 → 留文档）、L0–L4 任务分级门、门函数式验证、复用阶梯、产出不出盘、措辞规矩…… | `SKILL.md`（入口）＋ `references/` 分册（一层深）＋ `docs/jiangzuo/constitution.md`（常驻门槛） |
| **工具集**（次） | 一条**十环**的静态安全审计链：索引 → 地图 → 规则 → 调用图/污点 → 调度 → 反幻觉验证 → 分级报告 → SARIF → 靶场验收 → 规则治理 | `scripts/`（零依赖 Python）＋ `scripts/audit-rules/*.json`（声明式规则） |

> **为什么这一节不写具体数字**：分册数 / 脚本数 / 模板数 / 规则条数 / 用例数 / 校准例数
> **每轮都变** ⇒ 写死即过期 ⇒ ⇒ **唯一一处是 §0 的规模行**（生成器产出、逐字对账）
> ⇒ ⇒ 本文档任何别处都只**指向**它（§21.3 给了现查命令）。
> ⚠️ 这条纪律本身是本项目治了八轮的主线，见 §19.1。

**为什么是"技能"而不是"工具"**：技能被**别的** AI 助手加载使用 ⇒ 所以入口必须**极小**
（正文 ≤ 500 行 / ≤ 5000 token）、分册必须**按需读取**（一层深，不许互相引用）、
必须**零依赖零网络**（任何环境装上就能跑）、必须**可被发现**（skills.sh 生态索引）。

### 15.2 目标（这个仓库想达成什么）

1. **把"资深工程搭档"的行为做成可复制的纪律**：不是写一份"建议"，而是写成**能被机器抓住违规**的判据
   （逐项清单见 §5.2；校准例数现查，见 §21.3）。
2. **给 AI 助手一条能真的查出漏洞的静态审计链**：零依赖、可离线跑、有**靶场**（DVWA / flask / requests）
   与**语料**做量化回归，检出率与误报率都有分母（口径见 §6）。
3. **每一轮开发都留下可复核的证据链**：提交 → tag → CI → Release → 补记笔，数字全部从实物抄。
4. **知识不腐烂**：判据有"变异校准"（把实现改坏必须变红），台账有"逐行对账"，
   文档有"标记区对账" ⇒ 过期会**自己叫**。

### 15.3 明确的边界：不做什么，以及**怎么判断一件事该不该划进边界**

本项目的边界不是"做不动了所以不做"，而是**有登记、有证据、有代价**：

| 边界类型 | 判断标准 | 登记在哪 |
|---|---|---|
| **能力边界**（静态消不掉的） | 能说清"为什么做不到"＋"代价是什么"＋"实测证据是什么" | `references/audit-rule-authoring.md` 的能力边界表 |
| **停牌项 / 明确不做** | 写清"什么条件下可以重新拿出来" | **§11 的那一张表**（唯一一处，**不复述**） |
| **不宣称**（证据不足） | 证据基线没红 ⇒ 一律不宣称收益 | `evals/micro-tests.md` ＋ §21.2 |
| **还没做到**（不是"不做"，是"没做完"） | 写清前置与验收信号 | §21.2 ＋ §11 的下一轮规划 |

**具体条目只有 §11 与 §21.2 两处** ⇒ 本节不复述。

### 15.4 怎么算"做完了"（三层验收）

| 层 | 判定口径 | 在哪跑 |
|---|---|---|
| **仓内** | 结构校验 **0 警告 / 0 错误**、静态检查 critical/high = 0、交付闸门 L1 全过、全量 unittest 绿 | §23.1 的四道闸门 |
| **仓外** | 靶场与语料数字**一字未变**；A/B 逐条零差异；变异校准**全部 RED 且无 SKIP/GREEN/INVALID** | §23.2 |
| **远端** | CI **步骤逐一 success**（不是作业级那一个勾）；Release 正文与 CHANGELOG 生成版**逐字一致**；远端 tag ↔ Release 一一对应 | §24.3 的步骤 6–8 |

> 每一层的**期望输出长什么样**，见 §13 的十分钟自检（那里的期望值是机器校验过的）。

---

## 16. 技术栈与运行环境

### 16.1 技术栈（刻意极简）

| 层 | 选型 | 为什么 |
|---|---|---|
| 运行时 | **Python 3.8+ 标准库**，**零第三方依赖** | 技能要被别的项目直接采用 ⇒ 装上就能跑；CI 不能装包 |
| 分发形态 | **Agent Skill**（`SKILL.md` + `references/` + `scripts/` + `templates/` + `evals/`） | 生态原生格式，skills.sh 可索引 |
| 入口 | `SKILL.md` frontmatter（`name` / `description` / `when_to_use` / `metadata.version`） | 加载时只进这一份 ⇒ 预算就是硬约束 |
| 分册 | `references/*.md`（**一层深**） | 按需读，不预载 |
| 规则 | `scripts/audit-rules/*.json`（声明式） | 规则与引擎分离 ⇒ 加规则不改代码 |
| 报告 | JSON + **SARIF 2.1.0** | SARIF 可被 GitHub 上传；schema 白名单**硬编码**进自检（CI 装不了官方 validator） |
| CI | GitHub Actions（`validate.yml` 八步 + 一步失败诊断；`release-consistency.yml` 匿名 API） | 远端核"发出去的东西对不对" |
| 发布 | GitHub Release（正文由 `scripts/release_notes.py` 从 CHANGELOG 生成） | 发行说明**单一真源** = CHANGELOG |
| 版本 | SemVer（`v0.x.y`），tag 与 Release 一一对应 | 可机器核（`release_identity.py`） |
| 记账 | `CHANGELOG.md`（逐版）+ `docs/jiangzuo/evolution.md`（一行一次变异） | 没记账的变更视为未发生 |

### 16.2 三条硬约束（决定了上面那张表为什么这么选）

1. **零依赖 ⇒ 静态解析优先**：真源必须跨平台同色 ⇒ **绝不执行被测脚本来取数**
   （本地 Python 与 CI 的 Python 版本不同 ⇒ 动态取数会得到两套答案）。
2. **入口有预算 ⇒ 正文极小**：入口是唯一被强制加载的部分 ⇒ 细节一律下沉到分册（按需读）。
3. **产物不出盘**：所有中间产物写进**项目内草稿区**，**不占 C 盘**；用完即清并**回报残留**。

> 环境与操作的具体坑（GBK 编码、CRLF 还原、网络通道、行尾归一）见 **§9**；
> GitHub 相关的操作细节见 **§24**。本节不复述。

### 16.3 东西在哪

- **目录树与文件地图** ⇒ **§2**（那是唯一一份，不在这里抄第二遍）。
- **每个东西归谁管（改哪儿会被哪道判据拦住）** ⇒ **§18**。
- **本机怎么跑、期望输出长什么样** ⇒ **§13**（十分钟自检）与 **§23**（命令速查）。

---

## 17. 能力全景：已开发了什么（按能力域，不是按版本流水账）

> **逐轮流水账在两处**（**别复制到本文档**）：`CHANGELOG.md`（逐版）＋ 本文档 §4 的轮次台账（逐轮一行）。
> 本节只回答"**现在能干什么**"。

### 17.1 纪律侧（这个技能真正的产品）

| 能力 | 落地形态 | 机器守它的方式 |
|---|---|---|
| 核心循环五步 | `SKILL.md` | `evals/red-tests.md`（**纪律场景的红测**）＋ `evals/micro-tests.md`（行为微测台账） |
| L0–L4 分级门（单向棘轮） | `SKILL.md` | 人工守 + 复盘记录 |
| 门函数式验证（点命令/全量跑/读到底/对得上/才下结论） | `SKILL.md` ＋ `references/testing.md` | 第 10 条铁律（§3） |
| 复用阶梯（需要吗→已有→标准库→原生→已装依赖→一行→才写） | `references/design.md` | 人工守（写代码前先说停在第几级） |
| 十条核心不变量 | 本文档 §3 | 人工守 + 进化账本 |
| 常驻门槛 | `docs/jiangzuo/constitution.md` | `ship_check.py` 自检其中可机器化的部分（映射见 §20.1） |
| 门函数式**自进化**（让规则被证据淘汰，而不是被遗忘） | `references/self-evolution.md` ＋ `scripts/evolve_report.py` ＋ `templates/evolution-log.md` | `evolution.md` 的行序/重复检查（第 25 项） |
| 措辞规矩（不说"独立完成"、未收尾不说"已完成"） | `SKILL.md` ＋ 本文档 §10 | 人工守（**对外声称的防护栏必须当场可验证**） |

### 17.2 工具侧：审计链十环

| 环 | 脚本 | 干什么 | 关键约束 |
|---|---|---|---|
| ① 索引 | `audit_index.py` | 文件索引与忽略规则 | 忽略模块是**引擎级**的（撞 id 会静默遮蔽，E1 修） |
| ② 地图 | `audit_map.py` | 语言分布 / 入口 / 路由 / 全仓地图 | |
| ③ 规则 | `audit_rules.py` | 声明式规则引擎 | 规则**带角色×语境**二维条件（C2 引入） |
| ④ 调用图与污点 | `audit_graph.py` | 跨文件调用图 + 污点传播 | 返回摘要/跨文件作用域/引号上下文（E11/E30/E31） |
| ⑤ 调度 | `audit_scan.py` | 十环调度、分级、门控 | 门控后图成本才进预算 |
| ⑥⑦ 反幻觉验证与报告 | `audit_scan.py` | 独立验证挡掉假流；分级报告 | **验证环节丢弃**是真数据（DVWA 有 dropped） |
| ⑧ SARIF | `audit_scan.py` ＋ `sarif_schema_extract.py` | SARIF 2.1.0 输出 | schema 白名单硬编码（官方 validator CI 装不了） |
| ⑨ 靶场与语料 | `evals/audit-fixtures/*` | DVWA/flask/requests 复跑 + 语料生成/评分 + 覆盖映射 + bench | **分母口径**见 §6 |
| ⑩ 规则治理 | `references/audit-rule-authoring.md` | 能力边界表 + 规则写法 + 引擎成本 | 边界每条带**实测证据** |

### 17.3 发布与记账侧（这个仓库自己的"元工具"）

| 能力 | 脚本 | 干什么 |
|---|---|---|
| 身份单一真源 | `repo_identity.py` | owner/name/URL 的**唯一**出处（E42） |
| 发布身份核验 | `release_identity.py` | 每个 tag 指向的 commit **真的属于那个版本**（owner 规则）＋ 远端三边对账 |
| 发行说明生成/发布 | `release_notes.py` | 从 CHANGELOG 生成正文并发 Release；**先核远端 tag**再发 |
| 远端自洽核验 | `release_consistency.py` | 远端 tag ↔ Release（**匿名 API**、三态退出码） |
| 当前状态真源 | `current_state.py` | 「当前状态」的唯一机器可读出处 + 标记区对账（第 23 项） |
| 结构校验 | `validate_skill.py` | 逐项清单见 §5.2（判据地图见 §18.1） |
| 变异校准 | `mut_calibrate.py` | 把实现改坏 ⇒ 断言判据**当场变红** ⇒ 再按字节还原自证 |
| 交付闸门 | `ship_check.py` | 测试/静态/报告/自净/常驻/结构六项 |
| 计划对账 | `plan_check.py` | 提交前把工作树脏文件与**本轮计划清单**对账：计划外脏文件／计划内未动当场红；三态退出码（E51；**只在本地**，CI 看不住它） |
| 交付前静态检查 | `preflight.py` | 密钥形态、待办残留、仓库卫生 |
| 审查工单 | `review_packet.py` | 把"交给审查者/子代理的东西"钉成一个文件 |

---

## 18. 判据与门禁地图（改哪里就得知道谁在管）

### 18.1 `validate_skill.py` 的判据地图

> **逐项的一句话清单在 §5.2**（随实现更新，**以那里为准**）；本表只作"哪一项管哪一类问题"的地图。
> 信息条数**每轮会变** ⇒ 现查命令见 §23.1。

| 项 | 判据 | 抓什么 | 起始 |
|---|---|---|---|
| 第 7 项 | 门面的计数/预算/安装命令/仓库身份 | README（中英）计数漂移、**占位符安装命令**、身份抄到第二个文件 | E36 / E41 / E42 |
| 第 12 项 | Markdown 表格结构 | 表头被吃掉、**行尾竖线缺失**、**列数与表头不一致** | E38 |
| 第 14 项 | 「照着跑就能看到」的期望值 | 文档里的用例数/语料分母/规则条数与实物不符 | E8 |
| 第 18 项 | U+FFFD 替换字符 | 字符级损坏（**连中文标点都能坏**） | E15 |
| 第 19 项 | 变异校准器随技能分发 | 校准例数**手抄**（E19–E23 连续五轮写错） | E24 |
| 第 20 项 | 交接文档在仓库内 | 章节缺失、未被 git 跟踪 | E27 |
| 第 21 项 | 结论区判定表自洽 | 判定表内部不自洽 | E28 |
| 第 22 项 | 判定表 §四 口径拆解 | 加法不成立（分母混用） | E32 |
| 第 23 项 | 当前状态真源与载体对账 | 散文里的当前状态漂移；**规模行 / 远端状态行逐字对账** | E34 / **E46 / E47** |
| 第 24 项 | 微测台账状态格 vs 实测 | 改结论不改数据 | E35 |
| 第 25 项 | 台账自身不许被写坏 | 版本条目重复/降序、验收记录升序、进化账本行序与重复行、**轮次台账对账**、**§0 速览里的事故行必须带指针** | E36 / E40 / **E45 / E49** |
| 第 26 项 | 发布产物身份 | tag 指向错 commit（内容错，不是数量错） | E37 |
| 第 27 项 | 发布产物一致性核验器 | 核验器缺失/非零依赖/无三态退出码 | E39 |

### 18.2 本机四道闸门：各管什么

> 命令见 §23.1（**唯一一处**）；期望输出见 §13。

| 闸门 | 它管什么 | 红了意味着 |
|---|---|---|
| G1 结构校验 | 技能结构、台账、真源、发布身份 | 有一处**对不上账**：不是格式问题，是"文档与实物脱节" |
| G2 交付前静态检查 | 密钥形态、待办残留、仓库卫生 | 有东西**不该进这次提交** |
| G3 全量测试 | 判据本身、引擎行为、夹具 | 有回归（**只跑自己那几条新用例是不够的**，见 §19.2） |
| G4 交付闸门 | 测试/静态/报告/自净/常驻/结构六项 | 六项交付条件缺一项 |

### 18.3 远端 CI：哪一步会红

> 完整八步见 §5.3。**判据是"步骤逐一 success"，不是作业级那一个勾**
> （某步失败会让后面的 bench/靶场变 skipped ⇒ 历史上这 22 个红 run 里那两步从未真正执行过）。
> 另有 `release-consistency.yml`：用**匿名 API**核「远端 tag ↔ 远端 Release」⇒ **不写任何凭据**。

| 你改了什么 | 本机先跑 | CI 里会红的那一步 |
|---|---|---|
| `SKILL.md` 正文 / frontmatter | G1 ＋ G3 | 步骤 1（结构与预算） |
| `scripts/audit_*.py`（引擎） | 四闸门 ＋ 靶场 | 步骤 3（冒烟）、步骤 5（性能护栏）、步骤 7（靶场） |
| `scripts/validate_skill.py` | G1 ＋ G3 | 步骤 1 |
| 判据或测试（`tests/`） | G3 ＋ 变异校准 | 步骤 3、步骤 6（锚点核对） |
| `scripts/audit-rules/*.json` | G1 ＋ G3 ＋ 靶场 | 步骤 1（RULES-OK）、步骤 7 |
| `CHANGELOG.md` / 台账 / 交接文档 | G1 | 步骤 1（日期与台账对账） |
| `SKILL.md` 的 `description` | 另跑 `evals/trigger-tests.md` | 步骤 1（预算）＋ 本地触发率 |

---

## 19. 踩过的坑（分类索引；**细节与修法看 §8**）

> **§8 是坑位清单本体**（编号 1–78，症状 → 根因 → 修法 → 留下的东西）。
> ✅ **E52 已把 E28–E51 的坑回填进 §8**（第 56–78 条；此后新坑**当轮直接进 §8**，不再攒批）。
> ⇒ ⇒ 本节只做**分类索引**，**不复述 §8 的正文**（复述就是制造第二个来源）。

### 19.1 一类：**同一事实多处手抄 ⇒ 必然漂**（本项目治了八轮的主线）

**症状**：同一个数/同一件事在多处各写一遍 ⇒ 改一处忘一处 ⇒ 漂了**没人知道**，因为没人对账。

**索引**：§8 第 17、21、26、28、37、61、64、67、69、71、72、73、75、76 条 ＋ E32（口径三分）。

### 19.2 二类：**判据自己也会坏 / 是装饰**

**症状**：判据**恒绿**（锁不住任何东西，比没锁更坏）／**误伤**（把别的目录也拖下水）／
**自己算错**（夹具缺一个字段 ⇒ 整段检查被**静默跳过**，看着在跑其实没跑）／
**要求写死会变的数**（逼着人说假话）。

**索引**：§8 第 23、25、30、31、32、35、39、41、45、48、53、56、57、58、63、65、66、77、78 条（E43/E46/E52 已并入）。

### 19.3 三类：**"看起来对"其实不对**

**症状**：退出码 0 ≠ 事情做成了（`git push` 说 "Everything up-to-date" 而远端没有那个 tag）／
数字对得上 ≠ 口径对得上／文件存在 ≠ 内容对（手抄的副本）／表格能渲染 ≠ 它是表／
通过了 ≠ 没漏（校准的 GREEN/SKIP 也算失败）。

**索引**：§8 第 1、3、19、20、33、34、60、61、69、70、74 条（E41/E47/E52 已并入）。

### 19.4 四类：**引擎/规则层的静默缺陷**

**症状**：注释里的代码被当代码／成员方法借用同名全局函数的摘要／摘要为空时旧污点不清／
净化点不看插入上下文（真阳性被吃掉）／撞 id 的规则文件静默遮蔽前者。

**索引**：§8 第 36、42、43、49、52 条 ＋ E11、E13、E18、E19、E30、E31（引擎轮次的细节在 §4 台账与 CHANGELOG；E52 未新增引擎坑）。

### 19.5 五类：**环境与工具**

**症状**：PowerShell 5.1 的 GBK 重编码把中文整篇写坏／CRLF 还原与混合行尾／
git 传输通道时好时坏（API 正常）／CI 是 UTC 而作者是 +0800／匿名 API 的额度／
本地与 CI 的 Python 版本不同。

**索引**：§8 第 8、9、10、11、12、16、27、51、54、59、68、70、75 条（E24/E52 已并入）。

---

## 20. 硬性要求与本项目整理出来的纪律

### 20.1 硬性门槛（不可协商）

**权威出处：`docs/jiangzuo/constitution.md`（常驻门槛，逐条可查）** ⇒ 本节只给"哪条被哪道机器判据守着"的映射，
不复述条款原文（复述＝第二个来源）。

| 门槛大意 | 谁在机器上守它 |
|---|---|
| 全量测试通过（0 失败） | G3 ＋ CI 步骤 3 |
| 结构校验 0 警告 0 错误 | G1 ＋ CI 步骤 1 |
| 交付前静态检查 critical/high = 0 | G2 ＋ CI 步骤 2 |
| 交付闸门 L1 过 | G4 ＋ CI 步骤 4 |
| 入口预算（正文 ≤ 5000 tokens） | 第 14 项 ＋ `validate_skill.py --stats` |
| 改了 `description` ⇒ 复跑触发率并回填 | 人工 ＋ `evals/trigger-tests.md` |
| 改了纪律条款 ⇒ 复跑红测，基线未红要如实写"无区分度" | 第 24 项 ＋ `evals/red-tests.md` |
| 无试验残留 | `ship_check.py` 的自净核对（**只数个数、不比对清单** ⇒ 见 §24.5） |
| 外向操作先说明并取得同意 | 人工（**仓内没有判据能守这条**） |

### 20.2 本项目整理出来的纪律（**出处索引**：只列"这条在哪"，不抄正文）

| 纪律 | 权威出处 |
|---|---|
| 一轮 = 一件独立的事；一轮一版、一 tag、一 Release、一笔台账 | §10 协作规矩 ＋ §4 台账形态 |
| 先复核再动手：现扫 → 先否证 → 核引用 → 自己的改动先让它红 | §10 ＋ §5.5 |
| 改一处；不顺手重构、不加依赖 | §10 |
| 数字只从真实命令输出抄；复现不了写"未验证"；未收尾不说"已完成" | §3 第 10 条 ＋ §10 |
| 台账里的假话比缺一栏更坏 | §10 |
| 历史不许篡改（历史区块对账它自己那一版） | 第 25 项（台账检查） |
| 同一事实只许有一处；派生物不许手抄 | §19.1 ＋ 第 23 项 |
| 任何锁必须先证明它能红 | §5.5 |
| 一条判据要配正反用例（只写红例会把"判据恒绿"放过去） | §5.5 ＋ §19.2 |
| 判据自己也要被校准；判据不许误伤通用机制 | §5.5 ＋ §19.2 |
| 提交走 `git add <点名文件>`、提交信息走 UTF-8 文件、主题带版本号 | §24.3 |
| 推送顺序：push main → 附注 tag → push tag → 核 CI → 发 Release → 回读 → 补记笔 | §24.3 |
| 推完必须回读远端核对 | §24.3 步骤 3 ＋ §24.5 |
| 已发布的 tag 不要移动；真要移动（授权过的修复）⇒ 移动后回读三边 | §24.6 |
| 产物只进项目内草稿区，用完即清并回报残留 | §16.2 ＋ §25 |

---

## 21. 开发进度与未达标清单

### 21.1 已完成（按能力域，**逐轮明细见 §4 与 CHANGELOG**）

- **纪律侧**：五步循环、分级门、门函数验证、复用阶梯、核心不变量、常驻门槛、自进化台账、
  措辞规矩、双门面（中文/英文）、skills.sh 生态可安装（E21 实测装出 571 个文件、副本自检全绿）。
- **审计链**：十环齐活、声明式规则集、SARIF 2.1.0、能力边界表（每条带实测证据）。
- **元工具**：结构判据（逐项见 §5.2）、变异校准、发布身份/发行说明/远端自洽三件套、
  当前状态真源、交付闸门、静态检查、审查工单。
- **发布形态**：**tag ↔ GitHub Release 一一对应**（现查：`release_identity.py --remote`）；
  **发行说明走兜底 = 0**；**`main` 分支保护已配**（禁强推/删分支/管理员同禁，且不挡本项目自己的推送）。
- **文档体系**：本文档（交接）、进化台账、常驻门槛、验收记录、逐条判定表、术语表、
  交付报告、审计链报告、发行说明入库。

### 21.2 未达标 / 待办（**别当成"漏了"**）

> ⚠️ **「明确不做 / 停牌项」不在这里** —— 它们收口在 **§11 的那一张表**（那一节自己写着"收口在这一处，
> 别再抄到别处"）⇒ 本节只列**还没做到 / 还没做完**的，**不重复**停牌项。

| 项 | 状态 | 为什么 |
|---|---|---|
| 行为收益的**基线未红** | 微测 A 臂与 B 臂失败数相同（差 **0 个百分点**）⇒ 记作**回归哨兵** | **不许声称**纪律条款带来行为增益（E35） |
| DVWA 覆盖未满 | 5 个模块 MISS（bac / brute / captcha / csrf / xss_s） | 能力边界：跨请求存储型、限流/一次性令牌、缺检查、静态不可证（逐条见能力边界表） |
| 硬误报里的"静态可修" | 已清零；剩下的是能力边界型 | 口径见 §6 |

### 21.3 账目现状（**会变的数一律现查**，不写死 —— 见 §19.1 第一类）

| 项 | 现查命令 | 机器守住的出处 |
|---|---|---|
| 提交数 / tag 数 | `git rev-list --count HEAD` ／ `git tag --list` | — |
| Release 数 | `python scripts/release_identity.py --remote` 的「Release N 个」 | — |
| CHANGELOG 版本条目数 | `python scripts/release_notes.py --check` 的「CHANGELOG 条目 N 个」 | — |
| 台账行数与分类 | `docs/jiangzuo/evolution.md` 末尾的「上表 N 条…N 条 `KEEP`、N 条部分成立、**0 条 `ROLLBACK`**」 | 该文件末尾 |
| 用例数 / 校准例数 / validate 信息数 | `python -m unittest discover -s tests`（末行 `Ran N tests`）／ `python scripts/mut_calibrate.py --check-only`／ `python scripts/validate_skill.py .`（末行信息数） | 本文档 §0 的 `current-state` 标记区 |
| 分册/脚本/模板/规则条数 | `python scripts/current_state.py --derive` | §0 的规模行（第 23 项逐字对账） |
| **性能（ms/文件）** | `python evals/audit-fixtures/bench.py --files 400 --repeat 3 --max-ms-per-file 20` | ⚠️ **这个指标负载相关**：实测同一棵树上半小时内读到 9.993 与 4.225 两个值 ⇒ **单次读数不能当事实** ⇒ 唯一可信的口径是**同机同时刻交替 A/B**（E49 实测：本轮不比基线慢） |

> ⚠️ **为什么这里不写数字**：这些数**每轮都变** ⇒ 写死即过期 ⇒ 而"过期的事实"比"缺的数字"更坏
> ⇒ ⇒ **要数字就现查**；要**机器守住的**数字，接真源（`evals/current-state.json`）。

---

## 22. 接手路线图（第一周照着做）

### 22.1 第 0 天：先证明副本是好的

**照着 §13 的十分钟自检逐条跑**（那里的期望值是机器校验过的）⇒ 对不上就停。
**不要**"先改点东西看看"。

### 22.2 第 1 天：把地图读一遍（不要从代码读起）

| 顺序 | 读什么 | 为什么 |
|---|---|---|
| 1 | 本文档 §15–§21 | 先对齐目标、边界、技术栈、进度 |
| 2 | `SKILL.md`（**只读正文**） | 纪律的核心循环在这里（正文规模见 §0 的规模行） |
| 3 | `docs/jiangzuo/constitution.md` | 硬性门槛（逐条，映射见 §20.1） |
| 4 | §3 核心不变量 ＋ §10 协作规矩 | 改任何东西前的底线 |
| 5 | §4 轮次台账（**一行一轮**） | 看懂"这个项目怎么演进的" |
| 6 | §8 坑位清单 | 看懂"这里踩过什么"（注意它收录到 E26 前后，见 §19） |

### 22.3 第 2–3 天：摸清机器

- 跑一遍四道闸门（§18.2）＋ 靶场（§23.2）⇒ **先看到"绿"长什么样**。
- 读 `scripts/validate_skill.py` 的**开头部分 ＋ 各 `check_*` 函数的 docstring** ⇒ 知道判据都在哪。
- 读 `scripts/audit_scan.py` 的调度层（**不要一上来读污点引擎**）。

### 22.4 第 4 天起：做第一件事

**从 §11 的候选清单里挑**（那里每条都有前置与验收信号）⇒ 或者按 §22.5 自己挑。

### 22.5 自己挑的话，遵守这三条

1. **挑"能被机器判"的事**：能写出一条"改坏了就当场红"的判据 ⇒ 这类事做起来最省心、也最不容易烂尾。
2. **挑"你踩过的坑"**：读 §8 的坑位清单 ⇒ 里面每条都还开着。
3. **别挑"补文档"**：文档要**跟着改动长**，不要单独排一轮去补（补了也会立刻再漂）。

### 22.6 第一轮的标准动作（照抄这个骨架）

```
先复核 → 改一处 → 配正反判据 + 变异校准能红 → 四闸门 + 靶场 + A/B →
记账（CHANGELOG 一条 + evolution 一行 + 交接文档）→ 独立提交 → 推送 → 打 tag →
核远端 CI → 发 Release → 回读远端 → 补记"已推送" → 清草稿区并回报残留
```

---

## 23. 命令速查

> ⚠️ **这里只列命令，不写"期望输出"** —— 期望值只写在 §13 一处（那里是机器校验过的）。

### 23.1 本机闸门与验真

```bash
python scripts/validate_skill.py .            # 结构校验
python scripts/validate_skill.py . --stats     # 入口占用（正文行数 / tokens）
python scripts/preflight.py --all --strict     # 交付前静态检查
python -m unittest discover -s tests           # 全量测试
python scripts/ship_check.py --level L1        # 交付闸门
python scripts/plan_check.py --plan <清单>     # 计划对账（提交前；E51；只在本地，CI 看不住）
python scripts/mut_calibrate.py                # 变异校准（全部 RED，无 SKIP/GREEN/INVALID）
python scripts/mut_calibrate.py --check-only   # 只核锚点（CI 跑这个，秒级）
python scripts/audit_rules.py --validate       # 规则集自检
```

### 23.2 靶场与量化回归

```bash
python scripts/audit_scan.py <目标目录> --json out.json     # 单仓扫描
python evals/audit-fixtures/bench.py --files 400 --repeat 3 --max-ms-per-file 20
python evals/audit-fixtures/gen_corpus.py --out corpus/ && python evals/audit-fixtures/score.py --corpus corpus/
python evals/audit-fixtures/dvwa_coverage.py --json dvwa.json --same-dir
```

### 23.3 真源与发布

```bash
python scripts/current_state.py --derive      # 能当场推出来的数
python scripts/current_state.py --check       # 核对真源
python scripts/current_state.py --sync        # 重推 static 段
python scripts/current_state.py --refresh --scans <扫描产物目录> [--extras <json>]
python scripts/current_state.py --snapshot <X.Y.Z>          # 把当前值抄成某一版的历史快照
python scripts/release_identity.py --sync | --check | --remote [--token <T>]
python scripts/release_notes.py --version <X.Y.Z> | --check [--write] | --publish --version <X.Y.Z> --token <T>
```

### 23.4 远端核对（**匿名、无需令牌**）

```bash
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/actions/runs?per_page=1"
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/actions/runs/<run_id>/jobs"
curl -sS "https://api.github.com/repos/Zhang-jx00/jiangzuo/check-runs/<job_id>/annotations"
```

---

## 24. GitHub 操作规范（含"不得干扰其他项目"的边界）

> §5.4 是**速查**（凭证与流程一行一条）；本节是**完整规范**（怎么做、为什么、坑在哪、边界在哪）。
> ⚠️ **同一件事只许写一处**：规则本身在 §5.4，本节讲**步骤的展开、边界与坑**；
> 两者冲突时**以 §5.4 为准**。

### 24.1 本仓库的身份（先认清楚，别动错）

| 项 | 值 |
|---|---|
| 远端 | `origin` → **`Zhang-jx00/jiangzuo`**（**只认这一个**） |
| 分支 | 远端**只有 `main`** ⇒ 不新建、不删、不保护别的分支 |
| 提交身份 | `jiangzuo <jiangzuo@example.com>` |
| 凭证与令牌 | **见 §5.4（唯一一处）** —— 令牌名称、权限范围、到期日、放在哪、怎么脱敏查看，全在那里 |

### 24.2 ⚠️ 不得干扰其他项目（硬边界）

1. **只用「将作skill」这一枚令牌**（细节见 §5.4）。账号下另有 **workbuddy 项目的专用令牌
   ⇒ 绝不触碰、绝不使用**。（历史上"令牌有效但 push 报 `Authentication failed`"的根因，
   就是 GCM 用**别的**凭据覆盖了它。）
2. **账号下别的公开仓库会被同时推**，那是**另一台机器/另一个会话**在动：
   `Zhang-jx00/yushu`、`Zhang-jx00/gov-ragqa` ⇒ **本机没有它们的克隆、内容与身份都与本项目无关**
   ⇒ **"账号活动页看到别的仓库有动静"是正常的**，别误判成本项目推错仓库。
3. **只对 `Zhang-jx00/jiangzuo` 做写操作**：不改别的仓库的设置、不动别的仓库的分支/tag/Release。
4. **不新建分支**：本项目**只用 `main`** ⇒ 保护规则也**只加在 `main`**上（E48 做的就是这个）。
5. **`github` MCP 只用于只读核对**（`get_commit` / `list_tags` / `list_branches`）：无法确认它用的是哪一枚令牌
   ⇒ **写操作一律走 `git push`**。
6. **CI 的 `release-consistency.yml` 用匿名 API** ⇒ 不写任何凭据到仓库里。

### 24.3 一轮的标准 GitHub 流程（含每步的注意点）

| 步 | 做什么 | 注意点 |
|---|---|---|
| 0 闸门 | 四道闸门（§23.1） | **先绿再推**；不绿就推 ⇒ 远端红、本地绿，排查成本翻倍 |
| 1 对账工作树 | `python scripts/plan_check.py --plan <本轮计划清单>`（E51；清单也能用位置参数逐个给） | ⚠️ **只 `git add` 点名文件时，计划外的脏文件不会进提交** ⇒ 它能一直潜伏在工作树里（E49 实测：躺着一处校准变异残留，直到收尾现扫才发现）⇒ ⇒ **提交前必须跑这道机器闸**：计划外脏文件／计划内未动 ⇒ 退出码 1；没给清单或 git 不可用 ⇒ 退出码 2（**没核成 ≠ 通过**）。⚠️ **它做不了 CI 检查** —— CI checkout 出来的工作树本来就是干净的 ⇒ 这道闸只存在于**本地提交前**这一刻，别以为 CI 会替你看住 |
| 2 暂存 | `git add <点名文件>` | **不要 `git add -A`**（会把草稿区/临时产物一起带进去） |
| 3 提交 | `git commit -F <UTF-8 消息文件>` | 中文提交信息**必须走 UTF-8 文件**（`-m "中文"` 经 shell 会乱码）；**主题里带 `v<版本号>`**（校验器拿它跟 CHANGELOG 日期对账） |
| 4 推主干 | `git push origin main` | 推完**回读核对**（`git ls-remote origin refs/heads/main`）⇒ **退出码 0 不算数** |
| 5 打标签 | `git tag -a v<X.Y.Z> -F <UTF-8 说明文件>` | **附注标签**（`-a`）不是轻量标签 ⇒ 才有 tagger 时间戳与消息；**已发布的 tag 不要移动**（§24.6） |
| 6 推标签 | `git push origin v<X.Y.Z>` | 推完**回读核对**：`git ls-remote origin refs/tags/v<X.Y.Z>`（要核**对象**不是 commit） |
| 7 核 CI | 读 `actions/runs?head_sha=<完整 sha>` | ⚠️ **要用完整 sha**（短 sha 查不到 ⇒ 脚本会空转十分钟）；判据是**步骤逐一 success**，不是作业级那一个勾 |
| 8 发 Release | `python scripts/release_notes.py --publish --version <X.Y.Z> --token <T>` | **CI 全绿之后**才发（E48 之前有一次"先发后核 CI"⇒ 顺序不合规矩 ⇒ 撤回重发）；脚本会**先核远端 tag**（缺或指向不对 ⇒ **拒绝发布**）⇒ 不会在 main HEAD 上自动造 tag；⚠️ **发之前先 `python scripts/release_identity.py --sync`**（把新 tag 写进发布身份台账）—— 否则发布脚本的「发完自证」会因「**台账缺一条**」而红，**而那时 Release 已经发出去了，收不回来**（E49 实测：退出码 1，但 Release 其实已建好） |
| 9 回读自证 | `python scripts/release_identity.py --remote --token <T>` | 要看到「远端 N 个 tag 与本地逐条同 commit、Release N 个，一一对应 ✓」 |
| 10 补记 | 改交接文档 §0 的状态行 ＋ 每版的 ✅ 行 ＋ 真源的 `measured_at_commit` ⇒ 提交推送 | 补记笔本身**也要走一遍闸门与 CI**；**不要回头改已发布的版本笔**（tag 与 Release 已发布 ⇒ 改它＝制造第二个来源）⇒ 只能另起一笔订正并**如实记下** |

### 24.4 网络断了怎么办（**唯一的允许绕法**）

`github.com:443` 的 git 传输通道**时好时坏**（`api.github.com` 同时段往往正常 ⇒ **不是凭据问题**）。

1. **有界重试**：本项目用 10–14 次，每次间隔约 20 秒。
2. **唯一允许的绕法：换前端 IP**：`curl --resolve github.com:443:<ip>` 逐个扫可通的前端 IP ⇒ 直推即通。
   ⇒ **不落任何配置文件、不改走 SSH、不换令牌**。
3. 仍不通 ⇒ **停推、如实留痕**（不要为了"推上去"去换通道/换凭据）。
4. 恢复后按 §24.3 的步骤 4→5→6→7 走完。

### 24.5 常见坑（每条都发生过）与门径

| 坑 | 症状 | 门径 |
|---|---|---|
| 推了但没推成 | `git push` 退出码 0 ＋ "Everything up-to-date"，而远端没有那个 tag | **推完回读远端核对**（E41） |
| 令牌被 GCM 覆盖 | 令牌有效但报 `Authentication failed` | 仓库级 `credential.helper` 保持**空值**；**绝不用**别的项目的令牌 |
| tag 指错 commit | 远端 `refs/tags/<X.Y.Z>` 是轻量标签且指向别的版本 | 第 26 项 + `--publish` **先核远端 tag**（E37） |
| Release 正文不是真源 | 手抄的发行说明副本、从未发布过的聚合稿 | 发行说明**只从 CHANGELOG 生成**；仓里的副本必须**逐字一致**（E43） |
| 走兜底 | tag 有、CHANGELOG 没条目 ⇒ 发行说明取自 tag 提交说明 | 第 26 项**不允许**这一类例外（E44） |
| 少发一个 Release | 远端 tag ↔ Release 缺口 | `release-consistency.yml` 每日匿名核（E39） |
| CI 假红 | 日期判据拿跑闸机器的本地日期当"今天"（CI 是 UTC、作者是 +0800） | 基准取 **max(机器日期, 提交自己的作者日期)**（E41） |
| 查 CI 空转 | 用**短 sha** 查 `actions/runs?head_sha=` | **必须用完整 sha**（本项目脚本已改；手工查时注意） |
| 中文提交信息乱码 | `git commit -m "中文"` 经 shell | 走 `-F <UTF-8 文件>` |
| 误把别的仓库的动静当成本项目 | 账号活动页有别的仓库在推 | 见 §24.2 第 2 条 ⇒ **只看 `origin`** |
| **计划外的脏文件潜伏** | 工作树里躺着别人（或上一轮自己）的改动，`git add` 点名文件时它**不报错也不进提交** ⇒ 下一轮还在 | ⚠️ **提交前跑 `plan_check.py --plan <清单>`**（E51 的机器闸；`ship_check` 的自净核对只数个数、不比对清单，它不会报）⇒ 计划外脏文件当场红（E49 实测：躺着一处能改坏引擎的校准变异残留） |
| **发布身份台账没同步就发 Release** | Release **已经发出去**，脚本却在「发完自证」那一步报「台账缺一条」⇒ 退出码 1，看着像发布失败 | ⚠️ **发之前先 `release_identity.py --sync`**（E49 实测）⇒ 而且要分清**"发布失败"与"自证不过"**：前者 Release 不存在，后者 Release **已经在远端了** ⇒ 处置是补台账再核，不是重发 |

### 24.6 一旦要动"已发布的东西"（授权与流程）

| 动作 | 性质 | 规矩 |
|---|---|---|
| 移动已发布 tag | **改写别人看到的引用** | **默认不做**；确需修复 ⇒ **所有者明确授权** ＋ 移动后**回读三边**（本地 tag / 远端 tag / Release 指向）＋ 如实记进台账 |
| 改仓库设置（分支保护等） | 外向 | **先说明并取得同意**；改完**回读核对**（退出码 0 ≠ 配成了） |
| 轮换令牌 | 凭据 | 属**所有者决定**，不阻塞开发；换完要更新 §5.4 里的到期日与 §24.1 的指针 |

---

## 25. 风险与雷区（出事了从这里查）

| 雷区 | 会怎样 | 怎么防 |
|---|---|---|
| **入口超预算** | 正文超 5000 tokens ⇒ 技能被截断/加载失败 | 每次改动跑 `--stats`；**先删再加**；提交信息写净增数 |
| **分册互相引用** | 违反"一层深" ⇒ 路由表失效 | 第 12 项（`check_refs`） |
| **改了 `description`** | 触发率变化 ⇒ 技能不被加载 | 复跑 `evals/trigger-tests.md` 并回填实测 |
| **改了纪律条款** | 红测失去区分度 ⇒ 纪律变成空话 | 复跑 `evals/red-tests.md`；基线未红要**如实写"无区分度"** |
| **误报口径混用** | 不同分母混着说 ⇒ 结论自相矛盾 | §6 的口径表；第 22 项核加法 |
| **规则改宽** | 误报回潮 | 靶场 + 语料逐条对比；**A/B 要重建基线**再比 |
| **在 C 盘留产物** | 违反"产出不出盘" | 产物一律写草稿区；用完即清并**回报残留** |
| **草稿区混进提交** | 临时脚本进仓 ⇒ 污染分发 | `git add <点名文件>`，**不用 `-A`** |
| **计划外的脏文件潜伏** | 别人（或上一轮自己）的改动一直躺在工作树里 | 提交前跑 `plan_check.py --plan <清单>`（§24.3 步骤 1；E51 的机器闸） |
| **在别的会话/别的仓库上动手** | 干扰别的项目 | 见 §24.2 |
| **把"预计会好"当"做成了"** | 交付不可信 | 铁律：**没有本回合新鲜运行的证据 ⇒ 不得宣称完成** |

---

> 本节与 §1–§14 的关系：**§0–§14 是"现在是什么"（随实现更新）**；
> **§15–§25 是"为什么这样、接下来怎么走"（相对稳定）**。
> ⚠️ **"相对稳定"不等于"不会过期"** ⇒ 这两段同样要过第 12/23 项（表格结构 ＋ 标记区对账）
> ——**它们也在被守**。
> ⚠️ 本节**不重复** §0–§14 的正文：同一件事只写一处，其余**指向**；
> 任何"每轮都变的数"一律**现查**（命令见 §21.3）。
