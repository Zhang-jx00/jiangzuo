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
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
PY = sys.executable or "python"

SCRIPT_NAMES = ["evolve_report.py", "lookup.py", "new_doc.py", "preflight.py",
                "project_scan.py", "ship_check.py", "validate_skill.py"]


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

    def test_validate_readme_counts_match_on_self(self):
        """绿测：本仓库 README 的脚本/模板/分册计数必须与实物一致。"""
        r = run([os.path.join(SCRIPTS, "validate_skill.py"), "."])
        self.assertIn("README 计数与实物一致", r.stdout)


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
             ("配色视觉排版走查", "ui-design")]

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


if __name__ == "__main__":
    unittest.main()
