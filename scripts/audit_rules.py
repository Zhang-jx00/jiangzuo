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

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditlib  # noqa: E402

SCHEMA = "jiangzuo-audit-rules/1"
RULES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audit-rules")
SEVERITIES = ("critical", "high", "medium", "low", "info")
KINDS = ("taint", "pattern", "dependency", "auth_gap")
REQUIRED = ("id", "title", "kind", "severity", "languages", "cwe", "fix", "retest")
KNOWN_LANGS = set(auditlib.LANG_BY_EXT.values()) | {"*"}


def _compile_list(items, where, problems, need_window=False):
    """把 [{pattern, window}] 编译成带 _rx 的列表；坏模式直接记问题，不留到运行时炸。"""
    out = []
    for item in items or []:
        pat = item.get("pattern") if isinstance(item, dict) else item
        if not pat:
            problems.append("%s：有条目缺 pattern 字段" % where)
            continue
        try:
            rx = re.compile(pat)
        except re.error as exc:
            problems.append("%s：正则无法编译（%s）→ %r" % (where, exc, pat))
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


def load_rules(extra_paths=None, problems=None):
    """内置目录 + 用户文件 → 按 id 去重合并（用户后到，覆盖同名内置）。"""
    problems = problems if problems is not None else []
    soft_notes = []
    compiled = []
    sources = []
    if os.path.isdir(RULES_DIR):
        for fn in sorted(os.listdir(RULES_DIR)):
            if fn.endswith(".json"):
                sources.append(os.path.join(RULES_DIR, fn))
    for path in (extra_paths or []):
        if os.path.isfile(path):
            sources.append(path)
        else:
            problems.append("用户规则文件不存在：%s" % path)

    raw_by_id = {}
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
        for rule in data.get("rules") or []:
            rid = rule.get("id") or name
            if rid in raw_by_id:
                # 去重：同 id 只保留一份，后到的（用户规则）胜出
                raw_by_id[rid] = (rule, name)
            else:
                order.append(rid)
                raw_by_id[rid] = (rule, name)
    for rid in order:
        rule, name = raw_by_id[rid]
        validate_rule(rule, name, problems, compiled)
    return compiled, problems, soft_notes


def rules_version(rules):
    """规则集版本：id + 严重度 + 所有模式原文 + kind；解析器版本也进键。"""
    parts = []
    for r in sorted(rules, key=lambda x: x.get("id", "")):
        pats = []
        for field in ("sinks", "sources", "sanitizers", "unless_present"):
            for item in r.get(field) or []:
                pats.append("%s:%s" % (field, item.get("pattern")))
        if r.get("sensitive_path"):
            pats.append("path:" + r["sensitive_path"])
        adv = r.get("advisory") or {}
        if adv:
            pats.append("adv:%s@<%s" % (adv.get("name"), adv.get("vulnerable_below")))
        parts.append("|".join([r.get("id", ""), r.get("kind", ""),
                               r.get("severity", "")] + sorted(pats)))
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


def main():
    ap = argparse.ArgumentParser(
        description=u"声明式规则引擎（将作）：加载/校验/合并审计规则，规则是数据不是代码。")
    ap.add_argument("--validate", action="store_true", help=u"校验规则库，有问题退出码 1")
    ap.add_argument("--add", action="append", default=[],
                    help=u"追加用户规则文件，可多次（同 id 覆盖内置）")
    ap.add_argument("--json", dest="json_out", default=None, help=u"导出合并后的规则集")
    ap.add_argument("--list", action="store_true", help=u"按严重度列出规则")
    ap.add_argument("--dir", default=None, help=u"改用别的规则目录（调试用）")
    args = ap.parse_args()

    if args.dir:
        global RULES_DIR
        RULES_DIR = os.path.abspath(args.dir)

    problems = []
    rules, problems, soft_notes = load_rules(args.add, problems)
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
    print(u"规则 %d 条（来源：内置规则文件 %d 个 + 用户文件 %d 个）｜ 类型分布 %s ｜ 严重度分布 %s"
          % (len(rules), builtin_files, len(args.add),
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
