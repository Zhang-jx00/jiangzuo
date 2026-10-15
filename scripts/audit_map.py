#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""项目侦察与全仓地图 —— 将作 (jiangzuo) 审计链第 ② 环

在扫描之前先回答「这个仓库是什么语言、入口在哪、暴露了哪些路由、
哪些路由没见过鉴权边界、依赖了什么」。产出机器可读地图 JSON +
人类可读概览，供 audit_graph.py / audit_scan.py 当前置输入。

用法:
    python audit_map.py [项目目录] [--json 地图.json] [--md 概览.md]
                        [--index 索引.json] [--no-git] [--max-file-kb N] [--stats]

会做：语言分布、入口识别（文件名+启动语句双路）、HTTP 路由抽取
      （FastAPI/Flask/Django/Express/Nest/Spring/Laravel/Gin/Rails）、
      鉴权边界与「未见鉴权标记」的路由、依赖与锁文件、环境变量名、外部连接点。
不会做：判定漏洞（那是规则引擎的事）、判断鉴权是否**足够**
      （某路由 auth=false 只表示「本文件里没看到鉴权标记」，全局中间件、
       网关、装饰器在别处注册的情况它看不见——看见不当证据用是审计的头号误报源）。

依赖 audit_index.py / auditlib.py 的同一份文件清单：三处各走一遍目录、
结论对不上，是审计工具最常见的自伤。

仅使用 Python 标准库（3.8+），不联网、只读项目。
"""
import argparse
import io
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditlib  # noqa: E402
import project_scan  # noqa: E402  复用已有判定，不重写第二遍（复用阶梯第 2 级）

MAP_SCHEMA = "jiangzuo-audit-map/1"

# 入口：文件名命中即候选，启动语句命中则附带理由
ENTRY_NAMES = {
    "main.py", "app.py", "server.py", "asgi.py", "wsgi.py", "manage.py",
    "application.py", "index.js", "index.ts", "main.js", "main.ts",
    "server.js", "server.ts", "app.js", "app.ts", "index.jsx", "main.go",
    "main.rs", "mod.rs", "Program.cs", "Startup.cs", "Application.java",
    "app.rb", "config.ru", "index.php", "wp-config.php", "docker-compose.yml",
    "docker-compose.yaml", "Procfile", "Dockerfile",
}

ENTRY_CALLS = [
    ("uvicorn.run(", "Python/uvicorn 启动"),
    ("app.run(", "Flask 启动"),
    ("createServer(", "Node http 服务"),
    ("app.listen(", "Express 监听端口"),
    ("SpringApplication.run(", "Spring Boot 启动"),
    ("ListenAndServe(", "Go http 服务"),
    ("router.Run(", "Gin 监听"),
    ("Rails.application", "Rails 启动"),
]

AUTH_RX = re.compile(r"\b(login_required|requires_auth|requireAuth|require_auth|"
                     r"ensureAuthenticated|ensure_admin|jwt_required|auth_required|"
                     r"verify_token|check_token|checkToken|get_current_user|"
                     r"current_user|permission_classes|permission_required|"
                     r"PreAuthorize|PreAuthorize\(|@Secured|Secured\(|RolesAllowed|"
                     r"UseGuards|JwtAuthGuard|isAuthenticated|authenticate|"
                     r"authorizeRequests|authorizeHttpRequests|before_action|"
                     r"Depends)\b")

# 路由模式：path 必须以 / 或字母开头，避免把 map.get("key") 当路由。
# 每条模式自带"适用语言集合"——auditlib 的语言名是 javascript/typescript，
# 不是简写 js；早先用简写比较导致 Express 路由整批漏识别（测试实测出来的）。
ROUTE_PATTERNS = [
    ({"python"}, re.compile(
        r"@\s*(?P<obj>[A-Za-z_][\w.]*)\s*\.\s*(?P<m>get|post|put|patch|delete|head|"
        r"options|route|websocket)\s*\(\s*[\"'](?P<path>[^\"']+)[\"'](?P<rest>[^)]*)")),
    ({"python"}, re.compile(
        r"(?<![\w.])(?P<m>path|re_path|url)\s*\(\s*r?[\"'](?P<path>[^\"']*)[\"']")),
    ({"javascript", "typescript", "vue"}, re.compile(
        r"\.\s*(?P<m>get|post|put|patch|delete|all|route|handle|options)\s*\(\s*"
        r"[\"'`](?P<path>/[^\"'`]*)[\"'`](?P<rest>[^)]*)")),
    ({"javascript", "typescript", "vue"}, re.compile(
        r"@\s*(?P<m>Get|Post|Put|Patch|Delete|All)\s*\(\s*[\"'](?P<path>[^\"']*)[\"']")),
    ({"java", "kotlin"}, re.compile(
        r"@\s*(?P<m>GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|"
        r"RequestMapping)\s*\(\s*(?:value\s*=\s*)?[\"'](?P<path>[^\"']*)[\"']"
        r"(?P<rest>[^)]*)")),
    ({"php"}, re.compile(
        r"(?:Route|Router|App)::\s*(?P<m>get|post|put|patch|delete|any|match)\s*\(\s*"
        r"[\"'](?P<path>/[^\"']*)[\"']")),
    ({"go"}, re.compile(
        r"(?P<obj>\b\w+)\s*\.\s*(?P<m>GET|POST|PUT|PATCH|DELETE|ANY)\s*\(\s*"
        r"[\"'](?P<path>/[^\"']*)[\"']")),
    ({"ruby"}, re.compile(
        r"^\s*(?P<m>get|post|put|patch|delete)\s+[\"'](?P<path>/[^\"']*)[\"']")),
]

METHOD_BY_ANNO = {"getmapping": "GET", "postmapping": "POST", "putmapping": "PUT",
                  "patchmapping": "PATCH", "deletemapping": "DELETE",
                  "requestmapping": "ANY", "get": "GET", "post": "POST", "put": "PUT",
                  "patch": "PATCH", "delete": "DELETE", "all": "ANY", "any": "ANY",
                  "route": "ANY", "handle": "ANY", "options": "OPTIONS",
                  "match": "ANY", "path": "GET", "re_path": "GET", "url": "GET",
                  "websocket": "WS"}

PREFIX_RX = [
    (re.compile(r"APIRouter\s*\(\s*[^)]*prefix\s*=\s*[\"'](?P<p>/?[^\"']*)[\"']"), "FastAPI 路由器前缀"),
    (re.compile(r"include_router\s*\([^)]*prefix\s*=\s*[\"'](?P<p>/?[^\"']*)[\"']"), "FastAPI include_router"),
    (re.compile(r"@\s*RequestMapping\s*\(\s*(?:value\s*=\s*)?[\"'](?P<p>/?[^\"']*)[\"']"), "Spring 类级前缀"),
    (re.compile(r"(?:Group|RouterGroup)\s*\(\s*[\"'](?P<p>/?[^\"']*)[\"']"), "Gin 分组前缀"),
]

DEP_PATTERNS = {
    "package.json": None,          # 走 json 解析
    "requirements.txt": re.compile(
        r"^\s*([A-Za-z0-9][A-Za-z0-9._\-\[\]]+)\s*(?:[=<>~!]=?\s*([^#;\s]+))?"),
    "pyproject.toml": re.compile(r"^\s*[\"']([A-Za-z0-9][\w.\-]*)\s*([=<>~!][^\"']*)?[\"']"),
    "go.mod": re.compile(r"^\s*(?:require\s+)?([a-z0-9\-.]+\.[a-z]{2,}/[^\s]+)\s+([^\s]+)?"),
    "pom.xml": re.compile(r"<artifactId>\s*([^<\s]+)\s*</artifactId>\s*(?:<version>\s*([^<\s]+))?",
                          re.S),
    "build.gradle": re.compile(r"(?:implementation|api|compile)\s+[\"']([\w.\-]+):"
                               r"([\w.\-]+):([^\"']+)[\"']"),
    "Cargo.toml": re.compile(r"^\s*([A-Za-z0-9_\-]+)\s*=\s*[\"']([^\"']*)[\"']"),
    "composer.json": None,
    "Gemfile": re.compile(r"^\s*gem\s+[\"']([^\"']+)[\"']\s*(?:,\s*[\"']([^\"']+)[\"'])?"),
}

ENV_READ_RX = re.compile(r"(?:os\.getenv|os\.environ\.get|os\.environ)\s*[\[\(]\s*[\"']"
                         r"([A-Z][A-Z0-9_]{2,})[\"']|"
                         r"process\.env\.([A-Z][A-Z0-9_]{2,})|"
                         r"System\.getenv\(\s*[\"']([A-Za-z][A-Za-z0-9_.]{2,})[\"']")
ENDPOINT_RX = re.compile(r"\b(?:https?|wss?|mysql|postgres(?:ql)?|mongodb(?:\+srv)?|"
                         r"redis|amqp|jdbc:[a-z0-9]+|s3)://[^\s'\"`)<>]{4,120}")

HOST_RX = re.compile(r"://[^\s/'\"]*?(?:@(?P<host>[^\s/']+)|(?P<plain>[^\s/@:]+))")
URL_VARS = {"max_items": 40, "env_per_file": 20}


def _host_of(url):
    """只保留协议+主机，剥掉路径与任何凭证（地图是给人读的，不该带上连接串）。"""
    scheme, _, rest = url.partition("://")
    authority = re.split(r"[/?#]", rest, maxsplit=1)[0]
    if "@" in authority:
        authority = authority.rsplit("@", 1)[-1]
    authority = re.sub(r":\d+$", "", authority)
    return "%s://%s" % (scheme, authority) if authority else ""


def _frameworks_text(root, rel_paths):
    text = []
    for rel in rel_paths:
        if os.path.basename(rel) in project_scan.MANIFESTS or rel.endswith(
                ("package.json", "requirements.txt", "pyproject.toml", "go.mod",
                 "pom.xml", "build.gradle", "Cargo.toml", "composer.json", "Gemfile")):
            blob = ""
            for _ln, line, _trunc in auditlib.iter_lines(os.path.join(
                    root, rel.replace("/", os.sep)), max_bytes=200_000):
                blob += line
            text.append(blob.lower())
    return "\n".join(text)


def detect_routes(root, rel, lang, lines):
    """从若干行文本里抽路由。返回 [{path,method,file,line,auth,framework_hint}]"""
    out = []
    prefix = ""
    head = u"\n".join(t for _n, t, _x in lines[:80])
    for rx, _why in PREFIX_RX:
        m = rx.search(head)
        if m:
            prefix = "/" + m.group("p").strip("/") if m.group("p") else ""
            break
    for i, (lineno, line, _trunc) in enumerate(lines):
        m = None
        for langs_ok, rx in ROUTE_PATTERNS:
            if lang not in langs_ok:
                continue
            m = rx.search(line)
            if m and auditlib.match_in_string(line, m.start()):
                continue      # 命中位置在字符串字面量里：夹具/文档写的路由不是路由
            if m:
                break
        if not m:
            continue
        raw_method = m.group("m").lower()
        if raw_method == "route" and m.groupdict().get("rest"):
            methods = re.findall(r"[\"'](GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)[\"']",
                                 m.group("rest") or "", re.I)
        else:
            methods = []
        method = METHOD_BY_ANNO.get(raw_method, raw_method.upper())
        path = m.group("path")
        if lang == "python" and not path.startswith("/") and "url" not in line[:12]:
            if not re.match(r"^[a-z_]", path):
                continue
        window = line + "\n" + "\n".join(
            [t for _n, t, _x in lines[max(0, i - 5):i] if t.lstrip().startswith("@")])
        auth = bool(AUTH_RX.search(window))
        if re.search(r"@?(?:PermitAll|allowAnonymous|public|anon)", line):
            auth = False
        for meth in (methods or [method]):
            out.append({"path": (prefix + path) if prefix and path.startswith("/") else path,
                        "method": meth.upper(), "file": rel, "line": lineno,
                        "auth": auth, "lang": lang})
    return out


def detect_deps(root, rel, text):
    base = os.path.basename(rel)
    deps = []
    if base == "package.json":
        try:
            data = json.loads(text)
        except ValueError:
            return deps
        for section in ("dependencies", "devDependencies"):
            for name, spec in (data.get(section) or {}).items():
                deps.append({"name": name, "version": str(spec).lstrip("^~>=<"),
                             "manifest": rel, "kind": section})
    elif base == "composer.json":
        try:
            data = json.loads(text)
        except ValueError:
            return deps
        for name, spec in (data.get("require") or {}).items():
            deps.append({"name": name, "version": str(spec), "manifest": rel,
                         "kind": "require"})
    else:
        rx = DEP_PATTERNS.get(base if base in DEP_PATTERNS else
                              ("requirements.txt" if base.startswith("requirements")
                               else None))
        if rx is None:
            return deps
        for line in text.splitlines():
            m = rx.search(line)
            if m:
                groups = [g for g in m.groups() if g]
                if not groups:
                    continue
                name = groups[0]
                if base == "build.gradle" and len(groups) >= 3:
                    name = groups[1]
                version = groups[-1] if len(groups) > 1 else ""
                if name.lower() in ("dependencies", "require", "repositories",
                                    "plugins", "buildscript"):
                    continue
                deps.append({"name": name, "version": str(version).strip("\"',"),
                             "manifest": rel, "kind": "manifest"})
    return deps


def new_state():
    return {"routes": [], "entrypoints": [], "auth_boundaries": [],
            "dependencies": [], "env_vars": set(), "endpoints": set(),
            "lockfiles": [], "manifests": [], "scanned": 0}


def consume_file(state, root, rec, lines):
    """把**一个文件**抽进地图状态。

    单独成函数是为了让 `build_map` 与 `audit_scan.prescan` 共用同一份抽取规则——
    两处各写一遍，迟早和粗筛对不上账（等价性测试就是拦这个的）。
    """
    rel, lang = rec["path"], rec["lang"]
    base = os.path.basename(rel)
    if base in project_scan.LOCKFILES:
        state["lockfiles"].append(rel)
    if base in project_scan.MANIFESTS or base.startswith("requirements"):
        state["manifests"].append(rel)
    if base.startswith(".env") and "example" not in base and "sample" not in base:
        # 真实 .env 不进内容扫描（值可能含密钥），只登记存在性，交给 preflight/规则链
        state["endpoints"].add("dotenv:%s" % rel)
        return
    if lang not in auditlib.SOURCE_LANGS and lang not in ("dotenv", "yaml", "ini",
                                                          "json", "toml", "text"):
        return
    if not lines:
        return
    state["scanned"] += 1
    # 源码类文件只在**代码行**上抽路由/鉴权/连接点：测试夹具与文档里当字符串写的
    # `@app.route('/x')` 不是路由（自扫实测过一条这样的误报）。
    # 清单文件仍吃原文——package.json 的依赖就在字符串里，屏蔽掉就抽不着了。
    is_source = lang in auditlib.SOURCE_LANGS or lang == "vue"
    code_triples = [(n, raw, x) for n, raw, _m, x in
                    auditlib.code_lines(l for _i, l, _x in lines)] if is_source else lines
    if base in ENTRY_NAMES or len(rel.split("/")) <= 2:
        reason = u"文件名即入口约定" if base in ENTRY_NAMES else ""
        for call, why in ENTRY_CALLS:
            for lineno, line, _t in code_triples:
                if call in line:
                    reason = why
                    break
            if reason:
                break
        if base in ENTRY_NAMES or reason:
            state["entrypoints"].append({"path": rel, "lang": lang,
                                         "reason": reason or u"文件名约定"})
    if is_source:
        state["routes"].extend(detect_routes(root, rel, lang, code_triples))
    if base in project_scan.MANIFESTS or base.startswith("requirements"):
        # 只有清单文件才整份拼文本（几十 KB 级）；源码一律逐行扫，
        # 避免"为了抽依赖把每个源文件都拼成一个大字符串"这种内存自伤
        state["dependencies"].extend(detect_deps(root, rel, "".join(
            t for _n, t, _x in lines)))
    if lang in auditlib.SOURCE_LANGS:
        # 数据文件（json/yaml/md，包括本工具自己写出的地图）不参与
        # 环境变量/连接点/鉴权边界抽取，否则第二次扫描会读到第一次的产物，
        # 地图就会"越扫越脏"——可复现性是被这条毁掉的（测试实测出来）
        for lineno, line, _t in code_triples:
            for m in ENV_READ_RX.finditer(line):
                name = m.group(1) or m.group(2) or m.group(3)
                if name:
                    state["env_vars"].add(name)
            for m in ENDPOINT_RX.finditer(line):
                host = _host_of(m.group(0))
                if host and len(state["endpoints"]) < URL_VARS["max_items"]:
                    state["endpoints"].add(host)
            if AUTH_RX.search(line):
                state["auth_boundaries"].append(
                    {"file": rel, "line": lineno,
                     "marker": auditlib.redact(line.strip())[:80]})
                if len(state["auth_boundaries"]) > 400:
                    break


def build_map(root, index=None, use_git=True, max_file_kb=2048, exclude=None):
    root = os.path.abspath(root)
    if index is None:
        index = auditlib.build_index(root, use_git=use_git,
                                     max_file_bytes=max_file_kb * 1024,
                                     exclude=exclude)
    state = new_state()
    for rec in index["files"]:
        abs_path = os.path.join(root, rec["path"].replace("/", os.sep))
        consume_file(state, root, rec, list(auditlib.iter_lines(abs_path)))
    return finalize_map(state, root, index)


def finalize_map(state, root, index):
    """把累积好的状态收口成地图。抽取在 consume_file，这里只排序、去重、算哈希。"""
    files = index["files"]
    langs = {}
    for rec in files:
        langs[rec["lang"]] = langs.get(rec["lang"], 0) + 1
    routes = state["routes"]
    dep_uniq = {}
    for d in state["dependencies"]:
        key = (d["name"], d["manifest"])
        if key not in dep_uniq:
            dep_uniq[key] = d
    dependencies = sorted(dep_uniq.values(), key=lambda d: (d["name"], d["manifest"]))
    unauth = sorted(set(r["path"] for r in routes if not r["auth"]))
    payload = {
        "schema": MAP_SCHEMA,
        "index_sha1": index.get("index_sha1", ""),
        "languages": dict(sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))),
        "frameworks": sorted(set(project_scan.detect_frameworks(
            _frameworks_text(root, [f["path"] for f in files])))),
        "entrypoints": sorted(state["entrypoints"], key=lambda e: e["path"]),
        "routes": sorted(routes, key=lambda r: (r["file"], r["line"], r["method"])),
        "auth_boundaries": sorted(state["auth_boundaries"],
                                  key=lambda a: (a["file"], a["line"]))[:400],
        "dependencies": dependencies,
        "manifests": sorted(set(state["manifests"])),
        "lockfiles": sorted(set(state["lockfiles"])),
        "env_vars": sorted(state["env_vars"])[:200],
        "external_endpoints": sorted(state["endpoints"]),
        "scanned_files": state["scanned"],
    }
    payload["summary"] = {
        "routes_total": len(payload["routes"]),
        "routes_with_auth_marker": sum(1 for r in payload["routes"] if r["auth"]),
        "unauthenticated_routes": unauth,
        "dependencies_total": len(dependencies),
        "entrypoints_total": len(payload["entrypoints"]),
        "note": u"auth=false 只表示本文件内未见鉴权标记，全局中间件/网关看不见",
    }
    payload["map_sha1"] = auditlib.sha1_hex(json.dumps(
        {k: payload[k] for k in ("languages", "frameworks", "entrypoints", "routes",
                                 "auth_boundaries", "dependencies", "lockfiles",
                                 "env_vars", "external_endpoints", "summary")},
        sort_keys=True, ensure_ascii=False))
    return payload


def map_md(data, root):
    s = data["summary"]
    lines = [u"# 全仓地图（侦察）", u"",
             u"> schema：%s ｜ map_sha1：`%s` ｜ 上游索引：`%s`"
             % (data["schema"], data["map_sha1"][:12], data["index_sha1"][:12]),
             u"",
             u"| 项 | 值 |", u"|---|---|",
             u"| 语言分布 | %s |" % u"、".join(u"%s %d" % (k, v)
                                              for k, v in list(data["languages"].items())[:8]),
             u"| 框架（依赖推断） | %s |" % (u"、".join(data["frameworks"]) or u"未识别"),
             u"| 入口 | %d |" % s["entrypoints_total"],
             u"| 路由 | %d（见鉴权标记 %d） |" % (s["routes_total"],
                                                   s["routes_with_auth_marker"]),
             u"| 未见鉴权标记的路由 | %d |" % len(s["unauthenticated_routes"]),
             u"| 依赖 | %d（清单 %d / 锁文件 %d） |" % (
                 s["dependencies_total"], len(data["manifests"]), len(data["lockfiles"])),
             u"| 外部连接点 | %d |" % len(data["external_endpoints"]),
             u"| 环境变量名 | %d |" % len(data["env_vars"]),
             u"",
             u"## 入口", u""]
    lines += [u"- `%s`（%s）— %s" % (e["path"], e["lang"], e["reason"])
              for e in data["entrypoints"][:15]] or [u"- （未发现）"]
    lines += [u"", u"## 路由与鉴权标记", u"",
              u"| 方法 | 路径 | 文件:行 | 见鉴权标记 |", u"|---|---|---|---|"]
    for r in data["routes"][:60]:
        lines.append(u"| %s | `%s` | `%s:%d` | %s |" % (
            r["method"], r["path"], r["file"], r["line"], u"是" if r["auth"] else u"**否**"))
    if data["external_endpoints"]:
        lines += [u"", u"## 外部连接点（已剥凭证与路径）", u""]
        lines += [u"- `%s`" % h for h in data["external_endpoints"][:25]]
    lines += [u"", u"**读法**：%s。" % s["note"],
              u"下一步：`python audit_scan.py %s --index 索引.json --map 地图.json`" % root]
    return u"\n".join(lines) + u"\n"


def main():
    ap = argparse.ArgumentParser(
        description=u"项目侦察与全仓地图（将作）：语言/入口/路由/鉴权边界/依赖一张图。")
    ap.add_argument("path", nargs="?", default=".", help=u"项目目录")
    ap.add_argument("--json", dest="json_out", default=None, help=u"地图 JSON 输出")
    ap.add_argument("--md", dest="md_out", default=None, help=u"人类可读概览输出")
    ap.add_argument("--index", default=None, help=u"复用已有索引 JSON（缺省则现场建索引）")
    ap.add_argument("--no-git", action="store_true", help=u"索引强制走内置 gitignore 解析器")
    ap.add_argument("--max-file-kb", type=int, default=2048, help=u"单文件阈值 KB")
    ap.add_argument("--stats", action="store_true", help=u"只打印概览")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(u"错误：目录不存在：%s" % args.path, file=sys.stderr)
        print(u"下一步：检查路径拼写；含空格/中文路径加引号；扫当前目录用 .", file=sys.stderr)
        return 2

    index = auditlib.load_index(args.index) if args.index else None
    exclude = []
    for out in (args.json_out, args.md_out):
        if out:
            abs_out = os.path.abspath(out)
            if abs_out.startswith(root + os.sep):
                exclude.append(auditlib.norm_rel(abs_out, root))
    data = build_map(root, index=index, use_git=not args.no_git,
                     max_file_kb=args.max_file_kb, exclude=exclude)

    if args.json_out:
        out_dir = os.path.dirname(os.path.abspath(args.json_out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1))
    if args.md_out:
        with io.open(args.md_out, "w", encoding="utf-8") as f:
            f.write(map_md(data, args.path))
    if args.stats:
        print(map_md(data, args.path))
    else:
        s = data["summary"]
        print(u"地图：入口 %d ｜ 路由 %d（见鉴权 %d / 未见 %d）｜ 依赖 %d ｜ 框架 %s"
              % (s["entrypoints_total"], s["routes_total"],
                 s["routes_with_auth_marker"], len(s["unauthenticated_routes"]),
                 s["dependencies_total"], u"、".join(data["frameworks"]) or u"-"))
        if args.json_out:
            print(u"地图已写出：%s" % args.json_out)
    print(u"RESULT: MAP-OK（map_sha1=%s）" % data["map_sha1"][:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
