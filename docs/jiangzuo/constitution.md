# 项目常驻标准（Definition of Done）：将作 jiangzuo

> 每次改动都要过的**常驻**门槛，与单次任务的验收标准叠加。
> 改这份标准本身要走 ADR 并在 CHANGELOG 说明理由。
> 本仓库自己就是被这个技能约束的对象——做不到就别拿去要求别人的项目。

- [ ] 全量测试通过：`python -m unittest discover -s tests -q`（0 失败；新增脚本必须带 --help 冒烟与至少一个"能变红"的测试）
- [ ] 结构校验通过：`python scripts/validate_skill.py .`（0 错误 0 警告；含 17 分册骨架契约、299 字符可见预算、README 计数一致性）
- [ ] 交付前静态检查：`python scripts/preflight.py --all --strict`（critical/high = 0）
- [ ] 交付闸门：`python scripts/ship_check.py --level L1`（技能仓库自身按 L1 过闸）
- [ ] 入口预算：`python scripts/validate_skill.py . --stats` 的**正文 ≤5K tokens**，超了必须先删再加并在提交信息里写明净增数
- [ ] 改了 `description`：按 CONTRIBUTING 复跑 `evals/trigger-tests.md` 全部用例并回填实测记录
- [ ] 改了纪律条款：复跑 `evals/red-tests.md` 相关场景，记录是否仍具判别力（基线未红要如实写"无区分度"）
- [ ] 无试验残留：探针脚本、副本库、日志已删除（`ship_check.py` 自净核对）
- [ ] 外向操作（推送、打 tag、改仓库设置）先向用户说明并取得同意
