# 进化账本（evolution log）—— 将作 jiangzuo

> 一条变异一行。**没记账的变更视为未发生。** 结论只允许 `KEEP` / `ROLLBACK` / `WATCH`。
> 流程与判据见 `references/self-evolution.md`；本文件随仓库分发，是技能自我约束的公开证据。

| 日期 | 证据（来自哪次留痕） | 归因 | 假设（可证伪） | 变异 | 验证（命令 + 结果） | 行数收支 | 结论 |
|---|---|---|---|---|---|---|---|
| 2026-10-07 | 触发测试首跑正例 1/19、总体 6/24 | 规则没送达：description 尾部被清单 ~299 字符截断，触发词与竞争定位句会话根本没看到 | 把竞争定位与触发词放进 299 可见预算后，正例召回应上升 | SKILL.md description 373→241、when_to_use 压到 46；validate 新增 299 预算检查 | 新会话逐字抄回条目证实截断；24 条复跑：正例 2/19、反例 5/5、总体 7/24 | +0 / −132 | **KEEP（部分成立）**：夺回 #19 一例，但远未达 90%；瓶颈改判为加载竞争与 SessionStart 注入，非措辞 |
| 2026-10-07 | 测试会话 #12 报"preflight 抓不到 `github_pat_`" | 检测规则缺形态 | 扩规则后 fine-grained 与 classic 两种都报，且占位符不误报 | preflight.py GitHub 规则一行 | 红：只报 ghp_；绿：两种都报（critical/high=2）；`github_pat_11xxxx…` 仍不报 | +2 / −1 | KEEP |
| 2026-10-07 | 会话工具输出里 project_scan 中文整段乱码 | 脚本未设 stdout UTF-8（CI 在 Linux 不暴露） | 五个脚本统一 reconfigure 后 Windows 控制台输出应可读 | validate/preflight/project_scan/lookup/new_doc | 实跑三脚本，中文输出正常；validate 0 错 0 警 | +10 / −0 | KEEP |
| 2026-10-14 | 任务评测基线臂留下 `_verify*`、`server.log`、`tools/`；两臂 verify-log 有缺失 | 执行没验证：收尾是五步人工清单，没有判据 | 把收尾做成一条命令，缺项即非零退出，则残留与无证据交付会被当场拦下 | 新增 scripts/ship_check.py + templates/definition-of-done.md，CI 加一步 | 12→18 用例；`ship_check --level L1` SHIP-OK；L2 缺报告时 exit 1 | 新增 251 行脚本 | KEEP |
| 2026-10-14 | 我自己把"看不到改动"当成"子代理编造验证"，一周后复核发现是取样过早 | 规则缺可证伪锚：报告里没有"主张"，就无法核对到底该看到什么 | 报告强制一句可证伪主张后，闸门应能拦住没有主张的交付 | delivery-report.md §0 + ship_check REPORT_KEYS | **真红一次**：绿测夹具因缺主张失败 → 改夹具复绿；缺主张时输出「缺：主张（可证伪）」exit 1 | +6 / −0 | KEEP；同时把"并发写者未收尾时不得据看不到下结论"记入长期记忆 |
| 2026-10-14 | 规则只增不减的担忧无度量 | 缺观测层：不知道该改哪条，容易凭印象加规则 | 给出一套只读信号采集后，应能从现有留痕里产出可排序候选 | 新增 references/self-evolution.md + scripts/evolve_report.py + templates/evolution-log.md | 自跑本仓库产出 7 项真候选（含"入口超预算 112"）；18→21 用例全绿 | 新增 1 分册 + 231 行脚本 | KEEP |
| 2026-10-14 | 自然短语查 lookup 直接"无命中"（实测 0/17），且 BOOKLET_ALIASES 定义了从未参与打分 | 检索层没做中文切词 + 词表成死数据 + 新分册未登记 | 两段式检索（整词优先→2-gram 重试）＋别名加权＋df 泛词过滤后，top-1 应全部命中，且无意义查询仍应诚实报无命中 | lookup.py 检索层 + validate 第 8 项（分册必须登记词表） | 0/17 → **17/17**；`xyzzy不存在的词` 恢复无命中 exit 1；23 用例全绿 | 正文 −121（顺带还清预算债 4991） | KEEP |

## 回看

- 上表 7 条变异全部 `KEEP`，无 `ROLLBACK`；其中 1 条（description 修复）是**部分成立**——收益远小于预期，已把方向从"继续磨措辞"改判为"竞争定位挪到安装引导"。
- 两条 `WATCH`：① 行为层是否真的写下可证伪主张（需可控评测环境）；② 分册读取频率审计（需 harness 层 hook，本地工具，不可便携）。
