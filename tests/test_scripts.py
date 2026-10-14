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

SCRIPT_NAMES = ["audit_graph.py", "audit_index.py", "audit_map.py", "audit_rules.py",
                "audit_scan.py", "evolve_report.py", "lookup.py", "new_doc.py",
                "preflight.py", "project_scan.py", "ship_check.py",
                "validate_skill.py"]


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
        with tempfile.TemporaryDirectory() as tmp:
            self._tree(tmp)
            data, stdout = self._index(tmp)
            blob = json.dumps(data, ensure_ascii=False) + stdout
            self.assertNotIn(os.path.abspath(tmp).replace("\\", "/"), blob,
                             "报告不得泄露本机绝对路径（跨环境失效且可能含用户名）")
            for rec in data["files"]:
                self.assertNotIn("\\", rec["path"])

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


if __name__ == "__main__":
    unittest.main()
