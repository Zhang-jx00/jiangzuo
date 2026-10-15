#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""扫描调度 · 反幻觉验证 · 分级报告 —— 将作 (jiangzuo) 审计链第 ⑤⑥⑦ 环

一条命令跑完整链：索引 → 地图 → **确定性粗筛** → 只对候选文件做**语义深挖** →
**独立验证环节**（核验位置为真、净化未生效、输入可控、sink 可达）→
置信度×严重度分级 → Markdown/JSON/SARIF 报告（指纹去重）→ 可选缓存增量。

用法:
    python audit_scan.py [项目目录] [--json findings.json] [--md report.md]
                         [--sarif out.sarif] [--index idx.json] [--map map.json]
                         [--graph graph.json] [--rules user.json]... [--cache DIR]
                         [--incremental] [--max-file-kb N] [--strict] [--report-memory]

会做：全仓只读扫描；粗筛流式逐行（不整仓载入）；深挖只碰候选文件；
      每条发现在报告前重新打开文件核对行号与 sink 模式；命中行**先脱敏**再进报告；
      同一问题按指纹（规则+文件+归一化 sink 文本）去重。
不会做：改被扫项目的任何文件（缓存目录是工具产物，且默认关闭，需 --cache 显式指定）；
      输出修复补丁（只给修复示例与复测点，改不改由人决定）；
      保证零误报——核验只保证"位置和证据是真的"，业务逻辑漏洞仍要人判。

验证环节是**红旗自查的机器版补充**，不是替代：它拦的是"agent 报了个不存在的文件行号"，
`code-review.md` 的自疑循环拦的是"我以为它是对的"。

仅使用 Python 标准库（3.8+），不联网、只读项目。
"""
import argparse
import io
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import audit_graph   # noqa: E402
import auditlib      # noqa: E402
import audit_map     # noqa: E402
import audit_rules   # noqa: E402

FINDINGS_SCHEMA = "jiangzuo-audit-findings/1"
SARIF_VERSION = "2.1.0"
SARIF_URI = "https://json.schemastore.org/sarif-2.1.0.json"
TOOL_NAME = "jiangzuo-audit"
SEV_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
SARIF_LEVEL = {"critical": "error", "high": "error", "medium": "warning",
               "low": "warning", "info": "note"}
CONF_BONUS = {"sink_verified": 0.2, "interprocedural": 0.15,
              "reachable": 0.15, "unreachable": -0.25, "dep_called": 0.1}
CONF_LABELS = ((0.75, u"高"), (0.5, u"中"), (0.0, u"低"))
IMPORT_RX = re.compile(r"^\s*(?:import|from)\s+([\w\.]+)|require\(\s*[\"']([^\"'@/]+)"
                       r"|use\s+([a-z0-9_\.]+)|^\s*gem\s+[\"'](\w+)")
VERIFICATION_NOTE = u"核验五项：位置存在 / sink 仍匹配 / 输入可控 / 净化未生效 / 可达"


def _norm_version(text):
    parts = []
    for chunk in re.split(r"[.\-+]", str(text or "")):
        m = re.match(r"^(\d+)", chunk)
        parts.append(int(m.group(1)) if m else 0)
    return tuple(parts or [0])


def _fingerprint(rule_id, rel, text):
    norm = re.sub(r"\s+", "", re.sub(r"[0-9a-fA-F]{6,}", "*", text or ""))
    return auditlib.sha1_hex(u"%s|%s|%s" % (rule_id, rel, norm[:200]))[:16]


def _bucket_by_lang(rules, field, want_masked):
    """按语言分桶：每行只跑"这门语言可能命中"的少数模式。

    改之前是 每行 × 全部 55 条模式，光语言判断就占掉一半时间；
    分桶后不相关语言的模式一条都不碰，**且一个文件若一条相关模式都没有，
    连打开都不打开**。
    """
    by_lang, wild = {}, []
    for rule in rules:
        if rule.get("kind") not in ("taint", "pattern"):
            continue
        if bool(rule.get("ignore_strings")) != want_masked:
            continue
        pairs = [(rule["id"], item["_rx"]) for item in (rule.get(field) or [])]
        if not pairs:
            continue
        langs = rule.get("languages") or []
        if "*" in langs:
            wild.extend(pairs)
        for lang in langs:
            if lang != "*":
                by_lang.setdefault(lang, []).extend(pairs)
    return by_lang, wild


def _build_buckets(rules):
    return {"raw": _bucket_by_lang(rules, "sinks", False),
            "mask": _bucket_by_lang(rules, "sinks", True),
            "src": _bucket_by_lang(rules, "sources", False)}


def _bucket_items(buckets, lang):
    raw_by, raw_wild = buckets["raw"]
    mask_by, mask_wild = buckets["mask"]
    src_by, src_wild = buckets["src"]
    return (raw_by.get(lang, []) + raw_wild,
            mask_by.get(lang, []) + mask_wild,
            src_by.get(lang, []) + src_wild)


def _match_code_lines(buckets, lang, code_lines, imports, per_rule, src_per_rule):
    """对一文件的代码行跑三种桶。coarse_screen（分步）与 prescan（单遍）共用这一份，
    否则两条路径的命中口径会悄悄分叉——那比慢更糟。"""
    raw_items, mask_items, src_items = _bucket_items(buckets, lang)
    for lineno, raw, masked, _trunc in code_lines:
        for m in IMPORT_RX.finditer(raw):
            token = next((g for g in m.groups() if g), "")
            if token:
                imports.add(token.split(".")[0].lower())
        for rid, rx in src_items:
            if rx.search(raw):
                src_per_rule.setdefault(rid, []).append(lineno)
        for rid, rx in raw_items:
            if rx.search(raw):
                per_rule.setdefault(rid, []).append(lineno)
        for rid, rx in mask_items:
            if rx.search(masked):
                per_rule.setdefault(rid, []).append(lineno)
    return bool(raw_items or mask_items or src_items)


def coarse_screen(root, index, rules, max_bytes, peak=False):
    """确定性粗筛（分步路径）：按语言分桶匹配 sink/source，只留命中位置。

    这一层不做任何判断，目的就是把深挖范围从"全仓"缩到"候选文件"——
    大仓扫描的内存与时间都跟这一步的取舍有关，所以禁止在这里读整仓内容。
    """
    buckets = _build_buckets(rules)
    hits, imports = {}, set()
    trace = None
    peak_kb = 0
    if peak:
        import tracemalloc
        tracemalloc.start()
        trace = tracemalloc
    for rec in index["files"]:
        if trace:
            peak_kb = max(peak_kb, trace.get_traced_memory()[1] // 1024)
        rel = rec["path"]
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        per_rule, src_per_rule = {}, {}
        if not any(_bucket_items(buckets, rec["lang"])):
            continue      # 这门语言没有任何相关模式 → 连文件都不打开
        _match_code_lines(buckets, rec["lang"],
                          auditlib.iter_code_lines(abs_path, max_bytes=max_bytes,
                                                   both=True),
                          imports, per_rule, src_per_rule)
        if per_rule or src_per_rule:
            hits[rel] = {"sinks": per_rule, "sources": src_per_rule}
    if trace:
        peak_kb = max(peak_kb, trace.get_traced_memory()[1] // 1024)
        trace.stop()
    return hits, imports, peak_kb, []


def prescan(root, rules, max_bytes, use_git=True, exclude=None, extra_patterns=None,
            measure=False):
    """**单遍前端**：一次打开、一次逐行，同时产出索引记录、地图状态与粗筛命中。

    分步路径（build_index → build_map → coarse_screen）要把全仓读三遍、逐行循环跑三遍；
    基准实测这三遍占掉整链约 65% 的时间。这里合并成一遍：
    字节读进来算 sha1 与二进制判定 → 解码成行 → 地图抽取吃全行、粗筛吃代码行。
    内存仍是逐文件释放（一次只持有一个文件的内容），不是把仓库读进内存。
    """
    root = os.path.abspath(root)
    paths, rules_obj, generator = auditlib.list_scan_paths(
        root, use_git=use_git, extra_patterns=extra_patterns)
    skip_set = set(exclude or ())
    buckets = _build_buckets(rules)
    state = audit_map.new_state()
    index_files, skipped, hits = [], [], {}
    imports = set()
    n_binary = n_oversize = n_hidden = 0
    peak_kb = 0
    if measure:
        import tracemalloc
        tracemalloc.start()
    for rel in paths:
        if measure:
            peak_kb = max(peak_kb, tracemalloc.get_traced_memory()[1] // 1024)
        if rel in skip_set or auditlib._builtin_pruned(rel):
            continue
        if rules_obj.is_ignored(rel):
            continue
        base = os.path.basename(rel)
        if base.startswith(".") and base not in auditlib.DOTFILE_KEEP \
                and not base.startswith(".env"):
            n_hidden += 1
            continue
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        if not os.path.isfile(abs_path) or os.path.islink(abs_path):
            continue
        try:
            with io.open(abs_path, "rb") as fh:
                data = fh.read(max_bytes + 1)
        except OSError:
            skipped.append({"path": rel, "reason": "unreadable", "bytes": 0})
            continue
        size = len(data)
        if size > max_bytes:
            n_oversize += 1
            skipped.append({"path": rel, "reason": "oversize", "bytes": size})
            continue
        binary = auditlib.NUL_BYTE in data[:8192]
        if binary:
            n_binary += 1
            skipped.append({"path": rel, "reason": "binary", "bytes": size})
            continue
        rec = {"path": rel, "bytes": size,
               "sha1": auditlib.sha1_hex(data), "lang": auditlib.lang_of(rel)}
        index_files.append(rec)
        raw_lines = data.decode("utf-8", "replace").splitlines(keepends=True)
        audit_map.consume_file(state, root, rec,
                               [(i, l, False) for i, l in enumerate(raw_lines, 1)])
        raw_items, mask_items, src_items = _bucket_items(buckets, rec["lang"])
        if raw_items or mask_items or src_items:
            per_rule, src_per_rule = {}, {}
            _match_code_lines(buckets, rec["lang"],
                              auditlib.code_lines(raw_lines), imports,
                              per_rule, src_per_rule)
            if per_rule or src_per_rule:
                hits[rel] = {"sinks": per_rule, "sources": src_per_rule}
    counts = {"files": len(index_files), "binary": n_binary, "oversize": n_oversize,
              "hidden": n_hidden, "skipped_listed": len(skipped),
              "total_bytes": sum(r["bytes"] for r in index_files)}
    by_lang = {}
    for rec in index_files:
        by_lang[rec["lang"]] = by_lang.get(rec["lang"], 0) + 1
    index = {"schema": auditlib.INDEX_SCHEMA, "generator": generator,
             "ignore_sources": rules_obj.sources, "max_file_bytes": max_bytes,
             "files": index_files, "skipped": skipped[:auditlib.SKIP_LIST_CAP],
             "skipped_truncated": max(0, len(skipped) - auditlib.SKIP_LIST_CAP),
             "counts": counts, "by_lang": by_lang}
    index["index_sha1"] = auditlib.sha1_hex(json.dumps(
        {"files": index_files, "counts": counts}, sort_keys=True, ensure_ascii=False))
    if measure:
        peak_kb = max(peak_kb, tracemalloc.get_traced_memory()[1] // 1024)
        tracemalloc.stop()
    return index, audit_map.finalize_map(state, root, index), hits, imports, peak_kb


def _window_lines(all_lines, center, span):
    out = []
    for lineno, text, _t in all_lines:
        if abs(lineno - center) <= span:
            out.append(text)
    return u"\n".join(out)


def deep_pattern_findings(root, index, rules, hits, max_bytes):
    """对候选文件做语义深挖：pattern 规则的邻近行核（unless_present）与证据装配。"""
    by_id = {r["id"]: r for r in rules}
    findings = []
    streams = {}
    for rel, info in sorted(hits.items()):
        rec = [f for f in index["files"] if f["path"] == rel]
        if not rec:
            continue
        abs_path = os.path.join(root, rel.replace("/", os.sep))
        for rid, linenos in sorted(info["sinks"].items()):
            rule = by_id.get(rid)
            if not rule or rule.get("kind") != "pattern":
                continue
            masked = bool(rule.get("ignore_strings"))
            skey = (rel, masked)
            if skey not in streams:
                streams[skey] = list(auditlib.iter_code_lines(
                    abs_path, max_bytes=max_bytes, ignore_strings=masked))
            lines = streams[skey]
            text_by_line = dict((n, t) for n, t, _x in lines)
            for lineno in linenos:
                text = text_by_line.get(lineno, "")
                if not text:
                    continue      # 注释/文档块/已被剥掉的行不算命中
                sink_rx = None
                for item in rule["sinks"]:
                    if item["_rx"].search(text):
                        sink_rx = item["pattern"]
                        break
                if sink_rx is None:
                    continue
                blocked = False
                for item in rule.get("unless_present") or []:
                    near = _window_lines(lines, lineno, item.get("window", 2))
                    if item["_rx"].search(text if item.get("window", 2) == 0 else near):
                        blocked = True
                        break
                if blocked:
                    continue
                findings.append({
                    "rule_id": rid, "kind": "pattern", "title": rule["title"],
                    "masked": masked,
                    "severity": rule["severity"], "cwe": rule.get("cwe", []),
                    "owasp": rule.get("owasp", []), "file": rel, "line": lineno,
                    "sink_text": auditlib.redact(text.strip())[:200],
                    "sink_pattern": sink_rx,
                    "path": [{"file": rel, "line": lineno, "kind": "sink",
                              "text": auditlib.redact(text.strip())[:200]}],
                    "sanitizers_seen": [], "depth": "pattern-only",
                    "confidence_base": rule.get("confidence_base", 0.5),
                    "fix": rule.get("fix", ""), "retest": rule.get("retest", ""),
                    "note": rule.get("note", ""),
                })
    return findings


def auth_gap_findings(map_data, rules):
    by_id = {r["id"]: r for r in rules if r.get("kind") == "auth_gap"}
    out = []
    for rule_id, rule in by_id.items():
        rx = rule.get("_path_rx")
        if not rx:
            continue
        for route in map_data.get("routes", []):
            if route.get("auth"):
                continue
            if not rx.search(route.get("path", "")):
                continue
            out.append({
                "rule_id": rule_id, "kind": "auth_gap", "title": rule["title"],
                "severity": rule["severity"], "cwe": rule.get("cwe", []),
                "owasp": rule.get("owasp", []), "file": route["file"],
                "line": route["line"],
                "sink_text": u"%s %s（本文件内未见鉴权标记）" % (route["method"], route["path"]),
                "sink_pattern": rule.get("sensitive_path", ""),
                "path": [{"file": route["file"], "line": route["line"], "kind": "route",
                          "text": u"%s %s" % (route["method"], route["path"])}],
                "sanitizers_seen": [], "depth": "map-driven",
                "confidence_base": rule.get("confidence_base", 0.4),
                "fix": rule.get("fix", ""), "retest": rule.get("retest", ""),
                "note": rule.get("note", ""),
            })
    return out


def dependency_findings(map_data, rules, imports):
    out = []
    deps = map_data.get("dependencies", [])
    for rule in rules:
        if rule.get("kind") != "dependency":
            continue
        adv = rule.get("advisory") or {}
        name = (adv.get("name") or "").lower()
        limit = adv.get("vulnerable_below") or ""
        if not name or not limit:
            continue
        for dep in deps:
            dname = (dep.get("name") or "").lower()
            if dname != name and not dname.endswith("/" + name):
                continue
            ver = re.sub(r"^[\^~>=<\"]+|[^0-9A-Za-z.\-]+$", "", str(dep.get("version") or ""))
            if not ver or _norm_version(ver) >= _norm_version(limit):
                continue
            called = any(a in imports or a.replace("-", "_") in imports
                         for a in [name] + [str(x).lower() for x
                                            in (adv.get("module_alias") or [])])
            out.append({
                "rule_id": rule["id"], "kind": "dependency", "title": rule["title"],
                "severity": rule["severity"], "cwe": rule.get("cwe", []),
                "owasp": rule.get("owasp", []),
                "file": dep.get("manifest", ""), "line": 1,
                "sink_text": u"%s==%s（建议 < %s 已修复 / %s）"
                             % (dep.get("name"), ver, limit, adv.get("cve", "")),
                "sink_pattern": "dependency:%s" % name,
                "path": [{"file": dep.get("manifest", ""), "line": 1, "kind": "manifest",
                          "text": u"%s = %s" % (dep.get("name"), ver)}],
                "sanitizers_seen": [], "depth": "manifest-only",
                "confidence_base": rule.get("confidence_base", 0.7),
                "fix": rule.get("fix", ""), "retest": rule.get("retest", ""),
                "note": rule.get("note", ""), "called": called,
                "dep_name": dep.get("name"), "dep_version": ver,
            })
    return out


def flow_findings(graph):
    out = []
    for flow in graph.get("flows", []):
        flow = dict(flow)
        flow["kind"] = "taint"
        flow["sink_pattern"] = ""
        flow.setdefault("called", None)
        flow["note"] = flow.get("unreachable_reason", "")
        out.append(flow)
    return out


def verify(root, finding, map_data, all_lines_cache):
    """独立验证环节：五项核验，编造的位置直接丢弃，其余按结果降级。"""
    rel = finding["file"]
    abs_path = os.path.join(root, rel.replace("/", os.sep))
    result = {"path_exists": os.path.isfile(abs_path),
              "sink_still_matches": False, "input_controllable": False,
              "sanitizer_absent": True, "sink_reachable": True}
    reasons = []
    if not result["path_exists"]:
        reasons.append(u"报告里的文件在磁盘上不存在（行 %s）" % finding["line"])
        return False, result, reasons
    masked = bool(finding.get("masked"))
    skey = (rel, masked)
    if skey not in all_lines_cache:
        all_lines_cache[skey] = list(auditlib.iter_code_lines(abs_path,
                                                             ignore_strings=masked))
    lines = all_lines_cache[skey]
    text_by_line = dict((n, t) for n, t, _x in lines)
    line_text = text_by_line.get(finding["line"], "")
    if not line_text.strip() and finding["kind"] != "dependency":
        reasons.append(u"行 %s 是空行或超出文件长度" % finding["line"])
        return False, result, reasons
    rx = None
    if finding.get("sink_pattern"):
        try:
            rx = re.compile(finding["sink_pattern"])
        except re.error:
            rx = None
    if finding["kind"] in ("dependency", "auth_gap"):
        result["sink_still_matches"] = True
    elif finding["kind"] == "taint":
        # 污点流的 sink 证据不带单条模式（规则有多种命中方式），
        # 改用更强的一条：当前行原文必须仍等于当初记录的 sink 行原文
        stored = None
        for hop in reversed(finding.get("path", [])):
            if hop.get("kind") == "sink":
                stored = hop.get("text", "")
                break
        cur = auditlib.redact(line_text.strip())[:200]
        result["sink_still_matches"] = stored is not None and \
            auditlib.redact(stored.strip())[:200] == cur
        if stored is None:
            reasons.append(u"证据链里没有 sink 跳，无法核对位置")
            return False, result, reasons
        if not result["sink_still_matches"]:
            reasons.append(u"行 %s 的内容与记录时的 sink 证据不一致（编造或代码已变）"
                           % finding["line"])
            return False, result, reasons
    elif rx is not None:
        result["sink_still_matches"] = bool(rx.search(line_text))
        if not result["sink_still_matches"]:
            reasons.append(u"行 %s 现在的内容已不匹配 sink 模式（代码变了或位置记错）"
                           % finding["line"])
            return False, result, reasons
    else:
        result["sink_still_matches"] = True
    kinds = set(h.get("kind") for h in finding.get("path", []))
    if finding["kind"] == "taint":
        result["input_controllable"] = "source" in kinds
        if not result["input_controllable"]:
            reasons.append(u"证据链里没有 source 跳")
    elif finding["kind"] == "auth_gap":
        result["input_controllable"] = True
    elif finding["kind"] == "dependency":
        result["input_controllable"] = bool(finding.get("called"))
    else:
        result["input_controllable"] = True
    if finding["kind"] == "pattern" and finding.get("sink_pattern"):
        result["sanitizer_absent"] = True   # pattern 的邻近净化检查已在深挖阶段做过
    if finding.get("sanitizers_seen"):
        result["sanitizer_absent"] = False
        reasons.append(u"链路上有净化点：%s" % ", ".join(finding["sanitizers_seen"]))
    if finding["kind"] == "taint" and finding.get("reachable") is False:
        result["sink_reachable"] = False
        reasons.append(u"sink 从入口/路由不可达（不可利用）")
    keep = result["path_exists"] and result["sink_still_matches"]
    return keep, result, reasons


def grade(finding, result):
    value = float(finding.get("confidence_base", 0.5))
    if result["sink_still_matches"]:
        value += CONF_BONUS["sink_verified"]
    if finding.get("depth") == "interprocedural":
        value += CONF_BONUS["interprocedural"]
    if finding.get("kind") == "taint":
        value += CONF_BONUS["reachable"] if result["sink_reachable"] else CONF_BONUS["unreachable"]
    if finding.get("kind") == "dependency" and finding.get("called"):
        value += CONF_BONUS["dep_called"]
    if not result["input_controllable"]:
        value -= 0.15
    if not result["sanitizer_absent"]:
        value -= 0.2
    value = max(0.05, min(0.95, value))
    label = CONF_LABELS[-1][1]
    for threshold, name in CONF_LABELS:
        if value >= threshold:
            label = name
            break
    finding["confidence"] = {"value": round(value, 2), "label": label}
    finding["exploitable"] = bool(result["sink_reachable"])
    return finding


def rank_dependencies(findings):
    deps = [f for f in findings if f["kind"] == "dependency"]
    deps.sort(key=lambda f: (not f.get("called"), SEV_ORDER.get(f["severity"], 4),
                             f["rule_id"]))
    for i, f in enumerate(deps):
        f["rank"] = i
    for f in findings:
        if f["kind"] != "dependency":
            f.setdefault("rank", None)
    return findings


def load_cache(path, rules_version):
    if not path or not os.path.isfile(path):
        return None
    try:
        with io.open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return None
    if data.get("rules_version") != rules_version or \
            data.get("lib_version") != auditlib.LIB_VERSION:
        return None      # 规则或解析器变了 → 整个缓存作废（自动失效，不靠人记得清）
    return data


def save_cache(path, data):
    if not path:
        return
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, sort_keys=True))


def build_report_payload(root, index, map_data, graph, rules, findings, dropped,
                         blocked, stats):
    findings.sort(key=lambda f: (SEV_ORDER.get(f["severity"], 4),
                                 -f["confidence"]["value"], f["file"], f["line"],
                                 f["rule_id"]))
    for i, f in enumerate(findings):
        f["order"] = i + 1
        f["id"] = _fingerprint(f["rule_id"], f["file"], f["sink_text"])
    seen = {}
    deduped = []
    for f in findings:
        key = f["id"]
        if key in seen:
            seen[key]["duplicates"] = seen[key].get("duplicates", 0) + 1
            continue
        seen[key] = f
        deduped.append(f)
    stats["findings"] = len(deduped)
    stats["dropped_by_verifier"] = len(dropped)
    stats["by_severity"] = {}
    for f in deduped:
        stats["by_severity"][f["severity"]] = stats["by_severity"].get(f["severity"], 0) + 1
    return {"schema": FINDINGS_SCHEMA, "tool": TOOL_NAME,
            "index_sha1": index.get("index_sha1", ""),
            "map_sha1": map_data.get("map_sha1", ""),
            "rules_version": audit_rules.rules_version(rules),
            "scanned_root": os.path.basename(root),
            "stats": stats, "findings": deduped, "dropped": dropped,
            "blocked_by_sanitizer": blocked,
            "coverage": {
                "languages": map_data.get("languages", {}),
                "frameworks": map_data.get("frameworks", []),
                "skipped_files": index["counts"]["binary"] + index["counts"]["oversize"],
                "limits": [u"正则级分析，无 AST；同名函数按名字解析可能串味",
                           u"模块级代码不参与数据流", u"鉴权/越权类结论依赖地图，"
                           u"全局中间件与网关看不见",
                           u"依赖建议集为样例基线，不等于 advisory feed",
                           u"核验只保证位置与证据真实，不保证业务判断正确"],
                "verification": VERIFICATION_NOTE}}


def report_md(payload, root):
    s = payload["stats"]
    lines = [u"# 全项目审计报告（将作审计链）", u"",
             u"> 根目录：`%s` ｜ 索引 `%s` ｜ 地图 `%s` ｜ 规则 `%s`"
             % (payload["scanned_root"], payload["index_sha1"][:12],
                payload["map_sha1"][:12], payload["rules_version"][:12]),
             u"",
             u"| 结论 | 数 |", u"|---|---|",
             u"| 确认发现（去重后） | %d |" % s["findings"],
             u"| 验证环节丢弃（位置对不上） | %d |" % s["dropped_by_verifier"],
             u"| 净化断链（已排除） | %d |" % len(payload["blocked_by_sanitizer"]),
             u"| 扫描文件 | %d（重算 %d / 复用缓存 %d） |" % (
                 s.get("files_total", 0), s.get("recomputed_files", s.get("files_total", 0)),
                 s.get("cache_hit_files", 0)),
             u"| 粗筛候选文件 | %d（深挖只碰这些） |" % s.get("candidates", 0),
             u"| 严重度分布 | %s |" % u"、".join(
                 "%s=%d" % (k, v) for k, v in sorted(
                     s.get("by_severity", {}).items(), key=lambda kv: SEV_ORDER[kv[0]])),
             u""]
    if s.get("peak_memory_kb"):
        lines.append(u"| 粗筛峰值内存 | %d KB（tracemalloc 实测） |" % s["peak_memory_kb"])
        lines.append(u"")
    for f in payload["findings"]:
        v = f["verification"]
        lines += [u"## %d. [%s/%s 置信%s] %s — `%s:%d`" % (
            f["order"], f["severity"], f["kind"], f["confidence"]["label"],
            f["title"], f["file"], f["line"]), u"",
            u"- **位置**：`%s:%d`" % (f["file"], f["line"]),
            u"- **命中**：%s" % (f["sink_text"] or u"—"),
            u"- **CWE/OWASP**：%s / %s" % (u"、".join(f.get("cwe", [])) or u"—",
                                          u"、".join(f.get("owasp", [])) or u"—"),
            u"- **数据流**（%s）：" % f.get("depth", ""),]
        for hop in f.get("path", []):
            lines.append(u"  - `%s:%d` %s：%s" % (hop["file"], hop["line"], hop["kind"],
                                                  hop["text"][:120]))
        lines += [u"- **利用条件**：%s" % (u"可达（从入口/路由走得到）" if f["exploitable"]
                                          else u"不可达 — " + (f.get("note") or u"证据链上函数从入口不可达")),
                  u"- **置信度**：%s（%.2f）｜ **核验**：路径%s sink%s 输入%s 净化%s 可达%s" % (
                      f["confidence"]["label"], f["confidence"]["value"],
                      u"✓" if v["path_exists"] else u"✗",
                      u"✓" if v["sink_still_matches"] else u"✗",
                      u"✓" if v["input_controllable"] else u"✗",
                      u"未生效✓" if v["sanitizer_absent"] else u"存在✗",
                      u"✓" if v["sink_reachable"] else u"✗"),
                  u"- **修复示例**：%s" % (f.get("fix") or u"—"),
                  u"- **复测点**：%s" % (f.get("retest") or u"—"),
                  u"- **指纹**：`%s`%s" % (f["id"], u"（重复 %d 处已合并）"
                                          % f["duplicates"] if f.get("duplicates") else u""),
                  u""]
    if payload["dropped"]:
        lines += [u"## 验证环节丢弃（不粉饰）", u""]
        for d in payload["dropped"]:
            lines.append(u"- `%s:%s` %s → %s" % (d.get("file"), d.get("line"),
                                                 d.get("rule_id"), d.get("reason")))
        lines.append(u"")
    lines += [u"## 覆盖度与已知限制", u""]
    for lim in payload["coverage"]["limits"]:
        lines.append(u"- %s" % lim)
    lines.append(u"- 跳过的文件（二进制/超限）：%d 个" % payload["coverage"]["skipped_files"])
    lines.append(u"- 核验口径：%s" % payload["coverage"]["verification"])
    lines.append(u"")
    lines.append(u"RESULT: SCAN-OK（%d 条发现，其中不可达 %d 条已单独标注）" % (
        s["findings"], sum(1 for f in payload["findings"] if not f["exploitable"])))
    return u"\n".join(lines) + u"\n"


def to_sarif(payload, skill_version):
    used = {}
    results = []
    for f in payload["findings"]:
        if f["rule_id"] not in used:
            used[f["rule_id"]] = len(used)
        idx = used[f["rule_id"]]
        results.append({
            "ruleId": f["rule_id"], "ruleIndex": idx,
            "level": SARIF_LEVEL.get(f["severity"], "warning"),
            "message": {"text": u"%s — %s" % (f["title"], f["sink_text"] or u"")[:500]},
            "locations": [{"physicalLocation": {
                "artifactLocation": {"uri": f["file"], "uriBaseId": "%SRCROOT%"},
                "region": {"startLine": max(1, int(f["line"]))}}}],
            "partialFingerprints": {"primaryLocationLineHash": f["id"]},
            "codeFlows": [{"threadFlows": [{"locations": [
                {"location": {"physicalLocation": {
                    "artifactLocation": {"uri": hop["file"], "uriBaseId": "%SRCROOT%"},
                    "region": {"startLine": max(1, int(hop["line"]))},
                    "conceptualName": hop.get("kind", "")},
                    "message": {"text": hop.get("text", "")[:200]}}}
                for hop in f.get("path", [])]}]}] if f.get("path") else [],
            "properties": {"severity": f["severity"],
                           "confidence": f["confidence"]["value"],
                           "confidenceLabel": f["confidence"]["label"],
                           "exploitable": f["exploitable"], "kind": f["kind"],
                           "cwe": f.get("cwe", []), "owasp": f.get("owasp", []),
                           "fix": f.get("fix", ""), "retest": f.get("retest", "")},
        })
    rules_out = []
    for rule in payload.get("_rules", []):
        if rule["id"] not in used:
            continue
        rules_out.append({
            "id": rule["id"],
            "name": rule["title"],
            "shortDescription": {"text": rule["title"]},
            "fullDescription": {"text": rule.get("note") or rule["title"]},
            "helpUri": "https://github.com/Zhang-jx00/jiangzuo",
            "properties": {"tags": (rule.get("cwe", []) + rule.get("owasp", [])
                                     + [rule.get("severity", "")])},
            "defaultConfiguration": {"level": SARIF_LEVEL.get(rule.get("severity"), "warning")},
        })
    return {"$schema": SARIF_URI, "version": SARIF_VERSION,
            "runs": [{"tool": {"driver": {
                "name": TOOL_NAME, "version": skill_version,
                "informationUri": "https://github.com/Zhang-jx00/jiangzuo",
                "rules": rules_out}},
                "results": results,
                "columnKind": "utf16CodeUnits",
                "originalUriBaseIds": {"%SRCROOT%": {"uri": "file:///"}}}]}


def run(root, out_json=None, out_md=None, out_sarif=None, index_path=None,
        map_path=None, graph_path=None, user_rules=None, cache_dir=None,
        incremental=False, max_file_kb=2048, report_memory=False,
        ignore_patterns=None, fused=True, version="0.22.0"):
    root = os.path.abspath(root)
    max_bytes = max_file_kb * 1024
    rules, problems, _notes, _off = audit_rules.load_rules(user_rules or [])
    if problems:
        raise ValueError(u"规则库有问题，拒绝扫描：" + u"；".join(problems[:5]))
    rules_version = audit_rules.rules_version(rules)
    exclude = []
    for out in (out_json, out_md, out_sarif):
        if out:
            ap_ = os.path.abspath(out)
            if ap_.startswith(root + os.sep):
                exclude.append(auditlib.norm_rel(ap_, root))
    cache_file = os.path.join(cache_dir, "cache.json") if cache_dir else None
    if cache_file and os.path.abspath(cache_file).startswith(root + os.sep):
        exclude.append(auditlib.norm_rel(cache_file, root))

    t0 = time.time()
    cache = load_cache(cache_file, rules_version) if incremental else None
    taint_closure, cached_name_index = set(), None
    # 单遍前端（prescan）一次打开同时出索引、地图与粗筛命中；
    # 走缓存增量时仍用分步路径——它要按文件粒度复用，融合在那条路上没有收益。
    use_fused = bool(fused) and not index_path and not map_path and cache is None
    if use_fused:
        index, map_data, hits, imports, peak_kb = prescan(
            root, rules, max_bytes, exclude=exclude,
            extra_patterns=ignore_patterns or None, measure=report_memory)
        scan_index = index
        dirty = [rec["path"] for rec in index["files"]]
        cache_hits = []
    else:
        index = auditlib.load_index(index_path) if index_path else auditlib.build_index(
            root, max_file_bytes=max_bytes, exclude=exclude,
            extra_patterns=ignore_patterns or None)
        map_data = None
        if map_path:
            with io.open(map_path, "r", encoding="utf-8") as f:
                map_data = json.load(f)
        if map_data is None:
            map_data = audit_map.build_map(root, index=index, exclude=exclude)

        dirty, cache_hits = [], []
        if cache:
            by_path = dict((rec["path"], rec["sha1"]) for rec in index["files"])
            for rel, entry in cache.get("files", {}).items():
                if by_path.get(rel) == entry.get("sha1") and \
                        entry.get("rules_version") == rules_version:
                    cache_hits.append(rel)
                else:
                    dirty.append(rel)
            known = set(by_path)
            dirty = [r for r in dirty if r in known]
            for rel in known - set(cache.get("files", {})):
                dirty.append(rel)
        else:
            dirty = [rec["path"] for rec in index["files"]]

        # 增量闭包 = 变更文件 ∪ 其调用链邻居（用"便宜名片"算，不重新解析全仓）。
        # 为什么要它：taint 发现成不成立取决于**调用方**，只按 sink 文件自己的哈希
        # 决定复用，就会在改了 caller 之后把旧结论原样搬进新报告（实测漏过一次）。
        if cache and dirty:
            name_index = dict(cache.get("name_index") or {})
            sha_by_path = dict((r["path"], r["sha1"]) for r in index["files"])
            stale = set(dirty) | set(r for r, e in name_index.items()
                                    if e.get("sha1") != sha_by_path.get(r))
            for rec in index["files"]:
                if rec["path"] in stale and rec["lang"] in audit_graph.DEF_PATTERNS:
                    entry = audit_graph.name_entry(root, rec, max_bytes)
                    entry["sha1"] = rec["sha1"]
                    name_index[rec["path"]] = entry
            for rel in list(name_index):
                if rel not in sha_by_path:
                    del name_index[rel]
            cached_name_index = name_index
            taint_closure = audit_graph.closure_from_index(name_index, stale)

        scan_index = {"files": [rec for rec in index["files"]
                                if rec["path"] in set(dirty)],
                      "counts": index["counts"], "index_sha1": index["index_sha1"]}
        hits, imports, peak_kb, _ = coarse_screen(root, scan_index, rules, max_bytes,
                                                  peak=report_memory)
    findings = deep_pattern_findings(root, scan_index, rules, hits, max_bytes)
    reused = []
    if cache:
        for rel in cache_hits:
            for f in cache["files"][rel].get("findings", []):
                if rel in taint_closure and f.get("kind") == "taint":
                    continue      # 调用链邻居变了，这条流必须重算
                reused.append(f)
    findings = reused + findings
    findings.extend(auth_gap_findings(map_data, rules))
    findings.extend(dependency_findings(map_data, rules, imports))

    graph_parsed, graph_gated = 0, False
    stats_note = {}
    need_graph = True
    if cache and not set(dirty) and cache.get("flows") is not None:
        need_graph = False
        flows = cache["flows"]
    elif graph_path:
        with io.open(graph_path, "r", encoding="utf-8") as f:
            flows = json.load(f).get("flows", [])
        need_graph = False
    else:
        # seed 必须同时含 source 命中文件：跨文件污点流的**起点**往往在调用方，
        # 那里没有 sink。只按 sink 门控会把这类流整条丢掉（v0.21 就是这么退化的，
        # 由 TestAuditIncrementalGraph 抓到）。
        seed_files = set(r for r, i in hits.items() if i["sinks"])
        src_files = set(r for r, i in hits.items() if i["sources"] and not i["sinks"])
        if cached_name_index is not None:
            # 真增量：只重算"变更文件 ∪ 调用链邻居"，其余文件的污点流直接复用。
            # 闭包在上面算一次就好——这里再算一遍就是两份实现，迟早分叉。
            closure = taint_closure
            cached_sinks = set(r for r, e in cache.get("files", {}).items()
                              if (e.get("hits") or {}).get("sinks"))
            cached_srcs = set(r for r, e in cache.get("files", {}).items()
                              if (e.get("hits") or {}).get("sources")
                              and not (e.get("hits") or {}).get("sinks"))
            cand = (cached_sinks | seed_files) & closure
            src_cand = (cached_srcs | src_files) & closure
            graph = audit_graph.build_graph(root, index=index, map_data=map_data,
                                            rules=rules, candidates=cand,
                                            source_candidates=src_cand)
            reused = [f for f in cache.get("flows", []) if f["file"] not in closure]
            flows = reused + graph["flows"]
            stats_note = {"closure_files": len(closure), "reused_flows": len(reused)}
        else:
            graph = audit_graph.build_graph(root, index=index, map_data=map_data,
                                            rules=rules, candidates=seed_files,
                                            source_candidates=src_files)
            flows = graph["flows"]
            stats_note = {}
        graph_parsed = graph["stats"].get("parsed_files", 0)
        graph_gated = bool(graph["stats"].get("gated_by_candidates"))
    findings.extend(flow_findings({"flows": flows}))

    dropped = []
    verified = []
    line_cache = {}
    for f in findings:
        keep, result, reasons = verify(root, f, map_data, line_cache)
        if not keep:
            for reason in reasons:
                dropped.append({"rule_id": f["rule_id"], "file": f["file"],
                                "line": f.get("line"), "reason": reason})
            continue
        f["verification"] = result
        verified.append(grade(f, result))
    verified = rank_dependencies(verified)
    stats = {"graph_parsed_files": graph_parsed, "graph_gated": graph_gated,
             "closure_files": stats_note.get("closure_files", 0),
             "reused_flows": stats_note.get("reused_flows", 0),
             "files_total": len(index["files"]), "candidates": len(hits) + len(cache_hits),
             "recomputed_files": len(scan_index["files"]),
             "cache_hit_files": len(cache_hits), "files_cached": len(scan_index["files"]),
             "flows": len(flows), "elapsed_sec": round(time.time() - t0, 2),
             "peak_memory_kb": peak_kb}
    payload = build_report_payload(root, index, map_data, None, rules, verified, dropped,
                                   cache.get("blocked", []) if cache else [], stats)
    payload["_rules"] = [{"id": r["id"], "title": r["title"], "note": r.get("note", ""),
                          "cwe": r.get("cwe", []), "owasp": r.get("owasp", []),
                          "severity": r["severity"]} for r in rules]
    if cache_file:
        entries = dict((rel, {"sha1": rec["sha1"], "rules_version": rules_version,
                              "hits": hits.get(rel) or {},
                              "findings": [f for f in verified if f["file"] == rel]})
                       for rec in index["files"] for rel in [rec["path"]])
        # 名片索引 = "谁定义了谁、谁调用了谁"，是增量算邻居的依据。
        # 开了缓存就得付这一遍便宜扫描（不留函数体），换来之后每次增量只刷新脏文件；
        # 不建它，改了"调用方"就找不到下游的 sink 文件，增量会**假装没事**。
        name_index = {}
        for rec in index["files"]:
            if rec["lang"] not in audit_graph.DEF_PATTERNS:
                continue
            entry = audit_graph.name_entry(root, rec, max_bytes)
            entry["sha1"] = rec["sha1"]
            name_index[rec["path"]] = entry
        save_cache(cache_file, {"rules_version": rules_version,
                                "lib_version": auditlib.LIB_VERSION,
                                "index_sha1": index["index_sha1"],
                                "files": entries, "flows": flows,
                                "name_index": name_index,
                                "blocked": payload["blocked_by_sanitizer"]})
        payload["stats"]["cache_written"] = bool(cache_file)
    if out_json:
        d = os.path.dirname(os.path.abspath(out_json))
        if d and not os.path.isdir(d):
            os.makedirs(d)
        with io.open(out_json, "w", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False, indent=1, sort_keys=False) + "\n")
    if out_md:
        with io.open(out_md, "w", encoding="utf-8") as f:
            f.write(report_md(payload, root))
    if out_sarif:
        with io.open(out_sarif, "w", encoding="utf-8") as f:
            f.write(json.dumps(to_sarif(payload, version), ensure_ascii=False,
                               indent=1) + "\n")
    return payload


def main():
    ap = argparse.ArgumentParser(
        description=u"扫描调度与报告（将作）：粗筛→深挖→独立验证→分级→Markdown/JSON/SARIF。")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--json", dest="json_out", default=None)
    ap.add_argument("--md", dest="md_out", default=None)
    ap.add_argument("--sarif", dest="sarif_out", default=None)
    ap.add_argument("--index", default=None)
    ap.add_argument("--map", dest="map_in", default=None)
    ap.add_argument("--graph", default=None)
    ap.add_argument("--rules", dest="rules_in", action="append", default=[])
    ap.add_argument("--cache", default=None, help=u"缓存目录（默认关闭，需显式指定）")
    ap.add_argument("--incremental", action="store_true", help=u"配合 --cache 只重算变更文件")
    ap.add_argument("--max-file-kb", type=int, default=2048)
    ap.add_argument("--ignore", action="append", default=[],
                    help=u"追加忽略模式，可多次（如 --ignore 'tests/fixtures/**' 排除自造夹具）")
    ap.add_argument("--report-memory", action="store_true", help=u"粗筛阶段用 tracemalloc 测峰值")
    ap.add_argument("--staged", action="store_true",
                    help=u"走分步前端（索引→地图→粗筛三遍），用于与单遍融合版对照取证")
    ap.add_argument("--strict", action="store_true", help=u"critical/high 存在时退出码 1")
    ap.add_argument("--version", default="0.18.0", help=u"写进 SARIF 的工具版本")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(u"错误：目录不存在：%s" % args.path, file=sys.stderr)
        return 2
    try:
        payload = run(root, out_json=args.json_out, out_md=args.md_out,
                      out_sarif=args.sarif_out, index_path=args.index,
                      map_path=args.map_in, graph_path=args.graph,
                      user_rules=args.rules_in, cache_dir=args.cache,
                      incremental=args.incremental, max_file_kb=args.max_file_kb,
                      report_memory=args.report_memory,
                      ignore_patterns=args.ignore or None, fused=not args.staged)
    except ValueError as exc:
        print(u"错误：%s" % exc, file=sys.stderr)
        return 1

    s = payload["stats"]
    print(u"扫描：%d 文件（候选 %d / 重算 %d / 缓存复用 %d）｜ 粗筛峰值 %s KB ｜ 用时 %.2fs"
          % (s["files_total"], s["candidates"], s["recomputed_files"],
             s["cache_hit_files"], s.get("peak_memory_kb") or u"未测", s["elapsed_sec"]))
    dist = s.get("by_severity", {})
    print(u"发现 %d 条（%s）｜ 验证丢弃 %d 条 ｜ 净化排除 %d 处"
          % (s["findings"], u"、".join("%s=%d" % (k, dist[k])
                                     for k in audit_rules.SEVERITIES if dist.get(k)) or u"无",
             s["dropped_by_verifier"], len(payload["blocked_by_sanitizer"])))
    for f in payload["findings"][:12]:
        print(u"  %2d. [%s] %-14s 置信%s %-10s %s:%d"
              % (f["order"], f["severity"], f["rule_id"], f["confidence"]["label"],
                 f["kind"], f["file"], f["line"]))
    if len(payload["findings"]) > 12:
        print(u"  ……其余见报告")
    print(u"RESULT: SCAN-OK（%d 条发现，%d 条被独立验证拦下）"
          % (s["findings"], s["dropped_by_verifier"]))
    if args.strict and (dist.get("critical") or dist.get("high")):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
