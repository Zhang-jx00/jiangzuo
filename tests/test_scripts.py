#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""脚本冒烟测试 —— 将作 (jiangzuo)

K-Dense 铁律："a skill with untested scripts cannot land"。
用 stdlib unittest 对 scripts/ 全部脚本做黑盒冒烟：真实子进程调用，
断言退出码与关键输出片段。CI 在 validate.yml 中执行：
    python -m unittest discover -s tests -v

仅使用 Python 标准库（3.8+）。
"""
import glob
import importlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
PY = sys.executable or "python"

SCRIPT_NAMES = ["audit_graph.py", "audit_index.py", "audit_map.py", "audit_rules.py",
                "review_packet.py",
                "audit_scan.py", "evolve_report.py", "lookup.py", "new_doc.py",
                "preflight.py", "project_scan.py", "sarif_schema_extract.py",
                "ship_check.py", "validate_skill.py"]


def run(args, cwd=REPO):
    return subprocess.run([PY] + args, cwd=cwd, timeout=180,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          encoding="utf-8", errors="replace")


class TestHelp(unittest.TestCase):
    """每个脚本 --help 必须退出码 0（中文帮助信息不崩）。"""

    def test_help_exit_zero(self):
        for name in SCRIPT_NAMES:
            with self.subTest(script=name):
                r = run([os.path.join(SCRIPTS, name), "--help"])
                self.assertEqual(r.returncode, 0, "%s --help 失败：%s" % (name, r.stdout))
                self.assertIn("将作", r.stdout)


class TestValidate(unittest.TestCase):
    def test_validate_passes_on_self(self):
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("0 条错误", r.stdout)

    def test_validate_stats(self):
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), ".", "--stats"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("占用报告", r.stdout)
        self.assertIn("常驻", r.stdout)

    def test_validate_flags_over_budget_entry(self):
        """红测：正文超预算必须 exit 1。这条先前只是文档里的一句话，
        于是"再加一小段"一路把正文推到 5124 都没人拦——禁忌要有机器判据才不会复发。"""
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
                        u"汉字" * 3000 + u"\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0, u"超预算没拦住：%s" % r.stdout)
            self.assertIn("tokens", r.stdout)
            self.assertIn(u"超预算", r.stdout)

    def test_validate_flags_stale_entry_line_count_in_readme(self):
        """README 里写死的"SKILL.md 多少行"必须跟着**正文行数**走。

        2026-10-16 复核实物撞出来：README 写 220 行，文件其实 211 行——
        同一条"文档计数滞后"的坑，脚本/模板/分册三样早已有闸，唯独入口行数没有。

        ⚠️ E36 再修一层：**上限 500 约束的是正文（frontmatter 之后）**，
        所以真源必须是**正文行数**；旧实现拿**文件总行数**当真源
        ⇒ 文档只好写总行数 ⇒ **一道在逼人说假话的锁**（说真话反而被判错）。
        ⇒ 本测试因此比原来更强：写**总行数**必须被红，写**正文行数**才过。
        """
        body = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
                u"第一行正文。\n第二行正文。\n第三行正文。\n")
        total_lines = len(body.splitlines())
        body_lines = 3
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(body)
            # 红：写**文件总行数**（旧实现的"真源"）⇒ 必须被红
            with io.open(os.path.join(tmp, "README.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# demo\n\n- SKILL.md 正文 %d 行（上限 500）\n" % total_lines)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"README 入口行数写错却没拦住：%s" % r.stdout)
            self.assertIn(u"入口行数", r.stdout)
            # 绿：写**正文行数**（真源）⇒ 过
            with io.open(os.path.join(tmp, "README.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# demo\n\n- SKILL.md 正文 %d 行（上限 500）\n" % body_lines)
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_validate_flags_future_changelog_date(self):
        """CHANGELOG 的日期只能从真实日历抄。复核时发现四条写着"明天"——
        系统日期 2026-10-15，条目却是 2026-10-16，没有任何一道闸拦得住这种笔误。
        这条锁要同时证明两件事：晚于今天的日期必须报错，今天/过去的必须放过。"""
        import time
        today = time.strftime("%Y-%m-%d")
        future = time.strftime("%Y-%m-%d", time.localtime(time.time() + 86400))
        past = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
        fm = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
              u"正文一句。\n")
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(fm)
            with io.open(os.path.join(tmp, "CHANGELOG.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# 更新日志\n\n## [0.0.1] - %s\n\n内容。\n" % future)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"未来日期没拦住：%s" % r.stdout)
            self.assertIn(u"未来日期", r.stdout)
            # 反面：当天与过去的日期不该被误拦
            with io.open(os.path.join(tmp, "CHANGELOG.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# 更新日志\n\n## [0.0.1] - %s\n\n## [0.0.0] - %s\n\n内容。\n"
                        % (today, past))
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertNotIn(u"未来日期", ok.stdout)

    def test_validate_cross_checks_changelog_date_against_git(self):
        """条目日期必须能在 git 里找到落笔那天。
        复核时实测有 8 条对不上（0.23–0.29 写 10-14、提交在 10-15；0.6.0 写 10-05、提交 10-06），
        而"晚于今天就报错"那道闸完全拦不住这种"差一天"的错——方向相反也要有判据。
        规则：条目日期 ∈ 该版本号在 git 提交信息里出现的那些提交日期集合；
        没有对应提交（纯文档轮、没写版本号）就不判，别把校验器锁死在理想仓库上。
        夹具用**过去的固定日期**：否则会被"未来日期"那道闸先拦掉，测不到这条本身。"""
        with tempfile.TemporaryDirectory() as tmp:
            def git(*a):
                r = subprocess.run(["git"] + list(a), cwd=tmp, timeout=60,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(r.returncode, 0, r.stdout.decode("utf-8", "replace"))

            fm = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.2.0\n---\n"
                  u"正文一句。\n")
            def put(rel, text):
                with io.open(os.path.join(tmp, rel), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(text)

            put("SKILL.md", fm)
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "test")
            # 用固定时间戳造两笔提交：v0.1.0 在 01-01，v0.2.0 在 01-03
            env = dict(os.environ,
                       GIT_AUTHOR_DATE="2026-01-01T10:00:00 +0800",
                       GIT_COMMITTER_DATE="2026-01-01T10:00:00 +0800")

            def commit_with(subject, date):
                d = dict(env, GIT_AUTHOR_DATE=date + "T10:00:00 +0800",
                         GIT_COMMITTER_DATE=date + "T10:00:00 +0800")
                p = subprocess.Popen(["git", "commit", "-q", "--allow-empty", "-m", subject],
                                     cwd=tmp, env=d, stdout=subprocess.PIPE,
                                     stderr=subprocess.STDOUT)
                out, _ = p.communicate(timeout=60)
                self.assertEqual(p.returncode, 0, out.decode("utf-8", "replace"))

            commit_with("feat: v0.1.0 demo", "2026-01-01")
            commit_with("feat: v0.2.0 demo", "2026-01-03")
            # 红：v0.2.0 写成 01-02（提交日期集合里没有这一天）
            put("CHANGELOG.md", u"# 更新日志\n\n## [0.2.0] - 2026-01-02\n\n内容。\n\n"
                                u"## [0.1.0] - 2026-01-01\n\n内容。\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"条目日期与 git 不符却放行：%s" % r.stdout)
            self.assertIn(u"git 提交日期", r.stdout)
            self.assertIn(u"0.2.0", r.stdout)
            # 绿：改回提交那天
            put("CHANGELOG.md", u"# 更新日志\n\n## [0.2.0] - 2026-01-03\n\n内容。\n\n"
                                u"## [0.1.0] - 2026-01-01\n\n内容。\n")
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_validate_flags_stale_rule_counts_in_readme(self):
        """README 写死的规则条数也要有闸——E1 加了两条规则后才发现它写的是"30 条"，
        实物已是 34 条（含 1 条数据停用）；这个数不在 validate 的计数核对里，没人报红。
        同一条病根第三次复发：写死的数字没判据，改的时候没人提醒。"""
        body = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
                u"正文一句。\n")
        one = (u'{"id": "JZ-T-%d", "title": "t", "kind": "pattern", "severity": "high",'
               u' "languages": ["python"], "cwe": ["CWE-1"], "sinks": [{"pattern": "x%d"}],'
               u' "fix": "f", "retest": "r"}')
        with tempfile.TemporaryDirectory() as tmp:
            rules_dir = os.path.join(tmp, "scripts", "audit-rules")
            os.makedirs(rules_dir)
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(body)
            doc = (u'{"schema": "jiangzuo-audit-rules/1", "name": "t", "rules": [%s, %s, '
                   u'{"id": "JZ-T-3", "title": "停用", "kind": "pattern", "severity": "low", '
                   u'"enabled": false, "languages": ["python"], "cwe": ["CWE-1"], '
                   u'"sinks": [{"pattern": "x3"}], "fix": "f", "retest": "r"}]}\n')
            with io.open(os.path.join(rules_dir, "t.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(doc % (one % (1, 1), one % (2, 2)))
            # 红：README 写 99 条 / 9 条停用，实物 3 条 / 1 条停用
            with io.open(os.path.join(tmp, "README.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# demo\n\n内置规则库：99 条声明式规则（含 9 条数据停用）\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"README 规则条数写错却没拦住：%s" % r.stdout)
            self.assertIn(u"规则条数", r.stdout)
            # 两支各自都要有牙：只写错总条数（停用数写对）与只写错停用数（总条数写对）
            # ——第一版校准暴露出"废掉总条数那一支测试照样绿"，因为两支共用一句报错。
            for wrong_total, wrong_disabled, label in [
                    (99, 1, u"总条数"), (3, 9, u"停用数")]:
                with io.open(os.path.join(tmp, "README.md"), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(u"# demo\n\n内置规则库：%d 条声明式规则（含 %d 条数据停用）\n"
                            % (wrong_total, wrong_disabled))
                one_side = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
                self.assertNotEqual(one_side.returncode, 0,
                                    u"只写错%s那一支没被拦住：%s" % (label, one_side.stdout))
                self.assertIn(u"规则条数", one_side.stdout)
            # 绿：改成实物数
            with io.open(os.path.join(tmp, "README.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# demo\n\n内置规则库：3 条声明式规则（含 1 条数据停用）\n")
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_validate_flags_eaten_table_row_head(self):
        """表格行的行头被吃掉，必须当场红——这条我在 2026-10-16 又犯了一次
        （往账本插行时拿下一行的行头当锚点、没写回，E1 那条的行头没了）。
        症状很特征：那行仍然是 `a | b | c` 的形状，只是开头少了 `| `。
        判据不能只看"开头是 | 的行"，否则整行会被当成普通段落放过。"""
        head = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
                u"正文一句。\n")
        good = (u"# 台账\n\n| 日期 | 结论 |\n|---|---|\n"
                u"| 2026-01-01 | KEEP |\n| 2026-01-02 | KEEP |\n")
        broken = (u"# 台账\n\n| 日期 | 结论 |\n|---|---|\n"
                  u"| 2026-01-01 | KEEP |\n：行头被吃掉的一行 | KEEP |\n")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(head)
            with io.open(os.path.join(tmp, "docs", "ledger.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(broken)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"行头被吃却没拦住：%s" % r.stdout)
            self.assertIn(u"行头", r.stdout)
            with io.open(os.path.join(tmp, "docs", "ledger.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(good)
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_validate_flags_declared_table_count_mismatch(self):
        """文档里写"上表 N 条"就必须真数得出 N——账本这条我手抄错过一次（27 vs 28）。
        只在"该文件只有一张表"时判，多表文件不猜（判据别假定数据形状）。"""
        head = (u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n"
                u"正文一句。\n")
        body = (u"# 台账\n\n| 日期 | 结论 |\n|---|---|\n"
                u"| 2026-01-01 | KEEP |\n| 2026-01-02 | KEEP |\n\n- 上表 %s 条变异台账\n")
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "docs"))
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(head)
            with io.open(os.path.join(tmp, "docs", "ledger.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(body % u"9")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"声明条数与表格实际行数不符却没红：%s" % r.stdout)
            self.assertIn(u"条数", r.stdout)
            with io.open(os.path.join(tmp, "docs", "ledger.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(body % u"2")
            ok = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_entry_keeps_iron_law_scope_and_gate(self):
        """入口必须留着这两件行为判据（B6 加的），删掉就该红：
        ① 铁律的**范围声明**（同义改写与暗示同样违规）；
        ② 必验证的**门函数**（五步，跳一步＝没验证）。
        没有这条锁，将来谁压缩入口时把它们当废话删掉都不会有人知道。"""
        with io.open(os.path.join(REPO, "SKILL.md"), encoding="utf-8") as f:
            body = f.read()
        self.assertIn(u"同义改写与暗示同样违规", body, u"铁律范围句被删了")
        self.assertIn(u"必验证＝门函数", body, u"验证门函数声明被删了")
        for step in (u"①点命令", u"②全量跑", u"③读到底", u"④对得上吗", u"⑤才下结论"):
            self.assertIn(step, body, u"门函数少了第 %s 步" % step)
        self.assertIn(u"回执只收四态", body, u"子代理四态合同被删了")
        for state in (u"DONE", u"CONCERNS", u"NEEDS_CONTEXT", u"BLOCKED"):
            self.assertIn(state, body, u"四态少了 %s" % state)

    def test_validate_detects_broken_ref(self):
        """红测：制造一个不存在的引用，校验器必须报错。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill = os.path.join(tmp, "sk")
            os.makedirs(os.path.join(skill, "references"))
            with io.open(os.path.join(skill, "SKILL.md"), "w",
                         encoding="utf-8") as f:
                f.write("---\nname: sk\ndescription: 测试\n---\n见 references/ghost.md\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), skill])
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("ghost.md", r.stdout)

    def test_validate_detects_stale_readme_counts(self):
        """红测：README 写"4 个脚本"而实际 2 个 → 必须报出计数不符（防文档滞后）。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill = os.path.join(tmp, "sk")
            os.makedirs(os.path.join(skill, "scripts"))
            for name in ("a.py", "b.py"):
                with io.open(os.path.join(skill, "scripts", name), "w", encoding="utf-8") as f:
                    f.write("pass\n")
            with io.open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: sk\ndescription: 测试\n---\n正文\n")
            with io.open(os.path.join(skill, "README.md"), "w", encoding="utf-8") as f:
                f.write("# sk\n\nscripts/  # 4 个纯标准库脚本\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), skill])
            self.assertIn("README 计数与实物不符", r.stdout)

    def test_validate_detects_unparsable_readme_count(self):
        """红：README 声明了计数却**写不出数字** ⇒ 必须报（不许静默跳过）。

        E34 实测：批量改文档时用了占位符（`{{SCRIPTS}} 个纯标准库脚本`），
        而这道闸的正则匹配不上 ⇒ 老实现 `continue` 跳过 ⇒ **闸自己静默失效**，
        而看上去还是"全绿"⇒ **一条永远绿的锁比没有锁更坏**。
        ⇒ 现在：声明了概念却写不出数字 ⇒ 报错。
        """
        with tempfile.TemporaryDirectory() as tmp:
            skill = os.path.join(tmp, "sk")
            os.makedirs(os.path.join(skill, "scripts"))
            for name in ("a.py", "b.py"):
                with io.open(os.path.join(skill, "scripts", name), "w", encoding="utf-8") as f:
                    f.write("pass\n")
            with io.open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: sk\ndescription: 测试\n---\n正文\n")
            with io.open(os.path.join(skill, "README.md"), "w", encoding="utf-8") as f:
                f.write("# sk\n\nscripts/  # {{SCRIPTS}} 个纯标准库脚本\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), skill])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"写不出数字", r.stdout)

    def test_validate_detects_stale_expected_info_count(self):
        """红：代码块里写「期望 N 条信息」而实际条数不是 N ⇒ 必须红。

        E34 实测：这句话在交接文档里有**两处**且**已经过期**（写着 20，实际 23），
        而第 14 项的期望值核对**不认这一形态** ⇒ 没人守 ⇒ 只能过期。
        ⇒ 补上这道对账（扫代码块里的「期望 N 条信息」）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            skill = os.path.join(tmp, "sk")
            os.makedirs(skill)
            with io.open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: sk\ndescription: 测试\n---\n正文\n")
            with io.open(os.path.join(skill, "docs.md"), "w", encoding="utf-8") as f:
                f.write("# sk\n\n```bash\npython scripts/validate_skill.py ."
                        "   # 期望：99 条信息 / 0 警告 / 0 错误\n```\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), skill])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"条信息", r.stdout)

    def test_validate_readme_counts_match_on_self(self):
        """绿测：本仓库 README 的脚本/模板/分册计数必须与实物一致。"""
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertIn("README 计数与实物一致", r.stdout)


class TestValidateExpectedNumbers(unittest.TestCase):
    """第 11 节第 9 项：.md **代码块**里"复制即跑"的期望值必须与实物对账。

    E7 实测的教训：验收记录里"本仓库自扫 结论 0"这个**对照面基线**从 v0.37.0 起
    就一直是错的，错了一整轮没人发现——因为**没有任何判据把文档里的数字和实物对账**。
    错的是基线，所以它不会让任何检出看起来更好，只会让人拿一把坏尺子量别人。

    真源三件，全部**静态取**（不跑扫描、不生成语料、不执行被测脚本 ⇒ 跨平台同色）：
      用例数 ← unittest 的用例计数；语料分母 ← gen_corpus.py 的两个清单长度；
      规则条数 ← scripts/audit-rules/*.json 的条目数与停用数。
    """

    HEAD = u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n正文一句。\n"
    GOOD = (u"# 期望\n\n```bash\n"
            u"python -m unittest discover -s tests    # 期望 Ran 2 tests ... OK\n"
            u"python evals/audit-fixtures/score.py --corpus ../c    "
            u"# ACCEPT-OK 2/2 检出 & 0/3 安全样本\n"
            u"python scripts/audit_rules.py --validate    "
            u"# 期望 RULES-OK（2 条，另有 1 条数据停用）\n"
            u"```\n")

    def _mini(self, tmp, md_text):
        """建一个最小技能目录：真源三件 + 一份带期望值的 .md。"""
        sk = os.path.join(tmp, "sk")
        for d in ("docs", "tests", os.path.join("evals", "audit-fixtures"),
                  os.path.join("scripts", "audit-rules")):
            os.makedirs(os.path.join(sk, d))

        def put(rel, text):
            path = os.path.join(sk, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        put("SKILL.md", self.HEAD)
        # 真源①：一个测试文件 → 用例数 = 2
        put("tests/test_x.py",
            u"import unittest\n\n\nclass T(unittest.TestCase):\n"
            u"    def test_a(self):\n        pass\n\n"
            u"    def test_b(self):\n        pass\n")
        # 真源②：语料清单 → MUST_FIND 2 条、MUST_NOT_FIND 3 条
        put("evals/audit-fixtures/gen_corpus.py",
            u"MUST_FIND = [(\"a.py\", \"JZ-A-001\", \"x\"), (\"b.py\", \"JZ-B-001\", \"y\")]\n"
            u"MUST_NOT_FIND = [(\"s1.py\", \"JZ-A-001\"), (\"s2.py\", \"JZ-B-001\"),"
            u" (\"s3.py\", \"JZ-C-001\")]\n")
        # 真源③：规则库 → 活跃 2 条、停用 1 条
        put("scripts/audit-rules/a.json",
            u"{\"rules\": [{\"id\": \"JZ-A-001\"}, {\"id\": \"JZ-B-001\"},"
            u" {\"id\": \"JZ-C-001\", \"enabled\": false}]}")
        put("docs/expect.md", md_text)
        return sk

    def _validate(self, sk):
        return run([os.path.join(SCRIPTS, "validate_skill.py"), sk])

    def test_wrong_expected_numbers_are_flagged(self):
        """红：三类期望值各写错一个，必须当场红并点名错在哪；绿：改回实物数就过。"""
        cases = [
            (u"Ran 2 tests", u"Ran 99 tests", u"个用例"),
            (u"ACCEPT-OK 2/2 检出 & 0/3 安全样本",
             u"ACCEPT-OK 2/2 检出 & 0/9 安全样本", u"安全对照"),
            (u"ACCEPT-OK 2/2 检出 & 0/3 安全样本",
             u"ACCEPT-OK 2/3 检出 & 0/3 安全样本", u"应检出"),
            (u"ACCEPT-OK 2/2 检出 & 0/3 安全样本",
             u"ACCEPT-OK 1/2 检出 & 0/3 安全样本", u"分子分母不等"),
            (u"RULES-OK（2 条，另有 1 条数据停用）",
             u"RULES-OK（7 条，另有 1 条数据停用）", u"活跃"),
            (u"RULES-OK（2 条，另有 1 条数据停用）",
             u"RULES-OK（2 条，另有 5 条数据停用）", u"停用"),
        ]
        for good, wrong, label in cases:
            with tempfile.TemporaryDirectory() as tmp:
                sk = self._mini(tmp, self.GOOD.replace(good, wrong))
                r = self._validate(sk)
                self.assertNotEqual(r.returncode, 0,
                                    u"写错「%s」没被拦住：%s" % (label, r.stdout))
                self.assertIn(label, r.stdout)
        # 绿：三类都写对 → 通过
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, self.GOOD)
            r = self._validate(sk)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_history_numbers_outside_code_blocks_are_not_flagged(self):
        """反面：正文/表格里的历史数字是**当时真值**，不该被红。

        交付报告 §3 的 "Ran 124 tests" 是 v0.36.1 当时的数——判据只管代码块里
        "复制即跑"的契约，管到历史记录上就是误伤。
        """
        with tempfile.TemporaryDirectory() as tmp:
            body = self.GOOD + u"\n历史记录：当时是 Ran 124 tests、ACCEPT-OK 16/16 检出。\n"
            sk = self._mini(tmp, body)
            r = self._validate(sk)
            self.assertEqual(r.returncode, 0, r.stdout)

    def test_missing_expectation_form_is_flagged(self):
        """形态被删掉也要红——删一行就等于把这条检查静默关掉，那是"永远绿的锁"。"""
        with tempfile.TemporaryDirectory() as tmp:
            body = self.GOOD.replace(
                u"python scripts/audit_rules.py --validate    "
                u"# 期望 RULES-OK（2 条，另有 1 条数据停用）\n", u"")
            sk = self._mini(tmp, body)
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0,
                                u"形态被删却没拦住：%s" % r.stdout)
            self.assertIn(u"静默失效", r.stdout)


class TestPreflight(unittest.TestCase):
    def test_preflight_clean_on_self(self):
        r = run([os.path.join(SCRIPTS, "preflight.py"), "--all", "--strict"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("RESULT: PASS", r.stdout)

    def test_preflight_catches_secret(self):
        """红测：含假密钥的文件必须被抓到。"""
        # 动态拼接夹具令牌：避免测试源码自身命中本仓库 preflight 的密钥规则
        fake_token = "ghp_" + "A1b2C3d4E5" * 3
        self.assertRegex(fake_token, r"^ghp_[A-Za-z0-9]{30}$")  # 夹具有效性自检
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "app.js"), "w", encoding="utf-8") as f:
                f.write('const k = "%s";\n' % fake_token)
            r = run([os.path.join(SCRIPTS, "preflight.py"), tmp, "--all"])
            self.assertEqual(r.returncode, 0)  # 非 --strict 只报告
            self.assertIn("GitHub Token", r.stdout)
            self.assertIn("RESULT: FAIL", r.stdout)


class TestLookup(unittest.TestCase):
    def test_hit(self):
        r = run([os.path.join(SCRIPTS, "lookup.py"), "迁移", "回滚"])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("database.md", r.stdout)

    def test_no_match(self):
        r = run([os.path.join(SCRIPTS, "lookup.py"), "xyzzy不存在的词"])
        self.assertEqual(r.returncode, 1)
        self.assertIn("无命中", r.stdout)


class TestNewDoc(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(lambda: subprocess.run(
            ["rm", "-rf", self.tmp]) if os.name != "nt" else None)

    def test_generate_and_protect(self):
        script = os.path.join(SCRIPTS, "new_doc.py")
        r = run([script, "plan", "冒烟测试任务", "--dir", self.tmp])
        self.assertEqual(r.returncode, 0, r.stdout)
        plans = glob.glob(os.path.join(self.tmp, "docs", "jiangzuo", "plans", "*.md"))
        self.assertEqual(len(plans), 1)
        content = io.open(plans[0], encoding="utf-8").read()
        self.assertIn("冒烟测试任务", content)      # {{TITLE}} 已替换
        self.assertNotIn("{{TITLE}}", content)
        # 防覆盖：同参数再次生成必须被拒绝
        r2 = run([script, "plan", "冒烟测试任务", "--dir", self.tmp])
        self.assertEqual(r2.returncode, 2, r2.stdout)

    def test_learning_appends(self):
        script = os.path.join(SCRIPTS, "new_doc.py")
        run([script, "learning", "第一条", "--dir", self.tmp])
        path = os.path.join(self.tmp, "docs", "jiangzuo", "learnings.md")
        self.assertTrue(os.path.isfile(path))
        before = io.open(path, encoding="utf-8").read()
        run([script, "learning", "第二条", "--dir", self.tmp])
        after = io.open(path, encoding="utf-8").read()
        self.assertIn("第一条", before)
        self.assertIn("第二条", after)
        self.assertGreater(len(after), len(before))


class TestProjectScan(unittest.TestCase):
    def test_detects_node_stack(self):
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "package.json"), "w",
                         encoding="utf-8") as f:
                json.dump({"name": "demo", "dependencies": {"react": "^18.0.0"}}, f)
            r = run([os.path.join(SCRIPTS, "project_scan.py"), tmp])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("React", r.stdout)
            self.assertIn("demo", r.stdout)

    def test_missing_dir(self):
        r = run([os.path.join(SCRIPTS, "project_scan.py"),
                 os.path.join(tempfile.gettempdir(), "不存在的目录xyzzy")])
        self.assertEqual(r.returncode, 2)


class TestEvolveReport(unittest.TestCase):
    """进化信号采集器：要能认出真信号，也不能被无关的"作废"字样骗到。"""

    @staticmethod
    def _write(root, rel, text):
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def test_flags_high_confidence_learning(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "docs/jiangzuo/learnings.md",
                        "# 经验教训\n\n- [2026-10-01] 情境：改契约 教训：三处同批改 置信度：高\n"
                        "- [2026-10-02] 情境：改契约 教训：三处同批改 置信度：高\n")
            r = run([os.path.join(SCRIPTS, "evolve_report.py"), tmp])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("高置信度教训", r.stdout)
            self.assertIn("EVOLVE-CANDIDATES", r.stdout)

    def test_ignores_unrelated_void_wording(self):
        """精确度回归：任务描述里的"作废（搜索逻辑）"不是评测失效信号。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "evals/red-tests.md",
                        "- [ ] 停手，先盘点：哪些可复用、哪些作废（搜索逻辑）\n")
            r = run([os.path.join(SCRIPTS, "evolve_report.py"), tmp])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("0 条失效标记", r.stdout)

    def test_empty_project_reports_no_signals(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run([os.path.join(SCRIPTS, "evolve_report.py"), tmp])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("EVOLVE-NONE", r.stdout)


class TestShipCheck(unittest.TestCase):
    """交付闸门：绿（齐全→SHIP-OK）与红（缺项→SHIP-BLOCKED）配对。

    只测绿不测红，闸门就会退化成永远通过的摆设——所以每种缺项都要能把它打黑。
    """

    REPORT_OK = (
        "# 交付报告：demo\n\n## 0. 主张\n在 1 万行数据下 add() 结果与旧实现逐字段一致。\n\n"
        "## 改了什么\n新增 add()。\n\n## 为什么\n"
        "用户要加法。\n\n## 怎么验证的\npython -m unittest → OK\n\n"
        "## 剩余风险\n无。\n\n复用阶梯：停在 2——仓库已有 calc 模块，直接扩展。\n")

    REPORT_NO_RISK = ("# 交付报告：demo\n\n## 改了什么\n新增 add()。\n\n"
                      "## 为什么\n要加法。\n\n## 怎么验证的\n跑过测试\n\n"
                      "复用阶梯：停在 2\n")

    def _proj(self, tmp, report=None, with_tests=True):
        os.makedirs(os.path.join(tmp, "docs", "jiangzuo", "reports"))
        with io.open(os.path.join(tmp, "docs", "jiangzuo", "constitution.md"),
                     "w", encoding="utf-8") as f:
            f.write("# 常驻标准\n\n- [ ] 全量测试：python -m unittest\n"
                    "- [ ] 交付报告四问齐全\n- [ ] 无试验残留\n")
        if with_tests:
            os.makedirs(os.path.join(tmp, "tests"))
            with io.open(os.path.join(tmp, "tests", "test_ok.py"), "w", encoding="utf-8") as f:
                f.write("import unittest\n\n\nclass T(unittest.TestCase):\n"
                        "    def test_ok(self):\n        self.assertTrue(True)\n")
        if report is not None:
            with io.open(os.path.join(tmp, "docs", "jiangzuo", "reports",
                                      "2026-01-01-delivery-demo.md"), "w", encoding="utf-8") as f:
                f.write(report)

    def test_green_when_complete(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._proj(tmp, report=self.REPORT_OK)
            r = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("SHIP-OK", r.stdout)

    def test_red_when_risk_section_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._proj(tmp, report=self.REPORT_NO_RISK)
            r = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("剩余风险", r.stdout)

    def test_red_when_no_test_channel(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._proj(tmp, report=self.REPORT_OK, with_tests=False)
            r = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("测试通道", r.stdout)

    def test_report_must_actually_be_in_the_repository(self):
        """报告必须随仓库走。2026-10-15 复核实测：本仓库 .gitignore 的 `docs/jiangzuo/*`
        把 reports/ 整块挡住，两份交付报告**从未入库**，而 ship_check 连着几轮报
        「交付报告齐全」——闸门只看磁盘，就给「本地有、交付没有」开绿灯。
        两半都要测：被 ignore 时必须黑，放开并入库后必须绿（否则这条锁是在乱拦）。"""
        def put(root, rel, text):
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        with tempfile.TemporaryDirectory() as tmp:
            def git(*a):
                r = subprocess.run(["git"] + list(a), cwd=tmp, timeout=60,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
                self.assertEqual(r.returncode, 0, r.stdout.decode("utf-8", "replace"))

            self._proj(tmp, report=self.REPORT_OK)
            put(tmp, ".gitignore", "__pycache__/\n*.py[cod]\ndocs/jiangzuo/*\n")
            git("init", "-q", "-b", "main")
            git("config", "user.email", "t@example.com")
            git("config", "user.name", "test")
            git("add", "-A")
            git("commit", "-q", "-m", "base")
            tracked = subprocess.run(["git", "ls-files", "docs/jiangzuo/reports"],
                                     cwd=tmp, timeout=60, stdout=subprocess.PIPE)
            self.assertEqual(b"", tracked.stdout.strip(),
                             u"夹具没造出「报告存在但没入库」的状态，这条测不到东西")
            r = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(r.returncode, 1, u"报告没入库却放行了：%s" % r.stdout)
            self.assertIn(u"没有入库", r.stdout)
            # 放开 negation 并入库 → 必须转绿
            put(tmp, ".gitignore",
                "__pycache__/\n*.py[cod]\ndocs/jiangzuo/*\n!docs/jiangzuo/reports/\n")
            git("add", "-A")
            git("commit", "-q", "-m", "ship reports")
            ok = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(ok.returncode, 0, ok.stdout)
            self.assertIn("SHIP-OK", ok.stdout)

    def test_red_when_no_delivery_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._proj(tmp, report=None)
            r = run([os.path.join(SCRIPTS, "ship_check.py"), tmp, "--level", "L2"])
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("交付报告", r.stdout)


class TestRouting(unittest.TestCase):
    """检索层是"响应成本"的第一道闸：自然短语必须能 top-1 命中正确分册。

    回归背景：lookup 早期要求空格分开的同义词，agent 传"数据库迁移回滚"这类
    自然短语直接无命中，只能整册载入——路由失败 = token 白花。
    """

    CASES = [("数据库迁移回滚", "database"), ("越权鉴权漏洞", "security"),
             ("根因排查报错", "debugging"), ("接手陌生项目摸底", "onboarding"),
             ("验收标准怎么写", "requirements"), ("代码审查清单", "code-review"),
             ("慢查询性能优化", "refactor-performance"), ("上线部署检查", "devops"),
             ("测试金字塔分层", "testing"), ("组件拆分页面状态", "frontend"),
             ("技术选型决策记录", "design"), ("线上事故止血复盘", "incident"),
             ("交付报告文档同步", "docs-delivery"), ("协调其他技能分包商", "skill-orchestration"),
             ("接口契约字段命名", "api-design"), ("给技能加规则删规则", "self-evolution"),
             ("配色视觉排版走查", "ui-design"),
             ("整个项目有没有安全漏洞", "security-audit"),
             ("全项目体检出报告", "security-audit"),
             ("依赖漏洞排序", "security-audit"),
             # E2 拆册：新分册必须被自然短语够得着（否则登记了词表也等于没有），
             # 而"给技能加规则删规则"仍归 self-evolution——两条边界都用测试钉住。
             ("审计规则没生效排查", "audit-rule-authoring")]

    def test_natural_phrases_route_top1(self):
        misses = []
        for phrase, expected in self.CASES:
            r = run([os.path.join(SCRIPTS, "lookup.py"), phrase, "--top", "1"])
            got = re.search(r"## (\S+?)\.md", r.stdout)
            if not got or got.group(1) != expected:
                misses.append("%s → 期望 %s，实得 %s" % (
                    phrase, expected, got.group(1) if got else "无命中"))
        self.assertEqual([], misses, "自然短语路由失败 %d/%d" % (len(misses), len(self.CASES)))

    def test_validate_flags_unregistered_booklet(self):
        """红测：新加一本没登记路由词表的分册，校验器必须点名。"""
        with tempfile.TemporaryDirectory() as tmp:
            skill = os.path.join(tmp, "sk")
            os.makedirs(os.path.join(skill, "references"))
            os.makedirs(os.path.join(skill, "scripts"))
            with io.open(os.path.join(skill, "scripts", "lookup.py"), "w", encoding="utf-8") as f:
                f.write("BOOKLET_ALIASES = {\n    \"references/known.md\": \"已知 分册\",\n}\n")
            for name in ("known.md", "ghost-booklet.md"):
                with io.open(os.path.join(skill, "references", name), "w", encoding="utf-8") as f:
                    f.write("---\nname: sk\ndescription: d\n---\n")
            with io.open(os.path.join(skill, "SKILL.md"), "w", encoding="utf-8") as f:
                f.write("---\nname: sk\ndescription: 测试\n---\n正文\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), skill])
            self.assertIn("未登记进 lookup 路由词表", r.stdout)
            self.assertIn("ghost-booklet.md", r.stdout)


class TestAuditIndex(unittest.TestCase):
    """R2：文件索引与忽略模块——稳定、可复现、跳过要留痕。"""

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        mode = "wb" if isinstance(text, bytes) else "w"
        with io.open(path, mode, encoding=None if mode == "wb" else "utf-8") as f:
            f.write(text)

    def _tree(self, root):
        self._write(root, ".gitignore",
                    "# 注释\nbuild/\n*.log\n!keep.log\ndocs/*.tmp\n")
        self._write(root, "src/.gitignore", "secret*\n")
        self._write(root, "app.py", "print(1)\n")
        self._write(root, "main.ts", "let a = 1\n")
        self._write(root, "Service.java", "class Service {}\n")
        self._write(root, "build/out.js", "junk\n")
        self._write(root, "run.log", "junk\n")
        self._write(root, "keep.log", "kept\n")
        self._write(root, "docs/a.tmp", "junk\n")
        self._write(root, "docs/b.md", "kept\n")
        self._write(root, "src/secret_keys.py", "junk\n")
        self._write(root, "src/util.py", "kept\n")

    def _index(self, root, extra=None):
        out = os.path.join(root, "_idx.json")
        cmd = [os.path.join(SCRIPTS, "audit_index.py"), root,
               "--no-git", "--json", out]
        if extra:
            cmd += extra
        r = run(cmd)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_index_is_reproducible_and_sorted(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            first, _ = self._index(tmp)
            second, _ = self._index(tmp)
            self.assertEqual(first["index_sha1"], second["index_sha1"],
                             "同一棵树两次索引必须逐字节可复现")
            paths = [f["path"] for f in first["files"]]
            self.assertEqual(paths, sorted(paths), "清单顺序必须稳定（按路径排序）")
            self.assertIn("app.py", paths)

    def test_index_honors_ignore_rules_with_negation(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._index(tmp)
            paths = set(f["path"] for f in data["files"])
            for gone in ("build/out.js", "run.log", "docs/a.tmp", "src/secret_keys.py"):
                self.assertNotIn(gone, paths, "%s 应被忽略规则排除" % gone)
            for kept in ("keep.log", "docs/b.md", "src/util.py", ".gitignore"):
                self.assertIn(kept, paths, "%s 不该被误伤（!keep.log 取反/普通文件）" % kept)

    def test_index_records_skips_instead_of_silently_dropping(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            self._write(tmp, "asset.bin", b"\x00\x01\x02binary")
            self._write(tmp, "huge.py", "x = 1\n" * 400)  # >1KB
            data, _ = self._index(tmp, ["--max-file-kb", "1"])
            paths = set(f["path"] for f in data["files"])
            self.assertNotIn("asset.bin", paths)
            self.assertNotIn("huge.py", paths)
            reasons = dict((s["path"], s["reason"]) for s in data["skipped"])
            self.assertEqual("binary", reasons.get("asset.bin"))
            self.assertEqual("oversize", reasons.get("huge.py"))

    def test_index_emits_relative_posix_paths_only(self):
        """索引 JSON（要进报告、进 CI 缓存的机器可读产物）里不许出现本机绝对路径。

        2026-10-20 修好这条锁自己的两个错（CI 在 Linux 上红了六个版本才暴露）：
        1. 针被归一化成了正斜杠形式，而 Windows 上工具输出的是反斜杠形式——
           **两边永远对不上，这条断言在本机从来没有真正成立过**（假绿）。
        2. 比对的文本把 stdout 也算进去，而 stdout 回显的是调用方自己传进来的
           `--json` 落盘路径。Linux 上针恰好命中它，于是把"CLI 复述你的参数"
           判成泄露。回显参数不是泄露，产物里带绝对路径才是。
        """
        forms = []
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _stdout = self._index(tmp)
            blob = json.dumps(data, ensure_ascii=False)
            for cand in (tmp, os.path.abspath(tmp), os.path.realpath(tmp),
                         tmp.replace("\\", "/")):
                if cand and len(cand) > 3 and cand not in forms:
                    forms.append(cand)
            self.assertTrue(forms, "针为空等于没测")
            for form in forms:
                self.assertNotIn(form, blob,
                                 u"索引 JSON 里出现了本机绝对路径 %r（换机器就作废、可能含用户名）" % form)
            for rec in data["files"]:
                self.assertNotIn("\\", rec["path"])
                self.assertFalse(rec["path"].startswith("/"), rec["path"])
                self.assertFalse(os.path.isabs(rec["path"]), rec["path"])

    def test_index_hash_tracks_content_not_just_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            before, _ = self._index(tmp)
            self._write(tmp, "app.py", "print(2)\n")
            after, _ = self._index(tmp)
            self.assertNotEqual(before["index_sha1"], after["index_sha1"],
                                "内容哈希不进索引键，增量缓存就是假的")
            changed = [f for f in after["files"] if f["path"] == "app.py"][0]
            old = [f for f in before["files"] if f["path"] == "app.py"][0]
            self.assertNotEqual(changed["sha1"], old["sha1"])

    def test_index_maps_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._index(tmp)
            langs = dict((f["path"], f["lang"]) for f in data["files"])
            self.assertEqual("python", langs["app.py"])
            self.assertEqual("typescript", langs["main.ts"])
            self.assertEqual("java", langs["Service.java"])
            self.assertEqual("markdown", langs["docs/b.md"])

    def test_cli_ignore_pattern_actually_takes_effect(self):
        """红测：--ignore 声明了却没接线，会静默扫全部文件——
        这类"写了不用"的缺陷本仓库犯过一次（BOOKLET_ALIASES 定义了从未参与打分）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            base, _ = self._index(tmp)
            self.assertIn("docs/b.md", set(f["path"] for f in base["files"]))
            data, _ = self._index(tmp, ["--ignore", "docs/*"])
            paths = set(f["path"] for f in data["files"])
            self.assertNotIn("docs/b.md", paths, "--ignore 没生效")
            self.assertIn("app.py", paths, "--ignore 不该把无关文件一起排掉")


class TestAuditMap(unittest.TestCase):
    """R3：项目侦察与全仓地图——语言/入口/路由/鉴权边界/依赖，全部要能在磁盘上对上号。"""

    FILES = {
        "requirements.txt": "fastapi==0.110.0\nuvicorn[standard]\npython-jose==3.3.0\n",
        "package.json": json.dumps({"name": "svc", "dependencies": {
            "express": "^4.19.0", "mongoose": "^8.0.0"}}),
        "package-lock.json": "{}",
        "main.py": ("from fastapi import FastAPI\n"
                    "app = FastAPI()\n"
                    "if __name__ == '__main__':\n"
                    "    import uvicorn\n"
                    "    uvicorn.run(app, port=8000)\n"),
        "routers/items.py": (
            "from fastapi import APIRouter, Depends\n"
            "router = APIRouter()\n"
            "@router.get('/items')\n"
            "def list_items():\n"
            "    return []\n"
            "@router.post('/items', dependencies=[Depends(verify_token)])\n"
            "def create_item():\n"
            "    return {}\n"),
        "server.js": ("const express = require('express')\n"
                      "const app = express()\n"
                      "app.get('/health', (req, res) => res.end('ok'))\n"
                      "app.listen(3000)\n"),
        "routes/pay.js": ("const router = require('express').Router()\n"
                          "router.post('/pay', requireAuth, (req, res) => {})\n"
                          "module.exports = router\n"),
        "UserController.java": ("@RestController\n"
                                "public class UserController {\n"
                                "    @PreAuthorize(\"isAuthenticated()\")\n"
                                "    @GetMapping(\"/user/{id}\")\n"
                                "    public String get(String id) { return id; }\n"
                                "}\n"),
    }

    def _tree(self, root):
        for rel, text in self.FILES.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def _map(self, root):
        out = os.path.join(root, "_map.json")
        r = run([os.path.join(SCRIPTS, "audit_map.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_map_detects_languages_and_entrypoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._map(tmp)
            self.assertIn("python", data["languages"])
            self.assertIn("javascript", data["languages"])
            entries = set(e["path"] for e in data["entrypoints"])
            self.assertIn("main.py", entries)
            self.assertIn("server.js", entries)
            self.assertGreaterEqual(data["languages"]["python"], 2)

    def test_map_lists_routes_with_file_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._map(tmp)
            got = dict(((r["path"], r["method"]), r) for r in data["routes"])
            for key in (("/items", "GET"), ("/items", "POST"),
                        ("/health", "GET"), ("/pay", "POST"), ("/user/{id}", "GET")):
                self.assertIn(key, got, "路由漏识别：%s（已识别 %s）" % (key, sorted(got)))
                rec = got[key]
                self.assertTrue(rec["file"], "路由必须带文件")
                self.assertGreater(rec["line"], 0, "路由必须带行号")

    def test_map_marks_auth_boundary_and_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._map(tmp)
            got = dict(((r["path"], r["method"]), r) for r in data["routes"])
            self.assertTrue(got[("/items", "POST")]["auth"], "Depends(verify_token) 应算鉴权")
            self.assertTrue(got[("/pay", "POST")]["auth"], "requireAuth 中间件应算鉴权")
            self.assertTrue(got[("/user/{id}", "GET")]["auth"],
                            "@PreAuthorize 在上一行也要认（Java 注解分行写是常态）")
            self.assertFalse(got[("/items", "GET")]["auth"])
            self.assertIn("/items", data["summary"]["unauthenticated_routes"])
            self.assertTrue(data["auth_boundaries"], "鉴权边界要单独成表")

    def test_map_lists_dependencies_and_lockfiles(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, _ = self._map(tmp)
            deps = dict((d["name"], d) for d in data["dependencies"])
            self.assertIn("fastapi", deps)
            self.assertIn("express", deps)
            self.assertEqual("0.110.0", deps["fastapi"]["version"])
            self.assertIn("package-lock.json", [os.path.basename(x) for x in data["lockfiles"]])

    def test_map_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            first, _ = self._map(tmp)
            second, _ = self._map(tmp)
            self.assertEqual(first["map_sha1"], second["map_sha1"],
                             "地图必须可复现，否则增量缓存与前后对比都不可信")

    def test_routes_written_inside_string_literals_are_not_routes(self):
        """夹具与文档里当字符串写的 @app.route 不是路由（自扫实测过一条这样的误报）。"""
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "_m.json")
            with io.open(os.path.join(tmp, "fixtures.py"), "w", encoding="utf-8") as f:
                f.write("CASES = [\n    \"@app.route('/admin/leak')\",\n]\n\n\n"
                        "def real():\n    return 1\n")
            with io.open(os.path.join(tmp, "app.py"), "w", encoding="utf-8") as f:
                f.write("from flask import Flask\napp = Flask(__name__)\n\n"
                        "@app.route('/admin/real')\ndef admin():\n    return 1\n")
            r = run([os.path.join(SCRIPTS, "audit_map.py"), tmp, "--json", out])
            self.assertEqual(r.returncode, 0, r.stdout)
            with io.open(out, "r", encoding="utf-8") as f:
                data = json.load(f)
            paths = [x["path"] for x in data["routes"]]
            self.assertIn("/admin/real", paths, "真路由不能一起屏蔽掉")
            self.assertNotIn("/admin/leak", paths, "字符串字面量里的路由被当成了路由")
            self.assertEqual([], [a for a in data["auth_boundaries"]
                                  if a["file"] == "fixtures.py"])

    def test_map_consumes_index_and_rejects_absent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run([os.path.join(SCRIPTS, "audit_map.py"),
                     os.path.join(tmp, "nope")])
            self.assertEqual(r.returncode, 2, r.stdout)
            self.assertIn("目录不存在", r.stdout)


class TestAuditRules(unittest.TestCase):
    """R4：声明式规则引擎——规则是数据，能被加载、校验、合并、算出版本号。"""

    def _run_rules(self, *extra):
        return run([os.path.join(SCRIPTS, "audit_rules.py")] + list(extra))

    def test_builtin_rules_load_and_validate(self):
        r = self._run_rules("--validate")
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("RESULT: RULES-OK", r.stdout)
        m = re.search(r"规则\s*(\d+)\s*条", r.stdout)
        self.assertTrue(m, "没报规则条数：%s" % r.stdout)
        self.assertGreaterEqual(int(m.group(1)), 20,
                               "内置规则少于 20 条，覆盖不了注入/越权/密钥/弱加密四类")

    def test_every_rule_carries_report_fields(self):
        """报告八栏（位置/CWE/数据流/利用条件/置信度/严重度/修复示例/复测点）
        里 CWE、修复、复测三项由规则供给——缺一条就不算合格的规则。"""
        out = os.path.join(tempfile.mkdtemp(), "rules.json")
        r = self._run_rules("--validate", "--json", out)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        bad = []
        for rule in data["rules"]:
            for field in ("id", "title", "severity", "cwe", "languages", "fix", "retest"):
                if not rule.get(field):
                    bad.append("%s 缺 %s" % (rule.get("id", "?"), field))
            if rule["severity"] not in ("critical", "high", "medium", "low", "info"):
                bad.append("%s 严重度非法：%s" % (rule["id"], rule["severity"]))
        self.assertEqual([], bad)

    def test_malformed_rule_is_named_and_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with io.open(bad, "w", encoding="utf-8") as f:
                json.dump({"rules": [{"id": "JZ-BAD-001", "title": "缺字段的规则",
                                      "severity": "catastrophic", "languages": ["python"],
                                      "kind": "taint", "sink": [{"pattern": "x"}]}]},
                          f, ensure_ascii=False)
            r = self._run_rules("--validate", "--add", bad)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("JZ-BAD-001", r.stdout)

    def test_mid_pattern_global_flag_blocks(self):
        """`x|(?i)y` 这种写法在 Python 里是 DeprecationWarning，将来会变 SyntaxError。
        规则校验必须当场拦下，不能让一条"今天只是警告"的模式混进规则库、
        等下一代解释器把它变成整条链启动失败。"""
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "flag.json")
            with io.open(bad, "w", encoding="utf-8") as f:
                json.dump({"rules": [{"id": "JZ-FLAG-001", "title": "标志写错位置",
                                      "severity": "high", "kind": "pattern",
                                      "languages": ["python"], "cwe": ["CWE-1"],
                                      "sinks": [{"pattern": "foo = time()|(?i)bar"}],
                                      "fix": "f", "retest": "r"}]}, f, ensure_ascii=False)
            r = self._run_rules("--validate", "--add", bad)
            self.assertEqual(r.returncode, 1, "中途的全局标志被放过了：%s" % r.stdout)
            self.assertIn("JZ-FLAG-001", r.stdout)
            self.assertIn(u"全局标志", r.stdout)
            # 反面：正确写法（(?i) 在开头）不该被误拦
            good = os.path.join(tmp, "ok.json")
            with io.open(good, "w", encoding="utf-8") as f:
                json.dump({"rules": [{"id": "JZ-FLAG-002", "title": "写法正确",
                                      "severity": "high", "kind": "pattern",
                                      "languages": ["python"], "cwe": ["CWE-1"],
                                      "sinks": [{"pattern": "(?i)foo = time()|bar"}],
                                      "fix": "f", "retest": "r"}]}, f, ensure_ascii=False)
            ok = self._run_rules("--validate", "--add", good)
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_misplaced_global_flag_detector_is_interpreter_independent(self):
        """判据自己认"标志写错位置"，不吃解释器的警告时刻表。
        上一条测试在 3.8 走 DeprecationWarning 分支、在 3.11 走 re.error 分支，
        两支的措辞由 CPython 决定——断言中文关键字时就会一边绿一边红
        （CI 实测：Linux/3.11 红在这条上，本机 3.8 绿）。
        所以把判定收进 audit_rules.misplaced_global_flag，正反面都在这里锁死。
        """
        sys.path.insert(0, SCRIPTS)
        import audit_rules
        hit = ["foo = time()|(?i)bar", "(?:a|(?i)b)", "a(?=b)(?i)c", "(x)(?i)y",
               "(?i)a|b(?s)c"]
        miss = ["(?i)foo = time()|bar", "(?i)(?s)foo", "((?i)x)", "(?i:abc)",
                "(?i)x", "plain"]
        for pat in hit:
            self.assertTrue(audit_rules.misplaced_global_flag(pat),
                            u"这种写法必须拦：%s" % pat)
        for pat in miss:
            self.assertIsNone(audit_rules.misplaced_global_flag(pat),
                              u"合法写法不该被误拦：%s" % pat)

    def test_two_builtin_files_claiming_same_id_blocks(self):
        """内置规则文件之间撞 id 必须报错，不能静默覆盖。
        E1 实拍：我新增 crypto.json 时用了 JZ-CRYPTO-001，而 webapp.json 里早就有同 id 的
        弱哈希规则——按文件名排序后者胜出，**我那条规则整条没生效**，
        测试只表现为"规则没检出"，谁都不会想到是被同名规则遮蔽了。
        用户文件（--add）覆盖内置同 id 是有意的定制，仍要放行——两半都测。"""
        rule = (u'{"schema": "jiangzuo-audit-rules/1", "name": "%s", "rules": [%s]}')
        one = (u'{"id": "JZ-DUP-001", "title": "%s", "kind": "pattern", "severity": "high",'
               u' "languages": ["python"], "cwe": ["CWE-327"],'
               u' "sinks": [{"pattern": "%s"}], "fix": "f", "retest": "r"}')
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "a.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(rule % ("a", one % ("甲写法", "alpha_marker")))
            with io.open(os.path.join(tmp, "b.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(rule % ("b", one % ("乙写法", "beta_marker")))
            r = self._run_rules("--validate", "--dir", tmp)
            self.assertEqual(r.returncode, 1,
                             u"两个内置文件撞 id 却放行：%s" % r.stdout)
            self.assertIn("JZ-DUP-001", r.stdout)
            self.assertIn(u"内置规则文件", r.stdout)
            # 反面：只有一个文件声明该 id 时不该报
            with io.open(os.path.join(tmp, "b.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(rule % ("b", one % ("乙写法", "beta_marker")))
            with io.open(os.path.join(tmp, "a.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(rule % ("a", one % ("甲写法", "alpha_marker")))
            os.remove(os.path.join(tmp, "b.json"))
            ok = self._run_rules("--validate", "--dir", tmp)
            self.assertEqual(ok.returncode, 0, ok.stdout)

    def test_user_rule_overrides_same_id_without_dupes(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self._run_rules("--validate", "--json",
                                   os.path.join(tmp, "base.json"))
            self.assertEqual(base.returncode, 0, base.stdout)
            with io.open(os.path.join(tmp, "base.json"), encoding="utf-8") as f:
                builtin = json.load(f)
            target = builtin["rules"][0]["id"]
            override = os.path.join(tmp, "user.json")
            with io.open(override, "w", encoding="utf-8") as f:
                json.dump({"rules": [{"id": target, "title": "用户改写",
                                      "severity": "critical", "kind": "pattern",
                                      "languages": ["python"], "cwe": ["CWE-1234"],
                                      "sinks": [{"pattern": "placeholder_ok"}],
                                      "fix": "改法", "retest": "复测点"}]},
                          f, ensure_ascii=False)
            r = self._run_rules("--validate", "--add", override,
                                "--json", os.path.join(tmp, "merged.json"))
            self.assertEqual(r.returncode, 0, r.stdout)
            with io.open(os.path.join(tmp, "merged.json"), encoding="utf-8") as f:
                merged = json.load(f)
            ids = [x["id"] for x in merged["rules"]]
            self.assertEqual(len(ids), len(set(ids)), "同 id 必须去重，不能出现两条")
            got = [x for x in merged["rules"] if x["id"] == target][0]
            self.assertEqual("用户改写", got["title"], "用户规则应覆盖内置同 id 规则")
            self.assertNotEqual(builtin["rules_version"], merged["rules_version"],
                                "规则内容变了而版本号不变，增量缓存就是假的")

    def test_unknown_rule_kind_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "k.json")
            with io.open(bad, "w", encoding="utf-8") as f:
                json.dump({"rules": [{"id": "JZ-KIND-001", "title": "t",
                                      "severity": "high", "kind": "psychic",
                                      "languages": ["python"], "cwe": ["CWE-1"],
                                      "fix": "f", "retest": "r"}]}, f)
            r = self._run_rules("--validate", "--add", bad)
            self.assertEqual(r.returncode, 1, r.stdout)
            self.assertIn("psychic", r.stdout)


class TestAuditGraph(unittest.TestCase):
    """R5：跨文件调用图 + source→sink 污点分析（升级清单第 4 项）。

    这一层是"从正则到有证据"的分水岭：测试重点不只是命中，
    更要求**不命中时说得清为什么不命中**（净化了 / 不可达 / 常量）。
    """

    def _mk(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def _graph(self, root, files):
        self._mk(root, files)
        out = os.path.join(root, "_graph.json")
        r = run([os.path.join(SCRIPTS, "audit_graph.py"), root, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_same_function_taint_becomes_evidence_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"app.py": (
                "from flask import request, Flask\n"
                "import sqlite3\n"
                "app = Flask(__name__)\n\n"
                "@app.route(\"/search\")\n"
                "def search():\n"
                "    q = request.args[\"q\"]\n"
                "    con = sqlite3.connect(\"db.sqlite\")\n"
                "    con.execute(f\"SELECT * FROM t WHERE c LIKE {q}\")\n"
                "    return \"ok\"\n")})
            sql = [f for f in data["flows"] if f["rule_id"] == "JZ-SQLI-001"]
            self.assertEqual(1, len(sql), "flows=%s" % data["flows"])
            hops = sql[0]["path"]
            self.assertGreaterEqual(len(hops), 2, "source 与 sink 至少两跳")
            self.assertEqual("app.py", hops[0]["file"])
            self.assertTrue(all(h["line"] > 0 for h in hops), "每一跳都要带行号")
            self.assertTrue(sql[0]["reachable"], "路由处理函数应判为可达")

    def test_sanitizer_breaks_the_flow_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"app.py": (
                "from flask import request, Flask\n"
                "import sqlite3\n"
                "app = Flask(__name__)\n\n"
                "@app.route(\"/byid\")\n"
                "def byid():\n"
                "    q = int(request.args[\"id\"])\n"
                "    con = sqlite3.connect(\"db.sqlite\")\n"
                "    con.execute(f\"SELECT * FROM t WHERE id={q}\")\n"
                "    return \"ok\"\n")})
            sql = [f for f in data["flows"] if f["rule_id"] == "JZ-SQLI-001"]
            self.assertEqual([], sql, "int() 净化后不得再报污点流")
            self.assertGreaterEqual(data["stats"]["blocked_by_sanitizer"], 1,
                                    "净化点要被记下来，不能当没发生过")

    def test_taint_crosses_file_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {
                "web/handlers.py": (
                    "from flask import request\n\n\n"
                    "@app.route(\"/report\")\n"
                    "def handle():\n"
                    "    name = request.args[\"name\"]\n"
                    "    return render(name)\n"),
                "services/report.py": (
                    "import sqlite3\n\n\n"
                    "def render(value):\n"
                    "    con = sqlite3.connect(\"x.db\")\n"
                    "    return con.execute(f\"SELECT {value} FROM t\").fetchall()\n")})
            sql = [f for f in data["flows"] if f["rule_id"] == "JZ-SQLI-001"]
            self.assertEqual(1, len(sql), "跨文件污点没接上：%s" % data["flows"])
            files = set(h["file"] for h in sql[0]["path"])
            self.assertEqual(2, len(files), "证据链应跨两个文件：%s" % sql[0]["path"])
            self.assertEqual("interprocedural", sql[0]["depth"])

    def test_unreachable_sink_is_marked_not_exploitable(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"legacy/tool.py": (
                "import os\n"
                "from flask import request\n\n\n"
                "def top(user_input):\n"
                "    os.system(\"ls \" + user_input)\n\n\n"
                "def entry_unused():\n"
                "    top(request.args[\"d\"])\n")})
            cmd = [f for f in data["flows"] if f["rule_id"] == "JZ-CMDI-001"]
            self.assertEqual(1, len(cmd), "污点流应成立：%s" % data["flows"])
            self.assertFalse(cmd[0]["reachable"], "没有任何入口能走到，就不该说可利用")
            self.assertIn("可达", cmd[0]["unreachable_reason"] or "")

    def test_constant_sink_does_not_produce_a_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"app.py": (
                "import sqlite3\n"
                "con = sqlite3.connect(\"db.sqlite\")\n"
                "con.execute(\"SELECT 1\")\n")})
            self.assertEqual([], [f for f in data["flows"]
                                 if f["rule_id"].startswith("JZ-SQLI")],
                             "写死的 SQL 没有外部输入，不该报污点")


class TestAuditScan(unittest.TestCase):
    """R6–R8：调度层 + 反幻觉验证 + 分级报告 + 缓存增量（升级清单 6/7/8/9/10 项）。"""

    def _mk(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)

    def _scan(self, root, extra=None):
        out = os.path.join(root, "_findings.json")
        cmd = [os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out]
        cmd += extra or []
        r = run(cmd)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    VULN_APP = {
        "requirements.txt": "fastapi==0.110.0\npyyaml==5.3\n",
        "main.py": (
            "from fastapi import FastAPI\nfrom flask import request\nimport sqlite3\n"
            "app = FastAPI()\n\n"
            "@app.get(\"/search\")\n"
            "def search():\n"
            "    q = request.args[\"q\"]\n"
            "    con = sqlite3.connect(\"db.sqlite\")\n"
            "    return con.execute(f\"SELECT * FROM t WHERE c LIKE {q}\").fetchall()\n\n"
            "@app.get(\"/admin/users\")\n"
            "def admin_list():\n"
            "    return []\n"),
        "settings.py": "DEBUG = True\nHASH = \"md5\"\n\n"
                       "def pw_hash(password):\n    import hashlib\n"
                       "    return hashlib.md5(password.encode()).hexdigest()\n",
        "loader.py": "import yaml\n\n\ndef load(text):\n    return yaml.load(text)\n",
    }

    def test_scan_reports_taint_pattern_and_authgap(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp, self.VULN_APP)
            data, stdout = self._scan(tmp)
            kinds = set(f["rule_id"] for f in data["findings"])
            self.assertIn("JZ-SQLI-001", kinds, "污点流没进报告：%s" % kinds)
            self.assertIn("JZ-AUTHGAP-001", kinds, "敏感路由鉴权缺口没进报告：%s" % kinds)
            self.assertIn("JZ-CRYPTO-001", kinds, "弱哈希没进报告：%s" % kinds)
            self.assertIn("RESULT: SCAN-OK", stdout)

    def test_verifier_drops_hallucinated_location(self):
        """反幻觉验证的"能不能红"校准：喂一条指向不存在文件/行的假发现，必须被丢掉并计数。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp, self.VULN_APP)
            fake = {"schema": "jiangzuo-audit-graph/1", "index_sha1": "", "map_sha1": "",
                    "rules_version": "", "functions": [], "blocked": [],
                    "stats": {"sources": 0, "blocked_by_sanitizer": 0,
                              "sink_without_taint": 0, "passes": 1},
                    "flows": [{"rule_id": "JZ-SQLI-001", "title": "假的",
                               "severity": "critical", "confidence_base": 0.9,
                               "cwe": ["CWE-89"], "owasp": [], "file": "does/not_exist.py",
                               "line": 9999, "sink_text": "con.execute(f\"SELECT {q}\")",
                               "path": [{"file": "does/not_exist.py", "line": 9999,
                                         "kind": "source", "text": "q = request.args['q']"}],
                               "sanitizers_seen": [], "depth": "function-local",
                               "reachable": True, "unreachable_reason": "",
                               "fix": "f", "retest": "r"}]}
            gpath = os.path.join(tmp, "_fake_graph.json")
            with io.open(gpath, "w", encoding="utf-8") as f:
                json.dump(fake, f, ensure_ascii=False)
            data, _ = self._scan(tmp, ["--graph", gpath])
            ghost = [f for f in data["findings"] if f["file"] == "does/not_exist.py"]
            self.assertEqual([], ghost, "验证环节没拦住编造的位置")
            self.assertGreaterEqual(data["stats"]["dropped_by_verifier"], 1,
                                    "丢弃要计数，不能静默")
            self.assertTrue(any("不存在" in d["reason"] or "行" in d["reason"]
                                for d in data["dropped"]),
                            "丢弃要给原因：%s" % data["dropped"])

    def test_every_finding_carries_verification_and_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp, self.VULN_APP)
            data, _ = self._scan(tmp)
            self.assertTrue(data["findings"], "没有发现可检")
            for f in data["findings"]:
                self.assertTrue(os.path.isfile(os.path.join(tmp, f["file"].replace("/", os.sep))),
                                "报告里的文件必须真实存在：%s" % f["file"])
                self.assertGreater(f["line"], 0)
                for k in ("path_exists", "sink_still_matches", "input_controllable",
                          "sanitizer_absent", "sink_reachable"):
                    self.assertIn(k, f["verification"], "%s 缺核验项 %s" % (f["rule_id"], k))
                self.assertIn(f["confidence"]["label"], (u"高", u"中", u"低"))
                self.assertIn(f["severity"], ("critical", "high", "medium", "low", "info"))
                self.assertTrue(f["fix"] and f["retest"], "缺修复示例或复测点")

    def test_dependency_ranked_by_actual_usage(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp, self.VULN_APP)
            data, _ = self._scan(tmp)
            dep = [f for f in data["findings"] if f["rule_id"] == "JZ-DEP-002"]
            self.assertEqual(1, len(dep), "pyyaml 5.3 应命中依赖建议：%s" %
                             [f["rule_id"] for f in data["findings"]])
            self.assertTrue(dep[0]["called"], "loader.py 里 import yaml，应判为被实际调用")
            self.assertEqual(0, dep[0]["rank"], "被调用的依赖要排在最前")

    def test_sarif_export_structure(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._mk(tmp, self.VULN_APP)
            sarif = os.path.join(tmp, "_out.sarif")
            self._scan(tmp, ["--sarif", sarif])
            with io.open(sarif, "r", encoding="utf-8") as f:
                doc = json.load(f)
            self.assertEqual("2.1.0", doc["version"])
            self.assertIn("$schema", doc)
            run0 = doc["runs"][0]
            self.assertIn("driver", run0["tool"])
            self.assertTrue(run0["tool"]["driver"]["rules"])
            self.assertTrue(run0["results"])
            res = run0["results"][0]
            self.assertIn("ruleId", res)
            self.assertIn("level", res)
            self.assertIn("message", res)
            loc = res["locations"][0]["physicalLocation"]
            self.assertIn("artifactLocation", loc)
            self.assertIn("startLine", loc["region"])
            self.assertNotIn("\r", json.dumps(doc))

    def test_cache_incremental_equals_full(self):
        with tempfile.TemporaryDirectory() as tmp:
            cache = os.path.join(tmp, "_cache")
            self._mk(tmp, self.VULN_APP)
            full, _ = self._scan(tmp, ["--cache", cache])
            self.assertGreaterEqual(full["stats"]["files_cached"], 1,
                                    "第一次跑就该把结果写进缓存")
            again, _ = self._scan(tmp, ["--cache", cache, "--incremental"])
            self.assertEqual(0, again["stats"]["recomputed_files"],
                             "没改任何东西时增量为零重算")
            self.assertEqual([f["rule_id"] for f in full["findings"]],
                             [f["rule_id"] for f in again["findings"]],
                             "增量结论必须与全量一致")
            # 改一个文件：增量应只重算它（及调用链下游），结论与新全量一致
            self._mk(tmp, {"loader.py": "import yaml\n\n\ndef load(text):\n"
                                        "    return yaml.safe_load(text)\n"})
            inc, _ = self._scan(tmp, ["--cache", cache, "--incremental"])
            fresh, _ = self._scan(tmp)
            self.assertEqual([f["rule_id"] for f in fresh["findings"]],
                             [f["rule_id"] for f in inc["findings"]],
                             "改动后增量与全量结论不一致")
            self.assertLessEqual(inc["stats"]["recomputed_files"],
                                 full["stats"]["files_total"])
            self.assertIn("JZ-DEP-002", [f["rule_id"] for f in inc["findings"]],
                          "requirements.txt 没改，依赖结论不该在增量里蒸发")
            self.assertEqual(1, inc["stats"]["recomputed_files"],
                             "只应重算改动文件及其调用链邻居：%s" % inc["stats"])


class TestAuditCostModel(unittest.TestCase):
    """性能不是形容词，也不能靠"本机跑得快"证明——锁**工作量随候选数缩放**这条结构性质。

    计时断言在 CI 上必然抖动（本会话就吃过一次：单跑一遍全阶段统一慢 3 倍，
    而其中 build_index 我根本没碰）。所以这里断言的是"图层解析了几个文件"，
    它和仓库大小无关、只和候选数有关，可复现、能红能绿。
    """

    def _corpus(self, root, clean_files, flows=0):
        for i in range(clean_files):
            path = os.path.join(root, ("app/mod_%04d.py" % i).replace("/", os.sep))
            os.makedirs(os.path.dirname(path)) if not os.path.isdir(
                os.path.dirname(path)) else None
            with io.open(path, "w", encoding="utf-8") as f:
                f.write("def handle_%d(payload):\n"
                        "    total = 0\n"
                        "    for key in payload:\n"
                        "        total += len(str(key))\n"
                        "    return total\n" % i)
        for i in range(flows):
            path = os.path.join(root, ("app/vuln_%03d.py" % i).replace("/", os.sep))
            with io.open(path, "w", encoding="utf-8") as f:
                f.write("from flask import request\nimport sqlite3\n\n\n"
                        "@app.route('/x%d')\ndef h%d():\n"
                        "    q = request.args['q']\n"
                        "    con = sqlite3.connect('db.sqlite')\n"
                        "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}')"
                        ".fetchall()\n" % (i, i))

    def _stats(self, root):
        out = os.path.join(root, "_f.json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)["stats"]

    def test_clean_repo_pays_zero_graph_work(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._corpus(tmp, 200)
            stats = self._stats(tmp)
            self.assertEqual(200, stats["files_total"])
            self.assertEqual(0, stats["graph_parsed_files"],
                             "干净仓库里图层仍在全仓解析＝门控失效")
            self.assertTrue(stats["graph_gated"], u"应记录「图层被粗筛门控空转」")

    def test_graph_work_scales_with_candidates_not_repo_size(self):
        small, big = None, None
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            self._corpus(a, 60, flows=3)
            self._corpus(b, 240, flows=3)
            small, big = self._stats(a), self._stats(b)
        self.assertGreaterEqual(big["flows"], 3, "仓库放大后植入的漏洞必须仍被检出")
        self.assertEqual(small["graph_parsed_files"], big["graph_parsed_files"],
                         "图层解析的文件数只该跟候选走：仓库×4 它就×4 = 门控没起作用")
        self.assertLess(big["graph_parsed_files"], big["files_total"] // 4)


class TestAuditFusion(unittest.TestCase):
    """单遍前端（prescan）与分步前端必须给出**逐字节一致**的结论，否则融合就是漂移。"""

    FILES = {
        "requirements.txt": "flask==2.3.3\npyyaml==5.3\n",
        "main.py": ("from flask import request, Flask\n"
                    "import sqlite3\n"
                    "app = Flask(__name__)\n\n\n"
                    "@app.route('/search')\n"
                    "def search():\n"
                    "    q = request.args['q']\n"
                    "    con = sqlite3.connect('db.sqlite')\n"
                    "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}')"
                    ".fetchall()\n\n\n"
                    "@app.route('/admin/users')\n"
                    "def admin_users():\n"
                    "    return []\n"),
        "loader.py": "import yaml\n\n\ndef load(text):\n    return yaml.safe_load(text)\n",
        "legacy.php": ("<?php\n"
                       "$conn = mysqli_connect('localhost', 'u', 'p', 'db');\n"
                       "$res = mysqli_query($conn, 'SELECT * FROM posts WHERE id = ' "
                       ". $_GET['id']);\n"),
    }

    def _run_path(self, root, out_dir, extra):
        # 产物写到被扫目录**之外**：否则上一次的输出会进下一次的索引，
        # 两次运行的 index_sha1 天然不同——那是测试自己制造的污染，不是产品的错。
        out = os.path.join(out_dir, "f%s.json" % ("".join(extra) or "x"))
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out] + extra)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_fused_equals_staged(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            for rel, text in self.FILES.items():
                path = os.path.join(tmp, rel.replace("/", os.sep))
                with io.open(path, "w", encoding="utf-8") as f:
                    f.write(text)
            fused = self._run_path(tmp, out, [])
            staged = self._run_path(tmp, out, ["--staged"])
            key = lambda p: [(f["rule_id"], f["file"], f["line"]) for f in p["findings"]]
            self.assertTrue(key(fused), "两条路径都没查出东西＝这条锁是空的")
            self.assertEqual(key(staged), key(fused),
                             "单遍前端与分步前端的发现清单不一致")
            self.assertEqual(fused["index_sha1"], staged["index_sha1"],
                             "同一份文件两种走法算出的索引指纹不同＝忽略规则或口径分叉了")
            self.assertEqual(fused["map_sha1"], staged["map_sha1"],
                             "地图不一致：prescan 少抽了某个字段")
            self.assertEqual(fused["stats"]["files_total"],
                             staged["stats"]["files_total"])

    def test_parallel_front_end_matches_serial(self):
        """并发分片必须与串行**逐字节一致**——否则"提速"就是拿结论换时间。"""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as out:
            for i in range(420):          # 过 PARALLEL_MIN_FILES，才真走进程池
                d = os.path.join(tmp, "pkg")
                if not os.path.isdir(d):
                    os.makedirs(d)
                with io.open(os.path.join(d, "m%04d.py" % i), "w",
                             encoding="utf-8") as f:
                    f.write("def f%d(x):\n    return x * %d\n" % (i, i))
            for rel, text in self.FILES.items():
                with io.open(os.path.join(tmp, rel.replace("/", os.sep)), "w",
                             encoding="utf-8") as f:
                    f.write(text)
            one = self._run_path(tmp, out, [])
            two = self._run_path(tmp, out, ["--jobs", "2"])
            self.assertGreaterEqual(two["stats"].get("workers", 0), 2,
                                    "没真走并发，这条锁是空的")
            key = lambda p: [(f["rule_id"], f["file"], f["line"]) for f in p["findings"]]
            self.assertEqual(key(one), key(two), "并发与串行的发现清单不一致")
            self.assertEqual(one["index_sha1"], two["index_sha1"], "并发改变了索引口径")
            self.assertEqual(one["map_sha1"], two["map_sha1"], "并发合并地图时丢了字段或顺序不稳")

    def test_fused_is_the_default_and_can_be_disabled(self):
        with tempfile.TemporaryDirectory() as tmp:
            for rel, text in self.FILES.items():
                with io.open(os.path.join(tmp, rel.replace("/", os.sep)), "w",
                             encoding="utf-8") as f:
                    f.write(text)
            r = run([os.path.join(SCRIPTS, "audit_scan.py"), tmp, "--help"])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn("--staged", r.stdout)


class TestAuditIncrementalGraph(unittest.TestCase):
    """P4：增量必须**跟得上跨文件因果**——改了调用方，下游 sink 的结论也要跟着变。

    只测"没改动时零重算"是不够的：那种缓存在改了 caller 之后照样复用旧 flow，
    看起来快，实际是假装没事。
    """

    HANDLER = ("from flask import request\n\n\n"
               "@app.route('/report')\n"
               "def handle():\n"
               "    name = request.args['name']\n"
               "    return render(name)\n")
    HANDLER_SAFE = ("from flask import request\n\n\n"
                    "@app.route('/report')\n"
                    "def handle():\n"
                    "    name = int(request.args['name'])\n"
                    "    return render(name)\n")
    SERVICE = ("import sqlite3\n\n\n"
               "def render(value):\n"
               "    con = sqlite3.connect('x.db')\n"
               "    return con.execute(f'SELECT {value} FROM t').fetchall()\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8") as f:
            f.write(text)

    def _scan(self, root, cache, extra=None):
        out = os.path.join(cache, "f%s.json" % ("".join(extra or ["x"]).replace("-", "_")))
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out,
                 "--cache", cache] + (extra or []))
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_changing_the_caller_updates_the_downstream_flow(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as cache:
            for i in range(10):
                self._write(root, "pkg/mod_%02d.py" % i,
                            "def f%d(x):\n    return x + %d\n" % (i, i))
            self._write(root, "handlers.py", self.HANDLER)
            self._write(root, "services.py", self.SERVICE)
            cold = self._scan(root, cache)
            flows = [f for f in cold["findings"] if f["rule_id"] == "JZ-SQLI-001"]
            self.assertEqual(1, len(flows), "跨文件污点流应被检出：%s" % cold["findings"])
            self.assertEqual("services.py", flows[0]["file"])

            self._write(root, "handlers.py", self.HANDLER_SAFE)   # 只改调用方
            inc = self._scan(root, cache, ["--incremental"])
            fresh = self._scan(root, cache)                       # 对照：全量重扫
            key = lambda p: sorted((f["rule_id"], f["file"], f["line"])
                                   for f in p["findings"])
            self.assertEqual(key(fresh), key(inc), "增量结论与全量不一致")
            self.assertEqual([], [f for f in inc["findings"]
                                 if f["rule_id"] == "JZ-SQLI-001"],
                             "调用方已净化，下游污点流必须消失——缓存不许假装没事")
            self.assertLess(inc["stats"]["graph_parsed_files"],
                            inc["stats"]["files_total"],
                            "增量还是把全仓解析了一遍")
            self.assertGreaterEqual(inc["stats"]["reused_flows"], 0)

class TestAuditBaseline(unittest.TestCase):
    """P5：基线对照与复测闭环——CI 只拦新增，"报告里没了"不等于"修好了"。"""

    VULN = ("from flask import request\nimport sqlite3\n\n\n"
            "@app.route('/a')\ndef a():\n"
            "    q = request.args['q']\n"
            "    con = sqlite3.connect('db.sqlite')\n"
            "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}').fetchall()\n")
    FIXED = ("from flask import request\nimport sqlite3\n\n\n"
             "@app.route('/a')\ndef a():\n"
             "    q = int(request.args['q'])\n"
             "    con = sqlite3.connect('db.sqlite')\n"
             "    return con.execute('SELECT * FROM t WHERE c LIKE %s', (q,)).fetchall()\n")

    def _scan(self, root, out, extra=None):
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out]
                + (extra or []))
        self.assertEqual(r.returncode, 0, r.stdout)
        return r

    def _write(self, root, rel, text):
        with io.open(os.path.join(root, rel.replace("/", os.sep)), "w",
                     encoding="utf-8") as f:
            f.write(text)

    def test_baseline_reports_only_new_and_recheck_judges_fixes(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            self._write(root, "a.py", self.VULN)
            base = os.path.join(out, "base.json")
            self._scan(root, base)
            with io.open(base, "r", encoding="utf-8") as f:
                first = json.load(f)
            self.assertTrue([x for x in first["findings"]
                             if x["rule_id"] == "JZ-SQLI-001"], "基线里应有那条流")

            self._write(root, "b.py", self.VULN.replace("/a", "/b").replace("def a(", "def b("))
            again = os.path.join(out, "again.json")
            r = self._scan(root, again, ["--baseline", base])
            self.assertIn(u"新增 1", r.stdout)
            self.assertIn(u"仍在 1", r.stdout)

            only = os.path.join(out, "only.json")
            self._scan(root, only, ["--baseline", base, "--only-new"])
            with io.open(only, "r", encoding="utf-8") as f:
                new_only = json.load(f)
            self.assertEqual(1, len(new_only["findings"]), "--only-new 应只留新增")
            self.assertEqual("b.py", new_only["findings"][0]["file"])

            # 修掉 a.py 之后回查基线：不许直接判"已修复"，要落到需人工确认或消失
            self._write(root, "a.py", self.FIXED)
            rc = run([os.path.join(SCRIPTS, "audit_scan.py"), root,
                      "--check-fixes", base])
            self.assertEqual(rc.returncode, 0, rc.stdout)
            self.assertIn("RESULT: RECHECK-OK", rc.stdout)
            self.assertNotIn(u"全部已修复", rc.stdout)
            statuses = re.findall(r"→ \*\*(\w+)\*\*", rc.stdout)
            self.assertTrue(statuses, "复测报告没有逐条状态：%s" % rc.stdout[:200])


class TestAuditSuppression(unittest.TestCase):
    """B2：豁免是业界标配，但**没写理由的豁免不算豁免**——否则误报只是被藏起来了。"""

    VULN = ("from flask import request\nimport sqlite3\n\n\n"
            "@app.route('/a')\ndef a():\n"
            "    q = request.args['q']\n"
            "    con = sqlite3.connect('db.sqlite')\n"
            "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}').fetchall()\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_s_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_inline_suppression_with_reason_hides_and_is_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.py", self.VULN.replace(
                "    return con.execute(",
                "    return con.execute(").replace(
                "    q = request.args['q']",
                "    q = request.args['q']  # jiangzuo:ignore JZ-SQLI-001 只被内部任务调用，无外部输入"))
            data, _ = self._scan(tmp, "reason")
            self.assertEqual([], [f for f in data["findings"]
                                 if f["rule_id"] == "JZ-SQLI-001"],
                             "带理由的行内豁免没生效")
            sup = data.get("suppressed") or []
            self.assertTrue(any(s["rule_id"] == "JZ-SQLI-001" for s in sup),
                            "豁免必须留痕：%s" % data["stats"])
            self.assertIn(u"内部任务", sup[0]["reason"])

    def test_suppression_without_reason_does_not_hide(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.py", self.VULN.replace(
                "    q = request.args['q']",
                "    q = request.args['q']  # jiangzuo:ignore JZ-SQLI-001"))
            data, _ = self._scan(tmp, "noreason")
            self.assertTrue([f for f in data["findings"]
                             if f["rule_id"] == "JZ-SQLI-001"],
                            "没写理由的豁免不该生效，否则误报被静默藏掉")
            self.assertGreaterEqual(data["stats"].get("invalid_suppressions", 0), 1,
                                    "无效豁免要被数出来并报告")

    def test_suppression_is_rule_specific(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.py", self.VULN.replace(
                "    q = request.args['q']",
                "    q = request.args['q']  # jiangzuo:ignore JZ-SSRF-001 豁免的是别的规则"))
            data, _ = self._scan(tmp, "other")
            self.assertTrue([f for f in data["findings"]
                             if f["rule_id"] == "JZ-SQLI-001"],
                            "豁免另一条规则不该把这条一起藏掉")

    def test_invalid_suppression_is_counted_once_per_file(self):
        """无效豁免的计数口径是**文件**，不是**发现**。
        复核本仓库自扫时实测到反例：一个文件里只有 1 条没写理由的标记，
        但该文件有 12 条发现，`stats.invalid_suppressions` 就报成了 12——
        报告里"12 条豁免写法无效"是把同一条数了 12 遍，数字直接失真。"""
        with tempfile.TemporaryDirectory() as tmp:
            text = (u"import os\nfrom flask import request\nimport sqlite3\n\n\n"
                    u"@app.route('/a')\ndef a():\n"
                    u"    q = request.args['q']  # jiangzuo:ignore JZ-SQLI-001\n"
                    u"    con = sqlite3.connect('db.sqlite')\n"
                    u"    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}').fetchall()\n"
                    u"\n\n@app.route('/b')\ndef b():\n"
                    u"    cmd = request.args['c']\n"
                    u"    return os.system(cmd)\n")
            self._write(tmp, "a.py", text)
            data, out = self._scan(tmp, "count")
            hits = [f for f in data["findings"] if f["file"].endswith("a.py")]
            self.assertGreaterEqual(len(hits), 2,
                                    "夹具必须产生同文件多发，否则这条锁测不到东西：%s" % out)
            self.assertEqual(1, data["stats"].get("invalid_suppressions"),
                             "同一条无效标记被按发现条数重复累加（应为 1，实为 %s）"
                             % data["stats"].get("invalid_suppressions"))

    def test_ignore_file_suppresses_by_path_and_rule(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "a.py", self.VULN)
            self._write(tmp, ".jiangzuoignore",
                        "a.py JZ-SQLI-001 演示代码，不接生产\n")
            data, _ = self._scan(tmp, "file")
            self.assertEqual([], [f for f in data["findings"]
                                 if f["rule_id"] == "JZ-SQLI-001"])
            self._write(tmp, ".jiangzuoignore", "other.py JZ-SQLI-001 路径不匹配\n")
            data2, _ = self._scan(tmp, "file2")
            self.assertTrue([f for f in data2["findings"]
                             if f["rule_id"] == "JZ-SQLI-001"],
                            "忽略文件里的路径不该误伤别的文件")


class TestAuditSarifCheck(unittest.TestCase):
    """B3：SARIF 自检必须"能红"——同一条测试里既验干净通过，也验坏数据被抓。"""

    def _sarif(self, tmp):
        with io.open(os.path.join(tmp, "a.py"), "w", encoding="utf-8", newline="\n") as f:
            f.write("from flask import request\nimport sqlite3\n\n\n"
                    "@app.route('/a')\ndef a():\n"
                    "    q = request.args['q']\n"
                    "    con = sqlite3.connect('db.sqlite')\n"
                    "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}')"
                    ".fetchall()\n")
        sarif = os.path.join(tmp, "r.sarif")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), tmp, "--sarif", sarif])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("SARIF 字段级自检：通过", r.stdout)
        with io.open(sarif, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_clean_sarif_passes_and_broken_is_caught(self):
        sys.path.insert(0, SCRIPTS)
        import audit_scan
        with tempfile.TemporaryDirectory() as tmp:
            doc = self._sarif(tmp)
            self.assertEqual([], audit_scan.sarif_selfcheck(doc), "自家产物自检没过")
            cases = {
                "uri 用反斜杠": lambda d: d["runs"][0]["results"][0]["locations"][0]
                    ["physicalLocation"]["artifactLocation"].__setitem__("uri", "src\\a.py"),
                "ruleId 未在 rules 声明": lambda d: d["runs"][0]["results"][0].__setitem__(
                    "ruleId", "JZ-NOT-A-RULE"),
                "缺 partialFingerprints": lambda d: d["runs"][0]["results"][0].pop(
                    "partialFingerprints"),
                "level 非法": lambda d: d["runs"][0]["results"][0].__setitem__(
                    "level", "severe"),
                "缺 locations": lambda d: d["runs"][0]["results"][0].__setitem__(
                    "locations", []),
                "version 不对": lambda d: d.__setitem__("version", "2.0.0"),
            }
            for name, mutate in cases.items():
                broken = json.loads(json.dumps(doc))
                mutate(broken)
                problems = audit_scan.sarif_selfcheck(broken)
                self.assertTrue(problems, "坏 SARIF 没被抓出来：%s" % name)


class TestAuditSarifSchema(unittest.TestCase):
    """E21：SARIF 必须过官方 SARIF 2.1.0 schema。

    v0.54.0 之前把 conceptualName 塞在 physicalLocation 里——官方
    sarif-multitool validate 报 JSON1005（8 条 error），而当时的字段级自检是
    绿的：自检压根没看 codeFlows 里的 location。这条测试把那个盲区钉死：
    同一条里既验自家产物干净，也验三类坏数据（多属性、message 放错层、
    codeFlows 里的坏 location）都能被抓出来，还验自定义 properties 键不被误伤。
    """

    PHP = ("<?php\n"
           "$q = $_GET['q'];\n"
           "$sql = \"SELECT * FROM t WHERE id = \" . $q;\n"
           "mysql_query($sql);\n")

    def _sarif(self, tmp):
        with io.open(os.path.join(tmp, "v.php"), "w", encoding="utf-8", newline="\n") as f:
            f.write(self.PHP)
        sarif = os.path.join(tmp, "r.sarif")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), tmp, "--sarif", sarif])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(sarif, "r", encoding="utf-8") as f:
            return json.load(f)

    def _flow_location(self, doc):
        for res in doc["runs"][0]["results"]:
            for cf in res.get("codeFlows") or []:
                for tf in cf.get("threadFlows") or []:
                    for loc in tf.get("locations") or []:
                        return loc
        return None

    def test_real_sarif_passes_and_keeps_flow_info(self):
        sys.path.insert(0, SCRIPTS)
        import audit_scan
        with tempfile.TemporaryDirectory() as tmp:
            doc = self._sarif(tmp)
            self.assertEqual([], audit_scan.sarif_selfcheck(doc), "自家产物没过自检")
            self.assertEqual([], audit_scan.sarif_schema_problems(doc))
            flow_loc = self._flow_location(doc)
            self.assertIsNotNone(flow_loc,
                                 "夹具没产出数据流，测的就不是 codeFlows 那条路")
            phys = flow_loc["location"]["physicalLocation"]
            self.assertNotIn("conceptualName", phys)
            self.assertIn("message", flow_loc["location"],
                          "message 属于 location 层")
            self.assertNotIn("message", phys,
                             "message 不属于 physicalLocation 层")
            self.assertTrue((flow_loc["location"].get("message") or {}).get("text"))

    def test_bad_properties_are_caught_including_codeflows(self):
        sys.path.insert(0, SCRIPTS)
        import audit_scan
        with tempfile.TemporaryDirectory() as tmp:
            doc = self._sarif(tmp)
            cases = {
                "physicalLocation 多属性": lambda l: l["location"]["physicalLocation"]
                    .__setitem__("conceptualName", "x"),
                "message 放错层": lambda l: l["location"]["physicalLocation"]
                    .__setitem__("message", {"text": "x"}),
            }
            for name, mutate in cases.items():
                broken = json.loads(json.dumps(doc))
                loc = self._flow_location(broken)
                self.assertIsNotNone(loc)
                mutate(loc)
                problems = audit_scan.sarif_selfcheck(broken)
                self.assertTrue(problems, "坏 SARIF 没被抓出来：%s" % name)
                self.assertTrue(any("schema 不允许" in p for p in problems),
                                "报的不是 schema 违规：%s" % problems)
            # results[].locations 这条路（自检本来就在看）同样要能抓 schema 违规
            broken = json.loads(json.dumps(doc))
            broken["runs"][0]["results"][0]["locations"][0]["physicalLocation"][
                "conceptualName"] = "x"
            problems = audit_scan.sarif_selfcheck(broken)
            self.assertTrue(any("conceptualName" in p for p in problems),
                            "locations 层的 schema 违规没被抓：%s" % problems)

    def test_custom_property_keys_are_not_flagged(self):
        """自定义键（jiangzuo:context 之类）住在 propertyBag 里，不该被当成违规。"""
        sys.path.insert(0, SCRIPTS)
        import audit_scan
        with tempfile.TemporaryDirectory() as tmp:
            doc = self._sarif(tmp)
            res = doc["runs"][0]["results"][0]
            res.setdefault("properties", {})["jiangzuo:context"] = "main"
            res["properties"]["custom-key"] = [1, 2, 3]
            self.assertEqual([], audit_scan.sarif_schema_problems(doc),
                             "自定义 properties 键被误伤了")

    def test_schema_extractor_reports_mismatch_with_exit_code(self):
        """提取器对着残缺 schema 必须退出码非零——工具"跳过"不能长得像"通过"。"""
        with tempfile.TemporaryDirectory() as tmp:
            mini = os.path.join(tmp, "mini.json")
            with io.open(mini, "w", encoding="utf-8", newline="\n") as f:
                f.write(json.dumps({
                    "additionalProperties": False,
                    "properties": {"runs": {"type": "array"}},
                    "definitions": {"location": {
                        "additionalProperties": False,
                        "properties": {"id": {"type": "integer"}}}}},
                    ensure_ascii=False))
            r = run([os.path.join(SCRIPTS, "sarif_schema_extract.py"), "--check",
                     "--schema-file", mini])
            self.assertNotEqual(r.returncode, 0,
                                "白名单与残缺 schema 不一致却退出码 0：%s" % r.stdout)
            self.assertIn("MISSING-IN-SCHEMA", r.stdout)


class TestAuditCapabilityBoundaries(unittest.TestCase):
    """E22：能力边界表必须被最小夹具钉住——否则引擎演进之后那张表会开始说谎。

    锁的是「引擎当前的行为」，不是「它应该怎样」：边界表说做不到的事，
    当前行为就是做不到；哪天真做到了，这些测试会红 ⇒ 提醒改表而不是让表过期。
    """

    REFS = os.path.join(REPO, "references", "audit-rule-authoring.md")

    def _scan(self, tmp, name, body):
        d = os.path.join(tmp, name)
        os.makedirs(d)
        with io.open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        out = os.path.join(tmp, name + ".json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), d, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def _rules(self, payload):
        return set(f["rule_id"] for f in payload["findings"])

    def test_escaped_string_is_not_treated_as_sanitizer(self):
        """边界：**已闭合**（E33）—— 这个形态现在判得了。

        ⚠️ E22 记下时锁的是"净化点 pattern 匹配不到 mysqli_real_escape_string
        ⇒ 转义处照报"这个**已知缺陷的现状**；E30/E31 做掉一半后它变红了（它自己的失败信息
        就写着"能力边界表第 2 行该改"）⇒ **E33 把上下文判定接到 sink 行上**，边界闭合
        ⇒ 本条随之退役，换成 `TestAuditSqlQuoteInSink` 里的两条
        （引号内**不报** / 引号外**仍报**）。
        """
        self.skipTest("E33：这条边界已闭合；替代判据见 TestAuditSqlQuoteInSink")

    def test_js_regex_literal_swallows_same_line_code(self):
        """边界：JS 正则字面量里的 // 被当注释 ⇒ 同行后续代码整段被漏掉。"""
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "e22_jsregex.js",
                           "var re = /\\/\\//; var x = request.query['q']; eval(x);\n")
            self.assertNotIn("JZ-CODE-001", self._rules(p),
                             "JS 正则字面量不再吞掉同行代码 ⇒ 能力边界表第 3 行该改")
            p2 = self._scan(tmp, "e22_jscode.js",
                            "var x = request.query['q']; eval(x);\n")
            self.assertIn("JZ-CODE-001", self._rules(p2), "对照组：真代码必须照报")

    def test_nested_block_comment_ends_at_first_closer(self):
        """边界：块注释不支持嵌套（PHP/C 的实际语义）⇒ 第一个 */ 之后的代码是活的。"""
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "e22_nested.php",
                           "<?php\n"
                           "/* /* nested */\n"
                           "$x = $_GET['a'];\n"
                           "echo $x;\n")
            self.assertIn("JZ-XSS-002", self._rules(p),
                          "嵌套块注释后的代码没被当成活代码 ⇒ 行为变了")

    def test_boundary_table_has_why_and_cost(self):
        """边界表每行都要有「为什么做不到」和「代价」两列 —— 少一列这张表就没法用。"""
        with io.open(self.REFS, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        start = None
        for i, line in enumerate(lines):
            if line.startswith("| 边界 |"):
                start = i
                break
        self.assertIsNotNone(start, "能力边界表不见了")
        rows = []
        for line in lines[start + 2:]:
            if not line.startswith("|"):
                break
            rows.append(line)
        self.assertGreaterEqual(len(rows), 5, "能力边界表少于 5 行")
        for row in rows:
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            self.assertEqual(4, len(cells), "边界表列数变了：%s" % row[:60])
            self.assertTrue(cells[1], u"缺「为什么做不到」：%s" % row[:40])
            self.assertTrue(cells[2], u"缺「代价」：%s" % row[:40])
            self.assertTrue(cells[3], u"缺「实测证据」：%s" % row[:40])


class TestBenchAggregation(unittest.TestCase):
    """E23：性能护栏不许退回"单次测量"，而"取均值"这件事本身要被机器判据钉住。

    E16 实测：共享机器上单次 bench 读数在 4.4–10.1 ms/文件之间跳 ⇒ 单次测量
    **既会误红**（CI 红了但代码没退化）**也会误绿**（退化一次没被抓住）。
    CI 因此改成 `--repeat 2` 取均值；本类把"不许退回单次"变成会红的判据。
    """

    WORKFLOW = os.path.join(REPO, ".github", "workflows", "validate.yml")
    BENCH_DIR = os.path.join(REPO, "evals", "audit-fixtures")

    def test_ci_bench_uses_repeat_at_least_two(self):
        with io.open(self.WORKFLOW, "r", encoding="utf-8") as f:
            text = f.read()
        repeats = re.findall(r"--repeat\s+(\d+)", text)
        self.assertTrue(repeats, "CI 的 bench 步没写 --repeat")
        for r in repeats:
            self.assertGreaterEqual(int(r), 2,
                "CI 的 bench 用 --repeat %s（单次测量）⇒ 读数随机器负载跳变" % r)

    def test_aggregate_rows_takes_fastest_not_mean_or_sum(self):
        """时间必须取**最快一次**。

        ⚠️ 这条不是随手挑的统计量：本机实测（2026-10-21，400 文件各 3 轮）
        单次读数 4.605/4.642/4.780（极差 3.8%），而两轮**均值**是
        4.819/4.821/5.376（极差 11.6%）⇒ **均值反而更抖**（对离群值不稳健）。
        取最快一次的理由：性能噪声只会让读数**变大** ⇒ 最小值抗噪、不会误红；
        真回退会让每次都慢 ⇒ 最小值照样超预算 ⇒ 回退仍拦得住。
        """
        sys.path.insert(0, self.BENCH_DIR)
        import bench
        rows = [("整链 audit_scan.run", 4.0, 100),
                ("整链 audit_scan.run", 6.0, 200),
                ("索引 build_index", 2.0, 50),
                ("索引 build_index", 4.0, 80)]
        agg = bench.aggregate_rows(rows, 2)
        self.assertAlmostEqual(4.0, agg["整链 audit_scan.run"][0], places=6,
                               msg="时间必须取最快一次（4），不是均值 5，也不是累加 10")
        self.assertEqual(200, agg["整链 audit_scan.run"][1],
                         "峰值内存取最大值，不是平均")
        self.assertAlmostEqual(2.0, agg["索引 build_index"][0], places=6)

    def test_aggregate_rows_survives_repeat_zero(self):
        sys.path.insert(0, self.BENCH_DIR)
        import bench
        agg = bench.aggregate_rows([("x", 3.0, 10)], 0)
        self.assertAlmostEqual(3.0, agg["x"][0], places=6,
                               msg="repeat=0 不该崩也不该算出 0")



class TestMutCalibratorShipped(unittest.TestCase):
    """E24：变异校准器必须随技能一起分发，且例数**不许手抄**。

    ⚠️ 这条判据治的是本项目反复吃过的亏：校准例数是写进 CHANGELOG / 验收记录 /
    台账的数字，而 E19–E23 连续五轮把它**手数错了**（各差 1）。
    现在它由 validate 从实物数出来 ⇒ 写错当场红。
    """

    def test_validate_reports_mut_calibrator(self):
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("变异校准器已随技能分发", r.stdout)

    def test_changelog_case_count_matches_real_cases(self):
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        with io.open(os.path.join(SCRIPTS, "mut_calibrate.py"), "r",
                     encoding="utf-8") as f:
            src = f.read()
        n = validate_skill._mut_case_count(src)
        self.assertIsNotNone(n, "数不出 CASES 条数")
        self.assertGreaterEqual(n, 30, "校准用例少于 30 条——是不是被删过？")
        with io.open(os.path.join(REPO, "CHANGELOG.md"), "r", encoding="utf-8") as f:
            cl = f.read()
        m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)\]?", cl, re.M)
        seg = re.split(r"\n## ", cl[m.end():], 1)[0]
        mm = re.search(r"变异校准\s*\*?\*?(\d+)\s*/\s*(\d+)", seg)
        self.assertIsNotNone(mm, "CHANGELOG 最新条目没写「变异校准 N/N」")
        self.assertEqual(n, int(mm.group(1)),
                         "CHANGELOG 写的校准例数与实物不一致——数字只能从真实输出抄")

    def test_case_counter_really_counts(self):
        """反例：喂一份只有 2 条用例的假源码，必须数出 2（不是恒返回一个数）。"""
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        fake = "CASES = [('a', 'x', 'y', 'l', 't'), ('b', 'x', 'y', 'l', 't')]\n"
        self.assertEqual(2, validate_skill._mut_case_count(fake))
        self.assertIsNone(validate_skill._mut_case_count("x = 1\n"))
        self.assertIsNone(validate_skill._mut_case_count("def (:\n"))

    def test_calibrator_flags_a_case_whose_test_id_is_missing(self):
        """E29：校准器必须把「test id 不存在」报出来。

        ⚠️ 为什么这条要紧：`unittest` 对"找不到的测试 id"**也返回非零** ⇒
        校准器会把"恒红"当成"判据红"（**假红灯**）⇒ 那条校准什么都没证明，
        却照样被算进"全部 RED"。E29 那条 `xss-document-write-constant-back`
        就中招了：它指向的测试被放进了别的类 ⇒ 跑出来是 AttributeError，
        不是判据红 ⇒ 43 条"全红"里有 1 条是**空转**。
        ⇒ 这里喂一条**不存在的 test id** 进去，必须被报出来。
        """
        sys.path.insert(0, SCRIPTS)
        import mut_calibrate
        mut_calibrate = importlib.reload(mut_calibrate)
        bogus = [("scripts/x.py", "old", "new", "bogus-case",
                  "tests.test_scripts.TestAuditXssConstantAssignment"
                  ".test_no_such_method_here")]
        self.assertGreater(mut_calibrate.check_test_ids(bogus), 0,
                           "校准器没报出「test id 不存在」")
        # 正例：真实用例集必须一处问题都没有
        self.assertEqual(mut_calibrate.check_test_ids(mut_calibrate.CASES), 0,
                         "真实用例集里查出了问题")

    def test_calibrator_baseline_rejects_a_missing_test_id(self):
        """E29：运行时那道「基线必须绿」也要有牙齿。

        ⚠️ 静态检查只能查"存在"，查不了"本来是不是红的" ⇒ 运行时还得再兜一层：
        判据在**未变异**代码上就必须是绿的，否则这次变异证明不了任何东西。
        """
        sys.path.insert(0, SCRIPTS)
        import mut_calibrate
        mut_calibrate = importlib.reload(mut_calibrate)
        ok, why = mut_calibrate.baseline_ok(
            "tests.test_scripts.TestAuditXssConstantAssignment.test_no_such_method_here")
        self.assertFalse(ok, "基线检查没认出「测试 id 不存在」")
        self.assertIn("不存在", why)
        # 正例：一条真在跑、也确实绿的判据，必须被认成绿
        ok2, why2 = mut_calibrate.baseline_ok(
            "tests.test_scripts.TestAuditXssConstantAssignment"
            ".test_plain_variable_assignment_is_still_reported")
        self.assertTrue(ok2, "真实绿判据被误判成不绿：%s" % why2)


class TestVerdictTable(unittest.TestCase):
    """E29：判定表的自洽检查（`validate_skill` 第 21 项）必须**真的会红**。

    ⚠️ 这项检查此前**一把都没验过**：E28 把它加进 `validate` 就算数了，既没有
    单元测试，也没有变异校准例 ⇒ 它可能一直红不了（也可能一直乱红）。
    E29 复核时还挖出它一个**潜伏 bug**：「flask 等」的条数错用了「静态可修」的条数
    （E28 时两个数恰好都是 1，所以错了一个月也没露馅；E29 把「静态可修」清零后当场炸）。
    ⇒ 本类守住：① 自洽的表必须判**自洽**；② 各种破坏必须**当场红**。
    """

    # 一张**自洽**的合成表：故意让「静态可修」(3) ≠ flask 行(1)。
    # ⚠️ 这一条正对 E29 修的那个 bug：旧代码拿「静态可修」当「flask 等」用
    # ⇒ 60 + 3 = 63 ≠ 61 ⇒ 它会把**这张自洽的表**判成不自洽（误杀）。
    SYNTH = """# 合成判定表

## 一、汇总（按规则）

| 规则 | 结论区条数 | 真阳性 | 误报 | 备注 |
|---|---|---|---|---|
| JZ-XSS-001 | 60 | 55 | 5 | |
| **DVWA 小计** | **60** | **55** | **5** | |
| flask（`src/flask/json/tag.py:188`） | 1 | 0 | 1 | |
| **合计** | **61** | **55** | **6** | |

## 二、误报逐条

| # | 位置 | 形态 | 为什么是误报 | 归类 | 处置 |
|---|---|---|---|---|---|
| 1 | a.php:1 | x | y | **静态可修** | z |
| 2 | b.php:2 | x | y | **静态可修** | z |
| 3 | c.php:3 | x | y | **静态可修** | z |
| 4 | d.php:4 | x | y | **待能力升级** | z |
| 5 | e.php:5 | x | y | **待能力升级** | z |
| 6 | f.php:6 | x | y | **静态消不掉** | z |

## 三、三类误报的口径

| 类别 | 条数 | 含义 | 能不能靠改规则消掉 |
|---|---|---|---|
| **静态可修** | 3 | a | b |
| **待能力升级** | 2 | a | b |
| **静态消不掉（能力边界型）** | 1 | a | b |
"""

    def _run_on(self, tmp, table):
        """造一个最小技能目录（SKILL.md + evals/finding-verdicts.md）并跑 validate。"""
        evals = os.path.join(tmp, "evals")
        if not os.path.isdir(evals):
            os.makedirs(evals)
        with io.open(os.path.join(evals, "finding-verdicts.md"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write(table)
        with io.open(os.path.join(tmp, "SKILL.md"), "w",
                     encoding="utf-8", newline="\n") as f:
            f.write("---\nname: tmp-skill\ndescription: temporary fixture\n"
                    "---\n\nbody\n")
        return run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])

    def test_validate_reports_the_verdict_table_check(self):
        """正例：真仓库的判定表必须被判成自洽（且 validate 整体通过）。"""
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("结论区判定表自洽", r.stdout)

    def test_a_self_consistent_table_must_pass_even_when_fixable_differs_from_flask(self):
        """E29 修的正是这个：自洽的表**不许**被误杀。

        ⚠️ 旧代码拿「静态可修」的条数当「flask 等」用 ⇒ 这张自洽的表
        （静态可修 3 ≠ flask 1）会被算成 60 + 3 = 63 ≠ 61 ⇒ 误判不自洽。
        """
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_on(tmp, self.SYNTH)
            self.assertNotIn("判定表不自洽", r.stdout,
                             "自洽的表被判成不自洽（flask 的条数取错了）")

    def test_broken_totals_must_be_flagged(self):
        """反例：合计行的真阳性 + 误报 != 合计 ⇒ 必须当场红。"""
        broken = self.SYNTH.replace("| **合计** | **61** | **55** | **6** | |",
                                    "| **合计** | **61** | **55** | **7** | |", 1)
        self.assertNotEqual(broken, self.SYNTH, "没找到要破坏的合计行")
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_on(tmp, broken)
            self.assertNotEqual(r.returncode, 0, "合计不自洽时 validate 竟然通过了")
            self.assertIn("判定表不自洽", r.stdout)

    def test_broken_flask_row_must_be_flagged(self):
        """反例：flask 行的条数与合计对不上 ⇒ 必须当场红。"""
        broken = self.SYNTH.replace(
            "| flask（`src/flask/json/tag.py:188`） | 1 | 0 | 1 | |",
            "| flask（`src/flask/json/tag.py:188`） | 2 | 0 | 2 | |", 1)
        self.assertNotEqual(broken, self.SYNTH, "没找到要破坏的 flask 行")
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_on(tmp, broken)
            self.assertNotEqual(r.returncode, 0, "flask 行对不上时 validate 竟然通过了")
            self.assertIn("判定表不自洽", r.stdout)

    def test_section_two_rows_must_match_the_bucket_table(self):
        """反例：§二 里某行的「归类」改了、§三 没改 ⇒ 必须当场红。

        ⚠️ 这条正对 E29 新加的**逐行对账**（从 §二 的行反推三类条数）：
        只看 §三 声明的数字，看不出这种"改了一行没改另一处"。
        """
        broken = self.SYNTH.replace(
            "| 4 | d.php:4 | x | y | **待能力升级** | z |",
            "| 4 | d.php:4 | x | y | **静态消不掉** | z |", 1)
        self.assertNotEqual(broken, self.SYNTH, "没找到要破坏的 §二 行")
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run_on(tmp, broken)
            self.assertNotEqual(r.returncode, 0, "§二 与 §三 对不上时 validate 竟然通过了")
            self.assertIn("判定表不自洽", r.stdout)
            self.assertIn("标「待能力升级」", r.stdout)


class TestAuditOverbroadRuleNarrowing(unittest.TestCase):
    """E25：E20 判定出的 3 类「规则过宽」硬误报，收窄后必须**正反成对**地钉住。

    E20 的判定（按 sink 行逐条判过）：`preg_replace` 被当动态代码执行（2 条）、
    `error_reporting(E_ALL)` 被当调试信息泄露（1 条）、
    `$_SERVER['CONTENT_TYPE']` 被当文件上传（2 条）—— 合计 **5 条**（E20 当时写成 4 条，
    自己的算术就错了）。本轮把三条 sink 收窄，每条都要：
      · **正面**：真正的漏洞形态**仍要报**（不许把能力一起砍掉）
      · **反面**：DVWA 里那类形态**不再报**（这才是本轮的目的）
    ⚠️ 只测反面 = 把规则改死了；只测正面 = 什么都没修。
    """

    def _scan(self, tmp, name, files):
        d = os.path.join(tmp, name)
        os.makedirs(d)
        for fn, body in files.items():
            path = os.path.join(d, fn)
            parent = os.path.dirname(path)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(body)
        out = os.path.join(tmp, name + ".json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), d, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def _rules(self, payload):
        return set(f["rule_id"] for f in payload["findings"])

    def _app_files(self, extra):
        """让仓库被判成 app（config 型规则 scope=app ⇒ 库里会被压成"不适用"）。"""
        files = {"app.py": "from flask import Flask\napp = Flask(__name__)\n",
                 "templates/x.html": "<html><body>hi</body></html>\n"}
        files.update(extra)
        return files

    def test_preg_replace_is_not_dynamic_code_execution(self):
        """`preg_replace` 自 PHP 5.5 起没有 /e 修饰符 ⇒ 不再是动态代码执行。

        ⚠️ 能力边界（**当前检不出**，不是漏报）：PHP < 5.5 的 `preg_replace('/x/e', ...)`
        真的会执行代码，但 JZ-CODE-001 是 `ignore_strings: true` 的规则 ⇒ 它在
        **掩码桶**（字符串字面量被剥掉）上匹配 ⇒ **看不见字符串里的 `/e` 修饰符**。
        要认它就得让规则走**原文桶**（`ignore_strings: false`），而那会让所有 sink
        都能在字符串内部命中 ⇒ 误报面变大 ⇒ 本轮不做，登记为能力边界。
        ⚠️ 同理 `create_function` 的函数体也在字符串里 ⇒ 它在当前引擎下同样检不出
        真阳性（污点链断在字符串内）⇒ 正面的"能力还在"由 `eval` 承担（下一条）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            bad = self._scan(tmp, "pcre", {
                "a.php": "<?php\n$name = preg_replace('/<(.*)s(.*)c(.*)r(.*)i(.*)p(.*)t/i', '', $_GET['name']);\n"})
            self.assertNotIn("JZ-CODE-001", self._rules(bad),
                             "不带 /e 的 preg_replace 不该再被当动态代码执行")
            older = self._scan(tmp, "pcre_e", {
                "a.php": "<?php\n$name = preg_replace('/(.*)e/e', '', $_GET['name']);\n"})
            self.assertNotIn("JZ-CODE-001", self._rules(older),
                             "掩码桶看不见字符串里的 /e —— 这是**已知能力边界**，"
                             "不是本轮要保证的能力")

    def test_error_reporting_alone_is_not_a_leak(self):
        """`error_reporting(E_ALL)` 只设错误级别，本身不泄露；泄露的是 display_errors=On。"""
        with tempfile.TemporaryDirectory() as tmp:
            bad = self._scan(tmp, "errrep", self._app_files({
                "a.php": "<?php\nerror_reporting(E_ALL);\n"}))
            self.assertNotIn("JZ-DEBUG-001", self._rules(bad),
                             "error_reporting(E_ALL) 不是调试信息泄露")
            good = self._scan(tmp, "disp", self._app_files({
                "a.php": "<?php\nini_set('display_errors', 'On');\ndisplay_errors = On;\n"}))
            self.assertIn("JZ-DEBUG-001", self._rules(good),
                          "display_errors=On 是真泄露，必须仍报")

    def test_content_type_check_must_be_about_the_uploaded_file(self):
        """`$_SERVER['CONTENT_TYPE']` 是请求头（DVWA 的 JSON API 在读它），不是上传限制。

        ⚠️ 语义锁（本轮真踩过）：这条规则要报的是"上传**缺**类型/大小/文件名限制"，
        是**否定**判断；把它写成"出现了 `$_FILES[…]['type']` 检查"就把语义**反**了
        —— 那反而是"有类型检查"，是合规写法 ⇒ 实测在 DVWA 的**修复档**
        `upload/source/impossible.php` 里报出一条**新误报**（逐条 A/B 逮到的）。
        ⇒ 「缺少 X」这类否定判断在**正向 pattern** 里表达不了 ⇒ 那个 sink 整条去掉，
        这一子形态登记为能力边界；本条只保留"上传动作 + 原始文件名"那支（sink1）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            bad = self._scan(tmp, "ctype", {
                "a.php": ("<?php\nif (array_key_exists (\"CONTENT_TYPE\", $_SERVER) "
                          "&& $_SERVER['CONTENT_TYPE'] == \"application/json\") {\n"
                          "    handle();\n}\n")})
            self.assertNotIn("JZ-UPLOAD-001", self._rules(bad),
                             "请求头的内容类型检查不是文件上传限制")
            typed = self._scan(tmp, "typed", {
                "a.php": "<?php\nif ($_FILES['f']['type'] != 'image/jpeg') { exit; }\n"})
            self.assertNotIn("JZ-UPLOAD-001", self._rules(typed),
                             "**已经**检查了上传文件类型 ⇒ 那是合规写法，不该报"
                             "（语义反了就是这类错）")
            good = self._scan(tmp, "filetype", {
                "a.php": ("<?php\nmove_uploaded_file($_FILES['f']['tmp_name'], "
                          "$_FILES['f']['name']);\n")})
            self.assertIn("JZ-UPLOAD-001", self._rules(good),
                          "上传动作 + 直接用原始文件名必须仍报")

    def test_eval_still_counts_as_dynamic_code(self):
        """防误伤：收窄 preg_replace 不能把 eval 一起收掉。"""
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "eval", {
                "a.php": "<?php\n$code = $_GET['c'];\neval($code);\n"})
            self.assertIn("JZ-CODE-001", self._rules(p), "eval 必须仍归 JZ-CODE-001")


class TestAuditXssConstantAssignment(unittest.TestCase):
    """E26：给 `innerHTML` 赋**纯字符串常量**不是 XSS（E20 留下的"需人工细判"清零）。

    ⚠️ 为什么这件事能在**掩码桶**里判：`JZ-XSS-001` 是 `ignore_strings: true` 的
    pattern 规则 ⇒ 它匹配的行上字符串字面量被剥成 `''` ⇒
    「纯常量赋值」= `innerHTML = '';`，而「常量 + 变量」= `innerHTML = '' + name;`
    ⇒ 一条负向先行就能把两者分开。
    ⚠️ 也因此**必须写成"把空格算进负向先行"**：`(?!['"]["']\s*;)` 会被 `\s*` 的
    回溯绕过去（`\s*` 吃 0 个空格 ⇒ 负向先行看到 ` '';` ⇒ 通过）—— 我第一版就踩了。
    """

    def _scan(self, tmp, name, body):
        d = os.path.join(tmp, name)
        os.makedirs(d)
        with io.open(os.path.join(d, "a.js"), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        out = os.path.join(tmp, name + ".json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), d, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return set(x["rule_id"] for x in json.load(f)["findings"])

    def test_constant_assignment_is_not_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "const",
                           "var el = document.getElementById('a');\n"
                           "el.innerHTML = 'User details: ';\n")
            self.assertNotIn("JZ-XSS-001", p,
                             "给 innerHTML 赋纯字符串常量不是 XSS")

    def test_constant_plus_variable_is_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "var",
                           "var name = document.query['q'];\n"
                           "el.innerHTML = 'User details: ' + name;\n")
            self.assertIn("JZ-XSS-001", p,
                          "常量 + 变量仍要报（收窄不能把真阳性砍掉）")

    def test_plain_variable_assignment_is_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "plain",
                           "var k = document.query['k'];\n"
                           "cell.innerHTML = k;\n")
            self.assertIn("JZ-XSS-001", p, "变量赋值必须仍报")

    def test_document_write_constant_is_not_reported(self):
        """`document.write("<常量>")` 不是 XSS（E29）。

        ⚠️ 判据必须用**真实代码**（带字符串字面量），因为引擎跑在**掩码桶**上：
        字符串被剥成 `''` ⇒ 常量形态 = `document.write('');`、带变量形态 =
        `document.write('' + lang + '');` ⇒ 负向先行才能把两者分开。
        ⚠️ 掩码形态里 `''` 与 `;` 之间还夹着一个 `)` ⇒ 负向必须容忍它
        （E28 漏了这一个括号 ⇒ 收窄没生效，本轮补上）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "dwconst",
                           "var lang = document.query['q'];\n"
                           "document.write('<option>----</option>');\n")
            self.assertNotIn("JZ-XSS-001", p,
                             u"document.write 纯常量不是 XSS")

    def test_document_write_with_variable_is_still_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "dwvar",
                           "var lang = document.query['q'];\n"
                           "document.write('<option>' + lang + '</option>');\n")
            self.assertIn("JZ-XSS-001", p,
                          u"document.write 带上变量仍要报（收窄不能把真阳性砍掉）")



class TestHandoverInRepo(unittest.TestCase):
    """E27：交接文档必须**在仓库内**、章节完整、且被 git 跟踪。

    E26 那轮一个脚本 bug 把**仓库外**的交接文档整段覆盖掉了，而它当时不在 git 里
    ⇒ **无法回滚**，只能从会话记录里重建（整整花了一轮）。
    ⇒ 本类守住根因三件事：它在仓库里（validate 第 20 项）、关键章节齐全、且被 git 跟踪。
    """

    HANDOVER = os.path.join(REPO, "docs", "jiangzuo", "handover.md")

    def test_validate_reports_handover_in_repo(self):
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(u"交接文档在仓库内、章节完整、已被 git 跟踪", r.stdout)

    def test_handover_has_the_key_sections(self):
        with io.open(self.HANDOVER, "r", encoding="utf-8") as f:
            text = f.read()
        for head in (u"## 0. ", u"## 5. ", u"## 6. ", u"## 8. ", u"## 11. ",
                     u"## 13. ", u"## 14. "):
            self.assertIn(head, text, u"交接文档缺 %s" % head)

    def test_handover_is_tracked_by_git(self):
        p = subprocess.run(["git", "ls-files", "--error-unmatch", "--",
                             "docs/jiangzuo/handover.md"],
                           cwd=REPO, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        self.assertEqual(p.returncode, 0,
                         u"交接文档没被 git 跟踪（未跟踪的文件没有历史）：%s" % p.stderr)

    def test_validate_flags_a_handover_with_a_missing_section(self):
        """反例：交接文档缺关键章节时，validate 必须判错（不能静默放过）。"""
        with tempfile.TemporaryDirectory() as tmp:
            docs = os.path.join(tmp, "docs", "jiangzuo")
            os.makedirs(docs)
            with io.open(os.path.join(REPO, "docs", "jiangzuo", "handover.md"),
                         "r", encoding="utf-8") as f:
                text = f.read()
            broken = text.replace(u"## 8. ", u"## 8x. ", 1)
            self.assertNotEqual(broken, text, u"没找到要破坏的章节")
            with io.open(os.path.join(docs, "handover.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(broken)
            # validate 缺 SKILL.md 会**提前退出**、压根跑不到第 20 项 ⇒ 补一个最小入口
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write("---\nname: tmp-skill\ndescription: temporary fixture\n"
                        "---\n\nbody\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                u"交接文档缺章节时 validate 竟然通过了")
            self.assertIn(u"交接文档缺章节", r.stdout)

    def test_broken_pitfall_numbering_must_be_flagged(self):
        """反例：§8 坑位清单的编号**缺号**时，validate 必须判错。

        ⚠️ 编号是别人引用「§8 第 N 条」的索引 ⇒ 缺号会让引用指向错的地方
        （E32 实测：E22 插入时跳过了 36/37，编号 1..57 只有 55 条）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            docs = os.path.join(tmp, "docs", "jiangzuo")
            os.makedirs(docs)
            with io.open(os.path.join(REPO, "docs", "jiangzuo", "handover.md"),
                         "r", encoding="utf-8") as f:
                text = f.read()
            # 把 12. 改成 13. ⇒ 制造一个缺号（12）
            broken = text.replace("\n12. **", "\n13. **", 1)
            self.assertNotEqual(broken, text, "没找到要破坏的编号")
            with io.open(os.path.join(docs, "handover.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(broken)
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write("---\nname: tmp-skill\ndescription: temporary fixture\n"
                        "---\n\nbody\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                "§8 编号缺号时 validate 竟然通过了")
            self.assertIn("编号不连续", r.stdout)




class TestAuditOsv(unittest.TestCase):
    """B4：依赖建议接真实数据源。夹具是从 api.osv.dev 查 pyyaml 5.3 拉回的**真实记录**，
    不是编的样例；技能仓库只带这一份 10KB 样本，全量数据仍靠用户自己离线拉。"""

    OSV = os.path.join(REPO, "evals", "audit-fixtures", "osv-pyyaml.json")

    def _scan(self, root, extra):
        out = os.path.join(root, "_osv%s.json" % (len(extra) or 0))
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out] + extra)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_osv_import_adds_real_advisories(self):
        self.assertTrue(os.path.isfile(self.OSV), "OSV 夹具不存在")
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "requirements.txt"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write("pyyaml==5.3\n")
            plain, _ = self._scan(tmp, [])
            with_osv, stdout = self._scan(tmp, ["--osv", self.OSV])
            ids = [f["rule_id"] for f in with_osv["findings"]]
            self.assertTrue(any(i.startswith("OSV-") for i in ids),
                            "OSV 派生的建议没进报告：%s" % ids)
            self.assertGreater(len([i for i in ids if i.startswith("OSV-")]),
                               0)
            self.assertNotEqual(plain["rules_version"], with_osv["rules_version"],
                                "换了 advisory 数据而 rules_version 不变 → 缓存会拿旧结论")

    def test_malformed_osv_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = os.path.join(tmp, "bad.json")
            with io.open(bad, "w", encoding="utf-8") as f:
                f.write(json.dumps([{"id": "NOPE-1"}, {"package": {"name": "x"},
                                                       "affected": []}, "junk"]))
            r = run([os.path.join(SCRIPTS, "audit_rules.py"), "--validate",
                     "--osv", bad])
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"跳过 3 条", r.stdout)

    def test_validate_reports_osv_counts(self):
        r = run([os.path.join(SCRIPTS, "audit_rules.py"), "--validate",
                 "--osv", self.OSV])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("OSV 导入", r.stdout)
        self.assertIn("RESULT: RULES-OK", r.stdout)


class TestAuditPhpRequestBody(unittest.TestCase):
    """E9：PHP 读原始请求体（php://input）也是"外部可控输入"——E9 之前是整类盲区。

    PHP 的 JSON API 不走 $_POST，而是 `file_get_contents('php://input')` 读原始 body。
    E9 之前 source 词表只有 $_GET/$_POST/$_REQUEST ⇒ 这一整类入口看不见。
    DVWA `vulnerabilities/authbypass/change_user_details.php` 就是这个形态：
    读 body → json_decode → 取字段 → 拼进 SQL → mysqli_query。

    走通这条链要同时满足三件事，缺一件就断：
      ① source 认得 `file_get_contents('php://input')`——**必须匹配调用形状**：
         落在字符串字面量里的命中会被 match_in_string 过滤掉（那是夹具噪声逼出来的教训）；
      ② 污点能从 `json_decode($raw)` 的返回值传到 `$data`；
      ③ 污点能从 `$data->name` 这种对象属性取到。
    7 条 PHP 请求体规则都接了这个 source ⇒ 逐族各测一遍，不能只测 SQLi 那族。
    """

    HEAD = ("<?php\n"
            "$raw = file_get_contents('php://input');\n"
            "$data = json_decode($raw);\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_rb_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_request_body_reaches_each_php_rule(self):
        cases = [
            ("JZ-SQLI-003",
             "$name = $data->name;\n"
             "$sql = \"SELECT * FROM users WHERE name = '\" . $name . \"'\";\n"
             "$res = mysqli_query($conn, $sql);\n"),
            ("JZ-CMDI-001",
             "$cmd = $data->cmd;\n"
             "system(\"ls \" . $cmd);\n"),
            ("JZ-CODE-001",
             "$code = $data->code;\n"
             "eval($code);\n"),
            ("JZ-DESER-001",
             "$obj = unserialize($raw);\n"),
            ("JZ-TRAVERSAL-001",
             "$page = $data->page;\n"
             "include($page);\n"),
            ("JZ-SSRF-001",
             "$url = $data->url;\n"
             "$body = file_get_contents($url);\n"),
            # JZ-XSS-002 **暂不接**这个 source（E9 记录在案）：它的 sink 最宽
            # （任何 print/echo 一个 tainted 变量都报），加上请求体 source 后，
            # DVWA 的 check_token_high/impossible.php 报出 2 条**误报**——
            # check_token() 校验完只回一个常量 status JSON，可它返回的仍是
            # 入参派生的东西（引擎"污点穿函数返回值"这条近似）。
            # 根因在引擎不在规则，先修引擎再接这条（见验收记录 E9 与待办）。
        ]
        for rule_id, body in cases:
            with tempfile.TemporaryDirectory() as tmp:
                self._write(tmp, "api.php", self.HEAD + body)
                data, _ = self._scan(tmp, rule_id)
                ids = [f["rule_id"] for f in data["findings"]]
                self.assertIn(rule_id, ids,
                              "请求体流到 %s 的 sink 都没报出来：%s" % (rule_id, ids))

    def test_non_request_body_read_is_not_a_source(self):
        """`file_get_contents('/etc/passwd')` 读的是本地文件，**不是请求体**。

        source 词表认的是"读请求体"这个语义，不是"用了 file_get_contents"这个形状——
        否则任何读本地文件的 PHP 都会被当成外部输入。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "read_file.php",
                        "<?php\n"
                        "$content = file_get_contents('/etc/passwd');\n"
                        "$sql = \"SELECT * FROM t WHERE c = '\" . $content . \"'\";\n"
                        "$res = mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "notbody")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-SQLI-003", ids,
                             "读本地文件被当成了请求体：%s" % ids)

    def test_prepared_statement_still_blocks(self):
        """同一入口但走参数化 ⇒ 不该报（语料里的 safe_php_input_sql.php 是同一件事）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "api.php",
                        self.HEAD +
                        "$pdo = new PDO($dsn, $user, $pass);\n"
                        "$stmt = $pdo->prepare(\"SELECT * FROM users WHERE name = ?\");\n"
                        "$stmt->execute([$data->name]);\n")
            data, _ = self._scan(tmp, "prepared")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-SQLI-003", ids,
                             "参数化写法被报成注入了：%s" % ids)


class TestAuditPhpCrossFunction(unittest.TestCase):
    """E10：PHP 的**跨函数形参污点**——修复前整条是坏的（复核实测，不是推断）。

    真实 PHP 代码里极常见的一类形态：把 `$_GET['x']` 交给一个 helper，
    helper 里 echo / 拼 SQL / 调命令。**修复前这类形态一条都报不出来**，
    而且坏在**两层**：

    ① **形参名归一错了**：`_params()` 把 PHP 形参 `$name` 转成 `_name`，
       而载体名（`carriers_of`）是不带 `$` 的 `name` ⇒ 形参污点永远落不到
       被调函数里。
    ② **`{module}` 作用域的门槛**：`add_module_scope()` 写死"顶层行数 ≥ 3 才建作用域"，
       于是「`<?php` + 一个函数 + 一行顶层调用」这种最常见的短文件，
       **整段顶层代码都不进数据流**——与该函数自己的 docstring 自相矛盾。

    两层都修之后：同文件与跨文件的 helper 形态都能检出。
    """

    HELPER = ("<?php\n"
              "function show($name) {\n"
              "    echo \"Hello \" . $name;\n"
              "}\n")
    CALL = "show($_GET['name']);\n"

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_cf_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_param_taint_crosses_function_boundary_same_file(self):
        """同文件：helper 里 echo 形参 ⇒ 应报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php", self.HELPER + self.CALL)
            data, _ = self._scan(tmp, "same")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "同文件跨函数形参污点没报出来：%s" % ids)

    def test_param_taint_crosses_function_boundary_across_files(self):
        """跨文件：helper 在另一个文件里 ⇒ 应报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "lib.php", self.HELPER)
            self._write(tmp, "app.php",
                        "<?php\nrequire_once 'lib.php';\n" + self.CALL)
            data, _ = self._scan(tmp, "cross")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "跨文件跨函数形参污点没报出来：%s" % ids)

    def test_unused_param_is_not_reported(self):
        """形参没被用到 ⇒ 不该报（别把"有形参"当成"有洞"）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function show($name) {\n"
                        "    echo \"Hello\";\n"
                        "}\n"
                        "show($_GET['name']);\n")
            data, _ = self._scan(tmp, "unused")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "形参没被用到却报了：%s" % ids)


class TestAuditPhpReturnValue(unittest.TestCase):
    """E11：PHP 的**返回值**语义——修复前"实参"被当成了"返回值"。

    复核实测（四个最小夹具错三个，不是推断）：

    - `function check_token($t){ ...; return json_encode($ret); }` + `$out = check_token($t);`
      ⇒ `$out` 继承了 `$t` 的污点 ⇒ 报 XSS。**但 `check_token` 的返回值全是常量**
      （DVWA 真代码 `token_library_high.php`：`$ret` 的每个字段都来自常量表 `$users`，
      形参只用来解密校验和取下标，不进返回值）⇒ 误报。
    - 形参在被调函数里先被 `intval()` 净化再返回 ⇒ 净化被整条绕过 ⇒ SQLi 误报。
    - 污点源在被调函数**内部**（`return $_GET[$k];`）⇒ 调用方拿不到 ⇒ **漏报**。

    修法：给每个 (函数, 规则) 算一份「返回摘要」——返回值依赖哪些**形参下标**、
    返回值自带哪些污点；调用方不再把"实参"直接当成"返回值"。
    外部函数（`strtoupper` 这类）不在仓库里 ⇒ 保持原语义（保守，不制造漏报）。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_rv_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_return_value_not_inheriting_param_taint(self):
        """返回值不依赖形参（check_token 形态）⇒ 不该报。

        这是 DVWA `check_token_high/impossible.php` 的真实形态：
        `$ret = check_token($token);` 之后 `print $ret;`——而 `check_token`
        返回的 JSON 里每个字段都来自常量表 ⇒ 那是**误报**。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function check_token($token) {\n"
                        "    $ret = array('status' => 'ok', 'message' => 'constant');\n"
                        "    return json_encode($ret);\n"
                        "}\n"
                        "$token = $_GET['token'];\n"
                        "$out = check_token($token);\n"
                        "echo $out;\n")
            data, _ = self._scan(tmp, "notdep")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "返回值不依赖形参却继承了污点：%s" % ids)

    def test_return_value_inheriting_param_taint(self):
        """返回值**确实**依赖形参（原样转发）⇒ 该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function passthrough($k) {\n"
                        "    return $k;\n"
                        "}\n"
                        "$v = passthrough($_GET['name']);\n"
                        "echo $v;\n")
            data, _ = self._scan(tmp, "passthrough")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "返回值依赖形参却没报出来：%s" % ids)

    def test_sanitizer_inside_callee_blocks_taint(self):
        """形参在被调函数里先净化再返回 ⇒ 净化要生效，不该报 SQLi。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function clean_id($k) {\n"
                        "    $safe = intval($k);\n"
                        "    return $safe;\n"
                        "}\n"
                        "$v = clean_id($_GET['id']);\n"
                        "$q = \"SELECT * FROM t WHERE id = \" . $v;\n"
                        "mysqli_query($conn, $q);\n")
            data, _ = self._scan(tmp, "sanitized")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-SQLI-003", ids,
                             "被调函数里的净化被绕过了：%s" % ids)

    def test_source_inside_callee_reaches_caller(self):
        """污点源在被调函数**内部** ⇒ 调用方要拿到（修复前是漏报）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function get_value($k) {\n"
                        "    return $_GET[$k];\n"
                        "}\n"
                        "$v = get_value('name');\n"
                        "echo $v;\n")
            data, _ = self._scan(tmp, "inside")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "被调函数内部的污点源没传到调用方：%s" % ids)

    def test_external_function_call_still_inherits(self):
        """**外部**函数不在仓库里 ⇒ 保持原语义（不能因为收紧就制造漏报）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$t = $_GET['name'];\n"
                        "$out = strtoupper($t);\n"
                        "echo $out;\n")
            data, _ = self._scan(tmp, "external")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "外部函数的返回值不再继承污点（过度收紧 ⇒ 漏报）：%s" % ids)

    def test_dvwa_check_token_shape_not_reported(self):
        """DVWA 真代码形态（`token_library_high.php` + `check_token_high.php`）。

        ⚠️ 这里把 DVWA 原版的 `file_get_contents('php://input')` 换成了 `$_GET['token']`：
        **JZ-XSS-002 现在还没接 `php://input` 这个 source**（E9 实测接了会误报，
        根因就是这条引擎缺陷）。用没接的 source 写判据 ⇒ 这条**恒绿**，
        等于一条没有牙齿的锁（"永远绿的锁比没锁更坏"）。
        等下一轮接上 `php://input` 后，这里要换回原形态并补一条新判据。
        """
        lib = ("<?php\n"
               "function check_token ($data) {\n"
               "    $users = array ();\n"
               "    $users[1] = array (\"name\" => \"Geoffery\", \"level\" => \"admin\");\n"
               "    $data_array = json_decode ($data, true);\n"
               "    if (is_null ($data_array)) {\n"
               "        $ret = array (\"status\" => 522, \"message\" => \"Data in wrong format\");\n"
               "    } else {\n"
               "        $ret = array (\"status\" => 200, \"user\" => $users[1][\"name\"]);\n"
               "    }\n"
               "    return json_encode ($ret);\n"
               "}\n")
        page = ("<?php\n"
                "require_once (\"token_library_high.php\");\n"
                "$ret = \"\";\n"
                "$token = $_GET['token'];\n"
                "$ret = check_token ($token);\n"
                "print $ret;\n"
                "exit;\n")
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "lib.php", lib)
            self._write(tmp, "page.php", page)
            data, _ = self._scan(tmp, "dvwa")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "DVWA check_token 形态被误报（返回值全是常量）：%s" % ids)



class TestAuditSqlQuoteContext(unittest.TestCase):
    """E30：**净化点按 sink 上下文生效** —— 转义只在**引号内**有效。

    为什么需要它（E17/E22 两次登记的缺口）：DVWA 两处形态**几乎一样**
    （都调了 `mysqli_real_escape_string`），但判定必须不同：

    - `csrf/source/high.php:43`：`"UPDATE ... password = '" . $pass_new . "' ..."`
      ⇒ 值落在**引号内** ⇒ 转义把 `'` 变成 `\\'` ⇒ 注入不成立 ⇒ **不该报**；
    - `sqli_blind/source/medium.php:13`：`"SELECT ... WHERE user_id = $id;"`
      ⇒ 值落在**引号外**（数值上下文）⇒ 转义救不了任何东西 ⇒ **仍须报**。

    ⇒ 一刀切把转义当净化点＝**拿真阳性换误报**（E17 实测过这个坑）。

    ⚠️ 还有一条机制事实（E22 实测、到本轮才修）：旧净化点 pattern
    `\\breal_escape_string\\b` **匹配不到** `mysqli_real_escape_string`
    （`_` 是单词字符 ⇒ 无词边界）⇒ **这个净化点从来没生效过**。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_qc_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_quote_context_is_quoted(self):
        """DVWA 真实形态：拼接，前一段字面量以 `'` 收尾 ⇒ 值落在引号内。"""
        sys.path.insert(0, SCRIPTS)
        import audit_graph
        line = '''$insert = "UPDATE `users` SET password = '" . $pass_new . "' WHERE user = '"'''
        self.assertEqual("quoted",
                         audit_graph.sql_quote_context(line, "pass_new", "php"))

    def test_quote_context_is_bare(self):
        """DVWA 真实形态：双引号串里裸插 ⇒ 值落在引号外（数值上下文）。"""
        sys.path.insert(0, SCRIPTS)
        import audit_graph
        line = '''$query = "SELECT first_name, last_name FROM users WHERE user_id = $id;"'''
        self.assertEqual("bare",
                         audit_graph.sql_quote_context(line, "id", "php"))

    def test_escape_sanitizer_actually_matches_mysqli(self):
        """净化点必须真能匹配 `mysqli_real_escape_string`（旧的词边界 bug）。

        ⚠️ 旧 pattern `\\breal_escape_string\\b` 匹配不到它（`_` 是单词字符
        ⇒ 无词边界）⇒ 这个净化点**从来没生效过** ⇒ E22 把它记成了能力边界。
        """
        sys.path.insert(0, SCRIPTS)
        import audit_rules
        rules, problems, _notes, _skipped = audit_rules.load_rules()
        self.assertEqual([], problems, "规则库自检有问题")
        rule = [r for r in rules if r["id"] == "JZ-SQLI-003"][0]
        hit = [s for s in rule["sanitizers"]
               if s["_rx"].search("$id = mysqli_real_escape_string($conn, $id);")]
        self.assertTrue(hit,
                        "没有净化点匹配 mysqli_real_escape_string（旧 pattern 的词边界 bug）")
        self.assertEqual("sql_quoted", hit[0].get("context"),
                         "转义净化点必须标成条件净化点（否则引号外的真阳性会被吃掉）")

    def test_escaped_value_in_quotes_is_not_reported(self):
        """正例：转义 + 引号内 ⇒ 不是注入 ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        '''<?php
$id = $_GET['id'];
$id = mysqli_real_escape_string($conn, $id);
$query = "SELECT * FROM users WHERE user_id = '" . $id . "'";
mysqli_query($conn, $query);
''')
            data, _ = self._scan(tmp, "quoted")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-SQLI-003", ids,
                             "转义且落在引号内却报了：%s" % ids)

    def test_escaped_value_outside_quotes_is_still_reported(self):
        """反例（防误伤）：转义 + 引号外 ⇒ 仍须报。

        ⚠️ 这一条是 E30 的**主要风险**：把转义一刀切当净化点 ⇒ 真阳性被吃掉
        （DVWA `sqli_blind/source/medium.php:15` 就是这个形态）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        '''<?php
$id = $_GET['id'];
$id = mysqli_real_escape_string($conn, $id);
$query = "SELECT * FROM users WHERE user_id = $id;";
mysqli_query($conn, $query);
''')
            data, _ = self._scan(tmp, "bare")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-SQLI-003", ids,
                          "引号外的转义没报（真阳性被吃掉了）")


class TestAuditSanitizePlacement(unittest.TestCase):
    """E11 顺带核实：净化与输出**同行**（非赋值行）时，净化判定到底生不生效。

    E10 把它记成待确认的缺口（"净化点在非赋值行可能不生效"）。E11 实测**改判**：
    `echo htmlspecialchars($name);` 不报（source 与 sink 之间出现了净化/守卫），
    对照组 `echo $name;` 照报 ⇒ 那条缺口**不成立**。

    这两条是**配对**的：只有"有净化不报 / 没净化要报"同时成立，上一条才不是假绿。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_sp_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_sanitizer_on_output_line_blocks_the_flow(self):
        """净化与输出同行 ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$name = $_GET['name'];\n"
                        "echo htmlspecialchars($name);\n")
            data, _ = self._scan(tmp, "saninline")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "净化与输出同行时仍报了：%s" % ids)

    def test_same_shape_without_sanitizer_is_reported(self):
        """对照组：同样的形状但**没有净化** ⇒ 必须报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$name = $_GET['name'];\n"
                        "echo $name;\n")
            data, _ = self._scan(tmp, "nosan")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "没净化的同行输出没报出来：%s" % ids)


class TestAuditCommentNotCode(unittest.TestCase):
    """E12：注释里的代码**不是代码**——修复前图层把整行注释当成了真代码。

    复核发现（v0.45.0 E11 收尾时自己的注释触发了假流，顺藤摸到的）：
    `auditlib.iter_code_lines`（**规则层一直在用**）本来就会跳过注释行与 docstring 块，
    但 `audit_graph.build_graph` 的主路径用的是 `auditlib.iter_lines`（**全部行**）
    ⇒ **层间不一致** ⇒ 注释里的 source/sink 进了数据流。

    实测代价（三仓逐条对比）：DVWA 有 **3 条** JZ-XSS-002 的 sink 落在**整行注释**里
    （`vulnerabilities/sqli/source/low.php:32` 与 `medium.php:28` 的 `#print $query;`、
    `vulnerabilities/cryptography/source/xor_theory.php:12` 的 `//echo 'i=' . $i . …`），
    本仓库自扫有 2 条。它们当时都被独立验证当兜底挡着（没进结论区），
    但**兜底不是机制**——行号归属稍有偏差就会漏进结论区（实测行尾注释就会，见下面的缺口）。

    这四条判据全部是**修复前红、修复后绿**（第 3 条是配对的反向对照）。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_cn_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    @staticmethod
    def _reported(data):
        """**引擎认为有问题**的规则全集 = findings ＋ dropped（被独立验证拦下的）。

        ⚠️ 只查 findings 会漏掉一整层：引擎有"独立验证"这道兜底，
        证据链不成立的流停在 `dropped` 里、**没进 findings**——
        E12 校准实测：注释假流修复前就停在这层，判据只看 findings ⇒ **恒绿**（没牙齿）。
        `blocked`（被净化排除）不算：那是引擎看到了但认定安全，是正常结果。
        """
        return ([f["rule_id"] for f in data.get("findings", [])]
                + [f["rule_id"] for f in data.get("dropped", [])])

    def test_php_hash_comment_line_is_not_code(self):
        """DVWA `sqli/source/low.php` 的形态：`#print $query;` 是注释 ⇒ 不该报。

        真实代码长这样（source 在**上一行**，sink 在**下一行的注释里**——跨行形态）：
            $query = "SELECT ... WHERE user_id = '$id';";
            #print $query;

        ⚠️ 夹具里**必须另有一处真 sink**（SQLi）：`audit_scan` 的**种子阶段**用
        `iter_code_lines`（跳注释）决定"哪些文件进图层"⇒ 只剩注释里的 sink 时，
        文件压根不进候选，图层没机会犯错 ⇒ 判据会**恒绿**（E12 校准实测）。
        真 sink 用**另一条规则**（JZ-SQLI-003），断言只看 JZ-XSS-002。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$query = \"SELECT * FROM users WHERE user_id = '$id';\";\n"
                        "#print $query;\n"
                        "$sql = \"SELECT * FROM users WHERE id = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "hash")
            ids = self._reported(data)
            self.assertNotIn("JZ-XSS-002", ids,
                             "整行 # 注释里的 print 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_php_slash_comment_line_is_not_code(self):
        """DVWA `xor_theory.php` 的形态：`//echo 'i=' . $i . …` 是注释 ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$outText = $_GET['t'];\n"
                        "$outText .= 'x';\n"
                        "//echo 'i=' . $outText . '<br />'; // For debugging\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$outText';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "slash")
            ids = self._reported(data)
            self.assertNotIn("JZ-XSS-002", ids,
                             "整行 // 注释里的 echo 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_inline_comment_with_source_and_sink_is_not_code(self):
        """**同行**形态：source 与 sink 都在同一行注释里 ⇒ 也不该报。

        这一条是**修复前会直接进结论区**的形态（同行内联 source 走 `__inline__` 兜底），
        前两条（跨行）修复前停在 `dropped` 层。两种形态都锁住。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "//echo $_GET['x'];\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "inline")
            ids = self._reported(data)
            self.assertNotIn("JZ-XSS-002", ids,
                             "同行注释里的 source→sink 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_same_code_without_comment_is_reported(self):
        """配对对照：同样两行、去掉注释 ⇒ **必须**报（否则上面几条是假绿）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$query = \"SELECT * FROM users WHERE user_id = '$id';\";\n"
                        "print $query;\n")
            data, _ = self._scan(tmp, "nocmt")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "去掉注释后反而不报了（上面几条是假绿）：%s" % ids)

    def test_comment_brace_does_not_break_function_body(self):
        """注释里的 `}` 不该截断函数体（**顺带修掉的第二个隐患**）。

        修复前 `brace_end` 数括号时把注释里的 `}` 也算上 ⇒ 函数体提前结束
        ⇒ 后面真正的 sink 行不在函数体里 ⇒ **漏报**。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function f() {\n"
                        "    // }\n"
                        "    echo $_GET['x'];\n"
                        "}\n")
            data, _ = self._scan(tmp, "brace")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "注释里的 } 截断了函数体 ⇒ 漏报：%s" % ids)


class TestAuditTailComment(unittest.TestCase):
    """E13：**行尾注释**里的代码也不是代码（比整行注释严重——误报**直接进结论区**）。

    E12（v0.46.0）把**整行**注释排除了（`iter_code_lines` 本来就会跳整行注释，
    但图层主路径没用它）。行尾注释是另一回事：`auditlib.code_lines` 只按**行首**判断
    注释前缀 ⇒ `echo $x; // os.system("ls " . $x)` 里的 sink 形状**仍在行内**
    ⇒ 被当成真代码 ⇒ **误报直接进结论区**（不像整行注释那样被独立验证挡在 dropped 层）。

    修法：`auditlib.strip_line_comments(text, lang)` 把行尾注释换成等长空格，
    **注释符按语言分**、**必须先跳过字符串**。于是：
    ⚠️ **Python 的 `//` 是整除不是注释**（统一词表会把 `x = y // 2` 整行截断 ⇒ 漏报）；
    ⚠️ 字符串里的 `//`（`"http://x"`）与 `"#!/usr/bin/env python"` 的 `#` 都不是注释。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_tc_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    @staticmethod
    def _reported(data):
        """findings ＋ dropped（被独立验证拦下的）＝"引擎认为有问题"的全集。"""
        return ([f["rule_id"] for f in data.get("findings", [])]
                + [f["rule_id"] for f in data.get("dropped", [])])

    def test_php_slash_tail_comment_is_not_code(self):
        """PHP 的 `//` 行尾注释里的 sink ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "echo $cmd; // os.system(\"ls \" . $cmd)\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "slash")
            ids = self._reported(data)
            self.assertNotIn("JZ-CMDI-001", ids,
                             "行尾 // 注释里的 os.system 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_php_hash_tail_comment_is_not_code(self):
        """PHP 的 `#` 行尾注释里的 sink ⇒ 也不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "echo $cmd; # os.system(\"ls \" . $cmd)\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "hash")
            ids = self._reported(data)
            self.assertNotIn("JZ-CMDI-001", ids,
                             "行尾 # 注释里的 os.system 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_same_code_without_tail_comment_is_reported(self):
        """配对对照：不写注释 ⇒ **必须**报（否则上面两条是假绿）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "os.system(\"ls \" . $cmd);\n")
            data, _ = self._scan(tmp, "nocmt")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-CMDI-001", ids,
                          "不写注释时反而不报了（上面两条是假绿）：%s" % ids)

    def test_python_floor_division_is_not_a_comment(self):
        """⚠️ **Python 的 `//` 是整除，不是注释**——剥错了就把真代码截断（⇒ 漏报）。"""
        sys.path.insert(0, SCRIPTS)
        import auditlib
        src = "y = x // 2\n"
        self.assertEqual(auditlib.strip_line_comments(src, "python"), src,
                         "Python 的 // 被当成注释了（整除被截断 ⇒ 漏报）")

    def test_string_with_slashes_or_hash_is_not_a_comment(self):
        """字符串里的 `//` 与 `#` **不是**注释（先剥字符串才能找注释符）。"""
        sys.path.insert(0, SCRIPTS)
        import auditlib
        for src in ("u = 'http://x/y'\n", "$u = 'http://x/y';\n",
                    "$u = \"a # b\";\n", "u = 'a # b'\n"):
            lang = "php" if src.startswith("$") else "python"
            self.assertEqual(auditlib.strip_line_comments(src, lang), src,
                             "字符串里的注释符被当成了注释：%r" % src)


class TestAuditBlockComment(unittest.TestCase):
    """E14：**块注释** `/* … */`（可跨行）里的代码也不是代码（E13 补的是行注释）。

    E13 留下的边界：`code_lines` 与 `strip_line_comments` 都只管**行**注释 ⇒
    C 系与 PHP 的 `/* … */` 里的代码仍被当成真代码。
    ⚠️ **行注释与块注释必须单遍同时扫描**：`/* // */` 与 `// /* */` 两种写法互相截断，
    分两步做会把注释边界搞错（这是实现里最容易写错的地方）。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_bc_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    @staticmethod
    def _reported(data):
        return ([f["rule_id"] for f in data.get("findings", [])]
                + [f["rule_id"] for f in data.get("dropped", [])])

    def test_multiline_block_comment_is_not_code(self):
        """**跨行**块注释里的 sink ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "/*\n"
                        "os.system(\"ls \" . $cmd);\n"
                        "*/\n"
                        "echo $cmd;\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "multi")
            ids = self._reported(data)
            self.assertNotIn("JZ-CMDI-001", ids,
                             "跨行块注释里的 os.system 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_inline_block_comment_is_not_code(self):
        """**同行**块注释里的 sink ⇒ 也不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "echo $cmd; /* os.system(\"ls \" . $cmd) */\n"
                        "$sql = \"SELECT * FROM t WHERE c = '$id';\";\n"
                        "mysqli_query($conn, $sql);\n")
            data, _ = self._scan(tmp, "inline")
            ids = self._reported(data)
            self.assertNotIn("JZ-CMDI-001", ids,
                             "同行块注释里的 os.system 被当成了真代码：%s" % ids)
            self.assertIn("JZ-SQLI-003", ids,
                          "夹具里的真 sink 没进候选（种子阶段把它挡了，判据就恒绿）：%s" % ids)

    def test_same_code_without_block_comment_is_reported(self):
        """配对对照：不写块注释 ⇒ **必须**报（否则上面两条是假绿）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$id = $_GET['id'];\n"
                        "$cmd = $id;\n"
                        "os.system(\"ls \" . $cmd);\n")
            data, _ = self._scan(tmp, "nocmt")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-CMDI-001", ids,
                          "不写块注释时反而不报了（上面两条是假绿）：%s" % ids)

    def test_line_and_block_comment_do_not_cut_each_other(self):
        """⚠️ `/* // */` 与 `// /* */` 两种写法**不能互相截断**（必须单遍扫描）。"""
        sys.path.insert(0, SCRIPTS)
        import auditlib
        # `/* // */`：块注释里的 // 不是行注释 ⇒ 整段剥掉，但**块注释之后的真代码要留下**
        out, in_block = auditlib.strip_comments("/* // */ x = 1;\n", "php")
        self.assertNotIn("/*", out, "块注释没被剥：%r" % out)
        self.assertNotIn("//", out, "块注释里的 // 被当成了行注释：%r" % out)
        self.assertIn("x = 1;", out, "块注释之后的真代码被吃掉了：%r" % out)
        self.assertFalse(in_block)
        # `// /* */`：行注释先命中 ⇒ 后面全剥
        out, in_block = auditlib.strip_comments("x = 1; // /* y = 2;\n", "php")
        self.assertNotIn("//", out, "行注释没被剥：%r" % out)
        self.assertNotIn("/*", out, "行注释里的 /* 被当成了块注释：%r" % out)
        self.assertIn("x = 1;", out, "行注释之前的真代码被吃掉了：%r" % out)
        self.assertFalse(in_block)

    def test_block_comment_state_carries_across_lines(self):
        """跨行块注释：状态要延续到下一行（纯函数级）。"""
        sys.path.insert(0, SCRIPTS)
        import auditlib
        out, in_block = auditlib.strip_comments("/* start\n", "php")
        self.assertTrue(in_block, "块注释没有进入状态")
        self.assertNotIn("/*", out, "块注释首行没被剥：%r" % out)
        out, in_block = auditlib.strip_comments("end */ x = 1;\n", "php", in_block)
        self.assertFalse(in_block, "块注释没有正常结束")
        self.assertNotIn("*/", out, "块注释第二行没被剥：%r" % out)
        self.assertIn("x = 1;", out, "块注释之后的真代码被吃掉了：%r" % out)

    def test_string_with_block_markers_is_not_a_comment(self):
        """字符串里的 `/*` **不是**注释（先剥字符串才能找注释符）。"""
        sys.path.insert(0, SCRIPTS)
        import auditlib
        src = "$u = \"/* not a comment */\";\n"
        out, _ = auditlib.strip_comments(src, "php")
        self.assertEqual(out, src, "字符串里的 /* 被当成了块注释：%r" % out)


class TestValidateReplacementChars(unittest.TestCase):
    """E15：**U+FFFD 替换字符**（= 被损坏的字符）也得有判据。

    E11 收尾时发现：**E10 那轮自己写下的乱码**（`audit-acceptance.md` 里一个「同」字
    变成了 U+FFFD）**溜过了所有判据**——文件照样能跑、结构照样合法、数字照样对得上，
    **只有那个字符坏了**。`validate_skill.py` 查结构、查表格、查期望值，唯独不查"字符有没有坏"。

    ⚠️ 本文件里**不能出现真的 U+FFFD 字符**（否则它自己会被判据逮到）⇒ 一律用 `u"\\ufffd"` 转义。
    """

    def test_replacement_char_is_flagged(self):
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "broken.md")
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(u"正常的一行\n这一行有个坏字" + chr(0xFFFD) + u"\n")
            bad, scanned = validate_skill.find_replacement_chars(tmp)
            self.assertTrue(bad, u"含 U+FFFD 的文件没被逮住")
            self.assertEqual(bad[0][0], "broken.md")
            self.assertEqual(bad[0][1], 2, u"行号报错了：%r" % (bad[0],))

    def test_clean_file_is_not_flagged(self):
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "ok.md")
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(u"干净的一行\n还有一行\n")
            bad, scanned = validate_skill.find_replacement_chars(tmp)
            self.assertEqual(bad, [], u"干净文件被误报了：%r" % (bad,))
            self.assertEqual(scanned, 1)

    def test_repository_itself_has_no_replacement_chars(self):
        """本仓现在必须干净（E10 那处乱码已修掉）——判据上线的前提。"""
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        repo = os.path.dirname(SCRIPTS)
        bad, scanned = validate_skill.find_replacement_chars(repo)
        self.assertEqual(bad, [], u"仓库里还有 U+FFFD：%r" % (bad[:5],))


class TestAuditPhpInputXss(unittest.TestCase):
    """E16：`JZ-XSS-002` 接上 `php://input`（PHP 读原始请求体也是"外部可控输入"）。

    E9 之所以没接这条：**引擎当时把"实参"当成了"返回值"**——
    `check_token($token)` 的返回值全是常量（DVWA 真代码 `token_library_high.php`：
    `$ret` 的每个字段都来自常量表 `$users`）⇒ 报成 XSS（**误报**）。
    E11 修好「返回摘要」之后，这条才接得上来。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_ix_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_request_body_reaches_xss_rule(self):
        """请求体 → 反射输出 ⇒ 该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$raw = file_get_contents('php://input');\n"
                        "echo $raw;\n")
            data, _ = self._scan(tmp, "xss")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "请求体没进 XSS 规则：%s" % ids)

    def test_sanitized_output_is_not_reported(self):
        """同样入口，但输出前 htmlspecialchars ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$raw = file_get_contents('php://input');\n"
                        "echo htmlspecialchars($raw, ENT_QUOTES, 'UTF-8');\n")
            data, _ = self._scan(tmp, "san")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "净化后的输出仍被报了：%s" % ids)

    def test_local_file_read_is_not_a_source(self):
        """读**本地文件**不是读请求体 ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$content = file_get_contents('/etc/passwd');\n"
                        "echo $content;\n")
            data, _ = self._scan(tmp, "file")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "读本地文件被当成了请求体：%s" % ids)


class TestAuditExecClassification(unittest.TestCase):
    """E17：PHP 的 `exec()` 是**命令执行**，不是"动态代码执行"。

    复核（实测）：DVWA `vulnerabilities/api/src/HealthController.php:88` 的
    `exec("ping -c 4 " . $target)` 被归到 **JZ-CODE-001（动态代码执行）** ⇒ **归错类**。
    根因两条：
    ① `JZ-CODE-001` 的 sink 是 `\beval\s*\(|\bexec\s*\(` ⇒ **`exec` 无条件命中**；
    ② `JZ-CMDI-001` 的 PHP exec sink 要求 `+` 或 `${` ⇒ **PHP 的 `.` 拼接压根不匹配**
       （PHP 不用 `+` 做字符串拼接）⇒ 于是这条只被 CODE-001 认领。

    修法：CODE-001 只留 `eval`；CMDI-001 的 exec sink 补上 `.` 拼接形态。
    ⚠️ **Ruby 的 `Kernel#exec` 同样是命令执行**，去掉 CODE-001 里的 exec 对它是修正不是漏报。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_ex_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_php_exec_is_command_execution_not_dynamic_code(self):
        """`exec("ping -c 4 " . $target)` ⇒ 归 JZ-CMDI-001，**不**归 JZ-CODE-001。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$target = $_GET['host'];\n"
                        "exec(\"ping -c 4 \" . $target);\n")
            data, _ = self._scan(tmp, "exec")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-CMDI-001", ids,
                          "PHP 的 exec 没被认成命令执行：%s" % ids)
            self.assertNotIn("JZ-CODE-001", ids,
                             "PHP 的 exec 还被当成动态代码执行：%s" % ids)

    def test_eval_still_reported_as_dynamic_code(self):
        """`eval($x)` ⇒ 仍归 JZ-CODE-001（去掉 exec 不能误伤 eval）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "$x = $_GET['x'];\n"
                        "eval($x);\n")
            data, _ = self._scan(tmp, "eval")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-CODE-001", ids,
                          "eval 不再被认成动态代码执行：%s" % ids)


class TestAuditOverwriteClearsTaint(unittest.TestCase):
    """E18：赋值**覆盖**了目标时，摘要为空就**清掉**目标原有的污点。

    实测的残留（E11 修返回摘要时留下的）：`$x = $_GET['a']; $x = check_token($x); echo $x;`
    仍报 XSS —— 第二次赋值把 `$x` **覆盖成常量**了（`check_token` 的返回值全是常量），
    `$x` 上原有的污点却还留着。

    ⚠️ 配对那条是**防误伤**的：`passthrough` 的返回值**确实依赖**形参 ⇒ 必须**仍然报**。
    （把"清旧污点"做成"一律清"就会把真阳性也清掉。）
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_ow_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    CONST_HELPER = ("<?php\n"
                    "function check_token($token) {\n"
                    "    $ret = array('status' => 'ok', 'message' => 'constant');\n"
                    "    return json_encode($ret);\n"
                    "}\n")
    PASSTHROUGH = "<?php\nfunction passthrough($k) { return $k; }\n"

    def test_overwrite_by_constant_returning_helper_drops_old_taint(self):
        """被"返回常量的函数"覆盖 ⇒ 旧污点不该留着 ⇒ 不该报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        self.CONST_HELPER +
                        "$x = $_GET['a'];\n"
                        "$x = check_token($x);\n"
                        "echo $x;\n")
            data, _ = self._scan(tmp, "overwrite")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "被常量返回值覆盖后旧污点还留着：%s" % ids)

    def test_overwrite_by_passthrough_keeps_taint(self):
        """配对：返回值**确实依赖**形参 ⇒ 必须仍然报（防误伤真阳性）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        self.PASSTHROUGH +
                        "$x = $_GET['a'];\n"
                        "$x = passthrough($x);\n"
                        "echo $x;\n")
            data, _ = self._scan(tmp, "keep")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "真阳性被一起清掉了：%s" % ids)


class TestAuditPhpMemberCall(unittest.TestCase):
    """E19：PHP 的**成员方法** `->method(` 不是"调用仓库内同名函数"。

    复核实测（探针）：`_iter_calls(..., skip_members=True)` 对 `$o->get($x)`
    **仍返回** `('get', ['$x'])` ⇒ 因为排除只认 `.`（Python/JS 风格），
    **不认 PHP 的 `->`** ⇒ 成员方法被当成"调用仓库内同名函数"
    ⇒ 当仓库里恰好有 `function get($k){...}` 时，两个摘要会被**合并**
    ⇒ 用**全局函数**的语义去代表**方法**的语义 ⇒ 可能**漏报真阳性**。

    修法：成员方法一律排除 ⇒ 退化成"参数直传"的**保守假设**（宁可多报也不漏报）。
    ⚠️ 判据 1 是**修复前红、修复后绿**：修复前走摘要分支（同名函数返回常量 ⇒ 不继承）
    ⇒ 漏报；修复后成员方法被排除 ⇒ 参数直传 ⇒ 报（保守）。
    """

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_mc_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_member_call_not_treated_as_repo_function(self):
        """仓库内有同名全局函数 + 成员方法 ⇒ 成员方法不能借用全局函数的摘要。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function get($k) { return \"constant\"; }\n"
                        "class C { public function get($k) { return \"constant\"; } }\n"
                        "$o = new C();\n"
                        "$x = $_GET['x'];\n"
                        "$out = $o->get($x);\n"
                        "echo $out;\n")
            data, _ = self._scan(tmp, "member")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "成员方法借用了同名全局函数的摘要（漏报）：%s" % ids)

    def test_member_call_returning_argument_keeps_taint(self):
        """成员方法**返回参数** ⇒ 污点该流过去 ⇒ 必须报（配对，防误伤）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "class C { public function get($k) { return $k; } }\n"
                        "$o = new C();\n"
                        "$x = $_GET['x'];\n"
                        "$out = $o->get($x);\n"
                        "echo $out;\n")
            data, _ = self._scan(tmp, "arg")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertIn("JZ-XSS-002", ids,
                          "成员方法返回参数却没报（漏报）：%s" % ids)

    def test_plain_function_call_still_uses_summary(self):
        """普通函数调用**仍走摘要**（别把"排除成员"写成"排除所有调用"）。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.php",
                        "<?php\n"
                        "function constant_ret($k) { return \"constant\"; }\n"
                        "$x = $_GET['x'];\n"
                        "$out = constant_ret($x);\n"
                        "echo $out;\n")
            data, _ = self._scan(tmp, "plain")
            ids = [f["rule_id"] for f in data["findings"]]
            self.assertNotIn("JZ-XSS-002", ids,
                             "普通函数没走摘要分支（返回值与形参无关却继承了污点）：%s" % ids)


class TestAuditRoleScope(unittest.TestCase):
    """B7（第三方取证逼出来的一轮）：库代码与示例目录不该吃应用级规则的结论。

    requests 里出现 CERT_NONE / set_cookie 是它的职责，flask 的 examples 里
    `app.debug = True` 是示例。但**压掉之前必须留痕**，且应用仓库里的同样写法照报——
    两半都要断言，否则"降误报"只是把结论藏起来。
    """

    DEBUG_LIB = "debug = True\n"
    APP_FORM = ("from flask import request, Flask\napp = Flask(__name__)\n\n"
                "@app.route('/x')\ndef x():\n"
                "    return '<form method=post action=/save></form>'\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_r_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_library_repo_moves_app_rules_to_not_applicable(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "pyproject.toml",
                        '[project]\nname = "mylib"\nversion = "1.0"\n')
            self._write(tmp, "src/mylib/config.py", self.DEBUG_LIB)
            data, stdout = self._scan(tmp, "lib")
            self.assertEqual("library", data["stats"]["repo_role"])
            self.assertEqual([], [f for f in data["findings"]
                                 if f["rule_id"] == "JZ-DEBUG-001"],
                              "库代码里的 debug=True 不该进结论")
            self.assertTrue(any(n["rule_id"] == "JZ-DEBUG-001"
                                for n in data["not_applicable"]),
                            "被压掉的必须留痕：%s" % data["stats"])
            self.assertIn(u"不适用", stdout)

    def test_setup_py_only_library_is_still_judged_library(self):
        """`repo_role` 的 has_packaging 里写了 setup.py，但地图的 manifests 只收
        project_scan.MANIFESTS（不含 setup.py）——两边的名单不一致，
        只用 setup.py 打包的老库（现实里很常见）会被判成 app。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "setup.py",
                        "from setuptools import setup\nsetup(name=\"mylib\")\n")
            self._write(tmp, "src/mylib/config.py", self.DEBUG_LIB)
            data, _ = self._scan(tmp, "setuponly")
            self.assertEqual("library", data["stats"]["repo_role"],
                             "setup.py 也算打包清单：%s" % data["stats"].get("repo_role"))

    def test_app_repo_still_reports_the_same_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.py", "from flask import Flask\napp = Flask(__name__)\n"
                                       "app.debug = True\n")
            self._write(tmp, "templates/x.html", "<html><body>hi</body></html>\n")
            data, _ = self._scan(tmp, "app")
            self.assertEqual("app", data["stats"]["repo_role"],
                             "有页面/有入口就该判应用，不许靠'没路由'误判成库")
            self.assertTrue([f for f in data["findings"]
                             if f["rule_id"] == "JZ-DEBUG-001"],
                            "应用仓库里同样的写法必须照报（防过度抑制）")

    def test_example_and_test_paths_are_excluded_for_app_rules_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.py", "from flask import Flask\napp = Flask(__name__)\n")
            self._write(tmp, "examples/demo/settings.py", self.DEBUG_LIB)
            self._write(tmp, "examples/demo/bad.py",
                        "from flask import request\nimport os\n\n\n"
                        "def run():\n    os.system(\"ls \" + request.args['d'])\n")
            data, _ = self._scan(tmp, "ex")
            ids = set(f["rule_id"] for f in data["findings"])
            self.assertNotIn("JZ-DEBUG-001", ids, "示例目录里的配置型规则应转不适用")
            self.assertIn("JZ-CMDI-001", ids,
                          "示例目录里的注入类规则仍要报——只压配置型，不压能力型")
            self.assertTrue(any(n["rule_id"] == "JZ-DEBUG-001"
                                for n in data["not_applicable"]))


class TestAuditPhpFlows(unittest.TestCase):
    """B7 取证回填：DVWA 实测暴露的两处真实漏检。

    第一轮在 DVWA 上跑，SQL 注入 0 条——而 SQLi 是 DVWA 的招牌漏洞。
    根因两条：① SQLi-003 的 sink 只认拼接写法（`+` / `.`），PHP 双引号插值
    `$query = "… '$id';"` 后 `mysqli_query($link, $query)` 传变量整条链不命中；
    ② PHP 反射输出（`echo $html`）根本没有污点规则，只有 `<?php echo $_GET`
    这一种字面写法。这两条测试是**先红后绿**写出来的：规则改之前它们必须失败。
    """

    def _graph(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8") as f:
                f.write(text)
        out = os.path.join(root, "_graph.json")
        r = run([os.path.join(SCRIPTS, "audit_graph.py"), root, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_php_interpolated_sql_reaches_query_sink(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "if ( isset( $_REQUEST[ 'Submit' ] ) ) {\n"
                "    $id = $_REQUEST[ 'id' ];\n"
                "    $query = \"SELECT first_name FROM users WHERE user_id = '$id';\";\n"
                "    $result = mysqli_query($db_link, $query);\n"
                "}\n")})
            sql = [f for f in data["flows"] if f["rule_id"] == "JZ-SQLI-003"]
            self.assertEqual(1, len(sql),
                             "插值 SQL 交给 mysqli_query 必须成流；flows=%s"
                             % [f["rule_id"] for f in data["flows"]])
            hops = sql[0]["path"]
            self.assertGreaterEqual(len(hops), 3,
                                    "source→插值→sink 至少三跳证据")
            self.assertEqual("sink", hops[-1]["kind"])

    def test_php_numeric_cast_before_query_is_blocked_not_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "$id = $_GET[ 'id' ];\n"
                "$id = intval( $id );\n"
                "$result = mysqli_query($db_link, \"SELECT * FROM users WHERE id = $id\");\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-SQLI-003"],
                             "intval 收敛成整数后不该再报注入")
            self.assertGreaterEqual(data["stats"]["blocked_by_sanitizer"], 1,
                                    "净化要留痕，不能当没发生过")

    def test_php_concat_assignment_propagates_taint(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "$name = $_GET[ 'name' ];\n"
                "$html .= \"<pre>Hello \" . $name . \"</pre>\";\n"
                "echo $html;\n")})
            xss = [f for f in data["flows"] if f["rule_id"] == "JZ-XSS-002"]
            self.assertEqual(1, len(xss),
                             ".= 累加是 PHP 主流写法，污点必须续传；flows=%s"
                             % [f["rule_id"] for f in data["flows"]])

    def test_php_reflected_output_without_sanitizer_is_a_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "$name = $_GET[ 'name' ];\n"
                "echo \"<p>Hello \" . $name . \"</p>\";\n")})
            xss = [f for f in data["flows"] if f["rule_id"] == "JZ-XSS-002"]
            self.assertEqual(1, len(xss), "反射输出无转义要成流")

    def test_htmlspecialchars_breaks_reflected_output_flow(self):
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "$name = htmlspecialchars( $_GET[ 'name' ] );\n"
                "echo \"<p>Hello \" . $name . \"</p>\";\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-XSS-002"],
                             "htmlspecialchars 之后不得再报反射 XSS")
            self.assertGreaterEqual(data["stats"]["blocked_by_sanitizer"], 1)


    def test_guard_only_superglobal_does_not_taint_unrelated_output(self):
        """`if (isset($_POST['Submit']))` 是**守卫条件**，不是数据入口。

        DVWA 每个模块都有这句，实测它把同函数里一条与请求无关的
        `echo $out` 带成了反射 XSS——`__inline__` 兜底把"函数里出现过 source"
        当成了"source 流到了 sink"。守卫型出现不该产生污点。
        """
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "function run() {\n"
                "    if ( isset( $_POST['Submit'] ) ) {\n"
                "        $out = shell_exec('ls -la');\n"
                "        echo $out;\n"
                "    }\n"
                "}\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-XSS-002"],
                             "守卫里的 $_POST 不该污染无关输出：%s"
                             % [(f["rule_id"], f["path"][-1]["line"])
                                for f in data["flows"]])

    def test_inline_source_on_the_sink_line_still_counts(self):
        """反向半句：`echo $_GET['x']` 同行内联仍然是真漏洞，不能被上一条修没。"""
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "function head() {\n"
                "    echo $_GET['page'];\n"
                "}\n")})
            xss = [f for f in data["flows"] if f["rule_id"] == "JZ-XSS-002"]
            self.assertEqual(1, len(xss),
                             "同行内联的 source→sink 必须成流；flows=%s"
                             % [f["rule_id"] for f in data["flows"]])

    def test_non_controllable_server_keys_are_not_xss_sources(self):
        """`$_SERVER['REQUEST_METHOD']` 不是攻击者可控输入，不该当 XSS 入口；
        `$_SERVER['PHP_SELF']` 是可控的，该当。"""
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"v.php": (
                "<?php\n\n"
                "function nav() {\n"
                "    $m = $_SERVER['REQUEST_METHOD'];\n"
                "    echo $m;\n"
                "}\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-XSS-002"])
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"w.php": (
                "<?php\n\n"
                "function form() {\n"
                "    $self = $_SERVER['PHP_SELF'];\n"
                "    echo $self;\n"
                "}\n")})
            self.assertEqual(1, len([f for f in data["flows"]
                                     if f["rule_id"] == "JZ-XSS-002"]),
                             "PHP_SELF 可控，反射 XSS 要报")


    def test_php_page_script_flows_are_reachable(self):
        """过程式 PHP 的每个页面文件自己就是入口——不能一律判"不可利用"。

        DVWA 的漏洞体在 `vulnerabilities/*/source/*.php`，由 index.php 用
        变量路径的 `require_once …"…/{$vulnerabilityFile}"` 引入，静态跟图跟不动；
        上一版因此把 SQL 注入标成"不可利用"，把靶场最强信号降了档。
        """
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"vulnerabilities/xss_r/source/low.php": (
                "<?php\n\n"
                "$name = $_GET[ 'name' ];\n"
                "$html .= \"<p>Hello \" . $name . \"</p>\";\n"
                "echo $html;\n")})
            xss = [f for f in data["flows"] if f["rule_id"] == "JZ-XSS-002"]
            self.assertEqual(1, len(xss))
            self.assertTrue(xss[0]["reachable"],
                            "PHP 页面脚本的模块级污点流应判可达")

    def test_php_class_file_is_not_counted_as_a_page(self):
        """反向半句：只有 class/namespace/use 的定义文件不该被当成页面入口，
        否则"可达"这条闸就形同虚设。"""
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"src/Kernel.php": (
                "<?php\n\n"
                "namespace App;\n\n"
                "class Kernel\n{\n"
                "    private $db;\n"
                "    public function handle()\n    {\n"
                "        $cmd = $_GET[ 'c' ];\n"
                "        system( \"ls \" . $cmd );\n"
                "    }\n"
                "}\n")})
            cmdi = [f for f in data["flows"] if f["rule_id"] == "JZ-CMDI-001"]
            self.assertEqual(1, len(cmdi), "命令注入本身要检出：%s"
                             % [f["rule_id"] for f in data["flows"]])
            self.assertFalse(cmdi[0]["reachable"],
                             "定义文件里的方法没有入口路径，应仍判不可达")
            self.assertEqual(0, data["stats"]["roots"],
                             "纯 class/namespace 文件不能进可达根，否则"
                             "'可达性'这道闸就白设（roots=%s）" % data["stats"])


    def test_placeholder_name_inside_sql_string_is_not_a_variable_read(self):
        """字符串里的 SQL 关键字/占位符不是"读了这个变量"。

        DVWA 的 impossible.php 被报成反射 XSS，链条是
        `$id = $_GET['id']` → `$data = $db->prepare('… WHERE id = (:id)')`
        ——占位符名 `:id` 与变量名 `id` 撞字面，引擎以为这行读了 `id`，
        于是 prepare→fetch→print 一路把安全写法带成污点输出。
        """
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"p.php": (
                "<?php\n\n"
                "function q() {\n"
                "    $id = $_GET['id'];\n"
                "    $data = $db->prepare( 'SELECT name FROM users WHERE id = (:id)' );\n"
                "    $row = $data->fetch();\n"
                "    $who = $row['name'];\n"
                "    echo $who;\n"
                "}\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-XSS-002"],
                             "占位符撞名不该造出一条污点流：%s"
                             % [(f["rule_id"], f["path"][-1]["line"])
                                for f in data["flows"]])

    def test_non_page_php_dirs_are_not_promoted_to_entries(self):
        """半句保护：tests/ examples/ 里的 PHP 脚本不因"页面即入口"被抬成可达。
        （vendor/ 在索引层就跳过了，用不上这条；真正需要它挡的是索引会收的目录。）"""
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"tests/fixtures/paywall/page.php": (
                "<?php\n\n"
                "$amt = $_GET[ 'amt' ];\n"
                "$out = \"total \" . $amt;\n"
                "echo $out;\n")})
            reach = [f for f in data["flows"] if f["reachable"]]
            self.assertEqual([], reach,
                             "tests/ 路径不得算页面入口：%s"
                             % [(f["rule_id"], f["file"]) for f in reach])


    def test_request_superglobal_is_a_command_injection_source(self):
        """`$_REQUEST` 和 `$_GET`/`$_POST` 一样是外部输入。

        CMDI-001 的 source 原先只写 `\$_(?:GET|POST)`，DVWA exec 模块四档全部用
        `$_REQUEST['ip']`——上一轮那 8 条命令注入其实是靠
        `if (isset($_POST['Submit']))` 的 `__inline__` 兜底**误打误撞**报出来的；
        兜底收紧成"同行才算"后就整组漏掉了。这暴露的是 source 缺键，不是兜底过严。
        """
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"exec_low.php": (
                "<?php\n\n"
                "if ( isset( $_POST[ 'Submit' ] ) ) {\n"
                "    $target = $_REQUEST[ 'ip' ];\n"
                "    $cmd = shell_exec( 'ping  ' . $target );\n"
                "}\n")})
            cmdi = [f for f in data["flows"] if f["rule_id"] == "JZ-CMDI-001"]
            self.assertEqual(1, len(cmdi),
                             "$_REQUEST 拼进 shell_exec 必须成流；flows=%s"
                             % [(f["rule_id"], f["path"][-1]["line"])
                                for f in data["flows"]])

    def test_numeric_octet_reassembly_is_blocked_for_cmdi(self):
        """DVWA impossible.php 的四段 is_numeric 校验 + 逐段重组，是它公认的修复版；
        数值校验要能进 CMDI 的净化名单，否则靶场的"安全档"和"危险档"分不开。"""
        with tempfile.TemporaryDirectory() as tmp:
            data, _ = self._graph(tmp, {"exec_imp.php": (
                "<?php\n\n"
                "$target = $_REQUEST[ 'ip' ];\n"
                "$octet = explode( \".\", $target );\n"
                "if ( is_numeric( $octet[0] ) && is_numeric( $octet[1] ) ) {\n"
                "    $target = $octet[0] . '.' . $octet[1];\n"
                "    $cmd = shell_exec( 'ping  ' . $target );\n"
                "}\n")})
            self.assertEqual([], [f for f in data["flows"]
                                  if f["rule_id"] == "JZ-CMDI-001"],
                             "is_numeric 校验后的重组不应再报命令注入")
            self.assertGreaterEqual(data["stats"]["blocked_by_sanitizer"], 1)


class TestAuditContext(unittest.TestCase):
    """C1（B7 取证量出来的头号噪声源）：测试/示例语境单列一档。

    flask 13 条里 8 条在 `tests/`，requests 4 条全在测试或库实现处——
    这些**不能删**（示例里的注入写法是真代码，删了就等于闭眼），
    但也不能和 `app.py` 里的真洞混在同一个"结论条数"里报。
    所以这一档只动**结论归属**，不动检出、不动证据、不动 JSON。
    """

    CMDI = ("from flask import request, Flask\nimport os\napp = Flask(__name__)\n\n"
            "@app.route(\"/run\")\ndef run_it():\n"
            "    return os.system(\"ls \" + request.args[\"d\"])\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name, extra=None):
        out = os.path.join(root, "_c_%s.json" % name)
        cmd = [os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out]
        if extra:
            cmd += extra
        r = run(cmd)
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_test_and_example_paths_get_a_context_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.py", self.CMDI)
            self._write(tmp, "tests/test_app.py", self.CMDI)
            self._write(tmp, "examples/demo/tool.py", self.CMDI)
            data, _ = self._scan(tmp, "tag")
            by = dict((f["file"], f.get("context")) for f in data["findings"])
            self.assertIn("app.py", by)
            self.assertIsNone(by["app.py"], "正式代码不该带语境标签")
            self.assertEqual("test", by["tests/test_app.py"])
            self.assertEqual("example", by["examples/demo/tool.py"])
            s = data["stats"]
            self.assertEqual(1, s["conclusions"], "结论只算正式代码那条")
            self.assertEqual(2, s["context_excluded"])
            self.assertEqual(3, s["findings"], "总数不缩水：降误报不是藏证据")

    def test_name_substring_does_not_count_as_test_path(self):
        """`latest`/`biggest` 里含 test 但不是测试目录——按路径段与文件名形态判。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "src/latest_posts.py", self.CMDI)
            self._write(tmp, "contest.py", self.CMDI)
            data, _ = self._scan(tmp, "name")
            for f in data["findings"]:
                self.assertIsNone(f.get("context"),
                                  "文件名里的 test 子串不该打成测试语境：%s" % f["file"])
            self.assertEqual(len(data["findings"]), data["stats"]["conclusions"])

    def test_qualified_context_directory_is_recognised(self):
        """E7：带限定词的语境目录要认得出来——`evals/audit-fixtures/` 是夹具生成器。

        v0.37.0 新增的 JZ-CRYPTO-003 会命中语料生成器源码里的字面量 `'aes-128-ecb'`，
        而 `audit-fixtures` 不在整段词表里 ⇒ 三条本该"另计"的命中被算进了结论区，
        干净仓库这个标尺被污染（实测自扫 结论 3 / 另计 5）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.py", self.CMDI)
            self._write(tmp, "evals/audit-fixtures/gen_corpus.py", self.CMDI)
            data, _ = self._scan(tmp, "qualified")
            by = dict((f["file"], f.get("context")) for f in data["findings"])
            self.assertIn("evals/audit-fixtures/gen_corpus.py", by)
            self.assertEqual("test", by["evals/audit-fixtures/gen_corpus.py"],
                             "带限定词的夹具目录要算测试语境")
            s = data["stats"]
            self.assertEqual(1, s["conclusions"], "结论只算正式代码那条")
            self.assertEqual(1, s["context_excluded"])
            self.assertEqual(2, s["findings"], "总数不缩水：降误报不是藏证据")

    def test_component_split_still_requires_whole_words(self):
        """拆词后仍要**整词**匹配：`latest_posts` / `protest` / `attestation` 都不是语境。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "src/latest_posts.py", self.CMDI)
            self._write(tmp, "src/protest_tools.py", self.CMDI)
            self._write(tmp, "app/attestation-service/main.py", self.CMDI)
            data, _ = self._scan(tmp, "collide")
            for f in data["findings"]:
                self.assertIsNone(f.get("context"),
                                  "整词不在词表里就不该打成语境：%s" % f["file"])
            self.assertEqual(len(data["findings"]), data["stats"]["conclusions"])

    def test_report_splits_the_two_groups_and_keeps_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "app.py", self.CMDI)
            self._write(tmp, "tests/test_app.py", self.CMDI)
            md = os.path.join(tmp, "r.md")
            r = run([os.path.join(SCRIPTS, "audit_scan.py"), tmp, "--md", md])
            self.assertEqual(r.returncode, 0, r.stdout)
            text = io.open(md, encoding="utf-8").read()
            self.assertIn(u"## 测试/示例语境", text, "报告要有单独一档")
            self.assertIn(u"tests/test_app.py", text, "另计不等于不写")
            self.assertLess(text.index(u"`app.py:"), text.index(u"## 测试/示例语境"),
                            "正式结论要排在另计档之前")
            self.assertLess(text.count(u"## 测试/示例语境"), 3,
                            "另计档只有一个总标题，别每条重复")

    def test_sarif_keeps_context_as_property(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "tests/test_app.py", self.CMDI)
            sa = os.path.join(tmp, "s.sarif")
            r = run([os.path.join(SCRIPTS, "audit_scan.py"), tmp, "--sarif", sa])
            self.assertEqual(r.returncode, 0, r.stdout)
            doc = json.load(io.open(sa, encoding="utf-8"))
            results = doc["runs"][0]["results"]
            self.assertEqual(1, len(results), "SARIF 不能因为另计就少报")
            props = results[0].get("properties", {})
            self.assertEqual(u"test", props.get("jiangzuo:context"))


    def test_context_counts_survive_dedup(self):
        """语境两档必须从**去重后**的集合算。指纹是 (规则, 文件, 命中行文本)，
        所以同一个文件里两处一模一样的坏写法会并成一条——DVWA 复测当场出现
        「结论 52 / 总数 49」这种不可能的数，就是因为语境数用了去重前的集合。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "tests/dup_util.py",
                        "from flask import request\nimport os\n\n\n"
                        "def a():\n    return os.system(\"ls \" + request.args[\"d\"])\n\n\n"
                        "def b():\n    return os.system(\"ls \" + request.args[\"d\"])\n")
            self._write(tmp, "app.py",
                        "from flask import Flask\napp = Flask(__name__)\n")
            data, _ = self._scan(tmp, "dup")
            s = data["stats"]
            self.assertEqual(1, s["findings"],
                             "两处同文本坏写法应去重成 1 条（实得 %d，说明夹具没造出重复）"
                             % s["findings"])
            self.assertEqual(s["findings"],
                             s["conclusions"] + s["context_excluded"],
                             "三档口径必须自洽：%s" % {k: s[k] for k in
                                                       ("findings", "conclusions",
                                                        "context_excluded")})
            self.assertLessEqual(s["conclusions"], s["findings"],
                                 "结论数不可能大于总数")


class TestAuditRuleContext(unittest.TestCase):
    """C2（v0.31 结论区里剩下的就是这五发）：规则要能区分"角色 × 语境"。

    真实形状取自 flask / requests（逐行读过，不是我编的）：
      * flask/src/flask/cli.py:252 `raise NoAppException(f"…{traceback.format_exc()}")`
      * cli.py:653 `click.secho(f"{traceback.format_exc()}\\n", err=True, fg="red")`
      * cli.py:959 `traceback.print_exc()`（reloader 分支）
      —— 都在**没有任何路由的文件**里，输出目标是控制台/异常消息，不是 HTTP 响应体。
      * requests/src/requests/adapters.py:99 在 `def _urllib3_request_context(request, verify, …)`
        里 `if verify is False: cert_reqs = "CERT_NONE"`
      * adapters.py:344 在 `def cert_verify(self, conn, url, verify, cert)` 的 else 分支
        —— 库的职责就是**实现调用方的 verify 选项**，实现了不等于有漏洞。
    两半都必须断言：应用的 `verify=False`、路由文件里的 traceback 回显照报。
    """

    APP_ROUTE = ("from flask import Flask\napp = Flask(__name__)\n\n"
                 "@app.route(\"/u\")\ndef u():\n    return \"ok\"\n")

    def _write(self, root, rel, text):
        path = os.path.join(root, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _scan(self, root, name):
        out = os.path.join(root, "_r_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f), r.stdout

    def test_routeless_console_error_output_is_tagged_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py", self.APP_ROUTE)
            self._write(tmp, "mycli.py",
                        "import click\nimport traceback\n\n\n"
                        "def load():\n"
                        "    try:\n"
                        "        raise ValueError(\"x\")\n"
                        "    except Exception:\n"
                        "        click.secho(f\"{traceback.format_exc()}\\n\", err=True)\n")
            data, _ = self._scan(tmp, "cli")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-ERRINFO-001"]
            self.assertEqual(1, len(hit), "CLI 里的堆栈要检出：见 %s"
                             % [f["rule_id"] for f in data["findings"]])
            self.assertEqual("console", hit[0]["context"],
                             "无路由文件里的控制台输出不该算对外泄露")
            self.assertIn("路由", hit[0]["context_reason"])

    def test_raise_with_traceback_in_routeless_file_is_also_console(self):
        """cli.py:252 那一发没有 print/secho 标记，是 `raise X(f"…{format_exc()}")`。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py", self.APP_ROUTE)
            self._write(tmp, "tools/loader.py",
                        "import traceback\n\n\n"
                        "class NoAppException(Exception):\n    pass\n\n\n"
                        "def import_app(name):\n"
                        "    try:\n"
                        "        raise ImportError(name)\n"
                        "    except ImportError:\n"
                        "        raise NoAppException(f\"raised: {traceback.format_exc()}\")\n")
            data, _ = self._scan(tmp, "raise")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-ERRINFO-001"]
            self.assertEqual(1, len(hit), "检出本身要在：见 %s"
                             % [f["rule_id"] for f in data["findings"]])
            self.assertEqual("console", hit[0]["context"])

    def test_traceback_inside_route_file_stays_a_conclusion(self):
        """反面半句：同一个写法长在**有路由**的文件里就照报——只认语境不认文件名。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py",
                        "from flask import Flask\nimport traceback\n"
                        "app = Flask(__name__)\n\n"
                        "@app.route(\"/dbg\")\ndef dbg():\n"
                        "    traceback.print_exc()\n"
                        "    return \"x\"\n")
            data, _ = self._scan(tmp, "inroute")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-ERRINFO-001"]
            self.assertEqual(1, len(hit))
            self.assertIsNone(hit[0].get("context"),
                              "路由文件里的堆栈输出不能被另计")

    def test_library_verify_option_implementation_is_tagged_feature(self):
        lib = ("def _tls_context(request, verify, client_cert):\n"
               "    cert_reqs = \"CERT_REQUIRED\"\n"
               "    if verify is False:\n"
               "        cert_reqs = \"CERT_NONE\"\n"
               "    return cert_reqs\n")
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "setup.py", "from setuptools import setup\nsetup(name=\"x\")\n")
            self._write(tmp, "src/x/adapters.py", lib)
            data, _ = self._scan(tmp, "lib")
            self.assertEqual("library", data["stats"].get("repo_role"),
                             "夹具应判成库，否则这测的是别的条件")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-TLS-001"]
            self.assertEqual(1, len(hit), "TLS 命中要在：见 %s"
                             % [f["rule_id"] for f in data["findings"]])
            self.assertEqual("library_feature", hit[0]["context"],
                             "库实现 verify 选项不是漏洞")
            self.assertEqual(0, data["stats"]["conclusions"])

    def test_hardcoded_disable_in_library_and_app_usage_still_reported(self):
        """两半的反面：库里**没有** verify 形参也能关掉校验＝写死的默认值，照报；
        应用仓库里 `verify=False` 是调用方的决定，也照报。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "setup.py", "from setuptools import setup\nsetup(name=\"x\")\n")
            self._write(tmp, "src/x/pool.py",
                        "def make_conn(conn):\n"
                        "    conn.cert_reqs = \"CERT_NONE\"\n")
            data, _ = self._scan(tmp, "hard")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-TLS-001"]
            self.assertEqual(1, len(hit))
            self.assertIsNone(hit[0].get("context"),
                              "没有 opt-out 形参就是写死的不安全默认，必须算结论")
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py",
                        "from flask import Flask\nimport requests\n"
                        "app = Flask(__name__)\n\n"
                        "@app.route(\"/f\")\ndef f():\n"
                        "    return requests.get(\"https://x\", verify=False).text\n")
            data, _ = self._scan(tmp, "app")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-TLS-001"]
            self.assertEqual(1, len(hit))
            self.assertIsNone(hit[0].get("context"),
                              "应用里主动关掉校验就是结论")


    def test_two_console_hits_in_same_file_both_tagged(self):
        """行窗口缓存按文件键会读到"第一条命中的行号+4"就停，
        同一文件里更靠后的命中就再也读不到上下文——flask/cli.py 实测三发只标上一发。
        这条锁的是：缓存键必须带上要读到的位置。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py", self.APP_ROUTE)
            body = []
            for i in range(4):
                # 每发的 sink_text 要不同：指纹是 (规则, 文件, 命中行文本)，
                # 四行一模一样的话会被去重成一条，测不到"靠后的那一发"。
                body.append("    try:\n        raise ValueError(\"x%d\")\n"
                            "    except Exception:\n"
                            "        click.secho(f\"step%d {traceback.format_exc()}\\n\", err=True)\n"
                            % (i, i))
            self._write(tmp, "mycli.py",
                        "import click\nimport traceback\n\n\n"
                        "def load():\n" + "\n".join(body))
            data, _ = self._scan(tmp, "two")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-ERRINFO-001"]
            self.assertGreaterEqual(len(hit), 3, "夹具要造出多发命中：%s"
                                    % [(f["rule_id"], f["line"]) for f in data["findings"]])
            untagged = [f for f in hit if f.get("context") != "console"]
            self.assertEqual([], untagged,
                             "同一文件里靠后的控制台命中不能被漏掉：%s"
                             % [(f["line"], f.get("context")) for f in untagged])


    def test_routeless_file_with_real_response_leak_stays_reported(self):
        """另一半条件：「文件没路由」单独不够，**命中形状**也得是控制台/raise。
        服务层把异常文本 return 出去，最终会进响应体——这种不能被另计掉。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._write(tmp, "webapp.py", self.APP_ROUTE)
            self._write(tmp, "services/report.py",
                        "import sqlite3\n\n\n"
                        "def rows(db, key):\n"
                        "    con = sqlite3.connect(db)\n"
                        "    try:\n"
                        "        return con.execute(\"SELECT * FROM t WHERE k=\" + key).fetchall()\n"
                        "    except Exception as e:\n"
                        "        return \"query failed: \" + str(e) + sql\n")
            data, _ = self._scan(tmp, "shape")
            hit = [f for f in data["findings"] if f["rule_id"] == "JZ-ERRINFO-001"]
            self.assertEqual(1, len(hit), "检出要在：见 %s"
                             % [(f["rule_id"], f["file"]) for f in data["findings"]])
            self.assertIsNone(hit[0].get("context"),
                              "return 出去的错误文本不是控制台输出，必须算结论")


class TestAuditDvwaClasses(unittest.TestCase):
    """C3：DVWA 的模块目录名就是标准答案，分母不由我定。

    先有 `evals/audit-fixtures/dvwa_coverage.py` 量出"按主类别只检出 7/19"，
    这一轮补的是其中**能用正则正确解决**的四类；每类都带反面半句，
    避免把"报得多"当成"检得出"。
    """

    def _graph(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out = os.path.join(root, "_graph.json")
        r = run([os.path.join(SCRIPTS, "audit_graph.py"), root, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_output_buffer_concat_is_an_xss_sink(self):
        """DVWA 的反射 XSS 是 `$html .= '<pre>' . $_GET[...] . '</pre>'`，
        真正的 echo 在模板里（跨文件）——sink 必须认"把污点拼进要输出的 HTML 变量"这一步。"""
        data = self._graph(tempfile.mkdtemp(), {"vulnerabilities/xss_r/source/low.php": (
            "<?php\n\n"
            "if ( array_key_exists( \"name\", $_GET ) ) {\n"
            "    $html .= '<pre>Hello ' . $_GET[ 'name' ] . '</pre>';\n"
            "}\n")})
        xss = [f for f in data["flows"] if f["rule_id"] == "JZ-XSS-002"]
        self.assertEqual(1, len(xss), "拼进输出缓冲的污点要成流：%s"
                         % [f["rule_id"] for f in data["flows"]])

    def test_plain_include_without_parens_is_traversal(self):
        """原 sink 写成 `(?:include|require)_?once?\\s*\\(`——`once?` 要求必须有 "onc"，
        所以不带 `_once` 的 `include( $file )` 永远匹配不上。"""
        data = self._graph(tempfile.mkdtemp(), {"vulnerabilities/fi/index.php": (
            "<?php\n\n"
            "$file = $_GET[ 'page' ];\n"
            "include( $file );\n")})
        trav = [f for f in data["flows"] if f["rule_id"] == "JZ-TRAVERSAL-001"]
        self.assertEqual(1, len(trav), "无括号的 include 变量要检出：%s"
                         % [f["rule_id"] for f in data["flows"]])

    def test_static_include_is_not_traversal(self):
        """反面半句：`include_once 'config.php';` 是写死的路径，不是穿越。"""
        data = self._graph(tempfile.mkdtemp(), {"boot.php": (
            "<?php\n\n"
            "define( 'ROOT', __DIR__ );\n"
            "$status = 1;\n"
            "include_once 'dvwa/includes/dvwaPage.inc.php';\n")})
        self.assertEqual([], [f for f in data["flows"]
                              if f["rule_id"] == "JZ-TRAVERSAL-001"])

    def test_lowercase_location_header_is_open_redirect(self):
        """DVWA 写的是 `header (\"location: \" . $_GET['redirect'])`——小写 l。"""
        data = self._graph(tempfile.mkdtemp(), {"vulnerabilities/open_redirect/source/low.php": (
            "<?php\n\n"
            "if ( array_key_exists (\"redirect\", $_GET) ) {\n"
            "    header (\"location: \" . $_GET['redirect']);\n"
            "    exit;\n"
            "}\n")})
        redir = [f for f in data["flows"] if f["rule_id"] == "JZ-REDIR-001"]
        self.assertEqual(1, len(redir), "小写 location 的开放重定向要检出：%s"
                         % [f["rule_id"] for f in data["flows"]])

    def test_fixed_location_header_is_not_redirect(self):
        """反面半句：`header( 'Location:?page=include.php' )` 是写死的目标。"""
        data = self._graph(tempfile.mkdtemp(), {"vulnerabilities/fi/index.php": (
            "<?php\n\n"
            "$page = $_GET[ 'page' ];\n"
            "$count = 1;\n"
            "header( 'Location:?page=include.php' );\n")})
        self.assertEqual([], [f for f in data["flows"]
                              if f["rule_id"] == "JZ-REDIR-001"])

    def _scan(self, root, files, name):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out = os.path.join(root, "_w_%s.json" % name)
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_predictable_session_identifiers_are_caught(self):
        """weak_id 模块三档：递增计数器当会话值、`time()` 当 cookie 值、`md5(计数器)`。"""
        root = tempfile.mkdtemp()
        data = self._scan(root, {
            "app.py": "from flask import Flask\napp = Flask(__name__)\n\n"
                      "@app.route('/x')\ndef x():\n    return 'ok'\n",
            "vulnerabilities/weak_id/low.php": (
                "<?php\n\n$_SESSION['last_session_id']++;\n"
                "$cookie_value = $_SESSION['last_session_id'];\n"
                "setcookie(\"dvwaSession\", $cookie_value);\n"),
            "vulnerabilities/weak_id/medium.php": (
                "<?php\n\n$x = 1;\n$cookie_value = time();\n"
                "setcookie(\"dvwaSession\", $cookie_value);\n"),
            "vulnerabilities/weak_id/high.php": (
                "<?php\n\n$seed = 1;\n"
                "$cookie_value = md5($_SESSION['last_session_id_high']);\n"
                "setcookie(\"dvwaSession\", $cookie_value);\n"),
        }, "weak")
        got = set(f["file"] for f in data["findings"] if f["rule_id"] == "JZ-WEAKID-001")
        for want in ("low.php", "medium.php", "high.php"):
            self.assertTrue(any(want in g for g in got),
                            "%s 没检出可预测标识符：%s" % (want, sorted(got)))

    def test_csprng_generation_is_not_weak_id(self):
        """反面半句：`random_bytes()` / `random_int()` 生成的标识不该报。"""
        data = self._scan(tempfile.mkdtemp(), {
            "app.py": "from flask import Flask\napp = Flask(__name__)\n\n"
                      "@app.route('/x')\ndef x():\n    return 'ok'\n",
            "good.php": "<?php\n\n$salt = 1;\n"
                        "$session_id = bin2hex(random_bytes(16));\n"
                        "$token = bin2hex(openssl_random_pseudo_bytes(8));\n"
                        "setcookie(\"sid\", $session_id);\n",
        }, "good")
        self.assertEqual([], [f for f in data["findings"]
                              if f["rule_id"] == "JZ-WEAKID-001"],
                         "CSPRNG 生成的标识被误报了：%s"
                         % [(f["file"], f["line"]) for f in data["findings"]
                            if f["rule_id"] == "JZ-WEAKID-001"])


    def test_constant_append_to_tainted_buffer_is_not_a_flow(self):
        """赋值**左边的变量不是"读取"**：`$html .= "<p>Too many requests.</p>"` 里
        没有任何外部数据，只因为 `$html` 早先被污染过就报 XSS，是把输出容器当输入。
        DVWA 的 impossible.php 曾因此被成片误报（第一版实测 16 发里多数是常量拼接）。

        取舍写明白：拼接缓冲这类 sink 只认"同一行内联读了外部输入"（xss_r 那种），
        两步写法（先拼再 echo）交给 `echo` 那条 sink——只拼不输出的文件不报，
        因为输出发生在别的文件里，本来就跟不动，不该假装看得见。
        """
        data = self._graph(tempfile.mkdtemp(), {"page.php": (
            "<?php\n\n"
            "$name = $_GET[ 'name' ];\n"
            "$html .= \"<p>Hello \" . $name . \"</p>\";\n"
            "$html .= \"<p>Too many requests. Please try again later.</p>\";\n"
            "$html .= \"<p>Your image was not uploaded.</p>\";\n"
            "echo $html;\n")})
        lines = sorted(f["line"] for f in data["flows"] if f["rule_id"] == "JZ-XSS-002")
        lines = sorted(f["line"] for f in data["flows"] if f["rule_id"] == "JZ-XSS-002")
        # 行号：1 `<?php`、2 空、3 取参、4 拼污点、5-6 常量拼接、7 `echo $html`
        self.assertEqual([7], lines,
                         "污点经缓冲区最终输出时只报 echo 那一行，常量拼接不各自成流：%s" % lines)

    def test_numeric_coercion_is_xss_safe_and_breaks_the_flow(self):
        """`intval()` 出来的整数不含标签字符，拼进 HTML 是安全的（DVWA bac/impossible 就这样写）。
        数值收敛要进 XSS 的净化名单，否则官方修复档会被成片误报。

        夹具走 `echo` 那条 sink（不是缓冲拼接那条），这样"拦住它"的**只有净化名单**——
        第一版夹具写得让 sink 本来就不匹配，净化删掉也照样绿，等于没测。
        """
        data = self._graph(tempfile.mkdtemp(), {"bac.php": (
            "<?php\n\n"
            "$id = $_GET[ 'id' ];\n"
            "$id = intval( $id );\n"
            "echo \"<p>No user found with ID: {$id}</p>\";\n")})
        self.assertEqual([], [f for f in data["flows"]
                              if f["rule_id"] == "JZ-XSS-002"],
                         "intval 之后输出不该报反射 XSS：%s"
                         % [(f["line"],) for f in data["flows"]])
        self.assertGreaterEqual(data["stats"]["blocked_by_sanitizer"], 1,
                                "净化要留痕，不能当没发生过")


class TestAuditCryptoAndClient(unittest.TestCase):
    """E1：DVWA 的 cryptography 与 javascript 两个模块长期 MISS，
    分母是靶场自己给的（`dvwa_coverage.py` 的 CATEGORY 把 cryptography 的主类别规则
    列为 JZ-CRYPTO-001/002/003、javascript 列为 JZ-JSINSEC-001/JZ-XSS-001）。

    夹具形状**逐行取自真实 DVWA**（`vulnerabilities/cryptography/source/{low,medium}.php`、
    `vulnerabilities/javascript/source/{low.php,high.js,medium.js}`），不是我编的：
      * `openssl_encrypt($plaintext, 'aes-128-ecb', $key, OPENSSL_PKCS1_PADDING)`（ecb_attack.php:3）
      * `$outText .= $cleartext[$i] ^ $key[$j];`（low.php:9 手写 XOR）
      * `eval(function(d,e,f,g,h,i){…})` Dean-Edward 打包器（high.js 尾行）
      * `document.getElementById("token").value = md5(rot13(phrase));`（low.php 前端算令牌）
    每条都配**反面半句**，防止把"报得多"当"检得出"：
    GCM/普通拼接/服务端下发的令牌都不许报。
    """

    def _findings(self, files):
        root = tempfile.mkdtemp()
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out = os.path.join(root, "_scan.json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), root, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [(x["rule_id"], x["file"], x["line"]) for x in data["findings"]]

    def test_ecb_cipher_mode_is_flagged(self):
        hits = self._findings({"app/crypto.php": (
            "<?php\n"
            "function enc($plaintext, $key) {\n"
            "    $e = openssl_encrypt($plaintext, 'aes-128-ecb', $key, OPENSSL_PKCS1_PADDING);\n"
            "    return $e;\n"
            "}\n")})
        self.assertTrue([h for h in hits if h[0] == "JZ-CRYPTO-003"],
                        "ECB 密码模式没检出：%s" % hits)

    def test_authenticated_cipher_mode_is_not_flagged(self):
        hits = self._findings({"app/crypto.php": (
            "<?php\n"
            "$iv = random_bytes(12);\n"
            "$e = openssl_encrypt($plaintext, 'aes-256-gcm', $key, OPENSSL_RAW_DATA, $iv);\n")})
        self.assertEqual([], [h for h in hits if h[0] == "JZ-CRYPTO-003"],
                          "GCM 是正确写法，不该被弱加密规则报出：%s" % hits)

    def test_home_rolled_xor_cipher_is_flagged(self):
        hits = self._findings({"vulnerabilities/cryptography/source/low.php": (
            "<?php\n"
            "function xor_this($cleartext, $key) {\n"
            "    $outText = '';\n"
            "    for($i=0; $i<strlen($cleartext);) {\n"
            "        for($j=0; ($j<strlen($key) && $i<strlen($cleartext)); $j++,$i++) {\n"
            "            $outText .= $cleartext[$i] ^ $key[$j];\n"
            "        }\n"
            "    }\n"
            "    return $outText;\n"
            "}\n")})
        self.assertTrue([h for h in hits if h[0] == "JZ-CRYPTO-003"],
                        "手写逐字符 XOR 没检出：%s" % hits)

    def test_plain_string_concat_is_not_flagged(self):
        hits = self._findings({"app/build.php": (
            "<?php\n"
            "$out = '';\n"
            "for ($i = 0; $i < count($parts); $i++) {\n"
            "    $out .= $parts[$i];\n"
            "}\n")})
        self.assertEqual([], [h for h in hits if h[0] == "JZ-CRYPTO-003"],
                          "普通拼接不是加密，不该报：%s" % hits)

    def test_packed_obfuscated_js_is_flagged(self):
        hits = self._findings({"assets/high.js": (
            "var a=['fromCharCode','token'];\n"
            "eval(function(p,a,c,k,e,d){e=function(c){return c.toString(36)};"
            "while(c--){d[c]=k[c]||c}return p.replace(/\\w+/g,f)}"
            "('0|1',36,2,'token|value'.split('|'),0,{}))\n")})
        self.assertTrue([h for h in hits if h[0] == "JZ-JSINSEC-001"],
                        "打包/混淆的 eval 没检出：%s" % hits)

    def test_ordinary_js_call_is_not_flagged(self):
        hits = self._findings({"assets/app.js": (
            "function doSomething(x) { return x + 1; }\n"
            "doSomething(2);\n")})
        self.assertEqual([], [h for h in hits if h[0] == "JZ-JSINSEC-001"],
                          "普通 JS 不该被客户端安全规则报出：%s" % hits)

    def test_client_side_token_hash_is_flagged(self):
        hits = self._findings({"js/token.js": (
            "function generate_token() {\n"
            "    var phrase = document.getElementById('phrase').value;\n"
            "    document.getElementById('token').value = md5(rot13(phrase));\n"
            "}\n")})
        self.assertTrue([h for h in hits if h[0] == "JZ-JSINSEC-001"],
                        "前端自己算令牌没检出：%s" % hits)

    def test_server_provided_token_assignment_is_not_flagged(self):
        """正确的 CSRF 写法就是前端把服务端下发的值填进字段——不能因为"前端碰了 token"就报。"""
        hits = self._findings({"js/token.js": (
            "fetch('/csrf').then(function(r){ return r.json(); }).then(function(d) {\n"
            "    document.getElementById('token').value = d.csrf_token;\n"
            "});\n")})
        self.assertEqual([], [h for h in hits if h[0] == "JZ-JSINSEC-001"],
                          "服务端下发令牌是标准写法，不该报：%s" % hits)


class TestAuditMemoryProfile(unittest.TestCase):
    """E4：把"内存亚线性不平坦、残留点是 graph 保留函数体"这句含糊话换成实测数。

    实测（同形状语料，全部文件都含 sink = 候选占满的最坏情况）：
    1200 文件峰值 18.7 MB、4800 文件 74 MB，**严格线性 ~15.4 KB/文件（峰值口径）**；
    建图结束后驻留 7.4 KB/文件（400 文件口径）。门控路径（干净仓库、无候选）
    ×6.3 文件只 ×1.09 内存，已经是平的。
    所以这里只留**一条有牙齿的锁**：图层产物不许携带源码。
    曾经想加的第二条"驻留内存 KB/文件预算"被当场否掉——
    给 1200 个函数各多存一份行元组，驻留只从 7.4 涨到 9.0 KB/文件
    （字符串是共享的，涨的只是元组容器），阈值只能定在永远踩不到的位置。
    **一条永远绿的锁比没有锁更坏**（它挂着 ✅ 还教人无视红灯），故删除并把结论写进文档。
    """

    FILE = (u'"""模块 %d。"""\nfrom flask import request\nimport os\n\n\n'
            u'def load_%d(conn, limit):\n'
            u'    rows = []\n'
            u'    for i in range(limit):\n'
            u'        value = conn.fetch(i)\n'
            u'        if value is None:\n'
            u'            continue\n'
            u'        rows.append(value)\n'
            u'    return rows\n\n\n'
            u'def run_convert(fmt):\n'
            u'    name = request.args["name"]\n'
            u'    os.system("convert " + name + " out." + fmt)\n'
            u'    return "ok"\n')

    def _graph(self, n):
        sys.path.insert(0, SCRIPTS)
        import audit_graph
        import auditlib
        import audit_rules
        with tempfile.TemporaryDirectory() as root:
            for i in range(n):
                with io.open(os.path.join(root, "mod_%04d.py" % i), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(self.FILE % (i, i))
            index = auditlib.build_index(root)
            rules, _p, _no, _o = audit_rules.load_rules([])
            taint = [r for r in rules if r.get("kind") in ("taint", "pattern")]
            cands = set(f["path"] for f in index["files"])
            data = audit_graph.build_graph(root, index=index, rules=taint,
                                           candidates=cands)
            return data, len(index["files"])

    def test_graph_payload_does_not_carry_function_bodies(self):
        """产物的函数条目只能带廉价事实：name/file/lang/start/end/params/calls。
        带上 body/lines 就等于把整仓源码塞进每次交付的 JSON 与 SARIF——
        那既是体积炸弹，也让"报告可以直接外发"这句话失效。"""
        data, n = self._graph(120)
        funcs = data["functions"]
        self.assertGreater(len(funcs), n, "夹具该产出多个函数，否则这条测不到东西")
        self.assertTrue(data["flows"], "夹具必须真的产出污点流，否则锁是在空图上绿")
        heavy = sorted({k for f in funcs for k in f
                        if k in ("body", "lines", "source", "text", "code")})
        self.assertEqual([], heavy,
                         u"图层产物里出现了源码字段 %s——JSON/SARIF 会整份膨胀成仓库大小"
                         % heavy)
        self.assertTrue(all({"name", "file", "start", "end", "params", "calls"} <= set(f)
                            for f in funcs),
                        "函数条目该有的廉价事实不能少（少了图就不可解释）")


class TestAuditPatternCost(unittest.TestCase):
    """C3 自纠：我写的一条 sink 是 O(n²) 的，600KB 行要跑 106 秒。

    形状是 `[^;]*(?:A[^;]*<|<[^;]*A)`——一个无上界字符类里再套两个同类，
    失配时引擎要逐起点重扫。这类东西**本地永远测不出来**（真实行都短），
    所以不能只靠"跑得快"，要有一条当场把长行喂进去的时限锁。
    """

    # 两条对抗形状：都故意不带分号（让 `[^;]*` 一路扫到尾），
    # A 里放 superglobal 锚点、B 里放括号引号尖括号的混合噪声。
    # 尺寸取 20 万级而不是更大：Python 中断不了一次正在跑的 regex 搜索，
    # 输入必须小到"即使真是 O(n²) 也只几秒就红"——200K 上二次方约 1.4 秒（超 500ms 限值会红），
    # 线性只有几毫秒。实测过 540K：二次方要 10 秒以上，整条校准流水线因此卡死过一回。
    ADVERSARIAL = [
        "\$_GET['k'] . \"a<&" * 12000,
        "$x = foo(bar'baz\"qux <&=() " * 5000,
    ]
    LIMIT_MS = 500.0

    def test_every_rule_pattern_is_linear_on_long_lines(self):
        import re as _re
        sys_path = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "scripts")
        if sys_path not in sys.path:
            sys.path.insert(0, sys_path)
        import audit_rules as AR
        rules, problems, _notes, _off = AR.load_rules([])
        self.assertEqual([], problems, u"规则库有问题：%s" % problems[:2])
        worst = (0.0, u"")
        for r in rules:
            for field in ("sinks", "sources", "sanitizers", "unless_present"):
                for item in r.get(field, []):
                    rx = _re.compile(item["pattern"])
                    for text in self.ADVERSARIAL:
                        t0 = time.time()
                        rx.search(text)
                        ms = (time.time() - t0) * 1000.0
                        if ms > worst[0]:
                            worst = (ms, u"%s.%s %s" % (r["id"], field, item["pattern"][:60]))
                        self.assertLess(ms, self.LIMIT_MS,
                                        u"%s.%s 在 %d 字符的行上花了 %.0f ms——"
                                        u"疑似灾难性回溯（限 %d ms）：%s"
                                        % (r["id"], field, len(text), ms,
                                           self.LIMIT_MS, item["pattern"][:80]))
        # 让"最慢的那条"可见，别只报通过与否
        print(u"最慢 pattern：%.1f ms ｜ %s" % worst)


class TestAuditMultilineString(unittest.TestCase):
    """E31：跨行字符串字面量要当作**一个**字面量。

    为什么（DVWA 实测，一对**相反**的症状）：
    - `$log_query = "SELECT l.id, l.user_id, …`（多行 SQL 串的**第一行**）没有闭合引号
      ⇒ 逐行分析时它被当成**代码** ⇒ 里面的**列别名**（`l.id`）被当成"读了变量
      `$id`" ⇒ 污点顺着它流进了**根本不含该值**的查询（`bac/index.php:58`）⇒ **误报**；
    - 而真正该算读取的**插值**（`{$target_id}`，在**第二行**）反倒被漏掉
      ⇒ **真阳性也丢了**（一类既有的漏报）。

    ⇒ 折叠之后整段字符串是**一个**字面量 ⇒ 列别名不是读取、插值是读取
    ⇒ 误报与漏报**一起**解决。

    另外 E31 修掉同一条链上的另一处：include-scope 通道**要认被 include 文件里的
    无条件净化点**（`$id = intval($_GET['user_id']);` 出来的值是干净的，不该被当污点带走）。
    """

    def _graph(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out = os.path.join(root, "_graph.json")
        r = run([os.path.join(SCRIPTS, "audit_graph.py"), root, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def _sqli_flows(self, data):
        return [f for f in data["flows"] if f["rule_id"] == "JZ-SQLI-003"]

    def test_column_alias_in_multiline_string_is_not_a_variable_read(self):
        """正例：多行 SQL 串首行里的 `l.id` 是**列别名**，不是读 `$id`。

        ⚠️ 这正是 DVWA `bac/index.php:51` 的形状：`$log_query = "SELECT l.id, …`
        而 `$id`（来自被 include 的文件）恰好同名 ⇒ 旧逻辑把列别名当成了读取
        ⇒ 污点流进了一个**根本不含该值**的查询。
        """
        data = self._graph(tempfile.mkdtemp(), {
            "app.php": (
                "<?php\n"
                "$id = $_GET['id'];\n"
                "$log_query = \"SELECT l.id, l.user_id FROM logs\n"
                "             WHERE l.x = 1\";\n"
                "mysqli_query($conn, $log_query);\n")})
        self.assertEqual([], self._sqli_flows(data),
                         "多行串里的列别名被当成了变量读取 ⇒ 污点流进了不含它的查询：%s"
                         % [(f["line"],) for f in self._sqli_flows(data)])

    def test_interpolation_in_multiline_string_is_still_a_read(self):
        """反例（防误伤）：插值 `{$target_id}` 在**第二行**时**仍要算读取**。

        ⚠️ 这条不许被"折叠"顺手砍掉：砍掉它就丢**真阳性**。
        ⚠️ 它在 E31 之前是**红的** ⇒ 多行串里的插值以前**根本不算读取**
        ⇒ 那是一类**既有的漏报**（不只 DVWA）。
        """
        data = self._graph(tempfile.mkdtemp(), {
            "app.php": (
                "<?php\n"
                "$id = $_GET['id'];\n"
                "$target_id = $id;\n"
                "$log_query = \"INSERT INTO t (a, b) VALUES\n"
                "            ({$target_id}, 1)\";\n"
                "mysqli_query($conn, $log_query);\n")})
        self.assertTrue(self._sqli_flows(data),
                        "多行串里的插值不算读取 ⇒ 真阳性被漏掉了：%s"
                        % [(f["line"],) for f in self._sqli_flows(data)])

    def test_include_scope_honors_sanitizer_in_the_included_file(self):
        """正例：被 include 的文件里 `intval()` 过 ⇒ 那个值是干净的，不该被带走。

        形状逐字取自 DVWA `bac/source/high.php:25`：
        `$id = intval($_GET['user_id']);`
        """
        data = self._graph(tempfile.mkdtemp(), {
            "vulnerabilities/bac/index.php": (
                "<?php\n"
                "$vulnerabilityFile = 'high.php';\n"
                "require_once \"vulnerabilities/bac/source/{$vulnerabilityFile}\";\n"
                "$q = \"SELECT * FROM t WHERE id = $id\";\n"
                "mysqli_query($conn, $q);\n"),
            "vulnerabilities/bac/source/high.php": (
                "<?php\n"
                "$id = intval($_GET['user_id']);\n")})
        self.assertEqual([], self._sqli_flows(data),
                         "被 include 文件里已被 intval 净化的值仍被当污点带走：%s"
                         % [(f["line"],) for f in self._sqli_flows(data)])

    def test_include_scope_still_carries_unsanitized_taint(self):
        """反例（防误伤）：被 include 的文件里**没有**净化点 ⇒ 污点照旧跨文件流。

        ⚠️ 这条锁的是 DVWA `fi` 模块那条**真阳性**
        （`fi/source/high.php:4` 的 `$file = $_GET['page'];` ⇒ `fi/index.php:36`）。
        """
        data = self._graph(tempfile.mkdtemp(), {
            "vulnerabilities/fi/index.php": (
                "<?php\n"
                "$vulnerabilityFile = 'high.php';\n"
                "require_once \"vulnerabilities/fi/source/{$vulnerabilityFile}\";\n"
                "$q = \"SELECT * FROM t WHERE id = $file\";\n"
                "mysqli_query($conn, $q);\n"),
            "vulnerabilities/fi/source/high.php": (
                "<?php\n"
                "$file = $_GET['page'];\n")})
        self.assertTrue(self._sqli_flows(data),
                        "未净化的污点没有跨文件流过去 ⇒ 真阳性被误杀：%s"
                        % [(f["line"],) for f in self._sqli_flows(data)])


class TestLedgerTotals(unittest.TestCase):
    """E32：§四 的**口径拆解**必须自洽（`validate_skill` 第 22 项）。

    为什么需要它：E32 之前，「全部产出」口径的误报率一直是**未判定**，
    而且三份文档各写一个数（20 / 12 / "59 条里有 20 条"）⇒ 互相矛盾。
    E32 把这批逐条判完 ⇒ §四 有一张机器可读的口径拆解表
    ⇒ 它的每个加法都必须成立，且「误报」条数必须与 §一 合计行**对上**。
    """

    def test_validate_reports_the_ledger_totals(self):
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn("口径拆解自洽", r.stdout)

    def test_broken_ledger_totals_must_be_flagged(self):
        """反例：§四 的加法不成立时，validate 必须判错（不能静默放过）。"""
        with tempfile.TemporaryDirectory() as tmp:
            evals = os.path.join(tmp, "evals")
            os.makedirs(evals)
            with io.open(os.path.join(REPO, "evals", "finding-verdicts.md"),
                         "r", encoding="utf-8") as f:
                text = f.read()
            broken = text.replace(
                "| 全部产出 | 75 | 真阳性 55 + 误报 4 + 另计 16 |",
                "| 全部产出 | 76 | 真阳性 55 + 误报 4 + 另计 16 |", 1)
            self.assertNotEqual(broken, text, "没找到要破坏的口径行")
            with io.open(os.path.join(evals, "finding-verdicts.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(broken)
            with io.open(os.path.join(tmp, "SKILL.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write("---\nname: tmp-skill\ndescription: temporary fixture\n"
                        "---\n\nbody\n")
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), tmp])
            self.assertNotEqual(r.returncode, 0,
                                "口径加法不成立时 validate 竟然通过了")
            self.assertIn("口径拆解不自洽", r.stdout)



class TestAuditSqlQuoteInSink(unittest.TestCase):
    """E33：**值直接内插在 sink 调用里** ⇒ 上下文要在 **sink 那一行**判。

    为什么（能力边界表最后一条，E22 记下、E30/E31 只做掉了一半）：
    E30 的上下文判定只在**赋值行**上做（`$q = "... '$x'"; mysql_query($q);`）
    ⇒ 而 `mysql_query("SELECT * FROM t WHERE a = '$x'")` 这种**没有独立赋值行**的形态
    判不到 ⇒ 转义被无视 ⇒ 明明在引号内也照报（误报）。

    ⇒ E33 把上下文判定也接到 **sink 行**上 ⇒ 这条边界闭合。
    ⚠️ 配套必须有**反例**：同样在 sink 调用里内插，但**引号外** ⇒ 转义无效 ⇒ **仍须报**
    （否则就是拿真阳性换误报 —— 本项目吃过三次这个亏）。
    """

    def _scan(self, tmp, name, body):
        d = os.path.join(tmp, name)
        os.makedirs(d)
        with io.open(os.path.join(d, name), "w", encoding="utf-8", newline="\n") as f:
            f.write(body)
        out = os.path.join(tmp, "_e33.json")
        r = run([os.path.join(SCRIPTS, "audit_scan.py"), d, "--json", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return set(x["rule_id"] for x in json.load(f)["findings"])

    def test_escaped_value_interpolated_in_the_sink_is_not_reported(self):
        """正例：转义 + **引号内** ⇒ 不是注入 ⇒ 不该报。

        ⚠️ E22 那条边界测试锁的正是这个形态**照报** ⇒ E30/E31 做掉一半后它变红了
        （它自己的失败信息就写着"能力边界表第 2 行该改"）⇒ E33 把它搬到这里并反转期望。
        """
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "e33_escape.php",
                           "<?php\n"
                           "function q($c, $x) {\n"
                           "    $x = mysqli_real_escape_string($c, $x);\n"
                           "    mysql_query(\"SELECT * FROM t WHERE a = '$x'\");\n"
                           "}\n"
                           "q($conn, $_GET['a']);\n")
            self.assertNotIn("JZ-SQLI-003", p,
                             "转义 + 引号内仍报 ⇒ 上下文判定没接到 sink 行上")

    def test_escaped_value_interpolated_outside_quotes_is_still_reported(self):
        """反例（防误伤）：同样内插在 sink 调用里，但**引号外** ⇒ 转义无效 ⇒ 仍须报。

        ⚠️ 这条不许被"接 sink 行"顺手砍掉：砍掉它就丢了**真阳性**
        （DVWA `sqli_blind/source/medium.php:15` 就是这个形态）。
        """
        with tempfile.TemporaryDirectory() as tmp:
            p = self._scan(tmp, "e33_bare.php",
                           "<?php\n"
                           "function q($c, $x) {\n"
                           "    $x = mysqli_real_escape_string($c, $x);\n"
                           "    mysql_query(\"SELECT * FROM t WHERE a = $x\");\n"
                           "}\n"
                           "q($conn, $_GET['a']);\n")
            self.assertIn("JZ-SQLI-003", p,
                          "引号外的转义没报 ⇒ 真阳性被吃掉了")


class TestAuditIncludeScope(unittest.TestCase):
    """C4：DVWA 的 fi 模块一直没检出，原因是"跨文件的模块级变量"。

    真实形状（逐字读过）：
      vulnerabilities/fi/source/low.php → `$file = $_GET[ 'page' ];`
      vulnerabilities/fi/index.php:32   → `require_once …"vulnerabilities/fi/source/{$vulnerabilityFile}";`
      vulnerabilities/fi/index.php:36   → `include( $file );`
    PHP 的 include 共享调用方的符号表：被包含文件里赋的模块级变量，包含者直接能读。
    这条通道只在**文件里确实有"变量路径的 include/require"**时才打开——
    没有这种写法就把池子打开，等于让全仓同名变量互相污染（那是误报制造机）。
    """

    def _graph(self, root, files):
        for rel, text in files.items():
            path = os.path.join(root, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        out = os.path.join(root, "_graph.json")
        r = run([os.path.join(SCRIPTS, "audit_graph.py"), root, "--out", out])
        self.assertEqual(r.returncode, 0, r.stdout)
        with io.open(out, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_variable_path_include_opens_a_directory_scope_pool(self):
        data = self._graph(tempfile.mkdtemp(), {
            "vulnerabilities/fi/index.php": (
                "<?php\n\n"
                "$vulnerabilityFile = 'low.php';\n"
                'require_once DVWA_WEB_PAGE_TO_ROOT . "vulnerabilities/fi/source/{$vulnerabilityFile}";\n\n'
                "if( isset( $_GET[ 'include' ] ) ) {\n"
                "\tinclude( $file );\n"
                "}\n"),
            "vulnerabilities/fi/source/low.php": (
                "<?php\n\n"
                "// The page we wish to display\n"
                "$file = $_GET[ 'page' ];\n"),
        })
        trav = [f for f in data["flows"] if f["rule_id"] == "JZ-TRAVERSAL-001"]
        self.assertEqual(1, len(trav),
                         "跨文件的模块级污点要接上：flows=%s"
                         % [(f["rule_id"], f["file"], f["line"]) for f in data["flows"]])
        self.assertEqual("vulnerabilities/fi/index.php", trav[0]["file"])
        self.assertEqual(u"interprocedural", trav[0]["depth"],
                         "跨文件要标出来，不能伪装成本函数内的流")

    def test_no_include_keeps_the_pool_closed(self):
        """反面半句：两个文件之间没有任何 include 关系时，
        别的文件里 `$file = $_GET[...]` 不该把这个文件的 `include( $file )` 带成污点。"""
        data = self._graph(tempfile.mkdtemp(), {
            "app/loader.php": (
                "<?php\n\n"
                "if ( isset( $_GET[ 'p' ] ) ) {\n    include( $file );\n}\n"),
            "other/sets_var.php": (
                "<?php\n\n"
                "$file = $_GET[ 'page' ];\n"
                "echo $file;\n"),
        })
        self.assertEqual([], [f for f in data["flows"]
                              if f["rule_id"] == "JZ-TRAVERSAL-001"
                              and f["file"] == "app/loader.php"],
                         "没有 include 关系就不该开池：%s"
                         % [(f["file"], f["line"]) for f in data["flows"]])

    def test_pool_is_php_only(self):
        """只有 PHP 有"被包含文件共享调用方符号表"这回事：JS 的动态 require、
        Python 的动态 import 都不该把另一个文件的变量接进来。

        这条锁的是**行为**（非 PHP 不开池）。它证明不了 `lang != "php"` 那两个 if 有独立牙齿——
        生产者取变量名用的是 PHP 专属的赋值正则，机制本身就是 PHP 专用的，
        光删 if 也开不了别语言的门（变异校准实测如此，已如实记进账本）。
        """
        data = self._graph(tempfile.mkdtemp(), {
            "srv/page.js": (
                'const { exec } = require("child_process");\n'
                'require("./lib/mod" + $name);\n\n'
                'function go() {\n    exec("ls " + $name);\n}\n'),
            "srv/lib/sets.js": (
                'const $name = req.params.n;\n'),
        })
        self.assertEqual([], [f for f in data["flows"]
                              if f["file"] == "srv/page.js"],
                         "JS 的动态 require 不该把另一个文件的变量接进来：%s"
                         % [(f["rule_id"], f["file"], f["line"]) for f in data["flows"]])
        # Python 那半句：importlib 动态导入同理不开池（这里连 include 关键字都没有）
        data2 = self._graph(tempfile.mkdtemp(), {
            "srv/main.py": (
                "import importlib\nimport os\n\n\n"
                "def run(mod):\n"
                "    importlib.import_module(mod)\n"
                "    return os.system('ls ' + mod)\n"),
            "srv/sets_var.py": (
                "from flask import request\n\n\nmod = request.args['m']\n"),
        })
        self.assertEqual([], [f for f in data2["flows"] if f["file"] == "srv/main.py"],
                         "Python 的动态 import 不该开池：%s"
                         % [(f["file"], f["line"]) for f in data2["flows"]])


    def test_static_include_does_not_open_the_pool(self):
        """写死路径的 `require_once 'src/low.php'` **不**开名字池——这是有意的保守。

        注意区分：`include( $file )` 这一行本身就是"变量路径的 include"，
        所以 fi 那种写法会开池；而这里整份文件只有静态 require，池的钥匙不在它手上。
        静态路径本该被精确解析成一条边（那才是正解，记在验收记录的待办里），
        用"同名变量共享"糊上去等于把判据借给了不该借的地方。
        """
        data = self._graph(tempfile.mkdtemp(), {
            "page/index.php": (
                "<?php\n\n"
                "require_once 'src/low.php';\n\n"
                "if ( isset( $_GET[ 'i' ] ) ) {\n    system( \"ls \" . $dir );\n}\n"),
            "page/src/low.php": (
                "<?php\n\n"
                "$dir = $_GET[ 'd' ];\n"),
        })
        self.assertEqual([], [f for f in data["flows"]
                              if f["rule_id"] == "JZ-CMDI-001"
                              and f["file"] == "page/index.php"],
                         "静态 require 不该靠名字池成流：%s"
                         % [(f["rule_id"], f["file"], f["line"]) for f in data["flows"]])


class TestReviewPacket(unittest.TestCase):
    """B5：把"交给审查者/子代理的东西"变成一个文件。

    之前是多轮对话里散着的描述——上下文一压缩就丢，而且**说没做≠做没做**。
    这个脚本只做一件事：把 diff + 任务原话 + 验收标准 + 验证命令 + 四态回执
    钉进一个文件。它**不执行**任何验证命令（第 4 条测试专门锁这一点）。
    """

    def _repo(self, tmp):
        def git(*a):
            r = subprocess.run(["git"] + list(a), cwd=tmp, timeout=60,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(r.returncode, 0, r.stdout.decode("utf-8", "replace"))
        git("init", "-q", "-b", "main")
        git("config", "user.email", "t@example.com")
        git("config", "user.name", "test")

    def _write(self, tmp, rel, text):
        path = os.path.join(tmp, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)

    def _packet(self, tmp, extra, name):
        out = os.path.join(tmp, "_pkt_%s.md" % name)
        r = run([os.path.join(SCRIPTS, "review_packet.py"), "--root", tmp,
                 "--out", out] + extra)
        self.assertEqual(r.returncode, 0, r.stdout)
        return out, r

    def test_packet_pins_diff_brief_acceptance_and_four_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._repo(tmp)
            self._write(tmp, "app.py", "def add(a, b):\n    return a + b\n")
            subprocess.run(["git", "add", "-A"], cwd=tmp, timeout=60, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, timeout=60,
                           stdout=subprocess.DEVNULL)
            self._write(tmp, "app.py", "def add(a, b):\n    return a - b   # 故意改坏\n")
            self._write(tmp, "accept.md", u"- 验收①：add(2,3) 必须是 5\n")
            out, _ = self._packet(tmp, [u"--brief", u"修一个加法符号搞反的 bug",
                                        "--acceptance-file", os.path.join(tmp, "accept.md"),
                                        u"--verify-cmd", u"pytest -q"], "make")
            text = io.open(out, encoding="utf-8").read()
            self.assertIn(u"app.py", text, u"diff 摘要要在")
            self.assertIn(u"修一个加法符号搞反的 bug", text, u"任务原话要逐字钉进去")
            self.assertIn(u"add(2,3) 必须是 5", text, u"验收标准要进去")
            self.assertIn(u"pytest -q", text, u"验证命令要列出来")
            for state in (u"DONE", u"CONCERNS", u"NEEDS_CONTEXT", u"BLOCKED"):
                self.assertIn(state, text, u"四态回执缺 %s" % state)

    def test_secrets_are_redacted_before_the_packet_hits_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._repo(tmp)
            self._write(tmp, "cfg.py", "TOKEN = \"old\"\n")
            subprocess.run(["git", "add", "-A"], cwd=tmp, timeout=60, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, timeout=60,
                           stdout=subprocess.DEVNULL)
            secret = "ghp_" + "A1" * 18
            self._write(tmp, "cfg.py", "TOKEN = \"%s\"\n" % secret)
            out, _ = self._packet(tmp, [], "sec")
            text = io.open(out, encoding="utf-8").read()
            self.assertNotIn(secret, text, u"真实令牌不能被抄进交付文件")
            self.assertIn(u"****", text, u"要看得出「这里脱敏过」，而不是整行被删")
            self.assertIn("TOKEN", text, u"键名要留着，审查者才知道改的是哪一行")

    def test_oversized_diff_is_truncated_and_says_so(self):
        with tempfile.TemporaryDirectory() as tmp:
            self._repo(tmp)
            self._write(tmp, "a.py", "x = 1\n")
            subprocess.run(["git", "add", "-A"], cwd=tmp, timeout=60, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, timeout=60,
                           stdout=subprocess.DEVNULL)
            self._write(tmp, "a.py", "".join("y%d = %d\n" % (i, i) for i in range(6000)))
            out, _ = self._packet(tmp, [u"--max-diff-kb", "4"], "big")
            text = io.open(out, encoding="utf-8").read()
            self.assertLess(len(text), 60000, u"超预算必须截断，不能把 60KB 灌进交付文件")
            self.assertIn(u"截断", text, u"截断要留痕，不能悄悄少给")

    def test_the_packet_never_runs_the_verify_commands(self):
        """锁的是"只落文件、不执行"。列命令给人看，执行由人/上游决定。"""
        with tempfile.TemporaryDirectory() as tmp:
            self._repo(tmp)
            self._write(tmp, "a.py", "x = 1\n")
            subprocess.run(["git", "add", "-A"], cwd=tmp, timeout=60, stdout=subprocess.DEVNULL)
            subprocess.run(["git", "commit", "-q", "-m", "base"], cwd=tmp, timeout=60,
                           stdout=subprocess.DEVNULL)
            self._write(tmp, "a.py", "x = 2\n")
            marker = os.path.join(tmp, "SHOULD_NOT_EXIST")
            out, _ = self._packet(tmp, [u"--verify-cmd", "touch %s" % marker], "run")
            with io.open(out, encoding="utf-8") as fh:
                packet = fh.read()
            self.assertIn("SHOULD_NOT_EXIST", packet)
            self.assertFalse(os.path.exists(marker), u"脚本执行了验证命令——它不该执行任何东西")


class TestCurrentState(unittest.TestCase):
    """E34（第 23 项）：「当前状态」的真源与载体必须对得上。

    起因——**本项目已经吃过两次亏，同一类**：
      * E32：同一个数（「同目录路过」多少条）在三份文档里分别写了
        **20 / 12 / "59 条里有 20 条"** ⇒ 互相矛盾，且都没说清是哪个口径。
      * E33：把「补发那批 64 个」和「现在的 65 个」写成了同一个数。

    根因：第 14 项的期望值校验**只扫代码块**。那是对的——代码块是"复制即跑"的契约，
    正文与表格里的历史数字是**当时真值**（交付报告 §3 的 "Ran 124 tests" 是 v0.36.1 当时的数），
    管到历史记录上就是误伤。**但代价是散文里的"当前状态"没人守**。

    本项的办法不是"把散文也当代码块扫"（那会误伤历史），而是：
      ① 真源 `evals/current-state.json` = 「当前状态」的唯一机器可读出处；
         其中 `static` 段**能当场推出来** ⇒ 真源自己不会腐烂（E7 的教训：尺子自己也会坏）；
      ② 文档里用 `<!-- current-state:begin/end -->` 圈出"这里说的是**当前**状态"；
      ③ 逐指标比对 ⇒ 手抄的数一旦与真源不同，当场红并点名是哪个文件的哪个指标。
    """

    HEAD = u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n正文一句。\n"
    CARRIER = (u"<!-- current-state:begin -->\n"
               u"本机：2 用例 OK ｜ DVWA 7 发现/结论 6\n"
               u"<!-- current-state:end -->\n")

    MEASURED_KEYS = (
        "dvwa_findings", "dvwa_conclusions", "dvwa_dropped", "dvwa_flows",
        "flask_findings", "flask_conclusions",
        "requests_findings", "requests_conclusions",
        "self_findings", "self_conclusions", "self_context_excluded",
        "coverage_hit", "coverage_total",
        "corpus_must_find", "corpus_must_not_find",
        "bench_ms_per_file",
    )

    def _source(self, static=None, measured=None, carriers=None):
        st = {"tests": 2, "must_find": 2, "must_not_find": 3,
              "rules_active": 2, "rules_disabled": 1}
        if static:
            st.update(static)
        ms = dict((k, 0) for k in self.MEASURED_KEYS)
        ms["dvwa_findings"] = 7
        ms["dvwa_conclusions"] = 6
        if measured:
            ms.update(measured)
        return {
            "schema": 1,
            "static": st,
            "reported": {},
            "measured": ms,
            "patterns": {
                "tests": {"rx": r"(\d+) 用例", "group": 1},
                "dvwa_findings": {"rx": r"DVWA (\d+) 发现", "group": 1},
            },
            "carriers": carriers or {"docs/state.md": {"which": "first",
                                                       "metrics": ["tests", "dvwa_findings"]}},
        }

    def _mini(self, tmp, source=None, carrier=None):
        """建一个最小技能目录：真源四件 + 一份带标记区的载体。"""
        sk = os.path.join(tmp, "sk")
        for d in ("docs", "tests", os.path.join("evals", "audit-fixtures"),
                  os.path.join("scripts", "audit-rules")):
            os.makedirs(os.path.join(sk, d))

        def put(rel, text):
            path = os.path.join(sk, rel.replace("/", os.sep))
            d = os.path.dirname(path)
            if d and not os.path.isdir(d):
                os.makedirs(d)
            with io.open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)

        put("SKILL.md", self.HEAD)
        # 真源①：2 个用例
        put("tests/test_x.py",
            u"import unittest\n\n\nclass T(unittest.TestCase):\n"
            u"    def test_a(self):\n        pass\n\n"
            u"    def test_b(self):\n        pass\n")
        # 真源②：语料 2 / 3
        put("evals/audit-fixtures/gen_corpus.py",
            u"MUST_FIND = [(\"a.py\", \"JZ-A-001\", \"x\"), (\"b.py\", \"JZ-B-001\", \"y\")]\n"
            u"MUST_NOT_FIND = [(\"s1.py\", \"JZ-A-001\"), (\"s2.py\", \"JZ-B-001\"),"
            u" (\"s3.py\", \"JZ-C-001\")]\n")
        # 真源③：规则 2 活跃 / 1 停用
        put("scripts/audit-rules/a.json",
            u"{\"rules\": [{\"id\": \"JZ-A-001\"}, {\"id\": \"JZ-B-001\"},"
            u" {\"id\": \"JZ-C-001\", \"enabled\": false}]}")
        put("evals/current-state.json",
            json.dumps(source or self._source(), ensure_ascii=False, indent=2))
        put("docs/state.md", carrier if carrier is not None else self.CARRIER)
        return sk

    def _validate(self, sk):
        return run([os.path.join(SCRIPTS, "validate_skill.py"), sk])

    def test_current_state_agrees_on_a_well_formed_repo(self):
        """绿：真源与载体一致 ⇒ 校验器通过（这一项不制造噪声）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp)
            r = self._validate(sk)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn(u"[当前状态]", r.stdout)

    def test_stale_source_must_be_flagged(self):
        """红：真源的 static 段与实物不符（真源自己过期了）⇒ 必须点名。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, source=self._source(static={"tests": 99}))
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"[当前状态]", r.stdout)
            self.assertIn(u"static.tests", r.stdout)

    def test_drifted_carrier_must_be_flagged(self):
        """红：载体里的数与真源不同（同一个数两处不同）⇒ 必须点名是哪个文件。"""
        with tempfile.TemporaryDirectory() as tmp:
            bad = (u"<!-- current-state:begin -->\n"
                   u"本机：9 用例 OK ｜ DVWA 7 发现/结论 6\n"
                   u"<!-- current-state:end -->\n")
            sk = self._mini(tmp, carrier=bad)
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"docs/state.md", r.stdout)
            self.assertIn(u"tests", r.stdout)

    def test_history_outside_the_marker_is_not_flagged(self):
        """绿（防误伤）：标记区**外**的历史数字不该被红。

        这条是本项能不能长期活着的关键：文档里到处是"当时真值"的历史数字
        （交付报告 §3 的 "Ran 124 tests" 是 v0.36.1 当时的数）⇒ 判据若扫全文，
        就会把历史也判成错 ⇒ 那是一条天天红的闸，等于没有闸。
        """
        with tempfile.TemporaryDirectory() as tmp:
            body = self.CARRIER + u"\n历史记录：当时是 124 用例、DVWA 3 发现。\n"
            sk = self._mini(tmp, carrier=body)
            r = self._validate(sk)
            self.assertEqual(r.returncode, 0, r.stdout)
            self.assertNotIn(u"[当前状态]", r.stdout)

    def test_missing_marker_region_must_be_flagged(self):
        """红：载体被列进来了却没圈出标记区 ⇒ 必须红（否则这一项静默失效）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, carrier=u"本机：2 用例 OK ｜ DVWA 7 发现/结论 6\n")
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"标记区", r.stdout)

    def test_only_the_designated_region_is_checked(self):
        """绿：文档里**旧版本**的标记区不该被红，只有真源指定的那一个受管。

        为什么需要这条：CHANGELOG 是**新版本在前**、验收记录是**新版本在后** ⇒
        "哪个标记区算当前"不能一律取最后一个 ⇒ 真源里显式写了 which。
        这条判据锁住的是：**只有被指定的那个区受管**（另一个区的数即使过期也不红）。
        """
        old_region = (u"<!-- current-state:begin -->\n"
                      u"本机：9 用例 OK ｜ DVWA 7 发现/结论 6\n"
                      u"<!-- current-state:end -->\n")
        new_region = (u"<!-- current-state:begin -->\n"
                      u"本机：2 用例 OK ｜ DVWA 7 发现/结论 6\n"
                      u"<!-- current-state:end -->\n")
        # 旧区在前（过期）、新区在后（正确）⇒ index=-1（最后一个区）⇒ 应通过
        last_carriers = {"docs/state.md": {"index": -1,
                                           "metrics": ["tests", "dvwa_findings"]}}
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, carrier=old_region + new_region,
                            source=self._source(carriers=last_carriers))
            r = self._validate(sk)
            self.assertEqual(r.returncode, 0, r.stdout)
        # 旧区在前（过期）、新区在后（也过期）⇒ which=last ⇒ 应红
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, carrier=old_region + old_region,
                            source=self._source(carriers=last_carriers))
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"[当前状态]", r.stdout)

    def test_real_repo_has_a_current_state_source(self):
        """绿：本仓库必须自带真源，且它能推得出来的那些数与实物一致。"""
        path = os.path.join(REPO, "evals", "current-state.json")
        self.assertTrue(os.path.isfile(path), u"本仓库没有 evals/current-state.json")
        with io.open(path, "r", encoding="utf-8") as f:
            src = json.load(f)
        for k in ("static", "measured", "patterns", "carriers"):
            self.assertIn(k, src, u"真源缺 %s 段" % k)
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertNotIn(u"[当前状态]", r.stdout,
                         u"本仓库的「当前状态」与真源对不上：%s" % r.stdout)


class TestMicroTestClaims(unittest.TestCase):
    """E35（第 24 项）：微测台账的**状态格必须与实测数据一致**。

    为什么要有这一项：本项目的纪律层条款此前只有"文本 + 结构锁"，行为收益**未测**；
    E35 真跑了一轮双臂对照，结论是**基线未红** ⇒ **不得对外声称行为收益**。
    ⇒ 既然"不许声称"是要守的纪律，它就该有机器判据，而不是靠人记得。
    """

    GOOD = (u"# 规则微测（micro-test）规程\n\n"
            u"| 规则/条款 | 场景 | 状态 | 备注 |\n"
            u"|---|---|---|---|\n"
            u"| **铁律范围句**（同义改写与暗示同样违规） | 未跑 | **待测** | 只有文本，没有双臂数据 |\n"
            u"| **必验证门函数**（五步）＋**铁律** | E35 红测 MT-A/B | **基线未红** | "
            u"E35 实测 **A 0/5 失败（0%） vs B 0/5 失败（0%）**，差 **0 个百分点** |\n"
            u"| **子代理四态回执** | 未跑 | **待测** | 需要能派发子代理的环境 |\n")

    def _mini(self, tmp, md):
        sk = os.path.join(tmp, "sk")
        os.makedirs(os.path.join(sk, "evals"))
        with io.open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8") as f:
            f.write("---\nname: sk\ndescription: 测试\n---\n正文\n")
        with io.open(os.path.join(sk, "evals", "micro-tests.md"), "w", encoding="utf-8") as f:
            f.write(md)
        return sk

    def test_verdict_must_match_the_measured_numbers(self):
        """红：状态格写「有效」而实测差 0 个百分点 ⇒ 必须红（改结论不改数据当场红）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, self.GOOD.replace(u"**基线未红**", u"**有效**"))
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"[微测声称]", r.stdout)
            self.assertIn(u"个百分点", r.stdout)

    def test_verdict_must_be_a_legal_one(self):
        """红：状态格写了规程之外的词（"已验证"）⇒ 必须红。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, self.GOOD.replace(u"**待测**", u"**已验证**"))
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"[微测声称]", r.stdout)

    def test_verdict_without_data_must_be_flagged(self):
        """红：写了判定却解析不出实测数据 ⇒ 必须红（没有数据就不许写结论）。"""
        md = self.GOOD.replace(u"E35 实测 **A 0/5 失败（0%） vs B 0/5 失败（0%）**，差 **0 个百分点**",
                                u"实测过，感觉有效")
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, md)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"[微测声称]", r.stdout)

    def test_real_repo_micro_test_claims_are_consistent(self):
        """绿：本仓库的微测台账状态格与实测数据一致。"""
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertNotIn(u"[微测声称]", r.stdout,
                         u"本仓库的微测声称与数据对不上：%s" % r.stdout)


class TestReadmeCounts(unittest.TestCase):
    """E36：README（**中英两个门面**）声明的计数/预算必须与实物一致。

    为什么单独拎出来：这条判据原先只查中文 README，而**英文 README 停在 v0.3x 遗物状态**
    （4 个脚本 / 222 行 / 373 字符）——它是英文读者与 skills.sh 生态看到的那一面
    ⇒ 门面的另一半没人守。

    还有一条更要紧的：**入口行数的真源必须是"正文行数"**（500 上限约束的是正文），
    旧实现拿文件总行数当真源 ⇒ README 只好写总行数 ⇒ **一道在逼人说假话的锁**
    （说真话反而被判错）。本类里 `test_body_line_count_is_the_truth` 专门钉这一条。
    """

    MINI_README_ZH = (
        u"# sk\n\n"
        u"- 1 本分册、1 个填空即用模板、1 个纯标准库脚本\n"
        u"- SKILL.md 正文 3 行，description 1 字符（entry 合计 5）\n")
    MINI_README_EN = (
        u"# sk\n\n"
        u"- 1 booklets, 1 fill-in templates, 1 stdlib-only scripts\n"
        u"- SKILL.md body is 3 lines, description is 1 chars (manifest entry 5 chars)\n")

    def _mini(self, tmp, readme_zh=None, readme_en=None):
        sk = os.path.join(tmp, "sk")
        for d in ("references", "templates", "scripts", "evals"):
            os.makedirs(os.path.join(sk, d))
        with io.open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(u"---\nname: sk\ndescription: d\nwhen_to_use: w\n---\n"
                    u"正文第一行\n正文第二行\n正文第三行\n")
        with io.open(os.path.join(sk, "references", "a.md"), "w", encoding="utf-8") as f:
            f.write(u"# a\n")
        with io.open(os.path.join(sk, "templates", "a.md"), "w", encoding="utf-8") as f:
            f.write(u"# a\n")
        with io.open(os.path.join(sk, "scripts", "a.py"), "w", encoding="utf-8") as f:
            f.write(u"pass\n")
        with io.open(os.path.join(sk, "README.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(readme_zh if readme_zh is not None else self.MINI_README_ZH)
        with io.open(os.path.join(sk, "README.en.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(readme_en if readme_en is not None else self.MINI_README_EN)
        return sk

    def _validate(self, sk):
        return run([os.path.join(SCRIPTS, "validate_skill.py"), sk])

    def test_both_front_doors_are_checked_on_self(self):
        """绿：本仓库的**两个门面**都被核到，且都与实物一致。

        ⚠️ 断言必须包含**退出码**：E36 的校准首轮就发现，若只查 info 字符串，
        那么"真源被改坏"这种变异**照样绿**（info 照发，只是多了一条错误）
        ⇒ 判据要同时要求 `validate` **没有错误**。
        """
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn(u"README 计数与实物一致", r.stdout)
        self.assertIn(u"已核 2 个门面", r.stdout,
                      u"英文门面没被核到：%s" % r.stdout)
        self.assertIn(u"SKILL.md 正文 201 行", r.stdout)

    def test_wrong_english_count_must_be_flagged(self):
        """红：英文门面的计数写错 ⇒ 必须红（此前这道闸只查中文门面）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, readme_en=self.MINI_README_EN.replace(
                u"1 stdlib-only scripts", u"4 stdlib-only scripts"))
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"scripts=4", r.stdout)

    def test_body_line_count_is_the_truth(self):
        """红/绿：**正文行数**才是入口行数的真数 —— 说真话（3 行）不该被红，说总行数（6 行）必须被红。

        ⚠️ 这条是 E36 修掉的那个"逼人说假话的锁"的守卫：
        旧实现拿**文件总行数**当真源 ⇒ 文档只好写总行数 ⇒ 而 500 上限约束的是正文。
        """
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp)
            r = self._validate(sk)
            self.assertNotIn(u"entry_lines", r.stdout,
                             u"说真话（正文 3 行）被判错了：%s" % r.stdout)
        with tempfile.TemporaryDirectory() as tmp:
            bad = self.MINI_README_ZH.replace(u"SKILL.md 正文 3 行", u"SKILL.md 正文 6 行")
            sk = self._mini(tmp, readme_zh=bad)
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"entry_lines", r.stdout)

    def test_wrong_description_chars_must_be_flagged(self):
        """红：门面的 description / 清单 entry 字符数写错 ⇒ 必须红（此前完全没人管）。"""
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, readme_en=self.MINI_README_EN.replace(
                u"description is 1 chars", u"description is 373 chars"))
            r = self._validate(sk)
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"desc_chars=373", r.stdout)


class TestChangelogVersions(unittest.TestCase):
    """E36（第 25 项）：CHANGELOG 的版本条目**不得重复**、必须**按降序**。

    起因：E35 的台账脚本**跑了两遍** ⇒ CHANGELOG 里留下了**两份一模一样的 v0.69.0 条目**
    ⇒ 而此前**没有任何一道闸能发现它**（日期核对只看日期、"版本与 CHANGELOG 一致"只看最新那个）
    ⇒ 也就是说：**台账自己可以在无人察觉的情况下被写坏**。
    """

    def _mini(self, tmp, cl):
        sk = os.path.join(tmp, "sk")
        os.makedirs(sk)
        with io.open(os.path.join(sk, "SKILL.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(u"---\nname: sk\ndescription: 测试\nmetadata:\n  version: 0.0.1\n---\n正文一句。\n")
        with io.open(os.path.join(sk, "CHANGELOG.md"), "w", encoding="utf-8", newline="\n") as f:
            f.write(cl)
        return sk

    def test_duplicate_changelog_entry_must_be_flagged(self):
        """红：同一版本出现两次 ⇒ 必须红（台账脚本跑两遍就会留下这种）。"""
        cl = (u"# 更新日志\n\n## [0.2.0] - 2026-01-02\n\n第二条。\n\n"
              u"## [0.1.0] - 2026-01-01\n\n第一条。\n\n"
              u"## [0.2.0] - 2026-01-02\n\n第二条。\n")
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, cl)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"份 v0.2.0 条目", r.stdout)

    def test_out_of_order_changelog_entries_must_be_flagged(self):
        """红：版本条目不是降序（新版本在前）⇒ 必须红。"""
        cl = (u"# 更新日志\n\n## [0.1.0] - 2026-01-01\n\n旧的在前。\n\n"
              u"## [0.2.0] - 2026-01-02\n\n新的在后。\n")
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, cl)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn(u"降序", r.stdout)

    def test_duplicate_sections_in_other_ledgers_must_be_flagged(self):
        """红：**验收记录**与**交接文档规划表**里同一版本出现两次 ⇒ 也必须红。

        E35/E36 的台账脚本各跑过两遍 ⇒ 这三处台账都被写坏了，而**此前无人能发现**。
        """
        cl = u"# 更新日志\n\n## [0.2.0] - 2026-01-02\n\n条目。\n"
        acc = u"## v0.2.0（X）\n\n内容。\n\n## v0.2.0（X）\n\n内容。\n"
        hand = (u"## 11. 规划\n\n| 轮 | 版本 |\n|---|---|\n"
                u"| **E36** ✅ | v0.2.0 |\n| **E36** ✅ | v0.2.0 |\n")
        with tempfile.TemporaryDirectory() as tmp:
            sk = self._mini(tmp, cl)
            os.makedirs(os.path.join(sk, "evals"))
            with io.open(os.path.join(sk, "evals", "audit-acceptance.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(acc)
            os.makedirs(os.path.join(sk, "docs", "jiangzuo"))
            with io.open(os.path.join(sk, "docs", "jiangzuo", "handover.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(hand)
            r = run([os.path.join(SCRIPTS, "validate_skill.py"), sk])
            self.assertNotEqual(r.returncode, 0, r.stdout)
            # ⚠️ 断言要卡在**错误原文**上，不能卡"出现验收记录这几个字"——
            #    那句话在 info 行里也有（"（验收记录与交接文档同查）"）⇒ 判据会**恒绿**。
            self.assertIn(u"有 **2 份 v0.2.0 小节**", r.stdout)
            self.assertIn(u"有 **2 行 v0.2.0**", r.stdout)

    def test_real_repo_changelog_is_unique_and_ordered(self):
        """绿：本仓库的 CHANGELOG 无重复且降序。"""
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertIn(u"无重复且按降序", r.stdout)


class TestReleaseIdentity(unittest.TestCase):
    """E37：发布产物的**身份**必须对得上。

    背景：本项目此前核过「68 个 tag / 68 个 Release 一一对应、零缺口」——**全绿**。
    但那次只数了**名字与数量**。E37 查出远端 `v0.51.0` 实际指向 `d5b88e1a`
    （那是 **v0.66.0 的补记笔**），而不是 v0.51.0 的代码 ⇒ 谁 checkout v0.51.0
    拿到的都是别的版本 ⇒ 而那句话当时**是真的**。
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, SCRIPTS)
        import release_identity
        import release_notes
        cls.ri = importlib.reload(release_identity)
        cls.rn = importlib.reload(release_notes)

    def _truth(self):
        p = os.path.join(REPO, "evals", "release-identity.json")
        with io.open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_ls_remote_prefers_peeled_commit(self):
        """绿：annotated tag 要取 `^{}` 那行（commit），**不是**第一行（tag 对象）。

        E37 第一版就是漏了这一步 ⇒ 67 个 tag 全被误报成「指错了 commit」，
        而真的错的只有 1 个 ⇒ 这条判据必须钉住。
        """
        out = ("aaa111\trefs/tags/v0.51.0\n"
               "bbb222\trefs/tags/v0.51.0^{}\n"
               "ccc333\trefs/tags/v0.60.0\n")
        got = self.ri.parse_ls_remote(out)
        self.assertEqual(got.get("v0.51.0"), "bbb222")
        self.assertEqual(got.get("v0.60.0"), "ccc333")

    def test_publish_blockers_flags_missing_remote_tag(self):
        """红：远端**缺** tag ⇒ 必须拦住（否则 GitHub 会在 main HEAD 上造同名 tag）。"""
        blocked = self.rn.publish_blockers({"v0.1.0": "a" * 40},
                                           {"v0.1.0": "a" * 40, "v0.2.0": "b" * 40})
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn("v0.2.0", blocked[0])
        self.assertIn(u"远端**没有**这个 tag", blocked[0])

    def test_publish_blockers_flags_mismatched_commit(self):
        """红：远端 tag 指向**别的** commit ⇒ 必须拦住。"""
        blocked = self.rn.publish_blockers({"v0.1.0": "c" * 40}, {"v0.1.0": "a" * 40})
        self.assertEqual(len(blocked), 1, blocked)
        self.assertIn(u"远端指向", blocked[0])

    def test_publish_blockers_accepts_matching(self):
        """绿：完全一致 ⇒ 没有拦路项（**防误伤**的配对判据）。"""
        blocked = self.rn.publish_blockers({"v0.1.0": "a" * 40}, {"v0.1.0": "a" * 40})
        self.assertEqual(blocked, [])

    def test_truth_commit_mismatch_must_be_flagged(self):
        """红：真源里的 commit 与本地实物对不上 ⇒ 必须红。"""
        data = self._truth()
        first = sorted(data["tags"])[0]
        data["tags"][first]["commit"] = "0" * 40
        errs = []
        ok = self.ri.check_local(errs.append, lambda m: None, REPO, data)
        self.assertFalse(ok)
        self.assertTrue(any(u"真源与实物对不上" in e for e in errs), errs)

    def test_truth_owner_mismatch_must_be_flagged(self):
        """红：真源里某条目的 owner 与它的版本号不符 ⇒ 必须红。"""
        data = self._truth()
        first = sorted(data["tags"])[0]
        data["tags"][first]["owner"] = "9.9.9"
        errs = []
        ok = self.ri.check_local(errs.append, lambda m: None, REPO, data)
        self.assertFalse(ok)
        self.assertTrue(any(u"owner" in e for e in errs), errs)

    def test_tag_pointing_to_wrong_version_must_be_flagged(self):
        """红：**端到端** —— tag 指向别的版本的 commit ⇒ 判据必须红。

        这是「远端 v0.51.0 指向 v0.66.0 补记笔」的同一种错，在临时仓库里复现。
        """
        with tempfile.TemporaryDirectory() as tmp:
            def g(*a):
                return subprocess.run(["git", "-C", tmp] + list(a),
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                      encoding="utf-8", errors="replace").stdout
            g("init", "-q")
            g("config", "user.email", "t@example.com")
            g("config", "user.name", "t")
            with io.open(os.path.join(tmp, "a.txt"), "w", encoding="utf-8") as f:
                f.write("x")
            g("add", "a.txt")
            g("commit", "-q", "-m", "fix: v0.2.0 E1——这一笔属于 v0.2.0")
            g("tag", "v0.1.0")       # tag 名是 v0.1.0，指向的却是 v0.2.0 的 commit
            data = self.ri.derive(tmp)
            self.ri.write_truth(data, tmp)
            errs = []
            ok = self.ri.check_local(errs.append, lambda m: None, tmp)
            self.assertFalse(ok, "tag 指错了版本却判绿了")
            self.assertTrue(any(u"tag 指错了版本" in e for e in errs), errs)

    def test_real_repo_release_identity_passes(self):
        """绿：本仓库的发布身份对得上（**正例**：防止把判据做成恒红）。"""
        errs = []
        infos = []
        ok = self.ri.check_local(errs.append, infos.append, REPO)
        self.assertTrue(ok, errs)
        self.assertTrue(any(u"发布产物的身份" in i for i in infos), infos)

    def test_validate_reports_release_identity(self):
        """绿：`validate` 报告里**必须有**第 26 项。

        为什么要有这条：它给「把第 26 项整项摘掉」这种变异**一个会红的对象**——
        没有它的话，把整项从调用列表里删掉，本仓库仍然全绿 ⇒ 变异校准抓不到。
        """
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertIn(u"发布产物的身份", r.stdout)

    def test_matching_refs_parse(self):
        """绿：API 的 `matching-refs` 响应能解析成 {tag: (sha, type)}。

        为什么要有这条：E37 实测那天 `github.com:443` 在 **TLS 层**被选择性阻断
        （TCP 可连、`ls-remote` 21 秒超时），而 `api.github.com` **完全正常**
        ⇒ 核远端 tag 必须有**API 回退通道**，否则发布流程会被网络运气卡住。
        """
        entries = [
            {"ref": "refs/tags/v0.71.0",
             "object": {"sha": "9ba47406", "type": "tag"}},
            {"ref": "refs/tags/v0.20.0",
             "object": {"sha": "f267f803", "type": "commit"}},
            {"ref": "refs/heads/main",
             "object": {"sha": "abcdef01", "type": "commit"}},
        ]
        got = self.ri.parse_matching_refs(entries)
        self.assertEqual(got.get("v0.71.0"), ("9ba47406", "tag"))
        self.assertEqual(got.get("v0.20.0"), ("f267f803", "commit"))
        self.assertNotIn("main", got)      # 只认 refs/tags/ 前缀

    def test_api_channel_peels_annotated_tag(self):
        """绿：API 通道把 annotated tag **peel 到 commit**。

        轻量 tag 的 object 直接就是 commit；annotated tag 的 object 是 tag 对象
        ⇒ 必须再 peel 一层，否则拿到的不是 commit（比对就会全错）。
        """
        self.assertEqual(self.ri.peel_object(
            {"object": {"type": "commit", "sha": "d5da9f39"}}), "d5da9f39")
        self.assertIsNone(self.ri.peel_object(
            {"object": {"type": "tag", "sha": "60790e32"}}))
        self.assertIsNone(self.ri.peel_object({}))


class TestMdTableColumns(unittest.TestCase):
    """E38：**表内每行的列数必须与表头一致**。

    为什么要有这条：列数错了，Markdown 会把多出来的列**丢弃**、把少掉的列**补空**
    ⇒ 读者看到的字段顺序与表头对不上，而**人眼扫一排表格根本看不出**（一格宽一格窄而已）。
    E38 实测：本仓 58 个 .md 里有 **14 行**列数与表头不符（含**我自己上轮新加的那一行**），
    而此前**没有任何判据**会发现。

    ⚠️ 判据必须按 **GFM 规则**数列（`\\|` 是转义、不算分隔符）——
    否则会把 `ls scripts/*.py \\| wc -l` 这种**合法**写法误判成多一列。
    """

    def _check(self, md_text):
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        validate_skill = importlib.reload(validate_skill)
        with tempfile.TemporaryDirectory() as tmp:
            with io.open(os.path.join(tmp, "t.md"), "w", encoding="utf-8", newline="\n") as f:
                f.write(md_text)
            del validate_skill.ERRORS[:]
            del validate_skill.INFOS[:]
            validate_skill.check_md_tables(tmp)
            return list(validate_skill.ERRORS), list(validate_skill.INFOS)

    def test_column_count_mismatch_must_be_flagged(self):
        """红：少一格 ⇒ 必须报（少掉的列会被 Markdown 补空 ⇒ 字段顺序与表头对不上）。"""
        md = (u"| a | b | c |\n"
              u"|---|---|---|\n"
              u"| 1 | 2 |\n")
        errs, _infos = self._check(md)
        self.assertTrue(errs, "少一格却没被报出来")
        self.assertTrue(any(u"只有 **2 个单元格**" in e for e in errs), errs)
        self.assertTrue(any(u"表头有 3 个" in e for e in errs), errs)

    def test_extra_cell_must_be_flagged(self):
        """红：多一格 ⇒ 必须报（多半是内容里的 `|` 没转义）。"""
        md = (u"| a | b | c |\n"
              u"|---|---|---|\n"
              u"| 1 | 2 | 3 | 4 |\n")
        errs, _infos = self._check(md)
        self.assertTrue(errs, "多一格却没被报出来")
        self.assertTrue(any(u"**4 个单元格**" in e for e in errs), errs)

    def test_escaped_pipe_must_not_be_flagged(self):
        """绿：`\\|` 是**转义**（GFM 里竖线要转义）⇒ 不算分隔符 ⇒ 合法写法不报。"""
        md = (u"| a | b |\n"
              u"|---|---|\n"
              u"| `ls scripts/*.py \\| wc -l` | 14 |\n")
        errs, _infos = self._check(md)
        self.assertEqual([e for e in errs if u"单元格" in e], [],
                         "转义竖线被误判成多一列了")

    def test_orphan_pipe_row_is_not_a_table(self):
        """绿：**孤立**的竖线块（**没有表头 + 分隔行**）**不是表** ⇒ 不报。

        GFM 只有「表头行 + 分隔行」才构成表格 ⇒ 判它就是误伤。

        ⚠️ 这个用例**故意用 3 行、且其中一行列数不同** ——
        否则「把任何竖线块都当表」那种变异对它**毫无影响**（1 行的孤立块会被
        「块长 < 3」那条保护挡掉 ⇒ 变异前后都是绿 ⇒ 校准会报 GREEN＝锁无效）。
        E38 实测：**校准用例挑错了对象，判据本身没问题** ⇒ 这才是"校准能指出
        我自己选错"的样子。
        """
        md = (u"正文里的一行：\n"
              u"\n"
              u"| a | b |\n"
              u"| c | d | e |\n"
              u"| f | g |\n"
              u"\n"
              u"后面还有正文。\n")
        errs, _infos = self._check(md)
        self.assertEqual([e for e in errs if u"单元格" in e], [],
                         "孤立的竖线块被当成表了")

    def test_code_fenced_table_is_ignored(self):
        """绿：代码块里的表格行**不是表格** ⇒ 不报。"""
        md = (u"```\n"
              u"| a | b |\n"
              u"|---|---|\n"
              u"| 1 | 2 | 3 |\n"
              u"```\n")
        errs, _infos = self._check(md)
        self.assertEqual([e for e in errs if u"单元格" in e], [],
                         "代码块里的表格被当成真表格了")


class TestReleaseConsistency(unittest.TestCase):
    """E39：**远端**发布产物自洽核验（tag ↔ GitHub Release）—— CI 上从没有人在核。

    为什么要有这个（E39 复核）：本仓库有两条"发布产物"的一致性检查，
      · `validate` 第 26 项（E37）核**本地 git 对象**里每个 tag 指向的 commit ⇒ 碰不到远端；
      · `release_identity.py --remote`（E37）核远端三边 ⇒ 准，但**要 token、要手动跑**。
    ⇒ **少发一个 Release、tag 与 Release 对不上 ⇒ CI 上没人会发现。**

    ⚠️ 这个核验的**三态退出码**是它的要害：
      0 = 核过了且一致 ｜ 1 = 核过了且**不一致**（真问题，必红）｜
      2 = **没核成**（限流 / 网络）⇒ **绝不能当成 0**。
    ⇒ 「没核成」若被当成「通过」，就是一把**恒绿的空锁**——比没锁更坏。
    """

    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, SCRIPTS)
        import release_consistency
        cls.rc = importlib.reload(release_consistency)

    def _patch(self, rel_names, tag_names, local=None):
        """把脚本的两个远端读取函数换成假的（不联网）。"""
        self.rc.remote_release_names = lambda: (set(rel_names), 0, 0, "60")
        self.rc.remote_tag_names = lambda: (set(tag_names), "59")
        self.rc.local_tag_names = lambda: set(local or [])

    def test_mismatch_must_exit_nonzero(self):
        """红：Release 与 tag 对不上 ⇒ 必须**非零**退出（真问题必红）。"""
        self._patch(rel_names=["v0.1.0", "v0.2.0"], tag_names=["v0.1.0"], local=["v0.1.0"])
        code, out = self.rc.check()
        self.assertEqual(code, self.rc.EXIT_MISMATCH, out)
        self.assertTrue(any(u"没有对应" in o for o in out), out)

    def test_not_checked_must_not_be_reported_as_ok(self):
        """红：**没核成**（限流/网络）⇒ 退出码 **2**，**绝不是 0**。

        这是本类最要紧的一条：**「没核成」若被当成「通过」，就是恒绿的空锁**。
        """
        def boom():
            raise IOError(u"模拟：连接被重置")
        self.rc.remote_release_names = boom
        self.rc.remote_tag_names = boom
        code, out = self.rc.check()
        self.assertEqual(code, self.rc.EXIT_NOT_CHECKED, out)
        self.assertNotEqual(code, self.rc.EXIT_OK, "没核成被当成了通过")
        self.assertTrue(any(u"没核成" in o for o in out), out)

    def test_consistent_must_exit_zero(self):
        """绿：一致 ⇒ 退出码 0。"""
        self._patch(rel_names=["v0.1.0", "v0.2.0"], tag_names=["v0.1.0", "v0.2.0"],
                    local=["v0.1.0", "v0.2.0"])
        code, out = self.rc.check()
        self.assertEqual(code, self.rc.EXIT_OK, out)

    def test_workflow_exists_and_handles_not_checked(self):
        """绿：CI 作业存在，且**处理了「没核成」那一态**（不许静默变绿）。

        为什么要有这条：脚本自己会返回 2，但**作业怎么处置 2** 是另一件事 ⇒
        若作业把 2 当成功，绿灯就意味着"什么都没核"⇒ **恒绿的空锁**。
        """
        p = os.path.join(REPO, ".github", "workflows", "release-consistency.yml")
        self.assertTrue(os.path.isfile(p), "缺 %s" % p)
        with io.open(p, "r", encoding="utf-8") as f:
            txt = f.read()
        self.assertIn("release_consistency.py", txt)
        self.assertIn("exit_code", txt)
        # 「没核成」（非 0 且非 1）必须有独立分支，且要留痕
        self.assertIn(u"没核成", txt)
        self.assertIn("::notice::", txt)

    def test_checker_is_shipped_and_dependency_free(self):
        """绿：核验器**随技能分发**且**零依赖**（它要能被 CI 直接跑）。"""
        p = os.path.join(SCRIPTS, "release_consistency.py")
        self.assertTrue(os.path.isfile(p))
        with io.open(p, "r", encoding="utf-8") as f:
            src = f.read()
        for bad in ("import requests", "import yaml", "import httpx", "from pip"):
            self.assertNotIn(bad, src)


class TestLedgerIntegrity(unittest.TestCase):
    """E40：**进化账本自身不许被写坏** —— 行序不得回退、不得有完全相同的两行。

    为什么（E39 复核出来的洞）：E37 那轮把 E37 的行**插在了 E36 之前**（台账是时间倒序）
    ⇒ 错了整整一行，E38 才发现并手工换回来 ⇒ 而**没有任何判据**会报。
    E40 复核又挖出**更早的一批**：E9 的两行、E11 的四行被拆散插到了 E12/E13/E17 后面
    ⇒ 轮次序列 `… E9 E10 E12 E13 E11 E11 E9 E17 E11 E11 …` ⇒ **3 处回退**。

    ⚠️ 为什么它要**单独**写：进化账本的行格式是 `| 日期 | E37 …`（轮次在**第二格**），
    与第 25 项原有的查重正则（认 `| **E37** ✅ | v0.70.0 |`）**完全不同** ⇒ 此前**完全不在查重范围内**。
    """

    HEADER = (u"| 日期 | 证据 | 归因 | 假设 | 变异 | 验证 | 行数收支 | 结论 |\n"
              u"|---|---|---|---|---|---|---|---|\n")

    def _rows(self, body):
        return self.HEADER + body

    def _check(self, body, acc_text=None):
        """把一段台账行放进临时目录，跑第 25 项，返回错误列表。"""
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        validate_skill = importlib.reload(validate_skill)
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "docs", "jiangzuo")
            os.makedirs(d)
            with io.open(os.path.join(d, "evolution.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(u"# 台账\n\n" + self._rows(body))
            if acc_text is not None:
                e = os.path.join(tmp, "evals")
                os.makedirs(e)
                with io.open(os.path.join(e, "audit-acceptance.md"), "w",
                             encoding="utf-8", newline="\n") as f:
                    f.write(acc_text)
            del validate_skill.ERRORS[:]
            del validate_skill.INFOS[:]
            validate_skill.check_ledger_versions(tmp, u"")
            return list(validate_skill.ERRORS)

    def test_ledger_round_order_must_be_flagged(self):
        """红：轮次**回退**（E12 排在 E9 之前）⇒ 必须报。"""
        body = (u"| 2026-10-20 | E12 留下的缺口 | 归因 | 假设 | 变异 | 验证 | +1 / −0 | KEEP… |\n"
                u"| 2026-10-20 | E9 留下的缺口 | 归因 | 假设 | 变异 | 验证 | +1 / −0 | KEEP… |\n")
        errs = self._check(body)
        self.assertTrue(errs, "轮次回退却没被报出来")
        self.assertTrue(any(u"反而排在" in e for e in errs), errs)

    def test_ledger_same_round_rows_are_allowed(self):
        """绿：**同一轮的多行是合法的**（一轮可能有多个变异）⇒ 不得误报。"""
        body = (u"| 2026-10-20 | E9 留下的缺口甲 | 归因 | 假设 | 变异 | 验证 | +1 / −0 | KEEP… |\n"
                u"| 2026-10-20 | E9 留下的缺口乙 | 归因 | 假设 | 变异 | 验证 | +2 / −0 | KEEP… |\n")
        errs = self._check(body)
        self.assertEqual([e for e in errs if u"反而排在" in e], [],
                         "同一轮的两行被误判成逆序了")

    def test_ledger_duplicate_rows_must_be_flagged(self):
        """红：同一张表里**两行完全相同** ⇒ 必须报（台账脚本跑两遍的产物）。"""
        row = u"| 2026-10-20 | E9 留下的缺口 | 归因 | 假设 | 变异 | 验证 | +1 / −0 | KEEP… |\n"
        errs = self._check(row + row)
        self.assertTrue(errs, "完全相同的两行却没被报出来")
        self.assertTrue(any(u"完全相同" in e for e in errs), errs)

    def test_real_repo_ledger_is_ordered(self):
        """绿：本仓库的进化账本**行序不倒退、无重复行**。"""
        sys.path.insert(0, SCRIPTS)
        import validate_skill
        validate_skill = importlib.reload(validate_skill)
        del validate_skill.ERRORS[:]
        del validate_skill.INFOS[:]
        validate_skill.check_ledger_versions(REPO, u"")
        bad = [e for e in validate_skill.ERRORS if u"进化账本" in e]
        self.assertEqual(bad, [], "本仓库的进化账本有行序/重复问题：%s" % bad)

    def test_acceptance_sections_must_be_ascending(self):
        """红：验收记录的小节**倒序**（新版本排到旧版本前面）⇒ 必须报。

        E39 把 v0.73.0 小节插到了 v0.72.0 **之前**；E40 自己第一版也把 v0.74.0
        插到了 v0.73.0 之前 ⇒ 两处都因为"只看最后一个区块"的载体对账而**绿灯**。
        """
        acc = (u"## v0.73.0（E39）—— 某轮\n\n正文\n\n"
               u"## v0.72.0（E38）—— 某轮\n\n正文\n")
        errs = self._check(u"", acc_text=acc)
        self.assertTrue(errs, "验收记录小节倒序却没被报出来")
        self.assertTrue(any(u"不得回退" in e for e in errs), errs)

    def test_acceptance_sections_ascending_is_ok(self):
        """绿：验收记录的小节**升序**（新版本在后）⇒ 不得误报。"""
        acc = (u"## v0.72.0（E38）—— 某轮\n\n正文\n\n"
               u"## v0.73.0（E39）—— 某轮\n\n正文\n")
        errs = self._check(u"", acc_text=acc)
        self.assertEqual([e for e in errs if u"不得回退" in e], [],
                         "升序被误判成倒序了")


class TestCarrierBlockIntegrity(unittest.TestCase):
    """E40：**每个** current-state 标记区都必须对账**它自己那一版**的快照。

    为什么（E39 的教训）：E39 把验收记录里 **v0.72.0 的区块改写成了 v0.73.0 的数**
    （CHANGELOG 里 v0.72.0 的区块也被改了一半）⇒ 而载体对账当时**每个载体只查一个区块**
    ⇒ 那个被改的区块**恰好**被改成了"当前这一版"的数 ⇒ **对账跟着腐化一起漂 ⇒ 绿灯**
    ⇒ 一处假记录静悄悄地留在台账里，**没人能发现**。
    ⇒ E40 起：载体写 `version_rx` ⇒ **每个**区块都自动对账它自己那一版的快照
    （区块与版本的对应是**从文件里推出来的** ⇒ 人手写不错）。
    """

    PATTERNS = {
        "tests": {"rx": r"(\d+) 用例", "group": 1},
        "validate_infos": {"rx": r"validate \*\*(\d+)\*\* 信息", "group": 1},
        "mutation_cases": {"rx": r"变异校准 \*\*(\d+)/\d+ 全红", "group": 1},
        "bench_ms_per_file": {"rx": r"BENCH-OK ([\d.]+) ms/文件", "group": 1},
    }
    METRICS = ["tests", "validate_infos", "mutation_cases", "bench_ms_per_file"]

    def _block(self, tests, infos, cases, bench):
        return (u"<!-- current-state:begin -->\n"
                u"本机闸门：%d 用例 OK ｜ validate **%d** 信息/0 警告/0 错误 ｜ "
                u"变异校准 **%d/%d 全红** ｜ 靶场 ACCEPT-OK（25/25 检出 & 0/19 安全样本）｜\n"
                u"三仓：DVWA **58 发现/结论 58**、flask 13/1、requests 4/0、"
                u"DVWA 覆盖 **14/19** ｜ 本仓库自扫 **8 发现/结论 0/另计 8** ｜ "
                u"BENCH-OK %s ms/文件\n"
                u"<!-- current-state:end -->\n" % (tests, infos, cases, cases, bench))

    def _run(self, ledger, history):
        sys.path.insert(0, SCRIPTS)
        import current_state
        current_state = importlib.reload(current_state)
        errs = []
        infos = []
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "evals"))
            with io.open(os.path.join(tmp, "evals", "audit-acceptance.md"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(ledger)
            src = {
                "schema": 1,
                "static": {},
                "reported": {},
                "measured": {},
                "patterns": self.PATTERNS,
                "carriers": {
                    "evals/audit-acceptance.md": {
                        "version_rx": r"^##\s*v(\d+\.\d+\.\d+)",
                        "metrics": self.METRICS,
                    },
                },
                "history": history,
            }
            with io.open(os.path.join(tmp, "evals", "current-state.json"), "w",
                         encoding="utf-8", newline="\n") as f:
                f.write(json.dumps(src, ensure_ascii=False, indent=2,
                                   sort_keys=True) + "\n")
            current_state.check(tmp, errs.append, infos.append)
        return errs

    def test_block_written_with_another_versions_numbers_must_be_flagged(self):
        """红：v0.72.0 的区块被写成 v0.73.0 的数（E39 实际干过的事）⇒ 必须报。"""
        ledger = (u"## v0.72.0（E38）—— 某轮\n\n"
                   + self._block(276, 30, 74, "4.439") + u"\n")
        history = {"0.72.0": {"static": {}, "reported": {"validate_infos": 29},
                              "measured": {"bench_ms_per_file": 4.465}}}
        errs = self._run(ledger, history)
        self.assertTrue(errs, "区块被写成别的版本的数却没被报出来")
        self.assertTrue(any(u"同一个数不能两处不同" in e for e in errs), errs)

    def test_block_matching_its_own_version_is_ok(self):
        """绿：区块里的数与**它自己那一版**的快照一致 ⇒ 不得误报。"""
        ledger = (u"## v0.72.0（E38）—— 某轮\n\n"
                   + self._block(271, 29, 72, "4.465") + u"\n")
        history = {"0.72.0": {"static": {}, "reported": {"validate_infos": 29},
                              "measured": {"bench_ms_per_file": 4.465}}}
        errs = self._run(ledger, history)
        self.assertEqual([e for e in errs if u"同一个数不能两处不同" in e], [],
                         "正确的区块被误报了：%s" % errs)

    def test_block_without_snapshot_must_be_flagged(self):
        """红：区块所属的那一版**没有历史快照**⇒ 必须报（否则这个区块没人对账）。"""
        ledger = (u"## v0.72.0（E38）—— 某轮\n\n"
                   + self._block(271, 29, 72, "4.465") + u"\n")
        history = {"0.73.0": {"static": {}, "reported": {"validate_infos": 30},
                              "measured": {"bench_ms_per_file": 4.439}}}
        errs = self._run(ledger, history)
        self.assertTrue(errs, "缺快照却没被报出来")
        self.assertTrue(any(u"历史快照" in e for e in errs), errs)

    def test_real_repo_carrier_blocks_are_consistent(self):
        """绿：本仓库的**每个**标记区都对账它自己那一版。"""
        sys.path.insert(0, SCRIPTS)
        import current_state
        current_state = importlib.reload(current_state)
        errs = []
        infos = []
        current_state.check(REPO, errs.append, infos.append)
        bad = [e for e in errs
               if u"同一个数不能两处不同" in e or u"历史快照" in e
               or u"没人对账" in e or u"没有所属版本" in e]
        self.assertEqual(bad, [], "本仓库有标记区对不上账：%s" % bad)


if __name__ == "__main__":
    unittest.main()
