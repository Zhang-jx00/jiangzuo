#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""交付前静态检查 —— 将作 (jiangzuo)

对 git 变更文件（或指定目录）做机械可查的交付前检查：
疑似密钥、调试残留、合并冲突标记、TODO/FIXME、diff 统计。
它是 code-review.md 清单的机器层，查完仍需人工过清单。

用法:
    python preflight.py [路径...] [--staged] [--all] [--strict]

- 默认：在 git 仓库中检查「未提交变更 + 新增未跟踪文件」
- --staged：只检查已暂存（即将提交）的内容
- --all：忽略 git，全量扫描指定路径（非 git 目录自动走此模式）
- --strict：发现 critical/high 问题时退出码 1（可用于 CI）

会做：静态模式匹配——疑似密钥（8 类特征）、调试残留、合并冲突标记、
      TODO/FIXME、大文件提示、diff 统计；输出 RESULT 结论行供 CI 扫描。
不会做：逻辑错误、并发问题、契约不匹配、性能问题——RESULT PASS ≠ 审查通过，
      它只是 code-review.md 人工清单的机器层。

仅使用 Python 标准库（3.8+），只读不改。
"""
import argparse
import io
import os
import re
import subprocess
import sys

# Windows GBK 控制台打印 ⚪ 等符号会 UnicodeEncodeError（2026-10-07 本地实跑实测崩溃，CI 在 Linux 未暴露）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist",
             "build", "target", "vendor", ".next", ".nuxt", "coverage", ".idea"}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock",
    "Cargo.lock", "go.sum", "composer.lock", "Gemfile.lock",
}

SCAN_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".vue", ".php", ".rb", ".go",
             ".java", ".kt", ".swift", ".c", ".cpp", ".h", ".cs", ".json",
             ".yaml", ".yml", ".toml", ".ini", ".cfg", ".md", ".html", ".css",
             ".scss", ".less", ".sh", ".bat", ".ps1", ".sql", ".env", ".txt"}

# (级别, 名称, 编译后的正则, 说明)
SECRET_PATTERNS = [
    ("critical", "私钥块", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("critical", "AWS AccessKey", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("high", "GitHub Token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("high", "Google API Key", re.compile(r"\bAIza[0-9A-Za-z_\-]{30,}\b")),
    ("high", "Slack Token", re.compile(r"\bxox[baprs]-[A-Za-z0-9\-]{10,}\b")),
    ("high", "OpenAI/Anthropic Key", re.compile(r"\bsk-(?:proj-|ant-)?[A-Za-z0-9_\-]{20,}\b")),
    ("high", "带凭证的连接串", re.compile(
        r"\b(?:mongodb(?:\+srv)?|postgres(?:ql)?|mysql|redis|amqp)://[^\s:/@]+:[^\s/@]{4,}@")),
    ("high", "赋值型密钥", re.compile(
        r"(?i)(?:api[_-]?key|apikey|secret|access[_-]?token|auth[_-]?token|"
        r"private[_-]?key|password|passwd|pwd)\w*\s*[:=]\s*['\"]([^'\"]{6,})['\"]")),
]

PLACEHOLDER_HINTS = ("your", "xxx", "changeme", "change_me", "example", "placeholder",
                     "<", "${", "{{", "process.env", "os.environ", "getenv",
                     "config(", "dummy", "sample", "test_", "_test", "todo")

DEBUG_PATTERNS = [
    ("warning", "调试输出 console.log", re.compile(r"\bconsole\.log\s*\("), {".js", ".jsx", ".ts", ".tsx", ".vue"}),
    ("warning", "调试器语句 debugger", re.compile(r"^\s*debugger\s*;?\s*$"), {".js", ".jsx", ".ts", ".tsx", ".vue"}),
    ("warning", "Python 断点 pdb", re.compile(r"\bpdb\.set_trace\s*\(|\bbreakpoint\s*\("), {".py"}),
    ("warning", "PHP 调试 var_dump", re.compile(r"\bvar_dump\s*\(|\bprint_r\s*\("), {".php"}),
    ("warning", "Ruby 调试 pry/byebug", re.compile(r"\bbinding\.pry\b|\bbyebug\b"), {".rb"}),
]

CONFLICT_MARKER = re.compile(r"^(<{7}|={7}|>{7})( |$)")
TODO_MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX)\b[:\s(]")


def is_git_repo(path):
    probe = path if os.path.isdir(path) else os.path.dirname(path) or "."
    try:
        subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], cwd=probe,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def git_changed_files(root, staged):
    """返回 (变更文件列表, 统计摘要行)。"""
    diff_cmd = ["git", "diff", "--cached"] if staged else ["git", "diff", "HEAD"]
    try:
        names = subprocess.run(diff_cmd + ["--name-only"], cwd=root,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               check=True).stdout.decode("utf-8", "replace").split()
        untracked = []
        if not staged:
            untracked = subprocess.run(
                ["git", "ls-files", "--others", "--exclude-standard"], cwd=root,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                check=True).stdout.decode("utf-8", "replace").split()
        stat = subprocess.run(diff_cmd + ["--stat"], cwd=root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              check=True).stdout.decode("utf-8", "replace")
        files = sorted(set(names) | set(untracked))
        return files, stat.strip()
    except (OSError, subprocess.CalledProcessError):
        return [], ""


def walk_files(root):
    out = []
    if os.path.isfile(root):
        return [root]
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            out.append(os.path.join(dirpath, fn))
    return out


def scannable(rel_path):
    base = os.path.basename(rel_path)
    if base in SKIP_FILES or base.endswith(".min.js") or base.endswith(".min.css"):
        return False
    ext = os.path.splitext(base)[1].lower()
    if base.startswith(".env") and "example" not in base:
        return True  # .env 本身也要扫（不该提交）
    return ext in SCAN_EXTS or base.startswith(".env")


def read_lines(abs_path, limit=400_000):
    try:
        with io.open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read(limit).splitlines()
    except OSError:
        return []


def check_file(rel_path, root):
    """返回 [(级别, 类别, 行号, 摘要)]"""
    findings = []
    if not scannable(rel_path):
        return findings
    ext = os.path.splitext(rel_path)[1].lower()
    base = os.path.basename(rel_path)
    abs_path = os.path.join(root, rel_path)
    try:
        if os.path.getsize(abs_path) > 2_000_000:
            findings.append(("info", "大文件(>2MB)", 1, "确认是否应入库"))
    except OSError:
        pass
    lines = read_lines(abs_path)
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if CONFLICT_MARKER.match(stripped):
            findings.append(("critical", "合并冲突标记", i, stripped[:80]))
            continue
        if base.startswith(".env") and "example" not in base and re.match(
                r"^[A-Za-z_]*(KEY|SECRET|TOKEN|PASSWORD)\w*=..", line):
            findings.append(("high", "疑似真实 .env 入库", i, stripped[:80]))
        for level, label, rx in SECRET_PATTERNS:
            m = rx.search(line)
            if m:
                value = m.group(1) if m.groups() else m.group(0)
                if any(h in value.lower() for h in PLACEHOLDER_HINTS):
                    continue
                findings.append((level, "疑似密钥：%s" % label, i,
                                 "%s → %s****" % (label, value[:6])))
        for level, label, rx, exts in DEBUG_PATTERNS:
            if ext in exts and rx.search(line):
                findings.append((level, label, i, stripped[:80]))
        if TODO_MARKER.search(line):
            findings.append(("info", "TODO/FIXME 标记", i, stripped[:80]))
    return findings


def main():
    parser = argparse.ArgumentParser(
        description="交付前静态检查（将作）：密钥/调试残留/冲突标记/TODO/diff 统计。机器层检查，查完仍需人工过审查清单。")
    parser.add_argument("paths", nargs="*", default=["."], help="要检查的路径（默认当前目录的 git 变更）")
    parser.add_argument("--staged", action="store_true", help="只检查已暂存的内容")
    parser.add_argument("--all", action="store_true", help="忽略 git，全量扫描")
    parser.add_argument("--strict", action="store_true", help="发现 critical/high 时退出码 1")
    args = parser.parse_args()

    root = os.path.abspath(args.paths[0])
    use_git = not args.all and is_git_repo(root)
    files, stat = ([], "")
    if use_git:
        files, stat = git_changed_files(root, args.staged)
        if not files:
            print("（git 没有发现%s变更，无事可查）" % ("暂存区" if args.staged else "未提交"))
            print("RESULT: PASS（无变更）")
            return 0
    else:
        files = [os.path.relpath(p, root).replace("\\", "/")
                 for p in walk_files(root)]

    findings = []
    for rel in files:
        findings.extend((lvl, cat, rel, ln, txt)
                        for lvl, cat, ln, txt in check_file(rel, root))

    order = {"critical": 0, "high": 1, "warning": 2, "info": 3}
    findings.sort(key=lambda f: (order[f[0]], f[2], f[3]))

    print("# 交付前检查报告\n")
    if stat:
        print("## Diff 摘要\n\n```\n%s\n```\n" % stat)
    if not findings:
        print("## 结果\n\n机械检查全部通过，共扫描 %d 个文件。\n" % len(files))
        print("提醒：机械检查通过 ≠ 审查通过，请继续按 code-review.md 人工清单过一遍。")
        print("\nRESULT: PASS（0 发现）")
        return 0

    print("## 结果（%d 个文件，%d 条发现）\n" % (len(files), len(findings)))
    for level in ("critical", "high", "warning", "info"):
        group = [f for f in findings if f[0] == level]
        if not group:
            continue
        icon = {"critical": "🔴", "high": "🟠", "warning": "🟡", "info": "⚪"}[level]
        print("### %s %s（%d）\n" % (icon, level, len(group)))
        for _, cat, rel, ln, txt in group:
            print("- `%s:%d` **%s** — %s" % (rel, ln, cat, txt))
        print()

    print("处理建议：🔴/🟠 必须处理（密钥泄露要先作废轮换，不是只删代码）；"
          "🟡 提交前清掉；⚪ 记录到 TODO 或技术债。")
    blocking = [f for f in findings if f[0] in ("critical", "high")]
    print("\nRESULT: %s（critical/high=%d, warning=%d, info=%d）"
          % ("PASS" if not blocking else "FAIL", len(blocking),
             sum(1 for f in findings if f[0] == "warning"),
             sum(1 for f in findings if f[0] == "info")))
    if args.strict and blocking:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
