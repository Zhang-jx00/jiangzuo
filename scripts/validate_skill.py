#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能结构校验器 —— 将作 (jiangzuo)

按 Agent Skills 开放规范（agentskills.io）与渐进式披露实践校验技能目录，
可用作本地自检或 CI 门禁。

校验项：
  1. SKILL.md 存在且 frontmatter 可解析，name/description 必填
  2. name 规范（≤64 字符，建议小写 kebab-case）；description ≤1024 字符；
     清单 entry（description + when_to_use）≤299 字符可见预算
  3. SKILL.md 正文行数 ≤500；正文 token ≤5000（超预算直接 err——先删再加）
  4. 正文中引用的 references/ templates/ scripts/ 文件必须存在（路径含反斜杠即报错）
  5. scripts/*.py 语法可编译
  6. 分册之间不再互相引用（保持引用一层深，超深仅警告）
  7. README 声明的脚本/模板/分册数量、入口行数、规则条数与磁盘实物一致（防文档滞后）
  8. 每本分册都登记在 lookup.py 的 BOOKLET_ALIASES 路由词表里（防检索层漏配）
  9. 分册骨架契约：何时读/前置/产出/CRITICAL 防跳步行 + 常见错误节 + ≤160 行
 10. metadata.version 与 CHANGELOG 最新条目一致；CHANGELOG 条目日期不许晚于今天
 11. CHANGELOG 条目日期必须能在 git 里找到该版本号落笔那天（跨午夜要跟着改）
 12. 表格行头不许被吃（少开头的 `| ` 却仍是 `a | b` 形状 → err）
 13. 文档里"上表 N 条"这类声明的条数要与表里实际数据行数对上（单表文件才判）
 14. .md **代码块**里"复制即跑"的期望值（用例数 / 语料分母 / 规则条数）要与实物对上

会做：结构硬约束、引用存在性、绝对路径、版本一致性、期望值对账、占用估算（--stats）。
不会做：内容质量与触发率——那要靠 evals/trigger-tests.md 与 red-tests.md 实测。

用法:
    python validate_skill.py [技能目录]      # 退出码 0=通过 1=有错误
    python validate_skill.py --stats [技能目录]  # 只打印占用报告

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import json
import os
import ast
import re
import subprocess
import sys
import time

# 「当前状态」的机器可读真源与对账（E34 新增第 23 项）。
# ⚠️ 刻意**惰性**依赖：current_state 在被导入时**不**反过来 import 本模块
# （否则循环 import）；它只在**函数体内**惰性 import 本模块取推导实现。
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    import current_state
except ImportError:  # pragma: no cover - 只在脚本目录不在 sys.path 时发生
    current_state = None

# 发布产物的**身份**核验（E37 新增第 26 项）。同上：惰性依赖，绝不反向 import 本模块。
try:
    import release_identity
except ImportError:  # pragma: no cover - 只在脚本目录不在 sys.path 时发生
    release_identity = None

# Windows GBK 控制台打印 ✔ 等符号会 UnicodeEncodeError（2026-10-07 本地实跑实测崩溃，CI 在 Linux 未暴露）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RECOGNIZED_KEYS = {"name", "description", "when_to_use", "license", "metadata"}
TOLERATED_KEYS = {"version", "allowed-tools", "compatibility", "argument-hint",
                  "user-invocable", "disable-model-invocation"}
REF_RX = re.compile(r"(?:references|templates|scripts|assets|evals)/[A-Za-z0-9][A-Za-z0-9_\-./]*")
ERRORS = []
WARNINGS = []
INFOS = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNINGS.append(msg)


def info(msg):
    INFOS.append(msg)


def parse_frontmatter(text):
    """极简 frontmatter 解析：key: value + 两空格缩进的二级 key。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, None
    meta = {}
    current = None
    for line in lines[1:end]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  ") and ":" in line and current:
            k, _, v = line.strip().partition(":")
            meta.setdefault(current, {})[k.strip()] = v.strip().strip("\"'")
        elif ":" in line:
            k, _, v = line.partition(":")
            current = k.strip()
            v = v.strip().strip("\"'")
            # 空值先按字典占位（可能是嵌套块的父键），避免二级键写入字符串
            meta[current] = {} if v == "" else v
        else:
            current = None
    return meta, lines[end + 1:]


def check_changelog_dates(skill_dir, cl_text):
    """条目日期必须能在 git 里找到该版本号落笔的那一天。
    2026-10-16 复核实测：33 条里有 8 条与提交日期差一天（0.23–0.29 写 10-14、提交在 10-15；
    0.6.0 写 10-05、提交 10-06）——都是"活干过午夜"留下的。"晚于今天就报错"那道闸
    拦不住这种差一天，所以反向也要有判据。
    只核对提交信息里写了 v<版本号> 的版本；没写的（纯文档轮、合并提交）跳过——
    判据不能假定每个仓库都用同一种提交习惯，否则校验器会把自己锁死。"""
    entries = re.findall(
        r"^##\s*\[?(\d+\.\d+\.\d+)\]?\s*[-–—]?\s*(\d{4}-\d{2}-\d{2})", cl_text, re.M)
    if not entries:
        return
    try:
        proc = subprocess.Popen(
            ["git", "log", "--pretty=%ad|%s", "--date=short"], cwd=skill_dir,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        out = proc.communicate(timeout=30)[0].decode("utf-8", "replace")
        if proc.returncode != 0:
            info("CHANGELOG 日期未与 git 核对（这里不是 git 仓库）")
            return
    except Exception:
        info("CHANGELOG 日期未与 git 核对（git 不可用）")
        return
    by_ver = {}
    for line in out.splitlines():
        if "|" not in line:
            continue
        day, subj = line.split("|", 1)
        m = re.search(r"v(\d+\.\d+\.\d+)", subj)
        if m:
            by_ver.setdefault(m.group(1), set()).add(day)
    bad, checked, skipped = [], 0, 0
    for ver, day in entries:
        days = by_ver.get(ver)
        if not days:
            skipped += 1
            continue
        checked += 1
        if day not in days:
            bad.append("%s 写 %s，git 里是 %s" % (ver, day, "/".join(sorted(days))))
    if bad:
        err("CHANGELOG 有 %d 条日期不在该版本的 git 提交日期里：%s ——条目日期只取该版本号"
            "落笔那天，跨午夜就把条目跟着改到实际那天" % (len(bad), "；".join(bad)))
    else:
        info("CHANGELOG 日期与 git 提交日期一致（核对 %d 条，跳过 %d 条提交信息未带版本号）"
             % (checked, skipped))


def check_frontmatter(skill_dir, text):
    meta, _ = parse_frontmatter(text)
    if meta is None:
        err("SKILL.md 缺少可解析的 frontmatter（首行应为 --- 且有配对闭合）")
        return None
    name = meta.get("name", "")
    desc = meta.get("description", "")
    if not name:
        err("frontmatter 缺少 name")
    else:
        if len(name) > 64:
            err("name 超过 64 字符（规范上限）")
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
            warn("name 含大写/下划线/中文（agentskills.io 规范要求小写 kebab-case；"
                 "部分宽松解析器可接受，跨平台分发前建议确认）")
        dir_name = os.path.basename(os.path.abspath(skill_dir))
        if dir_name != name:
            warn("目录名 %r 与 name %r 不一致（规范要求一致）" % (dir_name, name))
    if not desc:
        err("frontmatter 缺少 description（description 是触发的唯一依据，必填）")
    else:
        if len(desc) > 1024:
            err("description %d 字符，超过 1024 上限——Codex/Copilot 会静默丢弃整个条目（比截断更危险）" % len(desc))
        else:
            info("description %d 字符（≤1024 ✓）" % len(desc))
        # 部分客户端（Claude Code）对 description+when_to_use 合计在 ~1536 字符处截断
        wtu = meta.get("when_to_use", "")
        if wtu and len(desc) + len(wtu) > 1536:
            warn("description+when_to_use 合计 %d 字符，超过约 1536 的截断阈值，"
                 "关键触发信息请放前面" % (len(desc) + len(wtu)))
        # Qoder CN 实测（2026-10-07，让新会话逐字抄回清单条目）：技能清单把每条 entry
        # 截断在约 299 字符，entry 文本 = description + " - " + when_to_use。
        # 超出的尾部对会话完全不可见——触发词写在后面等于没写。
        entry_len = len(desc) + (len(wtu) + 3 if wtu else 0)
        if entry_len > 299:
            warn("清单 entry（description+when_to_use）合计 %d 字符，超过 Qoder CN 实测的"
                 "约 299 字符截断预算，尾部 %d 字符不会被会话看到；"
                 "把竞争定位与触发词放进前 299 字符，或压缩后重跑 evals/trigger-tests.md"
                 % (entry_len, entry_len - 299))
        else:
            info("清单 entry %d 字符（≤299 Qoder CN 截断预算 ✓）" % entry_len)
    unknown = [k for k in meta if k not in RECOGNIZED_KEYS | TOLERATED_KEYS]
    if unknown:
        warn("未识别的 frontmatter 字段：%s（不同平台可能忽略）" % ", ".join(unknown))
    return meta


def check_ledger_versions(skill_dir, cl_text):
    """第 25 项：台账的版本条目**不得重复**、CHANGELOG 必须**按版本降序**（E36）。

    为什么加这一项：**E35 的台账脚本跑了两遍** ⇒ CHANGELOG 里出现了**两份一模一样的
    v0.69.0 条目**、验收记录里也出现了两份 ⇒ 而**没有任何一道闸发现它**
    （日期核对只看日期、"版本与 CHANGELOG 一致"只看最新那个）⇒
    也就是说：**台账自己可以在无人察觉的情况下被写坏**。

    覆盖面：CHANGELOG 的版本标题、验收记录的版本小节、交接文档规划表里的版本行
    ⇒ 三处台账里"同一个版本出现两次"一律报错。
    """
    def dups_of(vs):
        return sorted(set(v for v in vs if vs.count(v) > 1))

    vers = re.findall(r"^##\s*\[?(\d+\.\d+\.\d+)\]?", cl_text, re.M)
    if not vers:
        return None
    for v in dups_of(vers):
        err(u"CHANGELOG 有 **%d 份 v%s 条目**——台账脚本跑了两遍就会留下这种，"
            u"而它此前**无人能发现**；删掉多余的那份" % (vers.count(v), v))
    keys = [tuple(int(x) for x in v.split(".")) for v in vers]
    for i in range(1, len(keys)):
        if keys[i] > keys[i - 1]:
            err(u"CHANGELOG 的版本条目不是降序（新版本在前）：v%s 出现在 v%s 之后"
                % (vers[i], vers[i - 1]))
            break

    acc = os.path.join(skill_dir, "evals", "audit-acceptance.md")
    if os.path.isfile(acc):
        with io.open(acc, "r", encoding="utf-8", errors="replace") as f:
            acc_vers = re.findall(r"^##\s*v(\d+\.\d+\.\d+)", f.read(), re.M)
        for v in dups_of(acc_vers):
            err(u"验收记录 `evals/audit-acceptance.md` 有 **%d 份 v%s 小节**——"
                u"台账脚本跑了两遍就会留下这种" % (acc_vers.count(v), v))

    hand = os.path.join(skill_dir, "docs", "jiangzuo", "handover.md")
    if os.path.isfile(hand):
        with io.open(hand, "r", encoding="utf-8", errors="replace") as f:
            hlines = f.read().split("\n")
        # ⚠️ **按表分块**查重：交接文档 §11 里有**多张规划表**（十轮 / 后续五轮 / 下一轮），
        #    同一轮**合法地**出现在两张表里（E20–E24 就在十轮表与后续五轮表各出现一次）
        #    ⇒ 全文件查重会**误报** ⇒ 只在**同一张表内**查重
        #    （E36 台账脚本跑两遍时，同一行被塞进**同一张表**两次 ⇒ 仍会被逮到）。
        block = []
        for line in hlines + [""]:
            if line.startswith("|"):
                block.append(line)
                continue
            if block:
                vs = re.findall(r"^\|\s*\*\*E\d+\*\*[^\n|]*\|\s*v(\d+\.\d+\.\d+)\s*\|",
                                "\n".join(block), re.M)
                for v in dups_of(vs):
                    err(u"交接文档规划表有 **%d 行 v%s**（同一张表内）——"
                        u"台账脚本跑了两遍就会留下这种" % (vs.count(v), v))
                block = []

    if not dups_of(vers) and all(keys[i] <= keys[i - 1] for i in range(1, len(keys))):
        info(u"CHANGELOG 的 %d 个版本条目无重复且按降序 ✓（验收记录与交接文档同查）" % len(vers))
    return True


def check_refs(skill_dir, body):
    refs = sorted(set(REF_RX.findall(body)))
    missing = []
    for ref in refs:
        if "\\" in ref:
            err("路径含 Windows 反斜杠（跨平台会失效）：%s" % ref)
            continue
        if not os.path.isfile(os.path.join(skill_dir, ref.replace("/", os.sep))):
            missing.append(ref)
    if missing:
        for m in missing:
            err("引用的文件不存在：%s" % m)
    else:
        info("正文引用的 %d 个文件全部存在，路径为正斜杠 ✓" % len(refs))
    return refs


def check_one_level(skill_dir, refs):
    """阅读链保持一层深：分册不再引用其他分册。
    分册指向 templates/ 与 scripts/ 是正常用法（模板是复制使用的产物，
    脚本是执行的产物，不会形成递归阅读链），不算违规。"""
    deep = []
    for ref in refs:
        if not ref.startswith("references/"):
            continue
        path = os.path.join(skill_dir, ref.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for inner in set(REF_RX.findall(content)):
            if inner.startswith("references/") and inner != ref:
                deep.append("%s → %s" % (ref, inner))
    if deep:
        warn("分册之间互相引用形成阅读链（建议一层深，必要时由 SKILL.md 统一路由）：%s"
             % "; ".join(deep))
    else:
        info("分册间无嵌套阅读链（一层深 ✓）")


def check_scripts(skill_dir):
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return
    found = False
    for fn in sorted(os.listdir(scripts_dir)):
        if not fn.endswith(".py"):
            continue
        found = True
        path = os.path.join(scripts_dir, fn)
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        try:
            compile(src, fn, "exec")
        except SyntaxError as e:
            err("脚本语法错误：%s（%s）" % (fn, e))
    if found:
        info("scripts/ 下全部 Python 脚本语法可编译 ✓")


def check_booklet_contract(skill_dir):
    """分册骨架契约（K-Dense 模式：一致性靠校验器不靠约定）。
    references/*.md 必须含 何时读/产出/CRITICAL 防跳步行（缺一即错），
    建议含 前置 与「常见错误」节（缺失警告）；超过 160 行警告。"""
    import glob
    refs = sorted(glob.glob(os.path.join(skill_dir, "references", "*.md")))
    if not refs:
        return
    problems = []
    for path in refs:
        name = os.path.basename(path)
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        n_lines = len(content.splitlines())
        for must, label in (("何时读", "何时读"), ("产出**", "产出"),
                            ("CRITICAL：读完全册再动手", "CRITICAL 防跳步行")):
            if must not in content:
                problems.append((name, "%s 缺失（骨架契约）" % label, True))
        if "前置" not in content:
            problems.append((name, "缺 前置 行（建议）", False))
        if "## 常见错误" not in content:
            problems.append((name, "缺「常见错误」节（建议）", False))
        if n_lines > 160:
            problems.append((name, "%d 行超过 160 行上限" % n_lines, False))
    if problems:
        for name, msg, hard in problems:
            (err if hard else warn)("分册 %s：%s" % (name, msg))
    else:
        info("17 项分册骨架契约全部满足（何时读/前置/产出/CRITICAL/常见错误/行数） ✓"
             if len(refs) == 17 else
             "%d 本分册骨架契约全部满足 ✓" % len(refs))


# SKILL.md 正文预算：入口每次进上下文，超了就等于把成本推给所有任务
BODY_TOKEN_BUDGET = 5000


def estimate_tokens(text):
    """粗略 token 估算：CJK 字符约 1 token/字，其余约 4 字符/token。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text))
    return cjk + (len(text) - cjk) // 4


def print_stats(skill_dir):
    """占用报告：常驻成本（SKILL.md 全文）与按需成本（分册）分开计量。"""
    import glob
    print("\n# 占用报告（估算 token：CJK≈1/字，ASCII≈4 字符/token）\n")

    skill_md = os.path.join(skill_dir, "SKILL.md")
    with io.open(skill_md, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    idx = text.index("\n---", 4) if text.startswith("---") else 0
    front, body = (text[:idx + 4], text[idx + 4:]) if idx else ("", text)
    meta, _ = parse_frontmatter(text)
    print("常驻（每次触发都进上下文）:")
    print("  SKILL.md 全文    ~%5d tokens（frontmatter ~%d + 正文 ~%d）"
          % (estimate_tokens(text), estimate_tokens(front), estimate_tokens(body)))
    if meta:
        print("  description      ~%5d tokens" % estimate_tokens(meta.get("description", "")))
        if meta.get("when_to_use"):
            print("  when_to_use      ~%5d tokens" % estimate_tokens(meta.get("when_to_use", "")))

    refs = sorted(glob.glob(os.path.join(skill_dir, "references", "*.md")))
    if refs:
        rows = []
        for p in refs:
            with io.open(p, "r", encoding="utf-8", errors="replace") as f:
                rows.append((os.path.basename(p), estimate_tokens(f.read())))
        rows.sort(key=lambda r: -r[1])
        total = sum(est for _, est in rows)
        print("\n按需（进入对应阶段才读取）: references/ 共 %d 本，合计 ~%d tokens" % (len(rows), total))
        for name, est in rows[:5]:
            print("  最大 %-30s ~%5d tokens" % (name, est))
        if rows:
            print("  典型任务读取 1-3 本 ≈ %d-%d tokens" % (rows[0][1], sum(e for _, e in rows[:3])))


def _count_builtin_rules(skill_dir):
    """数 scripts/audit-rules/*.json 里的规则条目与其中 `enabled: false` 的条数。
    返回 (总数, 停用数)；没有规则目录时返回 (None, None)——没有就不判，别把校验器锁死。"""
    d = os.path.join(skill_dir, "scripts", "audit-rules")
    if not os.path.isdir(d):
        return None, None
    total = disabled = 0
    for fn in sorted(os.listdir(d)):
        if not fn.endswith(".json"):
            continue
        try:
            with io.open(os.path.join(d, fn), "r", encoding="utf-8") as f:
                doc = json.load(f)
        except (OSError, ValueError):
            return None, None
        for rule in doc.get("rules") or []:
            total += 1
            if rule.get("enabled") is False:
                disabled += 1
    return total, disabled


README_FILES = (("README.md", "zh"), ("README.en.md", "en"))

# 每个指标的中/英两种写法（外加"概念词"：写了概念却写不出数字 ⇒ 报错）。
# ⇒ 两个门面都有人守（E36：英文门面曾停在 v0.3x 遗物状态，写着 4 个脚本 / 222 行 /
#    373 字符，而且整条安全审计链主线一个字没提）。
README_FORMS = {
    "booklets": (r"(\d+)\s*本分册", r"(\d+)\s*booklets", u"本分册", u"booklets"),
    "templates": (r"(\d+)\s*个填空即用模板", r"(\d+)\s*fill-in templates",
                  u"填空即用模板", u"fill-in templates"),
    "scripts": (r"(\d+)\s*个纯标准库脚本", r"(\d+)\s*stdlib-only scripts",
                u"纯标准库脚本", u"stdlib-only scripts"),
    "rules": (u"内置规则库：(\d+)\s*条声明式规则(?:（含\s*(\d+)\s*条数据停用）)?",
              r"(\d+)\s*declarative rules(?:\s*\((\d+)\s*disabled by data\))?",
              u"声明式规则", u"declarative rules"),
    "entry_lines": (u"SKILL\.md\s*正文\s*(\d+)\s*行", r"SKILL\.md body is (\d+) lines",
                    u"SKILL.md 正文", u"SKILL.md body is"),
    "desc_chars": (u"description\s*(\d+)\s*字符", r"description is (\d+) chars",
                   u"description", u"description is"),
    "entry_chars": (u"entry 合计 (\d+)", r"manifest entry (\d+) chars",
                    u"entry 合计", u"manifest entry"),
}


def _readme_truth(skill_dir):
    """门面上的数字各自的**唯一真源**（全部现场可算，不手抄）。"""
    truth = {}
    for key, folder, suffix in (("booklets", "references", ".md"),
                                ("templates", "templates", ".md"),
                                ("scripts", "scripts", ".py")):
        path = os.path.join(skill_dir, folder)
        truth[key] = (len([f for f in os.listdir(path) if f.endswith(suffix)])
                      if os.path.isdir(path) else None)
    truth["rules"] = _count_builtin_rules(skill_dir)
    # 入口行数：**正文行数**（frontmatter 之后）—— 500 上限约束的是正文，不是文件总行数。
    # ⚠️ E36 实测：旧实现拿**总行数**当真源 ⇒ README 只好写"212 行（上限 500）"，
    #    而**说真话**（201 行）反而会被判错 ⇒ **一道在逼人说假话的锁**。
    entry = os.path.join(skill_dir, "SKILL.md")
    if os.path.isfile(entry):
        with io.open(entry, "r", encoding="utf-8", errors="replace") as f:
            meta, rest = parse_frontmatter(f.read())
        if rest is not None:
            truth["entry_lines"] = len(rest)
            desc = (meta or {}).get("description", "")
            wtu = (meta or {}).get("when_to_use", "")
            truth["desc_chars"] = len(desc) if desc else None
            truth["entry_chars"] = (len(desc) + (len(wtu) + 3 if wtu else 0)) if desc else None
    return truth


def check_readme_counts(skill_dir):
    """README（**中英两个门面**）声明的计数/预算必须与实物一致。

    文档计数滞后是接手者踩的第一个坑（本仓库曾把"4 个脚本"写了两个版本），
    所以这条做成机器检查，而不是靠人记得改。

    ⚠️ E36 三处修正：
      ① **两个门面都要查** —— 英文 README 曾停在 v0.3x 遗物状态（4 个脚本 / 222 行 / 373 字符），
         而它恰恰是英文读者与 skills.sh 生态看到的那一面 ⇒ 只查中文门面 = 门面的另一半没人守。
      ② **入口行数的真源是"正文行数"** —— 500 上限约束的是正文（frontmatter 之后），
         旧实现拿文件总行数当真源 ⇒ README 只好写总行数 ⇒ **一道在逼人说假话的锁**。
      ③ **description / 清单 entry 的字符数也纳入对账**（之前完全没人管）。
    """
    truth = _readme_truth(skill_dir)
    if not truth:
        return
    bad, seen, unparsable = [], {}, []
    for rel, lang in README_FILES:
        path = os.path.join(skill_dir, rel)
        if not os.path.isfile(path):
            continue
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        for key, forms in README_FORMS.items():
            rx_zh, rx_en, concept_zh, concept_en = forms
            rx = rx_zh if lang == "zh" else rx_en
            concept = concept_zh if lang == "zh" else concept_en
            m = re.search(rx, text)
            if not m:
                # ⚠️ **不许静默跳过**（E34 实测）：README 里写着「{{SCRIPTS}} 个纯标准库脚本」
                # 这种**占位符顶掉了数字**的情况时，正则匹配不上 ⇒ 老代码 `continue` 跳过
                # ⇒ 这道闸**因为解析不到而变成永远绿** ⇒ 那比没有闸更坏（它还让人以为有人管）。
                # ⇒ 声明了概念却写不出数字 ⇒ 报错。
                #    ⚠️ 但**根本没提这个概念**的门面不该被要求写 ⇒ 按概念词判。
                if concept in text:
                    unparsable.append(u"%s 的「%s」" % (rel, key))
                continue
            seen.setdefault(key, []).append(rel)
            if key == "rules":
                total, disabled = truth.get("rules") or (None, None)
                if total is None:
                    continue
                wrong = []
                if int(m.group(1)) != total:
                    wrong.append(u"总条数写 %s、实际 %s" % (m.group(1), total))
                if m.group(2) and int(m.group(2)) != disabled:
                    wrong.append(u"停用数写 %s、实际 %s" % (m.group(2), disabled))
                if wrong:
                    bad.append((key, u"%s 规则条数与实物不符：%s" % (rel, u"；".join(wrong))))
                continue
            actual = truth.get(key)
            if actual is None:
                continue
            if int(m.group(1)) != actual:
                bad.append((key, u"%s 写 %s=%s，实际 %s" % (rel, key, m.group(1), actual)))
    for who in unparsable:
        err(u"README 声明了 %s 却**写不出数字**（占位符顶掉了？写法变了？）——"
            u"**不许因为解析不到就静默跳过**：那等于这道闸自己失效了" % who)
    for key, msg in bad:
        if key in ("booklets", "templates", "scripts"):
            warn(u"README 计数与实物不符：%s —— 增删文件时同步改两个门面" % msg)
        else:
            err(u"README 与实物不符：%s —— 增删文件/改入口时同步改两个门面" % msg)
    for key, label in (("booklets", u"分册"), ("templates", u"模板"), ("scripts", u"脚本")):
        if key in seen:
            info(u"README 计数与实物一致（%s ✓，已核 %d 个门面）" % (label, len(seen[key])))
    if "rules" in seen:
        total, disabled = truth.get("rules") or (0, 0)
        info(u"README 规则条数与实物一致（%d 条，停用 %d ✓，已核 %d 个门面）"
             % (total, disabled, len(seen["rules"])))
    if "entry_lines" in seen:
        info(u"README 入口行数与实物一致（SKILL.md 正文 %d 行 ✓，已核 %d 个门面）"
             % (truth.get("entry_lines") or 0, len(seen["entry_lines"])))
    if "desc_chars" in seen or "entry_chars" in seen:
        info(u"README 的 description/清单 entry 字符数与实物一致"
             u"（description %d 字符、entry %d 字符 ✓，已核 %d 个门面）"
             % (truth.get("desc_chars") or 0, truth.get("entry_chars") or 0,
                len(seen.get("desc_chars", []) + seen.get("entry_chars", []))))


def check_lookup_aliases(skill_dir):
    """每本分册都必须登记进 lookup 的路由词表。

    实测教训：BOOKLET_ALIASES 写了却从没被打分用过，新分册也没登记——
    等于检索层看不见它。加了分册忘了登记，这种漂移只能靠机器拦。
    """
    lookup_py = os.path.join(skill_dir, "scripts", "lookup.py")
    ref_dir = os.path.join(skill_dir, "references")
    if not (os.path.isfile(lookup_py) and os.path.isdir(ref_dir)):
        return
    with io.open(lookup_py, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    if "BOOKLET_ALIASES" not in text:
        warn("scripts/lookup.py 里没有 BOOKLET_ALIASES 路由词表")
        return
    missing = [n for n in sorted(os.listdir(ref_dir))
               if n.endswith(".md") and ("references/" + n) not in text]
    if missing:
        warn("%d 本分册未登记进 lookup 路由词表：%s —— 检索层找不到它们，agent 只能整册读"
             % (len(missing), ", ".join(missing)))
    else:
        info("分册全部登记进 lookup 路由词表 ✓")


def _gfm_cells(line):
    """按 **GFM 规则**把一行表格切成单元格。

    ⚠️ **未转义的 `|` 才是分隔符**；`\\|` 是转义（渲染成字面的竖线）⇒ 不能算。
    这一条不是吹毛求疵：`ls scripts/*.py \\| wc -l` 这种写法**在 Markdown 里是合法的**
    （GFM 明确要求竖线要转义），而按朴素计数它会被算成多一列 ⇒ 判据会**误伤正确的写法**。
    """
    parts = []
    cur = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c == "\\" and i + 1 < n and line[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if c == "|":
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(c)
        i += 1
    parts.append("".join(cur))
    if parts and not parts[0].strip():
        parts = parts[1:]
    if parts and not parts[-1].strip():
        parts = parts[:-1]
    return parts


def _is_sep_row(line):
    """是不是表格的**分隔行**（`|---|---|`）——只有它 + 表头才构成一张表。"""
    st = line.strip()
    if not st.startswith("|"):
        return False
    return bool(re.match(r"^\|[\s:\-\|]+\|?$", st))


def check_md_tables(skill_dir):
    """三条文档结构判据（都是我自己踩出来的）：
    ① **表格行头不许被吃**——插行时拿下一行的行头当锚点又忘了写回，
       结果那一行还是 `a | b | c` 的形状、只是开头少了 `| `；Markdown 会把它当普通段落，
       人眼扫过去常常看不见。这个毛病在记忆里写过四次，2026-10-16 又犯一次，所以变成判据。
       只认"**紧邻表格行的下一行**长得像表格行却没有行头"，避免把正文里的 `a | b` 误伤。
    ② **"上表 N 条"要数得出 N**——账本条数我手抄错过一次（写 27、实 28）。
       只在"该文件恰好一张表"时判；多表文件不猜形状。
    ③ **表内每行的列数必须与表头一致**（E38）——**列数错了，表格就废了**：
       Markdown 会把多出来的列**丢弃**、把少掉的列**补空** ⇒ 读者看到的字段顺序与表头对不上，
       而**人眼扫一排表格根本看不出**（一格宽一格窄而已）。
       ⚠️ 判据要按 **GFM 规则**数列（`\\|` 是转义、不算分隔符），
       否则会把 `ls scripts/*.py \\| wc -l` 这种**合法**写法误判成多一列。
       ⚠️ 只对"**有表头 + 分隔行**"的表块判：孤立的 `| a | b |` 段落**不是表**（GFM 如此），
       判它就是误伤。"""
    import glob
    bad = []
    scanned = 0
    for path in sorted(glob.glob(os.path.join(skill_dir, "**", "*.md"), recursive=True)):
        norm = os.path.abspath(path)
        if (os.sep + ".git" + os.sep) in norm or "__pycache__" in norm:
            continue
        rel = os.path.relpath(path, skill_dir).replace(os.sep, "/")
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        scanned += 1
        fence = False
        prev_row = False
        blocks = []            # 每张表一个元素：该表的总行数（含表头与分隔行）
        table_blocks = []      # ③ 用：每块一行一行存 [(行号, 原文)]
        for i, line in enumerate(lines, 1):
            st = line.strip()
            if st.startswith("```"):
                fence = not fence
                prev_row = False
                continue
            if fence:
                prev_row = False
                continue
            if st.startswith("|"):
                if not st.endswith("|"):
                    bad.append(u"%s:%d 表格行缺行尾 `|`：%s" % (rel, i, st[:40]))
                if not prev_row:
                    blocks.append(0)
                    table_blocks.append([])
                blocks[-1] += 1
                table_blocks[-1].append((i, line))
                prev_row = True
                continue
            if prev_row and st.count("|") >= 2:
                bad.append(u"%s:%d 表格行**行头被吃**（少了开头的 `| `）：%s"
                           % (rel, i, st[:40]))
            if st:
                prev_row = False
        # ③ 列数一致：**只对"有表头 + 分隔行"的表块判**（孤立的 `| a | b |` 不是表）
        for blk in table_blocks:
            if len(blk) < 3 or not _is_sep_row(blk[1][1]):
                continue
            width = len(_gfm_cells(blk[0][1]))
            for ln, raw in blk:
                n = len(_gfm_cells(raw))
                if n == width:
                    continue
                if n > width:
                    bad.append(u"%s:%d 这一行有 **%d 个单元格**，表头只有 %d 个——"
                               u"多出来的分隔符多半是**内容里的 `|` 没转义**（GFM 里要写成 `\\|`）"
                               % (rel, ln, n, width))
                else:
                    bad.append(u"%s:%d 这一行只有 **%d 个单元格**，表头有 %d 个——"
                               u"少掉的列会让 Markdown 把它**补空** ⇒ 读者看到的字段顺序与表头对不上"
                               % (rel, ln, n, width))
        # ② 声明条数对账：只在"该文件恰好一张表"时判，多表文件不猜形状
        if len(blocks) == 1:
            data_rows = max(0, blocks[0] - 2)      # 去掉表头与分隔行
            for i, line in enumerate(lines, 1):
                m = re.search(u"上表\\s*(\\d+)\\s*条", line)
                if m and int(m.group(1)) != data_rows:
                    bad.append(u"%s:%d 声明「上表 %s 条」，表里实际 %d 条数据行——"
                               u"条数要数出来，别手抄"
                               % (rel, i, m.group(1), data_rows))
    if bad:
        for msg in bad:
            err(msg)
    elif scanned:
        info("文档结构核对通过（%d 个 .md：表格行头完整、**表内列数一致**、声明条数与实物一致）" % scanned)


def _md_fenced_lines(skill_dir):
    """产出仓库内所有 .md **围栏代码块**里的行：(相对路径, 行号, 原文)。

    只取代码块：代码块 = "复制即跑"的**契约**，里面的期望值错了，照着跑的人
    会以为工具挂了；正文与表格里的历史数字是**当时真值**（交付报告 §3 的
    "Ran 124 tests" 是 v0.36.1 当时的数），不该被红。
    """
    import glob
    for path in sorted(glob.glob(os.path.join(skill_dir, "**", "*.md"), recursive=True)):
        norm = os.path.abspath(path)
        if (os.sep + ".git" + os.sep) in norm or "__pycache__" in norm:
            continue
        rel = os.path.relpath(path, skill_dir).replace(os.sep, "/")
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.read().splitlines()
        fence = None
        for i, line in enumerate(lines, 1):
            st = line.strip()
            m = re.match(r"^(`{3,}|~{3,})", st)
            if m:
                mark = m.group(1)[0]
                if fence is None:
                    fence = mark
                elif mark == fence:
                    fence = None
                continue
            if fence is not None:
                yield rel, i, line


def _corpus_list_lengths(skill_dir):
    """AST 静态解析 gen_corpus.py 的 MUST_FIND / MUST_NOT_FIND 长度。

    **不执行脚本**（那会往磁盘写语料），只用 ast.literal_eval 取字面量长度。
    这两个清单与 expected.json 是严格 1:1（gen_corpus 每个条目生成一条答案，
    probe 定位不到时它自己 exit 1），所以静态长度就是运行时真值。
    取不到返回 (None, None)——调用方按"无法判定"处理，不假装通过。
    """
    import ast
    path = os.path.join(skill_dir, "evals", "audit-fixtures", "gen_corpus.py")
    if not os.path.isfile(path):
        return None, None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=path)
    except (OSError, ValueError, SyntaxError):
        return None, None
    found = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for t in node.targets:
            if isinstance(t, ast.Name) and t.id in ("MUST_FIND", "MUST_NOT_FIND"):
                try:
                    found[t.id] = len(ast.literal_eval(node.value))
                except (ValueError, SyntaxError, TypeError):
                    return None, None
    return found.get("MUST_FIND"), found.get("MUST_NOT_FIND")


def _expected_truth(skill_dir):
    """期望值的**唯一真源**。全部静态取：不跑扫描、不生成语料、不执行被测脚本。

    ⇒ 跨平台同色、秒级完成（E6 的教训：锁不能自己平台依赖）。
    """
    truth = {}
    # ① 测试用例数：只加载不执行（countTestCases 不跑 setUp 与用例本体）
    tests_dir = os.path.join(skill_dir, "tests")
    truth["tests"] = None
    if os.path.isdir(tests_dir):
        try:
            import unittest
            import warnings
            saved = list(sys.path)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                loader = unittest.TestLoader()
                suite = loader.discover(tests_dir, top_level_dir=tests_dir)
                truth["tests"] = suite.countTestCases()
            sys.path[:] = saved
        except Exception:
            truth["tests"] = None
    # ② 语料分母
    truth["must_find"], truth["must_not_find"] = _corpus_list_lengths(skill_dir)
    # ③ 规则条数（复用已有 helper）
    total, disabled = _count_builtin_rules(skill_dir)
    truth["rules_active"] = None if total is None else total - disabled
    truth["rules_disabled"] = disabled
    return truth


# 三类"复制即跑"的期望值形态：(键, 正则, 给人看的名字, 真源键)
EXPECT_FORMS = (
    (u"tests", re.compile(r"Ran\s+(\d+)\s+tests?\b"), u"Ran N tests", u"tests"),
    (u"corpus", re.compile(r"ACCEPT-OK\s+(\d+)/(\d+)\s*检出.*?0/(\d+)\s*安全样本"),
     u"ACCEPT-OK A/B 检出 & 0/C 安全样本", u"must_find"),
    (u"rules", re.compile(r"RULES-OK[（(]\s*(\d+)\s*条，另有\s*(\d+)\s*条数据停用[）)]"),
     u"RULES-OK（N 条，另有 M 条数据停用）", u"rules_active"),
)


def check_expected_numbers(skill_dir):
    """「照着跑就能看到」的期望值必须与实物一致（第 11 节第 9 项）。

    E7 实测的教训：验收记录里"本仓库自扫 结论 0"这个**对照面基线**从 v0.37.0 起
    就一直是错的，错了一整轮没人发现——因为**没有任何判据把文档里的数字和实物对账**。
    错的是基线，所以它不会让任何检出看起来更好，只会让人拿一把坏尺子量别人。

    本项把三类期望值接上唯一真源：
      ① 测试用例数 ← unittest 的用例计数（只加载不执行）
      ② 语料分母   ← gen_corpus.py 的 MUST_FIND / MUST_NOT_FIND 长度（AST 静态解析）
      ③ 规则条数   ← scripts/audit-rules/*.json 的条目数与停用数

    另外两件同样重要的事：
      · **形态要写全**——一个 .md 文件只要声明了期望值，就得把适用的形态写齐；
        少一种，这一项就静默失效了（等于没有检查）。**按文件判，不按仓库判**：
        一个没写期望值的文件不该被要求写（判据不许假定数据形状——§10A 第 11 条）。
      · **取不到真源不放过**——真源取不到时报错，不当"没问题"处理。
    """
    truth = _expected_truth(skill_dir)
    per_file = {}
    bad = []
    for rel, lineno, line in _md_fenced_lines(skill_dir):
        for kind, rx, _label, _src in EXPECT_FORMS:
            m = rx.search(line)
            if not m:
                continue
            per_file.setdefault(rel, set()).add(kind)
            if kind == "tests":
                claimed, real = int(m.group(1)), truth["tests"]
                if real is None:
                    bad.append(u"%s:%d 期望「Ran %d tests」，但用例数取不到（tests/ 目录或"
                               u"测试模块有问题）——真源取不到不等于没问题" % (rel, lineno, claimed))
                elif claimed != real:
                    bad.append(u"%s:%d 期望「Ran %d tests」，实际 %d 个用例——"
                               u"改了测试就要改这行期望值" % (rel, lineno, claimed, real))
            elif kind == "corpus":
                a, b, c = int(m.group(1)), int(m.group(2)), int(m.group(3))
                real_find, real_safe = truth["must_find"], truth["must_not_find"]
                if real_find is None or real_safe is None:
                    bad.append(u"%s:%d 期望「ACCEPT-OK %d/%d 检出 & 0/%d 安全样本」，但语料分母"
                               u"取不到（gen_corpus.py 的清单解析不了）" % (rel, lineno, a, b, c))
                else:
                    if a != b:
                        bad.append(u"%s:%d 期望「%d/%d 检出」——分子分母不等；语料现在有 %d 项应检出"
                                   % (rel, lineno, a, b, real_find))
                    elif b != real_find:
                        bad.append(u"%s:%d 期望「%d/%d 检出」，实际应检出 %d 项——"
                                   u"语料长了/改了要同步这行" % (rel, lineno, a, b, real_find))
                    if c != real_safe:
                        bad.append(u"%s:%d 期望「0/%d 安全样本」，实际安全对照 %d 个——"
                                   u"语料长了/改了要同步这行" % (rel, lineno, c, real_safe))
            elif kind == "rules":
                n, off = int(m.group(1)), int(m.group(2))
                real_on, real_off = truth["rules_active"], truth["rules_disabled"]
                if real_on is None:
                    bad.append(u"%s:%d 期望「RULES-OK（%d 条…）」，但规则库数不到"
                               % (rel, lineno, n))
                else:
                    if n != real_on:
                        bad.append(u"%s:%d 期望「RULES-OK（%d 条…）」，实际活跃 %d 条——"
                                   u"加/停规则要同步这行" % (rel, lineno, n, real_on))
                    if off != real_off:
                        bad.append(u"%s:%d 期望「另有 %d 条数据停用」，实际 %d 条——"
                                   u"停用规则要同步这行" % (rel, lineno, off, real_off))
    # 形态要写全：声明了期望值的文件必须把适用的形态写齐，少一种就等于让这一项静默失效。
    # **按文件判，不按仓库判**：没写期望值的文件不该被要求写（判据不许假定数据形状）。
    for rel in sorted(per_file):
        for kind, _rx, label, src in EXPECT_FORMS:
            if truth.get(src) is None:
                continue
            if kind not in per_file[rel]:
                bad.append(u"%s 声明了部分期望值却缺「%s」——形态不全就等于让这一项"
                           u"静默失效（等于没有检查）" % (rel, label))
    if bad:
        for msg in bad:
            err(msg)
    else:
        info("期望值与实物对账通过（用例数 / 语料分母 / 规则条数，%d 处声明）"
             % sum(len(v) for v in per_file.values()))


def find_replacement_chars(root):
    """找出含 U+FFFD（替换字符 = 被损坏的字符）的文本文件。

    E15 的由来：E11 收尾时发现 **E10 那轮自己写下的乱码**（`audit-acceptance.md` 里一个
    「同」字变成了 U+FFFD）**溜过了所有判据**——文件照样能跑、结构照样合法、
    数字照样对得上，**只有那个字符坏了**。`validate_skill.py` 查结构、查表格、查期望值，
    唯独不查"字符有没有坏"。

    返回 (坏处列表, 扫过的文件数)。坏处 = (相对路径, 行号, 该行摘要)。
    """
    suffixes = (".md", ".py", ".json", ".yml", ".yaml", ".txt", ".sh", ".ps1", ".cfg")
    bad = []
    scanned = 0
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "__pycache__", "node_modules", ".venv")]
        for fn in filenames:
            if not fn.endswith(suffixes):
                continue
            path = os.path.join(dirpath, fn)
            try:
                with io.open(path, encoding="utf-8") as f:
                    for i, line in enumerate(f, 1):
                        if chr(0xFFFD) in line:
                            bad.append((os.path.relpath(path, root), i,
                                        line.strip()[:80]))
            except (OSError, UnicodeDecodeError):
                continue
            scanned += 1
    return bad, scanned


def check_no_replacement_chars(skill_dir):
    """第 18 项：入库文本文件里不许有 U+FFFD 替换字符（E15）。"""
    bad, scanned = find_replacement_chars(skill_dir)
    if bad:
        for rel, lineno, text in bad[:10]:
            err(u"文件 %s:%d 含 U+FFFD 替换字符（字符坏了）：%s"
                % (rel, lineno, text))
        err(u"共 %d 处 U+FFFD——上一轮自己写下的乱码就是这么溜过去的"
            % len(bad))
    else:
        info(u"入库文本文件里没有 U+FFFD 替换字符（扫了 %d 个文件）" % scanned)



STDLIB_OK = {"argparse", "ast", "collections", "functools", "glob", "hashlib",
             "importlib", "io", "itertools", "json", "os", "pathlib", "platform",
             "random", "re", "shutil", "stat", "subprocess", "sys", "tempfile",
             "time", "typing"}


def _mut_case_count(src):
    """静态数出校准器的 CASES 条数（**不执行**被测脚本）。"""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Name) and t.id == "CASES":
                    try:
                        return len(node.value.elts)
                    except AttributeError:
                        return None
    return None


def _mut_imports(src):
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return set()
    mods = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                mods.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def check_mut_calibrator(skill_dir):
    """第 19 项：变异校准器必须随技能一起分发，且**例数不许手抄**（E24）。

    为什么要有这项：校准例数是**写进 CHANGELOG / 验收记录 / 台账的数字**，
    而它会随用例增删变——E19–E23 连续五轮把它**手数错了**（各差 1），
    而"手数"正是本项目明令禁止的（数字只从真实命令输出抄）。
    现在这条数字**从实物数出来**：CHANGELOG 最新条目写 N/N，N 必须等于
    `scripts/mut_calibrate.py` 里 CASES 的条数，写错就当场红。
    """
    path = os.path.join(skill_dir, "scripts", "mut_calibrate.py")
    repo_root = os.path.abspath(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), ".."))
    if os.path.abspath(skill_dir) != repo_root:
        # 被检的**不是将作自己** ⇒ 本项不适用：别的技能不需要带**我们的**校准器。
        # ⚠️ 同一个坑吃过一次：形态完整性第一版**按仓库判**，把一个合法的最小技能
        # 目录判死了 ⇒ 改成**按事实判**。这里同理。
        return None
    if not os.path.isfile(path):
        err("scripts/mut_calibrate.py 不见了——校准器必须随技能一起分发（E24）")
        return None
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        src = f.read()
    n_cases = _mut_case_count(src)
    if n_cases is None:
        err("scripts/mut_calibrate.py 解析不出 CASES（语法错或结构变了）")
        return None
    extra = sorted(m for m in _mut_imports(src) if m not in STDLIB_OK)
    if extra:
        err("scripts/mut_calibrate.py 依赖了非标准库模块：%s——校准器必须零依赖"
            % ", ".join(extra))
    # CHANGELOG 最新条目里写的 N/N 必须等于实物条数
    changelog = os.path.join(skill_dir, "CHANGELOG.md")
    claimed = None
    if os.path.isfile(changelog):
        with io.open(changelog, "r", encoding="utf-8", errors="replace") as f:
            cl = f.read()
        m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)\]?", cl, re.M)
        if m:
            seg = re.split(r"\n## ", cl[m.end():], 1)[0]
            mm = re.search(r"变异校准\s*\*?\*?(\d+)\s*/\s*(\d+)", seg)
            if mm:
                claimed = (int(mm.group(1)), int(mm.group(2)))
    if claimed is None:
        warn("CHANGELOG 最新条目里没写「变异校准 N/N」——例数对不上账，请补上")
    elif claimed[0] != claimed[1]:
        err("CHANGELOG 写的变异校准 %d/%d 分子分母不等" % claimed)
    elif claimed[0] != n_cases:
        err("CHANGELOG 写「变异校准 %d/%d」，实物是 %d 条用例——数字只能从真实输出抄"
            % (claimed[0], claimed[1], n_cases))
    else:
        info("变异校准器已随技能分发（%d 条用例，零依赖，CHANGELOG 数字与实物一致 ✓）"
             % n_cases)
    return n_cases



HANDOVER_SECTIONS = ("## 0. ", "## 5. ", "## 6. ", "## 8. ", "## 11. ", "## 13. ", "## 14. ")


def _git_tracked(root, rel):
    """文件是否被 git 跟踪。返回 None = 这里不是 git 仓库（不做判断）。"""
    try:
        p = subprocess.Popen(["git", "rev-parse", "--is-inside-work-tree"], cwd=root,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        code = p.wait()
        if code != 0:
            return None
        p = subprocess.Popen(["git", "ls-files", "--error-unmatch", "--", rel], cwd=root,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return p.wait() == 0
    except OSError:
        return None


def check_handover_in_repo(skill_dir):
    """第 20 项：交接文档必须**在仓库内**、章节完整、且被 git 跟踪（E27）。

    为什么加这一项：E26 那轮一个脚本 bug 把**仓库外**的交接文档整段覆盖掉了，
    而它当时不在 git 里 ⇒ **无法回滚**，只能从会话记录里重建（花了整整一轮）。
    ⇒ 根因修复：把它收进仓库（`docs/jiangzuo/handover.md`），并让本项守住三件事：
      ① 它在仓库里（不在的话 ⇒ 一次脚本 bug 就毁掉且没有历史）
      ② 它的关键章节齐全（恢复过程最容易丢的就是章节）
      ③ 它被 git 跟踪（存在但没被跟踪 ⇒ 一样的风险）
    """
    docs_dir = os.path.join(skill_dir, "docs", "jiangzuo")
    if not os.path.isdir(docs_dir):
        return None            # 最小形态技能目录不该被要求带交接文档
    rel = os.path.join("docs", "jiangzuo", "handover.md")
    path = os.path.join(skill_dir, rel)
    if not os.path.isfile(path):
        err("%s 不见了——交接文档必须在仓库内（E27）" % rel.replace(os.sep, "/"))
        return None
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    missing = [h.strip() for h in HANDOVER_SECTIONS if h not in text]
    if missing:
        err("交接文档缺章节：%s（E27：它在仓库内，内容完整是硬要求）" % " ".join(missing))
    tracked = _git_tracked(skill_dir, rel)
    if tracked is False:
        err("交接文档存在但**没被 git 跟踪**（%s）——未跟踪的文件没有历史，"
            "一次脚本 bug 就找不回来（E27）" % rel.replace(os.sep, "/"))
    elif missing:
        pass
    else:
        info("交接文档在仓库内、章节完整、已被 git 跟踪（%d 字符，7 个关键章节 ✓）"
             % len(text))
    # E32：§8 坑位清单的**编号必须连续** —— 它是别人引用「§8 第 N 条」的索引，
    # 缺号会让引用指向错的地方（E32 实测：E22 插入时跳过了 36/37，编号 1..57 只有 55 条）。
    sec8 = re.search(r"##\s*8\.[^\n]*\n(.*?)(?=\n##\s*9\.)", text, re.S)
    if sec8:
        nums = [int(m.group(1)) for m in
                (re.match(r"^(\d+)\.\s", l) for l in sec8.group(1).splitlines()) if m]
        if nums:
            gaps = [k for k in range(nums[0], nums[-1] + 1) if k not in set(nums)]
            if gaps:
                err("交接文档 §8 坑位编号不连续：缺 %s（编号是「§8 第 N 条」的索引，"
                    "缺号会让引用指错）" % "、".join(str(g) for g in gaps))
            elif nums != list(range(nums[0], nums[-1] + 1)):
                err("交接文档 §8 坑位编号乱序（E27 排过一次序，别打乱）")
    return None



def check_verdict_table(skill_dir):
    """第 21 项：结论区判定表必须在仓库内，且**表内自洽**（E28）。

    为什么加这一项：那张表是"误报率口径"的**唯一依据** ⇒ 它一旦不自洽
    （比如有人手改了某一行却没改合计），报出来的口径就在骗人。

    ⚠️ **它只能保证"表内自洽"，不能保证"表与引擎同步"**——后者要真跑一遍扫描
    （validate 全程不跑扫描、不执行被测脚本，这是它的定位）⇒ 所以表头写明了
    「改了规则/引擎就要重判」这条纪律。

    E29 修了两处（都是 E28 遗留的**潜伏缺陷**，因为当时两个数恰好相等而没炸）：
    ① **「flask 等」的条数原来错用了「静态可修」的条数**（变量名 `f_fp` 复用了）
       ⇒ E29 把「静态可修」清零后当场炸出来。
    ② **新增：从 §二 的逐行「归类」反推三类误报的条数**，再和 §三 声明的对账
       ⇒ 手改 §二 某一行却没改 §三（或反之），当场红。
    """
    if not os.path.isdir(os.path.join(skill_dir, "evals")):
        return None            # 没有 evals/ 的目录（最小形态技能 / 反例夹具）不适用本项
    path = os.path.join(skill_dir, "evals", "finding-verdicts.md")
    if not os.path.isfile(path):
        return None            # 表不在（最小形态技能 / 反例夹具）⇒ 本项不适用
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    def grab(rx, n=3):
        m = re.search(rx, text)
        if not m:
            return None
        return tuple(int(m.group(i + 1)) for i in range(n))

    total = grab(r"\*\*合计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*")
    dvwa = grab(r"\*\*DVWA 小计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*")
    # E29 修：这一行原来抓的是「静态可修」的条数，却当成「flask 等」用 ⇒
    # 两个数在 E28 恰好都是 1，所以错了一个月也没露馅。
    flask = grab(r"\|\s*flask[^|]*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|")
    fixable = re.search(r"\| \*\*静态可修\*\*\s*\|\s*(\d+)\s*\|", text)
    upgrade = re.search(r"\| \*\*待能力升级\*\*\s*\|\s*(\d+)\s*\|", text)
    bounded = re.search(r"\| \*\*静态消不掉（能力边界型）\*\*\s*\|\s*(\d+)\s*\|", text)

    # E29 新增：从 §二 的**逐行「归类」列**反推三类误报的条数（从行反推，不信声明）
    buckets = ("静态可修", "待能力升级", "静态消不掉", "已修")
    rows = dict((k, 0) for k in buckets)
    unknown = 0
    sec2 = re.search(r"##\s*二、(.*?)(?=\n##\s*三、)", text, re.S)
    if sec2:
        for line in sec2.group(1).splitlines():
            if not re.match(r"^\|\s*\d+\s*\|", line):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) < 5:
                unknown += 1
                continue
            kind = cells[4]
            hit = None
            for key in buckets:
                if kind.startswith("**%s**" % key):
                    hit = key
                    break
            if hit is None:
                unknown += 1
            else:
                rows[hit] += 1

    problems = []
    if not total or not dvwa or not flask or not (fixable and upgrade and bounded):
        problems.append("判定表的关键数字抓不到（合计 / DVWA 小计 / flask 行 / 三类误报）")
    elif not sec2:
        problems.append("判定表里找不到「## 二、」这一节（逐行对账做不了）")
    else:
        t_all, t_true, t_fp = total
        d_all, d_true, d_fp = dvwa
        f_all, f_true, f_fp = flask
        fixable_n = int(fixable.group(1))
        upgrade_n = int(upgrade.group(1))
        bounded_n = int(bounded.group(1))
        listed = rows["静态可修"] + rows["待能力升级"] + rows["静态消不掉"]
        if t_true + t_fp != t_all:
            problems.append("判定表合计行自相矛盾：真阳性 %d + 误报 %d != 合计 %d"
                            % (t_true, t_fp, t_all))
        if d_true + d_fp != d_all:
            problems.append("DVWA 小计自相矛盾：%d + %d != %d" % (d_true, d_fp, d_all))
        if f_true + f_fp != f_all:
            problems.append("flask 行自相矛盾：%d + %d != %d" % (f_true, f_fp, f_all))
        if d_all + f_all != t_all:
            problems.append("DVWA %d + flask 等 %d != 合计 %d" % (d_all, f_all, t_all))
        if fixable_n + upgrade_n + bounded_n != t_fp:
            problems.append("三类误报之和 %d != 误报合计 %d"
                            % (fixable_n + upgrade_n + bounded_n, t_fp))
        if rows["静态可修"] != fixable_n:
            problems.append("§二 里标「静态可修」的行数 %d != §三 声明的 %d"
                            % (rows["静态可修"], fixable_n))
        if rows["待能力升级"] != upgrade_n:
            problems.append("§二 里标「待能力升级」的行数 %d != §三 声明的 %d"
                            % (rows["待能力升级"], upgrade_n))
        if rows["静态消不掉"] != bounded_n:
            problems.append("§二 里标「静态消不掉」的行数 %d != §三 声明的 %d"
                            % (rows["静态消不掉"], bounded_n))
        if listed != t_fp:
            problems.append("§二 在册误报 %d 条 != 误报合计 %d（已修 %d 条另计）"
                            % (listed, t_fp, rows["已修"]))
        if unknown:
            problems.append("§二 有 %d 行的「归类」列认不出来" % unknown)
        if not problems:
            info("结论区判定表自洽（合计 %d 条 = 真阳性 %d + 误报 %d；三类误报 %d/%d/%d；"
                 "§二 逐行对账 %d 条在册 + %d 条已修）✓"
                 % (t_all, t_true, t_fp, fixable_n, upgrade_n, bounded_n,
                    listed, rows["已修"]))
    for pr in problems:
        err("判定表不自洽：%s" % pr)
    return None


def check_ledger_totals(skill_dir):
    """第 22 项：判定表 §四 的**口径拆解**必须自洽（E32）。

    为什么加这一项：E32 之前，「全部产出」口径的误报率一直是**未判定**，
    而且三份文档各写一个数（20 / 12 / "59 条里有 20 条"）⇒ 互相矛盾。
    E32 把这批逐条判完 ⇒ 现在 §四 有一张机器可读的口径拆解表
    （同目录路过 / 另计语境 / 全部产出）⇒ 它的每个加法都必须成立，
    且「误报」条数必须与 §一 合计行、§三 三类之和**对上**。

    ⚠️ 与第 21 项同源：只保证**表内自洽**，不保证"表与引擎同步"（那要真跑扫描）。
    """
    if not os.path.isdir(os.path.join(skill_dir, "evals")):
        return None
    path = os.path.join(skill_dir, "evals", "finding-verdicts.md")
    if not os.path.isfile(path):
        return None
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()

    def grab(rx):
        m = re.search(rx, text)
        return tuple(int(m.group(i + 1)) for i in range(len(m.groups()))) if m else None

    same_dir = grab(r"\|\s*同目录路过\s*\|\s*(\d+)\s*\|\s*真阳性\s*(\d+)\s*\+\s*误报\s*(\d+)\s*\|")
    other = grab(r"\|\s*另计语境\s*\|\s*(\d+)\s*\|\s*flask\s*(\d+)\s*\+\s*requests\s*(\d+)\s*\|")
    total = grab(r"\|\s*全部产出\s*\|\s*(\d+)\s*\|\s*真阳性\s*(\d+)\s*\+\s*误报\s*(\d+)\s*\+\s*另计\s*(\d+)\s*\|")
    t_fp = grab(r"\*\*合计\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*\*\*(\d+)\*\*")

    problems = []
    if not same_dir or not other or not total or not t_fp:
        problems.append("§四 的口径拆解表抓不到（同目录路过 / 另计语境 / 全部产出）或 §一 合计行抓不到")
    else:
        sd_all, sd_tp, sd_fp = same_dir
        o_all, o_flask, o_req = other
        t_all, t_true, t_fp_num, t_other = total
        total_fp = t_fp[2]
        if sd_all != sd_tp + sd_fp:
            problems.append("同目录路过 %d != 真阳性 %d + 误报 %d" % (sd_all, sd_tp, sd_fp))
        if o_all != o_flask + o_req:
            problems.append("另计语境 %d != flask %d + requests %d" % (o_all, o_flask, o_req))
        if t_all != t_true + t_fp_num + t_other:
            problems.append("全部产出 %d != 真阳性 %d + 误报 %d + 另计 %d"
                            % (t_all, t_true, t_fp_num, t_other))
        if t_other != o_all:
            problems.append("§四 的另计 %d != 另计语境 %d（同一件事不能两个数）"
                            % (t_other, o_all))
        if t_fp_num != total_fp:
            problems.append("§四 的误报 %d != §一 合计行的误报 %d（两份表必须对上）"
                            % (t_fp_num, total_fp))
        if t_true != t_fp[1]:
            problems.append("§四 的真阳性 %d != §一 合计行的真阳性 %d" % (t_true, t_fp[1]))
        if not problems:
            info("口径拆解自洽（同目录路过 %d = %d+%d；另计语境 %d = %d+%d；"
                 "全部产出 %d = %d+%d+%d，与 §一 合计行对上）✓"
                 % (sd_all, sd_tp, sd_fp, o_all, o_flask, o_req,
                    t_all, t_true, t_fp_num, o_all))
    for pr in problems:
        err("口径拆解不自洽：%s" % pr)
    return None


def check_current_state(skill_dir):
    """第 23 项：「当前状态」的真源与载体必须对得上（E34）。

    为什么要有这一项：第 14 项的期望值校验**只扫代码块**——那是对的（代码块是
    "复制即跑"的契约，正文里的历史数字是**当时真值**，管到它们就是误伤）。
    但代价是**散文里的"当前状态"没人守** ⇒ 本项目已经吃过两次亏：
    E32 同一个数在三份文档里写成 20 / 12 / "59 条里有 20 条"；
    E33 把「补发那批 64 个」和「现在的 65 个」写成了同一个数。

    修法不是"把散文也当代码块扫"（那会误伤历史），而是：
      ① `evals/current-state.json` = 「当前状态」的唯一机器可读真源；
      ② 文档里用 `<!-- current-state:begin/end -->` 圈出"这里说的是**当前**状态"；
      ③ 校验器拿真源里的数去标记区里逐个比对 ⇒ 手抄的数一旦与真源不同，当场红并点名。

    ⚠️ 真源自己也可能是**坏尺子**（E7 的教训）⇒ `static` 段（能当场推出来的数）
    每跑一次就重推一遍，推不出来就报 ⇒ 真源自己不会腐烂。
    """
    if current_state is None:
        err("scripts/current_state.py 导不进来——第 23 项没法跑（当前状态没人对账了）")
        return None
    return current_state.check(skill_dir, err, info)


MICRO_TEST_RULES = (u"铁律范围句", u"必验证门函数", u"子代理四态回执")
MICRO_TEST_VERDICTS = (u"有效", u"基线未红", u"无效", u"未跑", u"待测")


def check_micro_test_claims(skill_dir):
    """第 24 项：微测台账的**状态格必须与实测数据一致**（E35）。

    为什么要有这一项：本项目的纪律层条款此前只有"文本 + 结构锁"，行为收益**未测**；
    E35 真跑了一轮双臂对照，结论是**基线未红**（A 0/5 vs B 0/5）⇒ 不得对外声称行为收益。
    ⇒ 既然"不许声称"是要守的纪律，它就该有机器判据，而不是靠人记得。

    判据做两件事：
      ① **状态格只能是规程允许的判定**（有效 / 基线未红 / 无效 / 未跑 / 待测）——
         别的词（比如"已验证""通过"）一律判错。
      ② **状态格必须与实测数据对得上**：从备注里解析 "A x/n 失败" 与 "B y/m 失败"，
         算出失败率差 ⇒ 差 ≥40pp 必须写"有效"，差 =0 必须写"基线未红"，差 <0 必须写"无效"。
         ⇒ **改结论不改数据**（或反过来）当场红 —— 这正是 E32/E33 栽过两次的同一种病。
    """
    path = os.path.join(skill_dir, "evals", "micro-tests.md")
    if not os.path.isfile(path):
        return None
    with io.open(path, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    rows = {}
    for line in text.split("\n"):
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        for key in MICRO_TEST_RULES:
            if key in cells[0] and key not in rows:
                rows[key] = cells
    problems = []
    for key in MICRO_TEST_RULES:
        cells = rows.get(key)
        if cells is None:
            problems.append(u"台账里找不到「%s」那一行——三条纪律条款的判定必须一直在册" % key)
            continue
        status, note = cells[2], cells[3]
        if not any(v in status for v in MICRO_TEST_VERDICTS):
            problems.append(u"「%s」的状态格是「%s」，规程只允许 %s"
                            % (key, status, u"／".join(MICRO_TEST_VERDICTS)))
            continue
        ma = re.search(r"A\s*(\d+)\s*/\s*(\d+)\s*失败", note)
        mb = re.search(r"B\s*(\d+)\s*/\s*(\d+)\s*失败", note)
        if not ma or not mb:
            if any(v in status for v in (u"有效", u"基线未红", u"无效")):
                problems.append(u"「%s」写了判定「%s」却解析不出实测数据"
                                u"（应写成「A x/n 失败 … B y/m 失败」）" % (key, status))
            continue
        fa, ta = int(ma.group(1)), int(ma.group(2))
        fb, tb = int(mb.group(1)), int(mb.group(2))
        if ta == 0 or tb == 0:
            problems.append(u"「%s」的分母是 0，判不了" % key)
            continue
        diff = (fa / ta - fb / tb) * 100
        if diff >= 40:
            want = u"有效"
        elif diff < 0:
            want = u"无效"
        else:
            want = u"基线未红"
        if want not in status:
            problems.append(u"「%s」实测失败率差 **%.0f 个百分点** ⇒ 按规程该写「%s」，"
                            u"台账写的是「%s」——**改结论不改数据**（或反过来）当场红"
                            % (key, diff, want, status))
    for p in problems:
        err(u"[微测声称] " + p)
    if not problems:
        info(u"微测台账的状态格与实测数据一致（%d 条纪律条款，判定不许脱离数据）"
             % len(MICRO_TEST_RULES))
    return True


def check_release_identity(skill_dir):
    """第 26 项：发布产物的**身份**必须对得上（E37）。

    为什么要有这一项：本项目此前核过「68 个 tag / 68 个 Release 一一对应、零缺口」
    ——**全绿**。但那次只数了**名字与数量**。E37 复核发现远端 `v0.51.0` 实际指向
    `d5b88e1a`（那是 **v0.66.0 的补记笔**），而不是 v0.51.0 的代码 ⇒
    谁 `git checkout v0.51.0` 拿到的都是别的版本 ⇒ 而那句话当时**是真的**。

    ⇒ 「发布产物存在」不等于「发布产物是它该有的那个」。这一项核**内容**：
      ① 真源 `evals/release-identity.json` 每个条目自洽（键/版本号/sha/owner）；
      ② 真源与本地 git 事实对账（tag 集合、每个 tag 的指向）；
      ③ **每个 tag 指向的 commit 真的属于那个版本**（owner 规则）；
      ④ CHANGELOG 与 tag 的两个差集不许出现**未登记**的新缺口。

    ⚠️ 远端那一侧（`release_identity.py --remote`）要联网 ⇒ 不进本项；
       它由发布流程在**发之前**跑（`release_notes.py --publish` 现在自己就核）。
    ⚠️ 本环境没有 git tag（浅克隆 / 未 fetch tags）时，③ 跑不了 ⇒
       **不假绿**：如实发一条 info 说「这轮没跑」，且 info 条数恒定。
    """
    if release_identity is None:
        err(u"scripts/release_identity.py 导不进来——第 26 项没法跑"
            u"（发布产物的身份没人核了）")
        return None
    return release_identity.check_local(err, info, skill_dir)


def main():
    parser = argparse.ArgumentParser(
        description="技能结构校验器（将作）：按 Agent Skills 规范校验技能目录，可作 CI 门禁。")
    parser.add_argument("skill_dir", nargs="?", default=".", help="技能目录（默认当前目录）")
    parser.add_argument("--stats", action="store_true", help="打印上下文占用报告后退出（不做校验）")
    args = parser.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)
    if args.stats:
        if not os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
            print("错误：找不到 SKILL.md：%s" % skill_dir, file=sys.stderr)
            return 2
        print_stats(skill_dir)
        return 0

    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        err("找不到 SKILL.md：%s" % skill_md)
    else:
        with io.open(skill_md, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        meta, rest = parse_frontmatter(text)
        if meta is not None and rest is not None:
            body = "\n".join(rest)
            body_lines = len(rest)
            body_tokens = estimate_tokens(body)
            if body_lines > 500:
                warn("SKILL.md 正文 %d 行，超过建议的 500 行——考虑把内容外移到 references/" % body_lines)
            else:
                info("SKILL.md 正文 %d 行（≤500 ✓）" % body_lines)
            # 正文 token 预算是**硬闸**：这条先前只写在文档里没有判据，
            # 于是"再加一小段"一路把正文推到 5124 都没人报警——禁忌没有机器判据就会复发。
            if body_tokens > BODY_TOKEN_BUDGET:
                err("正文 ~%d tokens 超预算 %d——先删再加（细节移 references/），不要默默放宽预算"
                    % (body_tokens, BODY_TOKEN_BUDGET))
            else:
                info("SKILL.md 正文 ~%d tokens（预算 %d ✓）" % (body_tokens, BODY_TOKEN_BUDGET))
            if re.search(r"\b[A-Za-z]:[\\/]\S|/Users/\S|/home/\S", body):
                err("正文含本机绝对路径（跨环境会失效，应使用相对路径）")
            check_frontmatter(skill_dir, text)
            version = (meta.get("metadata") or {}).get("version", "")
            if version:
                changelog = os.path.join(skill_dir, "CHANGELOG.md")
                if os.path.isfile(changelog):
                    with io.open(changelog, "r", encoding="utf-8", errors="replace") as f:
                        cl = f.read()
                    m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)\]?", cl, re.M)
                    # 日期检查：2026-10-15 复核时实测四条写成"明天"（10-16）而全套闸门全绿——
                    # 时间戳和数字一样是"只能从真实输出抄"的东西，所以这里上判据。
                    dates = re.findall(
                        r"^##\s*\[?\d+\.\d+\.\d+\]?\s*[-–—]?\s*(\d{4}-\d{2}-\d{2})", cl, re.M)
                    today = time.strftime("%Y-%m-%d")
                    future = sorted(set(d for d in dates if d > today))
                    if future:
                        err("CHANGELOG 有 %d 个未来日期（%s ｜ 今天 %s）——"
                            "版本条目按真实当天写，别顺手写一个明天"
                            % (len(future), u"、".join(future), today))
                    if m and m.group(1) != version:
                        warn("metadata.version (%s) 与 CHANGELOG 最新版本 (%s) 不一致"
                             % (version, m.group(1)))
                    elif m:
                        info("metadata.version 与 CHANGELOG 一致（%s ✓）" % version)
                    check_changelog_dates(skill_dir, cl)
                    check_ledger_versions(skill_dir, cl)
            if os.path.isdir(os.path.join(skill_dir, "evals")):
                info("含 evals/ 评测集 ✓")
            refs = check_refs(skill_dir, text)
            check_one_level(skill_dir, refs)
            check_scripts(skill_dir)
            check_booklet_contract(skill_dir)
            check_readme_counts(skill_dir)
            check_lookup_aliases(skill_dir)
            check_md_tables(skill_dir)
            check_expected_numbers(skill_dir)
            check_no_replacement_chars(skill_dir)
            check_handover_in_repo(skill_dir)
            check_verdict_table(skill_dir)
            check_ledger_totals(skill_dir)
            check_mut_calibrator(skill_dir)
            check_current_state(skill_dir)
            check_micro_test_claims(skill_dir)
            check_release_identity(skill_dir)

    # 第 23 项的收尾：校验器**自己报的条数**也要与真源对账
    # （"validate 22 信息"这句话在交接文档里出现两处，E33 之前它们互相矛盾过）。
    # ⚠️ 本项**刻意不发 info**：它比较的是 len(INFOS)，而自己若再发一条就会差一
    # ⇒ 放在所有检查之后、且只报错不发信息 ⇒ len(INFOS) 就是最终打印出来的条数。
    if current_state is not None:
        # 文档里"照着跑就能看到"的**期望条数**（代码块里）必须等于实际条数。
        # ⚠️ E34 实测：这句在交接文档里出现**两处**且**已经过期**（写着 20，实际 23），
        #    而第 14 项的期望值核对**不认这一形态** ⇒ 没人守 ⇒ 只能过期。
        #    ⇒ 补上：扫代码块里的「期望 N 条信息」，与实际条数对账。
        #    （与真源无关 ⇒ 任何跑本校验器的仓库都适用。）
        for _rel, _lineno, _line in _md_fenced_lines(skill_dir):
            _m = re.search(r"期望[:：]?\s*(\d+)\s*条信息", _line)
            if _m and int(_m.group(1)) != len(INFOS):
                err(u"%s:%d 期望「%d 条信息」，实际 %d 条——"
                    u"改了检查项就同步这行期望值" % (_rel, _lineno,
                                                  int(_m.group(1)), len(INFOS)))
        _src = current_state.load_source(skill_dir)
        if _src is not None:
            _want = (_src.get("reported") or {}).get("validate_infos")
            if _want is not None and _want != len(INFOS):
                err(u"真源说本仓库应报 %d 条信息，实际报了 %d 条——"
                    u"加/减了检查项就同步真源与文档（交接文档 §0 与 §13 各有一处）"
                    % (_want, len(INFOS)))

    print("# 技能结构校验：%s\n" % os.path.basename(skill_dir))
    for i in INFOS:
        print("  ✔ %s" % i)
    for w in WARNINGS:
        print("  ⚠ %s" % w)
    for e in ERRORS:
        print("  ✘ %s" % e)
    print("\n结果：%d 条信息 / %d 条警告 / %d 条错误 —— %s" % (
        len(INFOS), len(WARNINGS), len(ERRORS),
        "通过" if not ERRORS else "未通过"))
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
