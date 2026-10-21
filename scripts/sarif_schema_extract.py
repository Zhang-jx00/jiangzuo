# -*- coding: utf-8 -*-
"""从官方 SARIF 2.1.0 JSON Schema 提取「允许属性」白名单，并核对 audit_scan 里的硬编码表。

为什么要它：audit_scan.sarif_selfcheck 用的 SARIF_SCHEMA_PROPS 是硬编码的
（零依赖、离线 CI 也能跑），硬编码就有抄错的可能——这个脚本（需要联网）能当场
核一遍，抄错了退出码 1。

用法：
    python scripts/sarif_schema_extract.py                     # 打印提取结果
    python scripts/sarif_schema_extract.py --check             # 与 audit_scan 对账
    python scripts/sarif_schema_extract.py --check --schema-file FILE  # 用本地 schema 离线对账

只依赖标准库（3.8+）。
"""
import argparse
import io
import json
import os
import sys
import urllib.request

# Windows GBK 控制台打印中文会乱码（2026-10-07 同源缺陷，CI 在 Linux 未暴露）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SCHEMA_URLS = [
    "https://json.schemastore.org/sarif-2.1.0.json",
    "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/main/"
    "sarif-2.1/schema/sarif-schema-2.1.0.json",
]


def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": "jiangzuo-sarif-check/1.0"})
    handle = urllib.request.urlopen(req, timeout=timeout)
    try:
        return handle.read()
    finally:
        handle.close()


def load_schema(path=None):
    if path:
        with io.open(path, "rb") as f:
            return f.read()
    last = None
    for url in SCHEMA_URLS:
        try:
            data = fetch(url)
            sys.stderr.write("OK %d bytes from %s\n" % (len(data), url))
            return data
        except Exception as exc:  # noqa: BLE001
            last = exc
            sys.stderr.write("FAIL %s: %r\n" % (url, exc))
    sys.stderr.write("SCHEMA-UNREACHABLE: %r\n" % (last,))
    return None


def extract(doc):
    """抽出所有 additionalProperties=false 的类型的允许属性名。"""
    out = {}
    defs = doc.get("definitions") or {}
    for name, d in defs.items():
        if not isinstance(d, dict):
            continue
        props = d.get("properties")
        if isinstance(props, dict) and d.get("additionalProperties", False) is False:
            out[name] = set(props.keys())
    top = doc.get("properties")
    if isinstance(top, dict) and doc.get("additionalProperties", False) is False:
        out["sarifLog"] = set(top.keys())
    return out


def main():
    ap = argparse.ArgumentParser(
        description=u"提取/核对 SARIF 2.1.0 schema 允许属性（将作）")
    ap.add_argument("--check", action="store_true",
                    help=u"与 audit_scan.SARIF_SCHEMA_PROPS 对账，不一致退出码 1")
    ap.add_argument("--schema-file", default=None,
                    help=u"用本地 schema 文件代替联网下载")
    ap.add_argument("--print", dest="do_print", action="store_true",
                    help=u"打印提取到的全部类型")
    args = ap.parse_args()

    data = load_schema(args.schema_file)
    if data is None:
        return 2
    try:
        doc = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        sys.stderr.write("SCHEMA-NOT-JSON: %r\n" % (exc,))
        return 2

    official = extract(doc)
    if args.do_print:
        for name in sorted(official):
            sys.stdout.write("%s: %s\n" % (name, ", ".join(sorted(official[name]))))
        return 0

    if not args.check:
        sys.stdout.write("extracted %d types; use --check to compare\n" % len(official))
        return 0

    import audit_scan
    mine = audit_scan.SARIF_SCHEMA_PROPS
    bad = 0
    for kind in sorted(mine):
        want = set(mine[kind])
        got = official.get(kind)
        if got is None:
            sys.stdout.write("MISSING-IN-SCHEMA %s\n" % kind)
            bad += 1
            continue
        if want != got:
            sys.stdout.write("DIFF %s only-in-code=%s only-in-schema=%s\n"
                             % (kind,
                                ",".join(sorted(want - got)) or "-",
                                ",".join(sorted(got - want)) or "-"))
            bad += 1
    if bad:
        sys.stdout.write("SCHEMA-TABLE-MISMATCH %d type(s)\n" % bad)
        return 1
    sys.stdout.write("SCHEMA-TABLE-OK %d types\n" % len(mine))
    return 0


if __name__ == "__main__":
    sys.exit(main())
