#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""文件索引与忽略模块 —— 将作 (jiangzuo) 审计链第 ① 环

给整个仓库出一份**稳定、可复现**的文件清单：路径 / 字节数 / 内容哈希 / 语言。
忽略规则按 gitignore 语义（含嵌套 .gitignore、! 取反、目录型模式），
再叠一层内置的依赖/构建产物目录黑名单；二进制与超限文件不静默丢弃，
一律进 skipped 明细并计数。

用法:
    python audit_index.py [项目目录] [--json 索引.json] [--md 概览.md]
                          [--no-git] [--max-file-kb N] [--include-binary]
                          [--ignore 模式]... [--stats]

会做：读 .gitignore / .git/info/exclude、git 可用时优先用 git 的忽略判定、
      流式算 sha1、按路径排序输出、给出 index_sha1（同一棵树两次运行必然相同）。
不会做：判断代码好坏（那是 audit_scan.py 的事）、修改被扫描项目（全程只读）。

下游：audit_map.py（侦察地图）、audit_graph.py（调用图）、audit_scan.py（扫描与缓存）
      都以这份清单为唯一文件口径——三处各走一遍目录、结论对不上，是审计工具最常见的自伤。

仅使用 Python 标准库（3.8+），不联网、只读项目。
"""
import argparse
import io
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import auditlib  # noqa: E402


def summarize_md(data, root):
    counts = data["counts"]
    lines = [u"# 文件索引概览", u"",
             u"> schema：%s ｜ 生成器：%s ｜ index_sha1：`%s`"
             % (data["schema"], data["generator"], data["index_sha1"]),
             u"",
             u"| 项 | 值 |", u"|---|---|",
             u"| 纳入扫描文件数 | %d |" % counts["files"],
             u"| 合计字节 | %.1f MB |" % (counts["total_bytes"] / 1048576.0),
             u"| 二进制跳过 | %d |" % counts["binary"],
             u"| 超限跳过（>%d KB） | %d |" % (counts.get("max_file_kb", 0),
                                              counts["oversize"]),
             u"| 隐藏文件跳过 | %d |" % counts["hidden"],
             u"| 单文件阈值 | %d 字节 |" % data["max_file_bytes"],
             u"",
             u"## 语言分布", u"",
             u"| 语言 | 文件数 |", u"|---|---|"]
    for lang, n in sorted(data["by_lang"].items(), key=lambda kv: (-kv[1], kv[0])):
        lines.append(u"| %s | %d |" % (lang, n))
    if data["ignore_sources"]:
        lines += [u"", u"## 忽略规则来源", u""]
        lines += [u"- %s" % s for s in data["ignore_sources"]]
    if data["skipped"]:
        lines += [u"", u"## 跳过明细（前 %d 条）" % len(data["skipped"]), u"",
                  u"| 路径 | 原因 | 字节 |", u"|---|---|---|"]
        for rec in data["skipped"]:
            lines.append(u"| `%s` | %s | %d |" % (rec["path"], rec["reason"], rec["bytes"]))
        if data["skipped_truncated"]:
            lines.append(u"| …… | 另有 %d 条未列出 | |" % data["skipped_truncated"])
    lines += [u"", u"下一步：`python audit_map.py %s --index 索引.json` 建全仓地图。" % root]
    return u"\n".join(lines) + u"\n"


def main():
    ap = argparse.ArgumentParser(
        description=u"文件索引与忽略模块（将作）：产出稳定可复现的待扫文件清单。")
    ap.add_argument("path", nargs="?", default=".", help=u"项目目录（默认当前目录）")
    ap.add_argument("--json", dest="json_out", default=None, help=u"清单 JSON 输出路径")
    ap.add_argument("--md", dest="md_out", default=None, help=u"人类可读概览输出路径")
    ap.add_argument("--no-git", action="store_true",
                    help=u"强制使用内置 gitignore 解析器（不用 git ls-files）")
    ap.add_argument("--max-file-kb", type=int, default=2048,
                    help=u"单文件阈值 KB（超限记入 skipped，默认 2048）")
    ap.add_argument("--include-binary", action="store_true",
                    help=u"连二进制一起收录（默认按 NUL 字节判定后跳过并记录）")
    ap.add_argument("--ignore", action="append", default=[],
                    help=u"追加忽略模式，可多次（如 --ignore 'tests/**'）")
    ap.add_argument("--stats", action="store_true", help=u"只打印概览，不写文件")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print(u"错误：目录不存在：%s" % args.path, file=sys.stderr)
        print(u"下一步：检查路径拼写；含空格/中文的路径加引号；扫当前目录用 .",
              file=sys.stderr)
        return 2

    exclude = []
    for out in (args.json_out, args.md_out):
        if out:
            abs_out = os.path.abspath(out)
            if abs_out.startswith(root + os.sep):
                exclude.append(auditlib.norm_rel(abs_out, root))

    data = auditlib.build_index(
        root, use_git=not args.no_git,
        max_file_bytes=args.max_file_kb * 1024,
        include_binary=args.include_binary,
        extra_ignore=None, exclude=exclude)
    data["counts"]["max_file_kb"] = args.max_file_kb

    if args.json_out:
        out_dir = os.path.dirname(os.path.abspath(args.json_out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(args.json_out, "w", encoding="utf-8") as f:
            f.write(json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1))
    if args.md_out:
        out_dir = os.path.dirname(os.path.abspath(args.md_out))
        if out_dir and not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        with io.open(args.md_out, "w", encoding="utf-8") as f:
            f.write(summarize_md(data, args.path))

    if args.stats:
        print(summarize_md(data, args.path))
    else:
        c = data["counts"]
        print(u"索引：%d 个文件 / %.1f MB ｜ 跳过 二进制 %d、超限 %d、隐藏 %d ｜ 生成器 %s"
              % (c["files"], c["total_bytes"] / 1048576.0, c["binary"],
                 c["oversize"], c["hidden"], data["generator"]))
        if data["ignore_sources"]:
            print(u"忽略规则：%s" % u"；".join(data["ignore_sources"]))
        if args.json_out:
            print(u"清单已写出：%s" % args.json_out)
        if args.md_out:
            print(u"概览已写出：%s" % args.md_out)
    print(u"RESULT: INDEX-OK（index_sha1=%s，同一棵树两次运行应完全相同）"
          % data["index_sha1"][:12])
    return 0


if __name__ == "__main__":
    sys.exit(main())
