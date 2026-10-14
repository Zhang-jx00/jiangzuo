#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计链共享库 —— 将作 (jiangzuo)

给 audit_index / audit_map / audit_graph / audit_scan 提供同一套底层件：
gitignore 语义的忽略规则、可复现的文件清单、内容哈希、分块流式读取、
二进制判定、密钥脱敏、缓存键计算。

设计约束（违反任何一条都算缺陷，见 references/security-audit.md 的轻量化红线）：
- 只用 Python 3.8+ 标准库；不联网；对被扫描项目**全程只读**。
- 禁止整仓载入内存：索引只存元数据，文件按行流式读，单行超长要截断并留痕。
- 清单必须可复现：同一棵树两次索引得到同一个 index_sha1，顺序按路径排序。
- 跳过必须留痕：二进制/超限文件进 skipped 清单，不静默丢弃。

会做：忽略规则解析（含嵌套 .gitignore 与 ! 取反）、git 兜底、哈希、语言映射、脱敏。
不会做：AST 解析（正则级分析，精度分档由 audit_graph 的 analysis_depth 声明）。

仅使用 Python 标准库（3.8+）。
"""
import hashlib
import io
import json
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

INDEX_SCHEMA = "jiangzuo-audit-index/1"
LIB_VERSION = "1"
NUL_BYTE = bytes([0])   # 二进制判定用；写成常量是为了不在源码里塞转义 NUL

# 依赖/构建/版本库目录：任何模式（含 git 模式）都排除，防止把 node_modules 当代码扫
BUILTIN_SKIP_DIRS = {
    ".git", ".svn", ".hg", ".bzr", "node_modules", "bower_components", "vendor",
    "__pycache__", ".venv", "venv", "env", ".tox", ".mypy_cache", ".pytest_cache",
    "site-packages", "dist", "build", "out", "target", ".next", ".nuxt", ".output",
    "coverage", ".gradle", ".idea", ".vscode", "bin", "obj", "Pods", ".dart_tool",
    ".terraform", "logs", ".cache", ".parcel-cache", ".svelte-kit", "DerivedData",
}

LANG_BY_EXT = {
    ".py": "python", ".pyi": "python", ".js": "javascript", ".jsx": "javascript",
    ".mjs": "javascript", ".cjs": "javascript", ".ts": "typescript",
    ".tsx": "typescript", ".vue": "vue", ".svelte": "svelte", ".java": "java",
    ".kt": "kotlin", ".kts": "kotlin", ".groovy": "groovy", ".gradle": "groovy",
    ".php": "php", ".rb": "ruby", ".go": "go", ".rs": "rust", ".c": "c",
    ".h": "c", ".cpp": "cpp", ".cc": "cpp", ".hpp": "cpp", ".cs": "csharp",
    ".swift": "swift", ".scala": "scala", ".sql": "sql", ".html": "html",
    ".htm": "html", ".css": "css", ".scss": "scss", ".less": "less",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml",
    ".ini": "ini", ".cfg": "ini", ".xml": "xml", ".md": "markdown",
    ".sh": "shell", ".bash": "shell", ".zsh": "shell", ".ps1": "powershell",
    ".bat": "batch", ".tf": "terraform", ".env": "dotenv", ".txt": "text",
}

SOURCE_LANGS = ("python", "javascript", "typescript", "vue", "java", "kotlin",
                "php", "ruby", "go", "rust", "c", "cpp", "csharp", "swift",
                "scala", "groovy", "shell", "powershell", "sql")

DEFAULT_MAX_FILE_BYTES = 2 * 1024 * 1024   # 单文件阈值：2MB
DEFAULT_MAX_LINE_BYTES = 4096              # 单行阈值：超长截断并留痕
SKIP_LIST_CAP = 200                        # skipped 明细最多列这么多条，其余计数汇总

# 隐藏文件默认不看，但配置类点文件是密钥泄露高发区，必须进清单
DOTFILE_KEEP = {".gitignore", ".dockerignore", ".gitattributes", ".gitmodules",
                ".htaccess", ".editorconfig", ".envrc", ".npmrc", ".pypirc"}


def norm_rel(path, root):
    """相对 root 的 POSIX 风格路径（不带反斜杠、不带盘符、不以 ./ 开头）。"""
    rel = os.path.relpath(os.path.abspath(path), os.path.abspath(root))
    return rel.replace(os.sep, "/").replace("\\", "/")


def lang_of(rel_path):
    base = os.path.basename(rel_path)
    if base.startswith(".env"):
        return "dotenv"
    return LANG_BY_EXT.get(os.path.splitext(base)[1].lower(), "other")


def sha1_hex(text):
    if isinstance(text, str):
        text = text.encode("utf-8", "replace")
    return hashlib.sha1(text).hexdigest()


def hash_and_probe(path, chunk=1 << 16, probe=8192):
    """**一次打开**同时算出内容 sha1 与二进制判定。

    基准实测：原先 sha1_file + looks_binary 各开一次文件，1500 个文件就是
    3000 次打开，索引层 5.76 ms/文件里大头是 IO 而不是计算。合并后减半。
    """
    h = hashlib.sha1()
    head = b""
    try:
        with io.open(path, "rb") as f:
            while True:
                block = f.read(chunk)
                if not block:
                    break
                if not head:
                    head = block[:probe]
                h.update(block)
    except OSError:
        return "", True
    return h.hexdigest(), (NUL_BYTE in head)


def sha1_file(path, chunk=1 << 16):
    """流式哈希：不把整个文件读进内存。"""
    return hash_and_probe(path, chunk)[0] or ""


def file_size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def looks_binary(path, probe=8192):
    try:
        with io.open(path, "rb") as f:
            head = f.read(probe)
    except OSError:
        return True
    if not head:
        return False
    return b"\x00" in head


# ---------------------------------------------------------------- 忽略规则

def _escape_literal(ch):
    return re.escape(ch)


def pattern_to_regex(pattern, base, dir_only):
    """把一条 gitignore 模式翻成匹配 relpath 的正则。

    规则（对齐 git 语义的常用子集）：
    - 模式内部出现 '/'（结尾的斜杠已剥掉）→ 锚定到声明它的那个目录；
      否则按文件名在任意深度匹配。
    - 前导 '/' 同样表示锚定到根。
    - '*' 不跨 '/'，'**' 跨 '/'，'?' 单字符，'[...]' 字符类。
    - 目录型模式（结尾 '/'）同时命中该目录本身与目录下所有内容。
    """
    anchored = "/" in pattern.rstrip("/") or pattern.startswith("/")
    body = pattern.lstrip("/")
    if base:
        prefix = re.escape(base) + "/"
        if not anchored:
            prefix += "(?:[^/]+/)*"
    else:
        prefix = "" if anchored else "(?:[^/]+/)*"

    out = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "*":
            if body[i:i + 2] == "**":
                i += 2
                if body[i:i + 1] == "/":
                    i += 1
                    out.append("(?:[^/]+/)*")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        elif ch == "[":
            j = body.find("]", i + 1)
            if j < 0:
                out.append(_escape_literal(ch))
            else:
                cls = body[i:j + 1]
                if cls[1] == "!":
                    cls = "[^" + cls[2:]
                out.append(cls)
                i = j + 1
                continue
        elif ch == "\\":
            if i + 1 < len(body):
                i += 1
                out.append(_escape_literal(body[i]))
        else:
            out.append(_escape_literal(ch))
        i += 1

    tail = "(?:/.*)?$" if dir_only else "$"
    raw = "^" + prefix + "".join(out) + tail
    try:
        return re.compile(raw)
    except re.error:
        return None


class IgnoreRules(object):
    """按"越深的目录越优先、同文件内越靠后越优先"的顺序求值，最后一条命中规则决定取舍。"""

    def __init__(self):
        self.rules = []          # [(depth, compiled, negate, raw)]
        self.sources = []
        self._ordered = None

    def add_file(self, path, root):
        scope = norm_rel(os.path.dirname(path), root)
        if scope == ".":
            scope = ""
        depth = len([p for p in scope.split("/") if p])
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.read(200_000).splitlines()
        except OSError:
            return
        loaded = 0
        for line in lines:
            if not line.strip() or line.strip().startswith("#"):
                continue
            negate = line.startswith("!")
            pat = line[1:] if negate else line
            if not pat.strip():
                continue
            dir_only = pat.endswith("/")
            pat = pat.rstrip("/")
            if not pat:
                continue
            rx = pattern_to_regex(pat, scope, dir_only)
            if rx is None:
                continue
            self.rules.append((depth, rx, negate, line.strip()))
            loaded += 1
        if loaded:
            self.sources.append("%s（%d 条）" % (norm_rel(path, root), loaded))
            self._ordered = None

    def add_pattern(self, pattern, source="cli"):
        dir_only = pattern.endswith("/")
        pat = pattern.rstrip("/")
        rx = pattern_to_regex(pat, "", dir_only)
        if rx is not None:
            self.rules.append((99, rx, False, pat))
            self._ordered = None
            if source not in self.sources:
                self.sources.append("%s（临时 %s）" % (source, pat))

    def ordered(self):
        if self._ordered is None:
            # 稳定排序：浅目录在前、深目录在后；同一文件内靠后的规则后命中即覆盖
            self._ordered = sorted(self.rules, key=lambda r: r[0])
        return self._ordered

    def is_ignored(self, rel_path, is_dir=False):
        """返回 True=忽略。语义对齐 git：最后一条命中的规则决定取舍，! 可反选。"""
        verdict = False
        for _depth, rx, negate, _raw in self.ordered():
            if rx.match(rel_path):
                verdict = not negate
        return verdict

    def builtin_skip_dir(self, name):
        return name in BUILTIN_SKIP_DIRS


def collect_ignore_files(root, extra_paths=None):
    """root/.gitignore → 各子目录 .gitignore → .git/info/exclude → 用户附加文件。"""
    rules = IgnoreRules()
    found = []
    top = os.path.join(root, ".gitignore")
    if os.path.isfile(top):
        found.append(top)
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in BUILTIN_SKIP_DIRS and not d.startswith(".")]
        if ".gitignore" in filenames and os.path.abspath(dirpath) != os.path.abspath(root):
            found.append(os.path.join(dirpath, ".gitignore"))
    exclude = os.path.join(root, ".git", "info", "exclude")
    if os.path.isfile(exclude):
        found.append(exclude)
    for path in (extra_paths or []):
        if os.path.isfile(path):
            found.append(path)
    for path in sorted(found, key=lambda p: (len(norm_rel(p, root).split("/")), p)):
        rules.add_file(path, root)
    return rules


# ---------------------------------------------------------------- 清单构建

def _git_list(root, mode):
    """mode='track'：受版本控制且未被忽略的文件；mode='ignored'：被忽略的（只为计数）。"""
    cmd = ["git", "ls-files", "--cached", "--others", "--exclude-standard"]
    if mode == "ignored":
        cmd = ["git", "ls-files", "--others", "--ignored", "--exclude-standard"]
    try:
        out = subprocess.run(cmd, cwd=root, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    return [ln.decode("utf-8", "replace").strip().replace("\\", "/")
            for ln in out.split(b"\n") if ln.strip()]


def _builtin_pruned(rel):
    parts = rel.split("/")
    return any(p in BUILTIN_SKIP_DIRS for p in parts[:-1]) or parts[0] in BUILTIN_SKIP_DIRS


def iter_files(root):
    """不带忽略规则的裸走：跳过隐藏目录与内置依赖目录，产出 (rel, abs, is_dir=False)。"""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames
                             if d not in BUILTIN_SKIP_DIRS and not d.startswith("."))
        for fn in sorted(filenames):
            full = os.path.join(dirpath, fn)
            if os.path.islink(full):
                continue
            yield norm_rel(full, root), full


def build_index(root, use_git=True, max_file_bytes=DEFAULT_MAX_FILE_BYTES,
                include_binary=False, extra_ignore=None, exclude=None,
                extra_patterns=None):
    """产出可复现的文件清单。git 可用时用 git 的忽略判定（语义最准），
    否则用内置 .gitignore 解析器；两条路径都再过一遍内置依赖目录黑名单。

    exclude：本工具自己写出的产物（如 --json 输出文件） must not 进清单，
    否则"扫第二次结果变了"会毁掉可复现性。
    """
    root = os.path.abspath(root)
    skip_set = set(exclude or ())
    rules = collect_ignore_files(root, extra_ignore)
    for pat in (extra_patterns or []):
        rules.add_pattern(pat, source="cli")
    rel_paths = None
    generator = "gitignore-parser"
    if use_git and os.path.isdir(os.path.join(root, ".git")):
        listed = _git_list(root, "track")
        if listed is not None:
            rel_paths = listed
            generator = "git-ls-files"
            ignored = _git_list(root, "ignored")
            if ignored:
                rules.sources.append("git 忽略判定（%d 个文件被 .gitignore 排除）"
                                     % len(ignored))
    if rel_paths is None:
        rel_paths = []
        for rel, full in iter_files(root):
            if rules.is_ignored(rel):
                continue
            rel_paths.append(rel)

    files, skipped = [], []
    n_binary = n_oversize = n_hidden = 0
    for rel in sorted(set(rel_paths)):
        if rel in skip_set:
            continue
        if _builtin_pruned(rel):
            continue
        if rules.is_ignored(rel):
            continue
        base = os.path.basename(rel)
        if base.startswith(".") and base not in DOTFILE_KEEP \
                and not base.startswith(".env"):
            n_hidden += 1
            continue
        full = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(full) or os.path.islink(full):
            continue
        size = file_size(full)
        if size < 0:
            skipped.append({"path": rel, "reason": "unreadable", "bytes": 0})
            continue
        if size > max_file_bytes:
            n_oversize += 1
            skipped.append({"path": rel, "reason": "oversize", "bytes": size})
            continue
        digest, binary = hash_and_probe(full)
        if not include_binary and binary:
            n_binary += 1
            skipped.append({"path": rel, "reason": "binary", "bytes": size})
            continue
        files.append({"path": rel, "bytes": size, "sha1": digest,
                      "lang": lang_of(rel)})

    counts = {"files": len(files), "binary": n_binary, "oversize": n_oversize,
              "hidden": n_hidden, "skipped_listed": len(skipped)}
    by_lang = {}
    total_bytes = 0
    for rec in files:
        by_lang[rec["lang"]] = by_lang.get(rec["lang"], 0) + 1
        total_bytes += rec["bytes"]
    counts["total_bytes"] = total_bytes
    payload = {"schema": INDEX_SCHEMA, "generator": generator,
               "ignore_sources": rules.sources,
               "max_file_bytes": max_file_bytes,
               "files": files, "skipped": skipped[:SKIP_LIST_CAP],
               "skipped_truncated": max(0, len(skipped) - SKIP_LIST_CAP),
               "counts": counts, "by_lang": by_lang}
    payload["index_sha1"] = sha1_hex(json.dumps(
        {"files": files, "counts": counts}, sort_keys=True, ensure_ascii=False))
    return payload


def load_index(path_or_dict):
    if isinstance(path_or_dict, dict):
        return path_or_dict
    with io.open(path_or_dict, "r", encoding="utf-8") as f:
        data = json.load(f)
    if data.get("schema") != INDEX_SCHEMA:
        raise ValueError("索引文件 schema 不是 %s：%r" % (INDEX_SCHEMA, data.get("schema")))
    return data


# ---------------------------------------------------------------- 流式读取

def iter_lines(path, max_bytes=DEFAULT_MAX_FILE_BYTES, max_line=DEFAULT_MAX_LINE_BYTES):
    """按行流式产出 (行号, 文本, 是否被截断)。超过 max_bytes 的文件整个跳过（产出 ()*0）。

    用文件对象迭代而不是 f.read().splitlines()：后者在 preflight.py 里会把
    整个文件一次性变成一个大 list，扫描大仓时内存随文件尺寸线性上涨。
    """
    if file_size(path) > max_bytes:
        return
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, line in enumerate(f, 1):
                if len(line) > max_line:
                    yield i, line[:max_line], True
                else:
                    yield i, line, False
    except OSError:
        return


DOCSTRING_DELIMS = ('"""', "'''")
COMMENT_PREFIXES = ("#", "//", "*", "/*")
STRING_SPAN_RX = re.compile(r"'[^'\n]*'|\"[^\"\n]*\"")


def iter_code_lines(path, max_bytes=None, ignore_strings=False):
    """**只产出可执行代码行**：跳过注释行与三引号块，可选把单行字符串字面量剥掉。

    为什么必须有这一层（v0.18 自扫实测）：把漏洞样例当字符串写进测试夹具、
    在文档里谈论 token 配额，都会被纯文本正则当成代码命中——本仓库 0 个真漏洞
    却报了 12 条，全部来自这类噪声。没有这一层，误报率就只能靠嘴说。

    ignore_strings=True 时把 '...' / "..." 的内容剥成空串再产出，
    供 `ignore_strings` 规则使用（日志脱敏、调试开关、弱哈希这类"标识符型"规则）。
    """
    limit = DEFAULT_MAX_FILE_BYTES if max_bytes is None else max_bytes
    if file_size(path) > limit:
        return
    block = None
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            for i, raw in enumerate(f, 1):
                stripped = raw.strip()
                if block:
                    if block in raw:
                        block = None
                    continue
                if stripped.startswith(COMMENT_PREFIXES):
                    continue
                for delim in DOCSTRING_DELIMS:
                    if stripped.startswith(delim) and stripped.count(delim) == 1:
                        block = delim
                        break
                if block:
                    continue
                line = STRING_SPAN_RX.sub(lambda m: m.group(0)[0] + m.group(0)[-1],
                                          raw) if ignore_strings else raw
                if len(line) > DEFAULT_MAX_LINE_BYTES:
                    yield i, line[:DEFAULT_MAX_LINE_BYTES], True
                else:
                    yield i, line, False
    except OSError:
        return


def match_in_string(line, pos):
    """判断某个匹配位置是否落在字符串字面量**内部**。

    存在的理由：测试夹具与代码生成器会把漏洞写法当字符串写下来，
    数据流引擎照单全收就会在干净仓库里造出一堆"critical"。
    真正的 sink 调用形如 `os.system("ls " + x)`——匹配点在任何引号之前；
    而 `    "os.system(...)"` 的匹配点落在引号里，那不是代码。
    """
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch in "\"'":
            j = i + 1
            while j < n:
                if line[j] == "\\":
                    j += 2
                    continue
                if line[j] == ch:
                    break
                j += 1
            if i < pos <= j:
                return True
            i = j + 1
            continue
        if ch == "#" or line[i:i + 2] == "//":
            break
        i += 1
    return False


# ---------------------------------------------------------------- 脱敏

SECRETISH_RX = re.compile(
    r"(?i)((?:api[_-]?key|apikey|secret|access[_-]?token|auth[_-]?token|"
    r"private[_-]?key|password|passwd|pwd|token)\s*[:=]\s*['\"]?)([^\s'\"]{6,})")
BEARER_RX = re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.=]{12,}")


def redact(text):
    """报告/日志输出前脱敏：只保留键名与值的前 4 位。

    扫描器会把命中行原文带进报告，未脱敏就等于把新漏洞写进交付物——
    这条是 references/security.md「日志不打印密码、token」的机器层。
    """
    if not text:
        return text
    out = SECRETISH_RX.sub(lambda m: m.group(1) + (m.group(2)[:4] + "****"), text)
    out = BEARER_RX.sub("Bearer ****", out)
    return out


if __name__ == "__main__":
    print(__doc__)
    print("INDEX_SCHEMA = %s ｜ 内置跳过目录 %d 个 ｜ 语言映射 %d 项"
          % (INDEX_SCHEMA, len(BUILTIN_SKIP_DIRS), len(LANG_BY_EXT)))
    sys.exit(0)
