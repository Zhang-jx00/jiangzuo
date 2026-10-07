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
import subprocess
import sys
import tempfile
import unittest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS = os.path.join(REPO, "scripts")
PY = sys.executable or "python"

SCRIPT_NAMES = ["lookup.py", "new_doc.py", "preflight.py",
                "project_scan.py", "validate_skill.py"]


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


if __name__ == "__main__":
    unittest.main()
