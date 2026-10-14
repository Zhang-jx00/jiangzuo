#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付闸门 —— 将作 (jiangzuo)

把"收尾五步"里能机械核对的部分一次核完：测试、密钥与残留、交付报告、
项目常驻标准。它是 code-review.md 与 SKILL.md「交付收尾」的机器层。

用法:
    python ship_check.py [项目目录] [--level L0|L1|L2|L3] [--report 路径]
                         [--timeout 秒] [--strict]

检查项（缺项即 BLOCKED，并给下一步指令）：
  1. 测试通道：自动识别 pytest / unittest / npm / cargo / go / make 并**执行**；
     识别不到时 L2/L3 判失败（"没测过"不等于"测不了"），L1 降级为警告。
  2. 交付前静态检查：调用 preflight.py --all --strict（密钥/冲突标记/调试残留）。
  3. 交付报告：**主张（可证伪的一句话）**+ 改了什么 / 为什么 / 怎么验证 / 剩余风险，
     外加**复用阶梯停在第几级**。
  4. 自净：git 工作区里不该留探针与试验残留（_probe*、_verify*、*.log、*.tmp、*.bak、scratch/）。
  5. 项目常驻标准：docs/jiangzuo/constitution.md 存在且有内容（L2/L3 必备）。

会做：执行项目自己的测试命令、读取 git 状态、逐项给结论与修复指令。
不会做：不写任何文件、不提交、不推送、不替你判断业务是否正确——
       RESULT: SHIP-OK ≠ 审查通过，它只证明"该跑的都跑过、该留的都留了"。

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))

PROBE_PATTERNS = (
    re.compile(r"(^|/)_probe"), re.compile(r"(^|/)_verify"), re.compile(r"\.log$"),
    re.compile(r"\.tmp$"), re.compile(r"\.bak$"), re.compile(r"(^|/)scratch/"),
    re.compile(r"(^|/)__pycache__/"), re.compile(r"\.orig$"),
)

REPORT_KEYS = (
    ("主张（可证伪）", re.compile(r"主张|断言|CLAIM")),
    ("改了什么", re.compile(r"改了什么|变更内容|改动清单")),
    ("为什么", re.compile(r"为什么|理由|动机")),
    ("怎么验证的", re.compile(r"怎么验证|验证|测试证据")),
    ("剩余风险", re.compile(r"剩余风险|风险|未验证")),
)
LADDER_RX = re.compile(r"阶梯|复用优先|停在第?\s*\d")

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"


def run(cmd, cwd, timeout):
    try:
        p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=timeout)
        return p.returncode, p.stdout.decode("utf-8", "replace").strip()
    except OSError as exc:
        return 127, "无法执行 %s：%s" % (" ".join(cmd), exc)
    except subprocess.TimeoutExpired:
        return 124, "超时（%ds）——测试卡住也是结论，别当通过" % timeout


def detect_test_command(root):
    """返回 (可读命令, argv) 或 (None, None)。按项目自己的入口优先。"""
    def read(path):
        try:
            return io.open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            return ""

    has_pytest_dir = os.path.isdir(os.path.join(root, "tests")) or os.path.isfile(
        os.path.join(root, "conftest.py"))
    if has_pytest_dir:
        if any(f.startswith("test_") and f.endswith(".py")
               for _, _, fs in os.walk(os.path.join(root, "tests")) for f in fs) \
                or any(f.endswith("_test.py") for _, _, fs in os.walk(os.path.join(root, "tests")) for f in fs):
            if "pytest" in read(os.path.join(root, "requirements.txt")) or \
                    os.path.isfile(os.path.join(root, "pytest.ini")):
                return "python -m pytest -q", [sys.executable, "-m", "pytest", "-q"]
            return (u"python -m unittest discover -s tests",
                    [sys.executable, "-m", "unittest", "discover", "-s", "tests"])
    try:
        pkg = read(os.path.join(root, "package.json"))
        if '"test"' in pkg:
            return "npm test", ["npm", "--silent", "test"]
    except OSError:
        pass
    if os.path.isfile(os.path.join(root, "Cargo.toml")):
        return "cargo test", ["cargo", "test", "--quiet"]
    if os.path.isfile(os.path.join(root, "go.mod")):
        return "go test ./...", ["go", "test", "./..."]
    mk = read(os.path.join(root, "Makefile"))
    if re.search(r"^test:", mk, re.M):
        return "make test", ["make", "test"]
    return None, None


def check_tests(root, level, timeout):
    label, argv = detect_test_command(root)
    if not argv:
        if level in ("L2", "L3"):
            return FAIL, "测试通道", "项目里找不到可执行的测试入口", \
                "L2/L3 不允许无测试交付：先建最小测试（带分支/循环/金额/权限的逻辑各一条）"
        return WARN, "测试通道", "未识别到测试入口（L1 允许，但需人工验证）", \
            "把人工验证步骤与输出写进交付报告"
    code, out = run(argv, root, timeout)
    tail = out.splitlines()[-1] if out else "（无输出）"
    if code == 0:
        return PASS, "测试通道", "%s → %s" % (label, tail), ""
    return FAIL, "测试通道", "%s 退出码 %d：%s" % (label, code, tail[:160]), \
        "先修测试，或把它如实写进「剩余风险」——不要用 --skip 蒙过闸门"


def check_preflight(root, timeout):
    script = os.path.join(HERE, "preflight.py")
    code, out = run([sys.executable, script, "--all", "--strict", root], root, timeout)
    if code == 0:
        return PASS, "静态检查", "preflight RESULT PASS（critical/high=0）", ""
    lines = [l for l in out.splitlines() if l.strip().startswith(("-", "RESULT"))]
    return FAIL, "静态检查", "preflight 未过：%s" % (lines[-1] if lines else "见输出"), \
        "密钥类要先作废轮换再删引用；调试残留与冲突标记提交前必须清"


def find_report(root, explicit):
    if explicit:
        return explicit if os.path.isfile(explicit) else None
    base = os.path.join(root, "docs", "jiangzuo", "reports")
    if not os.path.isdir(base):
        return None
    files = [os.path.join(dp, f) for dp, _, fs in os.walk(base) for f in fs
             if f.endswith(".md")]
    return max(files, key=os.path.getmtime) if files else None


def check_report(root, explicit, level):
    path = find_report(root, explicit)
    if not path:
        if level in ("L0", "L1"):
            return WARN, "交付报告", "未找到 docs/jiangzuo/reports/ 下的报告", \
                "L1 可用轻量报告：python scripts/new_doc.py delivery <标题>"
        return FAIL, "交付报告", "未找到交付报告", \
            "python scripts/new_doc.py delivery <标题> → 四问 + 复用阶梯补齐"
    text = io.open(path, encoding="utf-8", errors="replace").read()
    missing = [name for name, rx in REPORT_KEYS if not rx.search(text)]
    if not LADDER_RX.search(text):
        missing.append("复用阶梯停在第几级")
    if missing:
        return FAIL, "交付报告", "%s 缺：%s" % (os.path.basename(path), "、".join(missing)), \
            "补齐缺项；确实没做的事写进「剩余风险」，不要留空"
    return PASS, "交付报告", "%s 四问与阶梯齐全" % os.path.basename(path), ""


def check_cleanliness(root):
    code, out = run(["git", "status", "--porcelain", "--untracked-files=all"], root, 60)
    if code != 0:
        return WARN, "自净核对", "非 git 仓库或 git 不可用，跳过残留核对", \
            "手工确认没有留下探针文件"
    entries = [l[3:].strip() for l in out.splitlines() if l.strip()]
    probes = [e for e in entries if any(p.search(e.replace("\\", "/")) for p in PROBE_PATTERNS)]
    if probes:
        return FAIL, "自净核对", "工作区留有试验残留：%s" % ", ".join(probes[:6]), \
            "删除后重跑；确属产物的（如新增测试）请纳入版本管理"
    return PASS, "自净核对", "无试验残留（%d 项变更待交付）" % len(entries), ""


def check_constitution(root, level):
    path = os.path.join(root, "docs", "jiangzuo", "constitution.md")
    if not os.path.isfile(path):
        if level in ("L2", "L3"):
            return FAIL, "常驻标准", "缺 docs/jiangzuo/constitution.md", \
                "从 templates/definition-of-done.md 复制并按项目实际填（每个改动都要过的常驻门槛）"
        return WARN, "常驻标准", "未建立项目常驻标准（L0/L1 可暂缓）", \
            "摸底完成后建立，之后每次交付叠加检查"
    bullets = [l for l in io.open(path, encoding="utf-8", errors="replace").read().splitlines()
               if l.strip().startswith(("-", "*")) and len(l.strip()) > 3]
    if len(bullets) < 3:
        return FAIL, "常驻标准", "constitution.md 只有 %d 条，形同虚设" % len(bullets), \
            "至少写清：测试命令、lint/构建命令、契约同步要求、报告要求"
    return PASS, "常驻标准", "constitution.md 有 %d 条常驻门槛" % len(bullets), ""


def check_self_skill(root, timeout):
    """技能仓库自身：结构校验也必须过闸（validate_skill 会检查骨架契约）。"""
    if not os.path.isfile(os.path.join(root, "SKILL.md")):
        return None
    code, out = run([sys.executable, os.path.join(HERE, "validate_skill.py"), root],
                    root, timeout)
    if code == 0:
        return PASS, "技能结构", "validate_skill 通过（本目录是技能仓库）", ""
    return FAIL, "技能结构", "validate_skill 未过", "按输出修结构，0 错误才可交付"


def main():
    ap = argparse.ArgumentParser(
        description="交付闸门（将作）：一条命令核完测试/静态检查/报告/自净/常驻标准。")
    ap.add_argument("path", nargs="?", default=".", help="项目目录（默认当前目录）")
    ap.add_argument("--level", default="L2", choices=["L0", "L1", "L2", "L3"],
                    help="任务级别，决定缺项是失败还是警告（默认 L2）")
    ap.add_argument("--report", help="指定交付报告路径（默认取 reports/ 下最新）")
    ap.add_argument("--timeout", type=int, default=600, help="单条命令超时秒数")
    ap.add_argument("--strict", action="store_true", help="WARN 也视为不通过")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("目录不存在：%s\n下一步：确认路径，或先 cd 到项目根目录" % root)
        print("RESULT: SHIP-BLOCKED（1 项未过）")
        return 1

    results = [check_tests(root, args.level, args.timeout),
               check_preflight(root, args.timeout),
               check_report(root, args.report, args.level),
               check_cleanliness(root),
               check_constitution(root, args.level)]
    self_check = check_self_skill(root, args.timeout)
    if self_check:
        results.append(self_check)

    icon = {PASS: "✔", WARN: "⚠", FAIL: "✘"}
    print("# 交付闸门（%s ｜ 级别 %s）\n" % (root, args.level))
    for status, label, detail, next_step in results:
        print("  %s %-6s %s" % (icon[status], label, detail))
        if next_step:
            print("    └─ 下一步：%s" % next_step)

    blocked = [r for r in results if r[0] == FAIL]
    warned = [r for r in results if r[0] == WARN]
    if args.strict:
        blocked += warned
    print("\n统计：通过 %d ｜ 警告 %d ｜ 未过 %d" % (
        len(results) - len(blocked) - len(warned), len(warned), len(blocked)))
    if blocked:
        print("RESULT: SHIP-BLOCKED（%d 项未过）" % len(blocked))
        print("提醒：闸门不认「应该能过」。缺的那项补上并重新跑，才算交付。")
        return 1
    print("RESULT: SHIP-OK（闸门项全过；仍需按 code-review.md 人工过一遍）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
