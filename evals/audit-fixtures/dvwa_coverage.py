#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DVWA 检出分母 —— 将作 (jiangzuo)

语料是我自己写的，16/16=100% 有出题人偏置。DVWA 不一样：**模块目录名就是标准答案**，
分母不由我定。这个脚本把一个扫描 JSON 按"模块 → 该模块的主漏洞类别"对照，
输出每个模块是 OK 还是 MISS，以及它实际被哪些规则命中。

口径要说清楚：
- **OK = 该模块的主类别规则至少命中一条**（在模块目录下的任何文件里）。
  "同目录里报了别种类的洞"不算 OK——那只是路过。
- 类别映射是**人工声明**的（下表），不是 DVWA 官方给的；映射写错就会误报覆盖率，
  所以映射连同注释一起留在脚本里，让人能核对、能改。
- DVWA 每个模块有 low/medium/high/impossible 四档，impossible 是官方修复版。
  只在 impossible 里命中不算 OK（那是反向误报），所以脚本单独报"仅修复档命中"。

用法:
    python dvwa_coverage.py --json <audit_scan 输出的 dvwa JSON>

仅使用 Python 标准库（3.8+）。
"""
from __future__ import print_function

import argparse
import io
import json
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# 模块 → 该模块"主类别"对应的规则 id。多个 id 表示这一类有多种写法来源。
CATEGORY = {
    "api": ["JZ-XSS-001", "JZ-XSS-002", "JZ-CSRF-001"],
    "authbypass": ["JZ-SQLI-003", "JZ-AUTHGAP-001"],
    "bac": ["JZ-HORZ-001", "JZ-AUTHGAP-001"],
    "brute": ["JZ-BRUTE-001"],
    "captcha": ["JZ-CAPTCHA-001"],
    "cryptography": ["JZ-CRYPTO-001", "JZ-CRYPTO-002", "JZ-CRYPTO-003"],
    "csp": ["JZ-XSS-001", "JZ-XSS-002"],
    "csrf": ["JZ-CSRF-001"],
    "exec": ["JZ-CMDI-001"],
    "fi": ["JZ-TRAVERSAL-001"],
    "javascript": ["JZ-JSINSEC-001", "JZ-XSS-001"],
    "open_redirect": ["JZ-REDIR-001"],
    "sqli": ["JZ-SQLI-003"],
    "sqli_blind": ["JZ-SQLI-003"],
    "upload": ["JZ-UPLOAD-001"],
    "weak_id": ["JZ-WEAKID-001", "JZ-CRYPTO-001"],
    "xss_d": ["JZ-XSS-001", "JZ-XSS-002"],
    "xss_r": ["JZ-XSS-001", "JZ-XSS-002"],
    "xss_s": ["JZ-XSS-001", "JZ-XSS-002"],
}
# 官方修复档：这些文件里的命中不能算"检出真漏洞"
FIXED_PAT = ("source/impossible.php", "impossible.js", "check_token_impossible.php")


def is_fixed(path):
    return any(p in path for p in FIXED_PAT)


def main():
    ap = argparse.ArgumentParser(description=u"DVWA 检出分母对照（将作）")
    ap.add_argument("--json", required=True, help=u"audit_scan 对 DVWA 仓库输出的 JSON")
    args = ap.parse_args()

    data = json.load(io.open(args.json, encoding="utf-8"))
    per = {}
    for f in data.get("findings", []):
        parts = f["file"].split("/")
        if len(parts) < 2 or parts[0] != "vulnerabilities":
            continue
        per.setdefault(parts[1], []).append((f["rule_id"], f["file"], is_fixed(f["file"])))

    ok, miss, only_fixed = [], [], []
    for module in sorted(CATEGORY):
        rows = per.get(module, [])
        want = set(CATEGORY[module])
        real = [r for r in rows if r[0] in want and not r[2]]
        if real:
            ok.append(module)
        elif [r for r in rows if r[0] in want]:
            only_fixed.append(module)
        else:
            miss.append(module)
        passed = ", ".join(sorted(set(r[0] for r in rows))) or u"（该模块无任何发现）"
        print(u"  %-4s %-14s 路过规则：%s" % (
            u"OK" if module in ok else (u"仅修复档" if module in only_fixed else u"MISS"),
            module, passed))

    total = len(CATEGORY)
    print(u"\n主类别检出：%d/%d = %.1f%%（另有 %d 个模块只在官方修复档命中，等于没检出真漏洞）"
          % (len(ok), total, 100.0 * len(ok) / total, len(only_fixed)))
    print(u"MISS：%s" % (u"、".join(miss + only_fixed) or u"无"))
    print(u"\nRESULT: %s（%d/%d）" % (u"COVER-OK" if len(ok) >= total * 0.8 else
                                    u"COVER-LOW", len(ok), total))
    return 0


if __name__ == "__main__":
    sys.exit(main())
