#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""声明式规则引擎 —— 将作 (jiangzuo) 审计链第 ③ 环

规则是**数据**不是代码：scripts/audit-rules/*.json 里每条规则声明
kind / 严重度 / CWE / OWASP / source / sink / 净化点 / 修复示例 / 复测点。
扫描器只解释规则，规则变更不需要改扫描器代码。

用法:
    python audit_rules.py --validate                 # 校验内置规则库
    python audit_rules.py --validate --add my.json   # 叠上用户规则一起校
    python audit_rules.py --json rules.json          # 导出合并后的规则集
    python audit_rules.py --list                     # 按严重度列条目

合并语义（对齐升级清单第 5 项）：同 id 时**用户覆盖内置**（去重、只留一条），
用户没写的规则不改动内置语义；规则内容任何变化都会反映到 rules_version，
它是增量缓存键的一部分——版本号不动而规则改了，缓存就会拿旧结论糊新代码。

会做：字段完备性检查、**每条正则当场编译**（上一版手写转义把 51 条模式写坏了，
      从那时起"能编译"就是机器判据而不是口头要求）、kind 专属约束、去重合并。
不会做：判断规则是否该存在（那是 self-evolution.md 的六道闸）；执行扫描（audit_scan.py）。

仅使用 Python 标准库（3.8+），只读、不联网。
"""
import argparse
import io
import json
import os
import re
import sys
import warnings

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditlib  # noqa: E402

SCHEMA = "jiangzuo-audit-rules/1"
RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit-rules")
SEVERITIES = ("critical", "high", "medium", "low", "info")
KINDS = ("taint", "pattern", "dependency", "auth_gap")
REQUIRED = ("id", "title", "kind", "severity", "languages", "cwe", "fix", "retest")
KNOWN_LANGS = set(auditlib.LANG_BY_EXT.values()) | {"*"}

# 控制字符（\b 被 shell/字符串层吃掉后就是退格符）——
# 这类模式永远匹配不上，却会静默把规则变成哑弹，所以直接判错。
CONTROL_RX = re.compile(u"[\x00-\x08\x0b\x0c\x0e-\x1f]")

# 全局标志组：(?i) (?s) (?m) (?x) (?a) (?L) (?u) 这种整串写法（带冒号的 (?i:…) 是局域标志，不算）。
GLOBAL_FLAG_RX = re.compile(r"(?<!\\)\(\?[aiLmsux]+\)")


def misplaced_global_flag(pat):
    """返回第一处"不放在合法位置的全局标志组"，没有则 None。

    合法位置只有两处：整个表达式开头（可以连着写几个），或紧跟在一个 `(` 之后。
    写在分支中间（`x|(?i)y`）在有些解释器里只是 DeprecationWarning，在另一些里直接
    re.error——判据不能跟着解释器版本变，所以这一步**自己**认，不靠 re 的警告时刻表。
    """
    pos = 0
    while True:
        m = GLOBAL_FLAG_RX.search(pat, pos)
        if not m:
            return None
        if m.start() == pos or pat[:m.start()].endswith(u"("):
            pos = m.end()
            continue
        return m


def _flag_pat_message(where, pat):
    return (u"%s：全局标志 (?i)/(?s)/(?m)/(?x) 只能放在整个表达式开头（或紧跟在一个 `(` 之后），"
            u"写在分支中间是废弃写法，不同解释器有的警告有的直接报错 → %r" % (where, pat))



def _compile_list(items, where, problems, need_window=False):
    """把 [{pattern, window}] 编译成带 _rx 的列表；坏模式直接记问题，不留到运行时炸。"""
    out = []
    for item in items or []:
        pat = item.get("pattern") if isinstance(item, dict) else item
        if not pat:
            problems.append("%s：有条目缺 pattern 字段" % where)
            continue
        if CONTROL_RX.search(pat):
            problems.append("%s：模式里含控制字符（多半是 \\b 被某一层吃成了退格符），"
                            "这条永远不会命中" % where)
            continue
        if misplaced_global_flag(pat):
            # 自己认，不靠解释器：3.8 给 DeprecationWarning、3.11 可能直接 re.error、
            # 将来全变成报错——规则是长期存活的数据，判据不能跟着版本换措辞。
            problems.append(_flag_pat_message(where, pat))
            continue
        try:
            # `x|(?i)y` 这种"全局标志不在开头"的写法，今天只是 DeprecationWarning，
            # 换解释器版本就是 SyntaxError——规则是长期存活的数据，必须当场拦。
            # （catch_warnings 不是线程安全的：本函数只在加载期调用，扫描并发走子进程。）
            with warnings.catch_warnings():
                warnings.simplefilter("error", DeprecationWarning)
                rx = re.compile(pat)
        except re.error as exc:
            if misplaced_global_flag(pat):
                problems.append(_flag_pat_message(where, pat))
            else:
                problems.append("%s：正则无法编译（%s）→ %r" % (where, exc, pat))
            continue
        except DeprecationWarning as exc:
            problems.append(_flag_pat_message(where, pat) + u"（%s）" % exc)
            continue
        rec = dict(item) if isinstance(item, dict) else {"pattern": pat}
        rec["_rx"] = rx
        if need_window:
            rec.setdefault("window", 2)
        out.append(rec)
    return out


def validate_rule(rule, source, problems, compiled):
    rid = rule.get("id") or (source + " 的无名规则")
    for field in REQUIRED:
        if not rule.get(field):
            problems.append("%s（%s）：缺必填字段 %s" % (rid, source, field))
    sev = rule.get("severity")
    if sev and sev not in SEVERITIES:
        problems.append("%s：严重度非法 %r（只允许 %s）" % (rid, sev, "/".join(SEVERITIES)))
    kind = rule.get("kind")
    if kind and kind not in KINDS:
        problems.append("%s：kind 未知 %r（只允许 %s）" % (rid, kind, "/".join(KINDS)))
    for lang in rule.get("languages") or []:
        if lang not in KNOWN_LANGS:
            problems.append("%s：语言 %r 不在语言表里（规则永远不会命中）" % (rid, lang))

    key = "%s/%s" % (source, rid)
    entry = dict(rule)
    entry["_source"] = source
    entry["sinks"] = _compile_list(rule.get("sinks"), key + ".sinks", problems)
    entry["sources"] = _compile_list(rule.get("sources"), key + ".sources", problems)
    entry["sanitizers"] = _compile_list(rule.get("sanitizers"), key + ".sanitizers", problems)
    entry["unless_present"] = _compile_list(rule.get("unless_present"),
                                            key + ".unless_present", problems, need_window=True)
    if kind == "taint" and not (entry["sinks"] and entry["sources"]):
        problems.append("%s：kind=taint 必须同时给 sinks 与 sources" % rid)
    if kind == "pattern" and not entry["sinks"]:
        problems.append("%s：kind=pattern 至少要有一条 sinks" % rid)
    if kind == "dependency":
        adv = rule.get("advisory") or {}
        for field in ("name", "vulnerable_below"):
            if not adv.get(field):
                problems.append("%s：kind=dependency 的 advisory 缺 %s" % (rid, field))
    if kind == "auth_gap" and not rule.get("sensitive_path"):
        problems.append("%s：kind=auth_gap 需要 sensitive_path" % rid)
    if rule.get("sensitive_path"):
        try:
            entry["_path_rx"] = re.compile(rule["sensitive_path"])
        except re.error as exc:
            problems.append("%s：sensitive_path 正则坏（%s）" % (rid, exc))
    compiled.append(entry)
    return entry


def load_rules(extra_paths=None, problems=None, include_disabled=False,
              osv_paths=None):
    """内置目录 + 用户文件 → 按 id 去重合并（用户后到，覆盖同名内置）。

    `enabled: false` 的规则不进活动集（实测误报率高的规则要被数据停用，
    不是靠人记得"别用那条"），--enable-all 可强行带回。
    """
    problems = problems if problems is not None else []
    soft_notes = []
    compiled = []
    sources = []
    builtin_paths = set()
    if os.path.isdir(RULES_DIR):
        for fn in sorted(os.listdir(RULES_DIR)):
            if fn.endswith(".json"):
                p = os.path.join(RULES_DIR, fn)
                sources.append(p)
                builtin_paths.add(os.path.abspath(p))
    for path in (extra_paths or []):
        if os.path.isfile(path):
            sources.append(path)
        else:
            problems.append("用户规则文件不存在：%s" % path)

    raw_by_id = {}
    origin = {}          # rid -> ("builtin" | "user", 来自哪个文件)
    order = []
    for path in sources:
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as exc:
            problems.append("规则文件读不了（%s）：%s" % (path, exc))
            continue
        if data.get("schema") and data.get("schema") != SCHEMA:
            # 明确声明了别的 schema = 格式不认识，跳过比硬猜安全
            problems.append("%s：schema 是 %r，本引擎只认 %s"
                            % (path, data.get("schema"), SCHEMA))
            continue
        if not data.get("schema"):
            soft_notes.append(u"%s 未声明 schema（按宽松模式加载；建议补 "
                              u"\"schema\": \"%s\"）" % (path, SCHEMA))
        name = os.path.basename(path)
        is_builtin = os.path.abspath(path) in builtin_paths
        for rule in data.get("rules") or []:
            rid = rule.get("id") or name
            if rid in raw_by_id:
                prev_kind, prev_name = origin.get(rid, ("builtin", "?"))
                if prev_kind == "builtin" and is_builtin:
                    # 用户 --add 覆盖内置是同 id 定制的既有语义；
                    # 但两份**内置**文件撞名会让其中一条整条静默失效
                    # （E1 实拍：crypto.json 与 webapp.json 都写了 JZ-CRYPTO-001，
                    # 新规则一条都没生效，表现却像"规则写错了没检出"）。
                    problems.append(u"%s：内置规则 id %s 与 %s 重复——两份内置文件撞同 id，"
                                    u"后加载的那条会静默覆盖前者；要么合并进同一条，要么换新 id"
                                    % (name, rid, prev_name))
                raw_by_id[rid] = (rule, name)
            else:
                order.append(rid)
                raw_by_id[rid] = (rule, name)
            origin[rid] = ("builtin" if is_builtin else "user", name)
    if osv_paths:
        osv_rules, n_bad = load_osv(osv_paths)
        for rec in osv_rules:
            if rec["id"] in raw_by_id:
                continue          # 用户/内置已有同 id 时不覆盖
            raw_by_id[rec["id"]] = (rec, "osv")
            order.append(rec["id"])
        soft_notes.append(u"OSV 导入 %d 条建议（跳过 %d 条无法解析的记录）"
                          % (len(osv_rules), n_bad))

    active = []
    skipped = []
    for rid in order:
        rule, name = raw_by_id[rid]
        holder = []
        validate_rule_into(rule, name, problems, holder)
        if rule.get("enabled") is False and not include_disabled:
            skipped.append((rid, holder))
            continue
        active.extend(holder)
    return active, problems, soft_notes, skipped


def validate_rule_into(rule, source, problems, compiled):
    return validate_rule(rule, source, problems, compiled)


def rules_version(rules):
    """规则集版本：**整条规则的原文**（含 advisory/alias/fix/retest 等全部字段）+ 解析器版本。

    早先只哈希 id/severity/模式原文，结果加了一条 module_alias（会改变判定结果）
    版本号却纹丝不动——缓存就会拿旧结论糊新规则。规则的任何一处变更都必须作废缓存。
    """
    parts = []
    for rec in sorted(export_rules(rules), key=lambda x: x.get("id", "")):
        parts.append(json.dumps(rec, sort_keys=True, ensure_ascii=False))
    return auditlib.sha1_hex(u"\n".join(parts) + "|parser=" + auditlib.LIB_VERSION)


def export_rules(rules):
    out = []
    for r in rules:
        rec = {}
        for k, v in r.items():
            if k.startswith("_"):
                continue
            if k in ("sinks", "sources", "sanitizers", "unless_present"):
                rec[k] = [{kk: vv for kk, vv in item.items() if kk != "_rx"}
                          for item in (v or [])]
            else:
                rec[k] = v
        out.append(rec)
    return out


OSV_SEVERITY = {"CRITICAL": "critical", "HIGH": "high", "MODERATE": "medium",
                "MODERATE ": "medium", "LOW": "low", "NONE": "info"}
OSV_LANG_BY_ECO = {"PyPI": "python", "npm": "javascript", "Go": "go", "Maven": "java",
                   "RubyGems": "ruby", "Packagist": "php", "crates.io": "rust",
                   "NuGet": "csharp"}


def _osv_severity(rec):
    for sev in rec.get("severity") or []:
        text = str(sev.get("score", "")).upper()
        for key, val in OSV_SEVERITY.items():
            if text.startswith(key.strip()):
                return val
    return "high"


def load_osv(paths):
    """把 OSV 记录（https://osv.dev 的 JSON）变成 dependency 规则。

    为什么需要：内置那 6 条手写建议是**样例基线**，不是 advisory feed——
    拿它当"依赖漏洞已覆盖"是自欺。OSV 可按生态离线拉取（`all.zip`），
    我们只做导入通道，**不把数据提交进技能仓库**（体积与时效都不合适）。
    """
    rules, skipped, seen = [], 0, set()
    files = []
    for path in paths or []:
        if os.path.isdir(path):
            for name in sorted(os.listdir(path)):
                if name.endswith(".json"):
                    files.append(os.path.join(path, name))
        elif os.path.isfile(path):
            files.append(path)
    for path in files:
        try:
            with io.open(path, "r", encoding="utf-8") as f:
                blob = json.load(f)
        except (OSError, ValueError):
            skipped += 1
            continue
        records = blob if isinstance(blob, list) else [blob]
        for rec in records:
            if not isinstance(rec, dict):
                skipped += 1
                continue
            oid = rec.get("id")
            aliases = [a for a in (rec.get("aliases") or []) if str(a).startswith("CVE")]
            pairs = []
            for aff in rec.get("affected") or []:
                pkg = aff.get("package") or rec.get("package") or {}
                fixed = None
                for rng in aff.get("ranges") or []:
                    for event in rng.get("events") or []:
                        if "fixed" in event:
                            fixed = str(event["fixed"])
                            break
                    if fixed:
                        break
                if pkg.get("name") and fixed:
                    pairs.append((pkg, fixed))
            if not pairs:
                skipped += 1
                continue
            for pkg, fixed in pairs:
                name = str(pkg.get("name") or "").strip()
                eco = str(pkg.get("ecosystem") or "").strip()
                if not (name and eco and oid):
                    skipped += 1
                    continue
                key = (eco.lower(), name.lower(), fixed)
                if key in seen:
                    continue
                seen.add(key)
                rules.append({
                    "id": "OSV-%s" % oid,
                    "title": u"依赖已知漏洞：%s %s（%s）" % (name, u"< " + fixed,
                                                           (aliases or [oid])[0]),
                    "kind": "dependency",
                    "severity": _osv_severity(rec),
                    "confidence_base": 0.75,
                    "languages": [OSV_LANG_BY_ECO.get(eco, "*")],
                    "cwe": ["CWE-1035", "CWE-1104"],
                    "owasp": [u"A06:2021 易受攻击组件"],
                    "advisory": {"ecosystem": eco, "name": name.lower(),
                                 "vulnerable_below": fixed,
                                 "cve": (aliases or [oid])[0],
                                 "module_alias": [name.lower(),
                                                  name.lower().replace("-", "_")]},
                    "fix": u"升级到 %s %s 或更高；无法升级时按 OSV 记录的 workaround 处理。"
                           % (name, fixed),
                    "retest": u"用包管理器确认**实际解析版本**（不只是清单声明）已不在受影响区间："
                              u" pip show / npm ls / cargo tree。",
                    "source": "osv",
                })
    return rules, skipped


def main():
    ap = argparse.ArgumentParser(
        description=u"声明式规则引擎（将作）：加载/校验/合并审计规则，规则是数据不是代码。")
    ap.add_argument("--validate", action="store_true", help=u"校验规则库，有问题退出码 1")
    ap.add_argument("--add", action="append", default=[],
                    help=u"追加用户规则文件，可多次（同 id 覆盖内置）")
    ap.add_argument("--json", dest="json_out", default=None, help=u"导出合并后的规则集")
    ap.add_argument("--list", action="store_true", help=u"按严重度列出规则")
    ap.add_argument("--dir", default=None, help=u"改用别的规则目录（调试用）")
    ap.add_argument("--osv", action="append", default=[],
                    help=u"OSV JSON 文件或目录（可多次）；数据不入库，只走导入通道")
    ap.add_argument("--enable-all", action="store_true",
                    help=u"连 enabled:false 的规则一起加载（默认按数据停用）")
    args = ap.parse_args()

    if args.dir:
        global RULES_DIR
        RULES_DIR = os.path.abspath(args.dir)

    problems = []
    rules, problems, soft_notes, disabled = load_rules(args.add, problems,
                                                       include_disabled=args.enable_all,
                                                       osv_paths=args.osv or None)
    version = rules_version(rules)
    by_sev = {}
    by_kind = {}
    for r in rules:
        by_sev[r.get("severity")] = by_sev.get(r.get("severity"), 0) + 1
        by_kind[r.get("kind")] = by_kind.get(r.get("kind"), 0) + 1

    if args.json_out:
        payload = {"schema": SCHEMA, "rules_version": version,
                   "rules": sorted(export_rules(rules), key=lambda x: x["id"])}
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n")

    if args.list:
        for sev in SEVERITIES:
            group = [r for r in rules if r.get("severity") == sev]
            if not group:
                continue
            print(u"### %s（%d）" % (sev, len(group)))
            for r in sorted(group, key=lambda x: x["id"]):
                print(u"  %-16s %-4s %s" % (r["id"], r["kind"], r["title"]))

    builtin_files = len([f for f in os.listdir(RULES_DIR) if f.endswith(".json")]) \
        if os.path.isdir(RULES_DIR) else 0
    print(u"规则 %d 条（来源：内置规则文件 %d 个 + 用户文件 %d 个；数据停用 %d 条）"
          u"｜ 类型分布 %s ｜ 严重度分布 %s"
          % (len(rules), builtin_files, len(args.add), len(disabled),
             ", ".join("%s=%d" % kv for kv in sorted(by_kind.items())),
             ", ".join("%s=%d" % (k, by_sev[k]) for k in SEVERITIES if k in by_sev)))
    print(u"rules_version=%s" % version[:12])

    for note in soft_notes:
        print(u"  ⚠ %s" % note)
    if problems:
        for p in problems:
            print(u"  ✘ %s" % p)
        print(u"RESULT: RULES-FAIL（%d 条问题）" % len(problems))
        return 1
    print(u"RESULT: RULES-OK（%d 条规则全部通过字段与正则编译校验）" % len(rules))
    return 0


if __name__ == "__main__":
    sys.exit(main())
