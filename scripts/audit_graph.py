#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""跨文件调用图 + 污点分析 —— 将作 (jiangzuo) 审计链第 ④ 环

把"这行像危险调用"升级成"外部输入确实流到了这里，路上有没有被净化，
从入口/路由走不走得到"。产出带证据链的候选发现，交给 audit_scan.py 复核与定级。

用法:
    python audit_graph.py [项目目录] [--out graph.json] [--index 索引.json]
                          [--map 地图.json] [--rules rules.json] [--max-depth N] [--stats]

会做：函数级定义/调用抽取（Python 按缩进定界，其余按括号计数定界）、
      函数内污点传播（source→赋值→拼接→sink）、跨函数跨文件的参数传递、
      净化点断链并记账、从路由/入口出发的可达性 BFS、证据链逐跳 file:line。
不会做：AST 级精度（没有 tree-sitter，纯标准库；同名函数按名字解析，
      可能串味）、模块级代码的数据流（只分析函数体内）、
      kind=pattern 的规则（那是 audit_scan.py 的活）。
      每条发现都带 depth 字段声明自己分析到哪一档——不假装比实际更准。

仅使用 Python 标准库（3.8+），不联网、只读项目。
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditlib      # noqa: E402
import audit_map     # noqa: E402
import audit_rules   # noqa: E402

GRAPH_SCHEMA = "jiangzuo-audit-graph/1"
MAX_PASSES = 3           # 污点不动点迭代上限：3 轮还没稳定就按现状收，防大仓跑不完
MAX_CALL_FANOUT = 12     # 同名调用的候选被调方上限，防爆炸
MAX_PATH_HOPS = 8        # 单条证据链最多记 8 跳

DEF_PATTERNS = {
    "python": re.compile(r"^(?P<ind>[ \t]*)(?:async\s+)?def\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"),
    "ruby": re.compile(r"^\s*def\s+(?P<name>\w+[?!]?)(?:\s*\((?P<params>[^)]*)\))?"),
    "javascript": re.compile(r"(?:function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
                             r"|const\s+(?P<name2>\w+)\s*=\s*(?:async\s*)?\((?P<params2>[^)]*)\)\s*=>"
                             r"|(?P<name3>\w+)\s*\((?P<params3>[^)]*)\)\s*(?:async\s*)?\{)"),
    "java": re.compile(r"(?:public|private|protected|static|final|synchronized)"
                       r"[\w<>\[\],\s]*\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"
                       r"[^;{]*\{"),
    "php": re.compile(r"function\s+(?P<name>\w+)\s*\((?P<params>[^)]*)\)"),
    "go": re.compile(r"func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s*)?(?P<name>\w+)\s*\((?P<params>[^)]*)\)"),
}
DEF_PATTERNS["typescript"] = DEF_PATTERNS["javascript"]
DEF_PATTERNS["vue"] = DEF_PATTERNS["javascript"]
DEF_PATTERNS["kotlin"] = DEF_PATTERNS["java"]
DEF_PATTERNS["csharp"] = DEF_PATTERNS["java"]
DEF_PATTERNS["scala"] = DEF_PATTERNS["java"]

CALL_RX = re.compile(r"\b([A-Za-z_]\w*)\s*\(")
ASSIGN_RX = {
    "python": re.compile(r"^\s*(?P<target>\w+)\s*(?::[^=]*)?=\s*(?P<expr>.+)"),
    "ruby": re.compile(r"^\s*(?P<target>\w+)\s*=\s*(?P<expr>.+)"),
}
ASSIGN_RX["javascript"] = re.compile(
    r"(?:const|let|var)\s+(?P<target>\w+)\s*=\s*(?P<expr>.+)|"
    r"^\s*(?P<target2>\w+)\s*=\s*(?P<expr2>.+)")
ASSIGN_RX["java"] = re.compile(r"\b(?P<type>[\w<>]+)\s+(?P<target>\w+)\s*=\s*(?P<expr>.+)")
ASSIGN_RX["php"] = re.compile(r"\$(?P<target>\w+)\s*=\s*(?P<expr>.+)")
ASSIGN_RX["go"] = re.compile(r"(?::=|=)\s*(?P<expr>.+)|(?P<target>\w+)\s*:=")

IDENT_RX = re.compile(r"\b([A-Za-z_]\w*)\b")
JS_LIKE = ("javascript", "typescript", "vue")


def _params(raw):
    if not raw:
        return []
    out = []
    depth = 0
    cur = ""
    for ch in raw:
        if ch in "([{<":
            depth += 1
        elif ch in ")]}>":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    names = []
    for item in out:
        item = item.strip()
        if not item or item in ("self", "cls"):
            continue
        m = re.search(r"([A-Za-z_$]\w*)", item.replace("$", "_"))
        if m:
            names.append(m.group(1))
    return names


def _split_args(raw):
    out, depth, cur = [], 0, ""
    for ch in raw:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    if cur.strip():
        out.append(cur.strip())
    return out


def brace_end(lines, idx, indent):
    """括号计数定界；计数不可靠时退回 60 行窗口——诚实标注比假装精确好。"""
    depth = 0
    started = False
    for j in range(idx, len(lines)):
        text = lines[j][1]
        for ch in text:
            if ch == "{":
                depth += 1
                started = True
            elif ch == "}":
                depth -= 1
        if started and depth <= 0:
            return j + 1
    return min(len(lines), idx + 60)


def parse_functions(lang, rel, lines):
    """抽取函数边界。Python 用缩进，其它语言用括号计数。"""
    rx = DEF_PATTERNS.get(lang)
    if not rx:
        return []
    funcs = []
    for i, (lineno, text, _t) in enumerate(lines):
        m = rx.search(text)
        if not m:
            continue
        groups = m.groupdict()
        name = groups.get("name") or groups.get("name2") or groups.get("name3")
        if not name or name in ("if", "for", "while", "switch", "catch", "return"):
            continue
        raw_params = (groups.get("params") or groups.get("params2")
                      or groups.get("params3") or "")
        end = len(lines)
        if lang in ("python", "ruby"):
            ind = len(text) - len(text.lstrip())
            for j in range(i + 1, len(lines)):
                nxt = lines[j][1]
                if not nxt.strip():
                    continue
                nind = len(nxt) - len(nxt.lstrip())
                if nind <= ind and not nxt.lstrip().startswith(("#", ")", "]", "}")):
                    end = j
                    break
        else:
            end = brace_end(lines, i, 0)
        funcs.append({"name": name, "file": rel, "lang": lang,
                      "start": lineno, "end": lines[end - 1][0] if end <= len(lines) else lineno,
                      "params": _params(raw_params), "body": lines[i:end],
                      "indent": len(text) - len(text.lstrip())})
    # 丢弃被外层函数包含的内层定义重叠（同名同文件保留最短范围）
    return funcs


def enclosing_function(funcs, line):
    best = None
    for fn in funcs:
        if fn["start"] <= line <= fn["end"]:
            if best is None or (fn["end"] - fn["start"]) < (best["end"] - best["start"]):
                best = fn
    return best


def function_for_route(funcs, route_line):
    """路由装饰器/声明行之后第一个 def 就是处理函数。"""
    cands = [f for f in funcs if f["start"] >= route_line]
    return min(cands, key=lambda f: f["start"]) if cands else None


def collect_edges(funcs, name_index):
    """调用图：函数 → 该函数里出现的被调名（解析到候选定义）。"""
    edges = {}
    for fn in funcs:
        names = set()
        for _lineno, text, _t in fn["body"]:
            for m in CALL_RX.finditer(text):
                n = m.group(1)
                if n == fn["name"] or n in ("if", "for", "while", "switch", "return",
                                           "catch", "def", "func"):
                    continue
                names.add(n)
        targets = []
        for n in names:
            for d in name_index.get(n, [])[:MAX_CALL_FANOUT]:
                targets.append((d["file"], d["name"]))
        edges[(fn["file"], fn["name"])] = targets
    return edges


def reachable_roots(map_data, all_funcs):
    roots = set()
    for route in map_data.get("routes", []):
        fn = function_for_route(enclosing_for_file(all_funcs).get(route["file"], []),
                                route["line"])
        if fn:
            roots.add((fn["file"], fn["name"]))
    entry_files = set(e["path"] for e in map_data.get("entrypoints", []))
    for fn in all_funcs:
        if fn["file"] in entry_files and fn["indent"] == 0:
            roots.add((fn["file"], fn["name"]))
    return roots


_FILE_FUNCS = {}


def enclosing_for_file(all_funcs):
    out = {}
    for fn in all_funcs:
        out.setdefault(fn["file"], []).append(fn)
    return out


def reachable_set(roots, edges):
    seen, stack = set(roots), list(roots)
    while stack:
        cur = stack.pop()
        for nxt in edges.get(cur, []):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _hop_view(hop):
    """导出前把证据文本截到 200 字并脱敏，其余字段原样带走。"""
    rec = dict(hop)
    rec["text"] = auditlib.redact(hop.get("text", ""))[:200]
    return rec


class Flow(object):
    def __init__(self, rule, fn, hops, sanitizer_hops):
        self.rule = rule
        self.fn = fn
        self.hops = hops
        self.sanitizers = sanitizer_hops

    def as_dict(self, all_reachable, edges_names):
        sink_hop = self.hops[-1]
        funcs_in_path = set()
        for h in self.hops:
            f = enclosing_function(_FILE_FUNCS.get(h["file"], []), h["line"])
            if f:
                funcs_in_path.add((f["file"], f["name"]))
        reachable = bool(funcs_in_path) and all(
            fr in all_reachable for fr in funcs_in_path)
        depth = "function-local"
        if len(set(h["file"] for h in self.hops)) > 1 or len(funcs_in_path) > 1:
            depth = "interprocedural"
        return {
            "rule_id": self.rule["id"],
            "title": self.rule["title"],
            "severity": self.rule["severity"],
            "confidence_base": self.rule.get("confidence_base", 0.5),
            "cwe": self.rule.get("cwe", []),
            "owasp": self.rule.get("owasp", []),
            "file": sink_hop["file"],
            "line": sink_hop["line"],
            "sink_text": auditlib.redact(sink_hop["text"].strip())[:200],
            "path": [_hop_view(h) for h in self.hops],
            "sanitizers_seen": [s["rule_field"] for s in self.sanitizers],
            "depth": depth,
            "reachable": reachable,
            "unreachable_reason": ("" if reachable else
                                   u"不可利用：证据链上的函数从入口/路由不可达"),
            "fix": self.rule.get("fix", ""),
            "retest": self.rule.get("retest", ""),
        }


def analyze_function(fn, rules, tainted_params, transfers, blocked, stats):
    """函数内污点传播 + 出参传递登记。tainted_params[(file,name)] = set(参数名)。"""
    key = (fn["file"], fn["name"])
    tainted = {}                       # var -> hops 列表
    for pname, incoming in (tainted_params.get(key) or {}).items():
        tainted[pname] = list(incoming) + [{
            "file": fn["file"], "line": fn["start"], "kind": "param-in",
            "text": u"形参 %s 由调用方传入污点值" % pname}]
    for rule in rules:
        if rule.get("kind") != "taint":
            continue
        if fn["lang"] not in rule.get("languages", []) and "*" not in rule.get("languages", []):
            continue
        sinks, sources, sanits = rule["sinks"], rule["sources"], rule["sanitizers"]
        arx = ASSIGN_RX.get(fn["lang"])
        for lineno, text, _trunc in fn["body"]:
            src_hit = any(s["_rx"].search(text) for s in sources)
            sink_hit = any(s["_rx"].search(text) for s in sinks)
            san_hit = any(s["_rx"].search(text) for s in sanits)
            if src_hit:
                target = None
                if arx:
                    m = arx.search(text)
                    if m:
                        target = (m.groupdict().get("target")
                                  or m.groupdict().get("target2"))
                if san_hit:
                    blocked.append({"rule_id": rule["id"], "file": fn["file"],
                                    "line": lineno,
                                    "sanitizer": [s["pattern"] for s in sanits
                                                  if s["_rx"].search(text)][0],
                                    "text": auditlib.redact(text.strip())[:160]})
                    stats["blocked_by_sanitizer"] += 1
                    if target and target in tainted:
                        del tainted[target]
                    continue
                if target:
                    tainted[target] = [{"file": fn["file"], "line": lineno,
                                        "kind": "source", "text": text}]
                    stats["sources"] += 1
                else:
                    tainted.setdefault("__inline__", []).append(
                        {"file": fn["file"], "line": lineno, "kind": "source",
                         "text": text})
            if arx and not src_hit:
                m = arx.search(text)
                if m and m.groupdict().get("target") or (m and m.groupdict().get("target2")):
                    target = m.groupdict().get("target") or m.groupdict().get("target2")
                    expr = m.groupdict().get("expr") or m.groupdict().get("expr2") or ""
                    carriers = [v for v in IDENT_RX.findall(expr) if v in tainted]
                    if carriers:
                        if san_hit:
                            blocked.append({"rule_id": rule["id"], "file": fn["file"],
                                            "line": lineno,
                                            "sanitizer": "assignment-line", "text": text})
                            stats["blocked_by_sanitizer"] += 1
                            continue
                        tainted[target] = tainted[carriers[0]] + [
                            {"file": fn["file"], "line": lineno, "kind": "propagate",
                             "text": text}]
            if sink_hit:
                idents = IDENT_RX.findall(text)
                carriers = [v for v in idents if v in tainted]
                if not carriers and "__inline__" in tainted:
                    carriers = ["__inline__"]
                if carriers:
                    hops = tainted[carriers[0]] + [
                        {"file": fn["file"], "line": lineno, "kind": "sink", "text": text}]
                    if len(hops) > MAX_PATH_HOPS:
                        hops = hops[:MAX_PATH_HOPS - 1] + hops[-1:]
                    yield Flow(rule, fn, hops, [])
                else:
                    stats["sink_without_taint"] += 1
        # 出参传递：本函数里调用了 name(污点实参)
        for lineno, text, _t in fn["body"]:
            for m in re.finditer(r"\b([A-Za-z_]\w*)\s*\(", text):
                callee = m.group(1)
                inner, depth = "", 0
                for ch in text[m.end() - 1:]:
                    if ch == "(":
                        depth += 1
                    elif ch == ")":
                        depth -= 1
                        if depth == 0:
                            break
                    inner += ch
                args = _split_args(inner.lstrip("("))
                for idx, arg in enumerate(args):
                    carriers = [v for v in IDENT_RX.findall(arg) if v in tainted]
                    if carriers:
                        transfers.append({"callee_name": callee, "arg_index": idx,
                                          "caller": (fn["file"], fn["name"]),
                                          "hops": tainted[carriers[0]] + [
                                              {"file": fn["file"], "line": lineno,
                                               "kind": "call-out", "text": text}],
                                          "rule_id": rule["id"]})


def build_graph(root, index=None, map_data=None, rules=None, max_bytes=None,
                max_passes=None):
    root = os.path.abspath(root)
    if index is None:
        index = auditlib.build_index(root)
    if map_data is None:
        map_data = audit_map.build_map(root, index=index)
    if rules is None:
        rules, problems, _notes = audit_rules.load_rules([])
        if problems:
            raise ValueError(u"规则库有问题，拒绝出图：%s" % u"；".join(problems[:3]))

    all_funcs = []
    per_file = {}
    for rec in index["files"]:
        if rec["lang"] not in DEF_PATTERNS:
            continue
        abs_path = os.path.join(root, rec["path"].replace("/", os.sep))
        lines = list(auditlib.iter_lines(abs_path, max_bytes=max_bytes
                                         or auditlib.DEFAULT_MAX_FILE_BYTES))
        if not lines:
            continue
        funcs = parse_functions(rec["lang"], rec["path"], lines)
        for fn in funcs:
            fn["file_rec"] = rec
        all_funcs.extend(funcs)
        per_file[rec["path"]] = funcs
    _FILE_FUNCS.clear()
    _FILE_FUNCS.update(per_file)

    name_index = {}
    for fn in all_funcs:
        name_index.setdefault(fn["name"], []).append(fn)

    edges = collect_edges(all_funcs, name_index)
    roots = reachable_roots(map_data, all_funcs)
    reached = reachable_set(roots, edges)

    taint_rules = [r for r in rules if r.get("kind") == "taint"]
    flows, blocked, stats = [], [], {"sources": 0, "blocked_by_sanitizer": 0,
                                     "sink_without_taint": 0, "passes": 0}
    tainted_params = {}
    for _pass in range(max_passes or MAX_PASSES):
        stats["passes"] = _pass + 1
        transfers = []
        new_found = []
        for fn in all_funcs:
            for flow in analyze_function(fn, taint_rules, tainted_params, transfers,
                                         blocked, stats):
                new_found.append(flow)
        for flow in new_found:
            if not any(f.rule["id"] == flow.rule["id"]
                       and f.hops[-1]["line"] == flow.hops[-1]["line"]
                       and f.hops[-1]["file"] == flow.hops[-1]["file"] for f in flows):
                flows.append(flow)
        changed = False
        for tr in transfers:
            for cand in name_index.get(tr["callee_name"], [])[:MAX_CALL_FANOUT]:
                params = cand["params"]
                if tr["arg_index"] < len(params):
                    pname = params[tr["arg_index"]]
                    k = (cand["file"], cand["name"])
                    slot = tainted_params.setdefault(k, {})
                    if pname not in slot:
                        slot[pname] = tr["hops"]
                        changed = True
        if not changed:
            break

    out_flows = [f.as_dict(reached, name_index) for f in flows]
    out_flows.sort(key=lambda f: (f["severity"] != "critical", f["rule_id"],
                                  f["file"], f["line"]))
    payload = {
        "schema": GRAPH_SCHEMA,
        "index_sha1": index.get("index_sha1", ""),
        "map_sha1": map_data.get("map_sha1", ""),
        "rules_version": audit_rules.rules_version(rules),
        "functions": [{"name": f["name"], "file": f["file"], "lang": f["lang"],
                       "start": f["start"], "end": f["end"], "params": f["params"],
                       "calls": [t[1] for t in edges.get((f["file"], f["name"]), [])]}
                      for f in sorted(all_funcs, key=lambda f: (f["file"], f["start"]))],
        "flows": out_flows,
        "blocked": blocked,
        "stats": {"files": len(index["files"]), "functions": len(all_funcs),
                  "flows": len(out_flows), "reachable_flows": sum(
                      1 for f in out_flows if f["reachable"]),
                  "roots": len(roots), "reached": len(reached),
                  "passes": stats["passes"], **stats},
    }
    return payload


def main():
    ap = argparse.ArgumentParser(
        description=u"跨文件调用图与污点分析（将作）：source→sink 逐跳证据链与可达性。")
    ap.add_argument("path", nargs="?", default=".", help=u"项目目录")
    ap.add_argument("--out", default=None, help=u"输出 graph JSON 路径")
    ap.add_argument("--index", default=None, help=u"复用已有索引 JSON")
    ap.add_argument("--map", dest="map_in", default=None, help=u"复用已有地图 JSON")
    ap.add_argument("--rules", dest="rules_in", default=None, help=u"用户规则文件（可多次）")
    ap.add_argument("--max-depth", type=int, default=MAX_PASSES, help=u"污点迭代轮数上限")
    ap.add_argument("--stats", action="store_true", help=u"只打印统计")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(u"错误：目录不存在：%s" % args.path, file=sys.stderr)
        return 2

    index = auditlib.load_index(args.index) if args.index else None
    map_data = None
    if args.map_in:
        with io.open(args.map_in, "r", encoding="utf-8") as f:
            map_data = json.load(f)
    rules = None
    if args.rules_in:
        rules, problems, _notes = audit_rules.load_rules(args.rules_in)
        if problems:
            for p in problems:
                print(u"  ✘ %s" % p, file=sys.stderr)
            return 1

    data = build_graph(root, index=index, map_data=map_data, rules=rules,
                       max_passes=max(1, args.max_depth))
    if args.out:
        out_dir = os.path.dirname(os.path.abspath(args.out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(args.out, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    s = data["stats"]
    print(u"图：函数 %d ｜ 污点流 %d（可达 %d）｜ 净化断链 %d ｜ 不动点迭代 %d 轮 ｜ 入口点 %d"
          % (s["functions"], s["flows"], s["reachable_flows"],
             s["blocked_by_sanitizer"], s["passes"], s["roots"]))
    if args.stats:
        for flow in data["flows"][:20]:
            print(u"  %-14s %-10s %s:%d  链长%d  %s"
                  % (flow["rule_id"], flow["severity"], flow["file"], flow["line"],
                     len(flow["path"]), u"可达" if flow["reachable"] else u"不可达"))
    if not args.out:
        print(u"提示：加 --out graph.json 供 audit_scan.py 消费")
    print(u"RESULT: GRAPH-OK（rules_version=%s）" % data["rules_version"][:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
