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
                             r"|(?P<name3>\w+)\s*\((?P<params3>[^)]*)\)\s*(?:=>\s*)?\{)"),
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
# PHP：`$x = …` 之外还必须认 `$html .= …`（拼接累加是 PHP 的主流输出构造写法，
# DVWA 的反射输出就是 `$html .= "… {$_GET[…]}";` 后 `echo $html;`——只认 `=` 时
# 污点在累加处断掉）。`=(?!=)` 把 `==` 排除掉，否则比较行会被当成赋值。
ASSIGN_RX["php"] = re.compile(r"\$(?P<target>\w+)\s*(?:\.=|=(?!=))\s*(?P<expr>.+)")
ASSIGN_RX["go"] = re.compile(r"(?::=|=)\s*(?P<expr>.+)|(?P<target>\w+)\s*:=")

IDENT_RX = re.compile(r"\b([A-Za-z_]\w*)\b")
JS_LIKE = ("javascript", "typescript", "vue")

# PHP 页面入口判定：模块级出现"变量读写"才算这页真的在处理数据；
# 成员声明/继承/类定义那些行不算（库里满是这样写的文件）。
PHP_VAR_RX = re.compile(r"\$\w+")
PHP_MEMBER_RX = re.compile(
    r"^\s*(?:public|private|protected|static|const|var|function|abstract|final"
    r"|interface|trait|class|namespace|use|extends|implements|require|include)\b")
PHP_NON_PAGE_RX = re.compile(r"(?:^|/)(?:tests?|spec|docs?|examples?|vendor)/")

STR_SPAN_RX = re.compile(
    r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"|`(?:[^`\\]|\\.)*`")
PHP_INTERP_RX = re.compile(r"\$(\w+)")
RUBY_INTERP_RX = re.compile(r"#\{\s*(\w+)")
JS_INTERP_RX = re.compile(r"\$\{\s*(\w+)")
PY_INTERP_RX = re.compile(r"\{([^{}]*)\}")


def carriers_of(text, lang):
    """取一行里真正"被读的变量名"——字符串字面量里的普通单词不算读取。

    这条是 DVWA 实测逼出来的：impossible.php（修复版）里
    `$data = $db->prepare( 'SELECT … WHERE user_id = (:id)' )` 的占位符名 `:id`
    撞上上面 `$_GET[ 'id' ]` 的变量名 `id`，引擎以为这一行读了 `id`，
    于是 prepare→fetch→print 一路把**安全写法**报成反射 XSS。
    SQL 关键字、列名、占位符、注释性文本都在字符串里，不是数据流。
    只有各语言明确的"字符串内插"语法才算：PHP 双引号 `$var`、
    Ruby 双引号 `#{var}`、JS 模板串 `${var}`、Python f-string `{expr}`。
    """
    out = []
    pos = 0
    for m in STR_SPAN_RX.finditer(text):
        out.extend(IDENT_RX.findall(text[pos:m.start()]))
        body = m.group(0)
        quote = body[0]
        if lang == "python":
            # f"…" 的引号前 2 个字符里一定有 f（STR_SPAN_RX 从前引号开始匹配，
            # 不含前缀）；普通 "…" 里的 SQL 关键字不算变量读取。
            pre = text[max(0, m.start() - 2):m.start()].lower()
            if quote in "'\"" and "f" in pre:
                for inner in PY_INTERP_RX.findall(body[1:-1]):
                    out.extend(IDENT_RX.findall(inner))
        elif quote == '"' and lang == "php":
            out.extend(PHP_INTERP_RX.findall(body))
        elif quote == '"' and lang == "ruby":
            out.extend(RUBY_INTERP_RX.findall(body))
        elif quote == "`" and lang in JS_LIKE:
            out.extend(JS_INTERP_RX.findall(body))
        pos = m.end()
    out.extend(IDENT_RX.findall(text[pos:]))
    return out


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


def add_module_scope(funcs, rel, lang, lines):
    """把没被任何函数包裹的行合成一个 {module} 作用域。

    PHP/Node 的过程式脚本顶层就是一条 source→sink（验收夹具实测因此漏检）；
    不补这一档，整份文件都不进数据流。
    """
    covered = set()
    for fn in funcs:
        for ln in range(fn["start"], fn["end"] + 1):
            covered.add(ln)
    rest = [(n, t, x) for n, t, x in lines if n not in covered]
    if len(rest) >= 3:
        funcs.append({"name": "{module}", "file": rel, "lang": lang,
                      "start": rest[0][0], "end": rest[-1][0], "params": [],
                      "body": rest, "indent": 0})
    return funcs


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
    # 过程式 PHP：一个 .php 文件本身就是一个 URL，不需要被谁调用。
    # DVWA 的漏洞体在 vulnerabilities/*/source/*.php，由 index.php 用
    # `require_once DVWA_WEB_PAGE_TO_ROOT . "…/{$vulnerabilityFile}"` 引入——
    # 变量路径 + 无括号 include 静态图跟不动，于是把招牌漏洞标成"不可利用"。
    # 边界：模块级要出现"变量读写"才算页面（纯 class/namespace/use/属性的定义
    # 文件不算），并跳过 tests/examples/docs/vendor 这类非部署路径。
    for fn in all_funcs:
        if fn["lang"] != "php" or fn["name"] != "{module}":
            continue
        if PHP_NON_PAGE_RX.search(fn["file"]):
            continue
        if any(PHP_VAR_RX.search(t) and not PHP_MEMBER_RX.match(t)
               for _n, t, _x in fn["body"]):
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


def _first_code_match(items, text):
    """返回第一个**落在代码里**（不在字符串字面量内）的命中项。

    没有这一道，测试夹具里当字符串写的 `os.system(...)` 会被当成真漏洞——
    自扫本仓库实测：14 条发现全部来自夹具/生成器字符串，全是误报。
    """
    for item in items:
        m = item["_rx"].search(text)
        if m and not auditlib.match_in_string(text, m.start()):
            return item
    return None


def analyze_function(fn, rules, tainted_params, transfers, blocked, stats):
    """函数内污点传播 + 出参传递登记。tainted_params[(file,name)] = set(参数名)。"""
    key = (fn["file"], fn["name"])
    # 污点上下文**按规则隔离**：净化点是每条规则自己的（SQL 注入认 int()，
    # SSRF 不认）。共用一份 tainted 会让 A 规则的净化被 B 规则的 source 绕过，
    # 最后由 C 条 sink 认领——实测就是 int() 净化后跨文件流照报。
    in_params = tainted_params.get(key) or {}
    # 每行的"被读变量名"只算一次（按语言剥字符串字面量），规则循环里复用。
    body_view = [(ln, tx, _x, carriers_of(tx, fn["lang"])) for ln, tx, _x in fn["body"]]
    for rule in rules:
        if rule.get("kind") != "taint":
            continue
        if fn["lang"] not in rule.get("languages", []) and "*" not in rule.get("languages", []):
            continue
        sinks, sources, sanits = rule["sinks"], rule["sources"], rule["sanitizers"]
        arx = ASSIGN_RX.get(fn["lang"])
        tainted = {}                   # 本规则视角下的 var -> hops 列表
        for pname, incoming in (in_params.get(rule["id"]) or {}).items():
            tainted[pname] = list(incoming) + [{
                "file": fn["file"], "line": fn["start"], "kind": "param-in",
                "text": u"形参 %s 由调用方传入污点值" % pname}]
        for lineno, text, _trunc, idents in body_view:
            src_item = _first_code_match(sources, text)
            sink_item = _first_code_match(sinks, text)
            san_item = _first_code_match(sanits, text)
            src_hit = bool(src_item)
            sink_hit = bool(sink_item)
            san_hit = bool(san_item)
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
                                    "sanitizer": san_item["pattern"],
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
                    # 只算等号右边的"被读变量"——左边的目标名不是读取（自我强化会
                    # 让 hops 每行 +1，MAX_PATH_HOPS 只是兜底不是设计）。
                    key_name = "expr" if m.groupdict().get("expr") else "expr2"
                    carriers = [v for v in carriers_of(text[m.start(key_name):], fn["lang"])
                                if v in tainted]
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
                carriers = [v for v in idents if v in tainted]
                if not carriers and "__inline__" in tainted:
                    # 兜底只认"同一行内联"：source 表达式直接写在 sink 调用里
                    # （os.system("ls " + request.args['d'])、echo $_GET['page']）。
                    # 跨行借用会把守卫当数据入口——DVWA 每个模块开头的
                    # `if ( isset( $_POST['Submit'] ) )` 实测把同函数里一条与请求
                    # 无关的 `echo $out` 带成了反射 XSS。
                    if any(h["line"] == lineno and h["file"] == fn["file"]
                           for h in tainted["__inline__"]):
                        carriers = ["__inline__"]
                if carriers:
                    hops = tainted[carriers[0]] + [
                        {"file": fn["file"], "line": lineno, "kind": "sink", "text": text}]
                    # 同函数内、source 与 sink 之间出现过净化/守卫 → 判为已净化，不报流
                    same_file = [h["line"] for h in hops if h["file"] == fn["file"]]
                    lo = min(same_file or [lineno])
                    guard = [s for s in sanits
                             for ln, t, _x in fn["body"]
                             if lo <= ln <= lineno and _first_code_match([s], t)]
                    if guard:
                        blocked.append({"rule_id": rule["id"], "file": fn["file"],
                                        "line": guard[0]["pattern"],
                                        "sanitizer": guard[0]["pattern"],
                                        "text": u"source 与 sink 之间出现净化/守卫"})
                        stats["blocked_by_sanitizer"] += 1
                        continue
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
                    carriers = [v for v in carriers_of(arg, fn["lang"]) if v in tainted]
                    if not carriers and _first_code_match(sources, arg):
                        # 实参本身就是外部输入：top(request.args["d"])
                        # 不先赋给变量，一样是污点入口。
                        carriers = ["__inline__"]
                        tainted.setdefault("__inline__", []).append(
                            {"file": fn["file"], "line": lineno, "kind": "source",
                             "text": text})
                    if carriers:
                        transfers.append({"callee_name": callee, "arg_index": idx,
                                          "caller": (fn["file"], fn["name"]),
                                          "hops": tainted[carriers[0]] + [
                                              {"file": fn["file"], "line": lineno,
                                               "kind": "call-out", "text": text}],
                                          "rule_id": rule["id"]})


def _stream_lines(root, rec, limit):
    return auditlib.iter_code_lines(
        os.path.join(root, rec["path"].replace("/", os.sep)), max_bytes=limit)


def _collect_calls(root, rec, limit):
    names = set()
    for _n, text, _t in _stream_lines(root, rec, limit):
        for m in CALL_RX.finditer(text):
            names.add(m.group(1))
    return names


def _def_names(root, rec, limit):
    """只扫 def 行拿函数名：不切函数体、不留行。

    图层要跨文件解析调用，得先知道"这个名字在哪个文件被定义"；
    但为这件事把全仓函数体都留在内存里，就是基准实测的 32MB/96% 峰值来源。
    """
    rx = DEF_PATTERNS.get(rec["lang"])
    out = set()
    if not rx:
        return out
    for _n, text, _t in _stream_lines(root, rec, limit):
        m = rx.search(text)
        if not m:
            continue
        groups = m.groupdict()
        for key in ("name", "name2", "name3"):
            if groups.get(key):
                out.add(groups[key])
                break
    return out



def name_entry(root, rec, limit):
    """一个文件的**便宜名片**：它定义了哪些名字、调用了哪些名字（不留函数体）。

    增量扫描靠它算"调用链邻居"：不必重新解析全仓，也能知道
    改了 A 之后，哪些文件因为调用 A 里的东西而可能被影响。
    """
    defs = sorted(_def_names(root, rec, limit))
    calls = sorted(_collect_calls(root, rec, limit))
    return {"defs": defs, "calls": calls, "lang": rec["lang"]}


def closure_from_index(name_index, seed, sha1_by_path=None):
    """seed ∪ seed 调用的定义文件 ∪ 调用了 seed 内定义的文件（一跳，可复现）。"""
    seed = set(seed)
    out = set(seed)
    seed_calls = set()
    seed_defs = set()
    for rel in seed:
        entry = name_index.get(rel) or {}
        seed_calls |= set(entry.get("calls") or [])
        seed_defs |= set(entry.get("defs") or [])
    for rel, entry in name_index.items():
        defs = set(entry.get("defs") or [])
        calls = set(entry.get("calls") or [])
        if (defs & seed_calls) or (calls & seed_defs):
            out.add(rel)
    return out

def build_graph(root, index=None, map_data=None, rules=None, max_bytes=None,
                max_passes=None, candidates=None, source_candidates=None):
    """candidates：粗筛给出的候选文件集合。

    给了就**门控**——粗筛没有候选 → 图层直接空转返回；有候选 → 只全量解析
    "候选文件 ∪ 被候选文件调用的定义文件"。不给则维持旧行为（全仓解析）。
    这是把"贵层由便宜层驱动"落到结构上：干净仓库扫描的图层成本应接近 0。
    """
    root = os.path.abspath(root)
    limit = max_bytes or auditlib.DEFAULT_MAX_FILE_BYTES
    if index is None:
        index = auditlib.build_index(root)
    if map_data is None:
        map_data = audit_map.build_map(root, index=index)
    if rules is None:
        rules, problems, _notes, _off = audit_rules.load_rules([])
        if problems:
            raise ValueError(u"规则库有问题，拒绝出图：%s" % u"；".join(problems[:3]))

    source_recs = [r for r in index["files"] if r["lang"] in DEF_PATTERNS]
    by_path = dict((r["path"], r) for r in source_recs)
    gated_skip = False
    if candidates is None:
        parse_set = set(by_path)
    else:
        cand = set(candidates) & set(by_path)
        if not cand:
            parse_set, gated_skip = set(), True
        else:
            seeds = set(cand)
            # 名片索引一次算完，后面两处判定都复用它（各算一遍就是两遍全仓扫描）。
            defs_by_file = {}
            calls_by_file = {}
            for rec in source_recs:
                defs_by_file[rec["path"]] = _def_names(root, rec, limit)
            all_defs = set()
            for names in defs_by_file.values():
                all_defs |= names

            def _outbound(rel):
                """本文件调用的、**不是自己定义的**仓库内名字。"""
                own = defs_by_file.get(rel) or set()
                return (_collect_calls(root, by_path[rel], limit) - own) & (all_defs - own)

            # source 命中文件只有"会调用到仓库内别的文件定义的函数"时，
            # 才可能是跨文件污点流的起点；否则数据只会在本文件内成流，
            # 而本文件有 sink 时它早就是候选了。少了这一道，
            # 满屏带 request.args 的路由文件都会被拖进图层（实测 1025/1502）。
            for rel in sorted(set(source_candidates or ()) - seeds):
                if _outbound(rel):
                    seeds.add(rel)
            called = set()
            for rel in sorted(seeds):
                called |= (_collect_calls(root, by_path[rel], limit))
            parse_set = set(seeds)
            for rec in source_recs:
                if rec["path"] in parse_set:
                    continue
                if defs_by_file[rec["path"]] & called:
                    parse_set.add(rec["path"])

    all_funcs = []
    per_file = {}
    for rec in source_recs:
        if rec["path"] not in parse_set:
            continue
        abs_path = os.path.join(root, rec["path"].replace("/", os.sep))
        lines = list(auditlib.iter_lines(abs_path, max_bytes=limit))
        if not lines:
            continue
        funcs = add_module_scope(parse_functions(rec["lang"], rec["path"], lines),
                                 rec["path"], rec["lang"], lines)
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
                    slot = tainted_params.setdefault(k, {}).setdefault(
                        tr["rule_id"], {})
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
                  "passes": stats["passes"],
                  "parsed_files": len(per_file),
                  "gated_by_candidates": gated_skip, **stats},
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
        rules, problems, _notes, _off = audit_rules.load_rules(args.rules_in)
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
