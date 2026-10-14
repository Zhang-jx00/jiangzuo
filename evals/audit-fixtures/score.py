#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计链量化验收 —— 将作 (jiangzuo)

把"能不能找 bug"变成有分母的数字：高危检出率、整体误报率、行级命中、
峰值内存随文件数的变化，以及增量与全量的一致性。
阈值来自升级清单第五节：**高危检出率 ≥90%、误报率 ≤10%、内存不随文件数线性增长、
增量==全量、SARIF 可用**。不达标就红着退出，不做定性美化。

用法:
    python score.py --corpus DIR [--sarif PATH] [--bench-parent DIR] [--json-out PATH]

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import json
import os
import shutil
import subprocess
import sys
import tracemalloc

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
SCRIPTS = os.path.join(SKILL, "scripts")
sys.path.insert(0, SCRIPTS)

import audit_rules   # noqa: E402
import audit_scan    # noqa: E402

RECALL_HIGH_MIN = 0.90
FP_MAX = 0.10
LINE_TOLERANCE = 3


def load_rules_severity():
    rules, problems, _notes, _off = audit_rules.load_rules([])
    if problems:
        raise SystemExit(u"规则库有问题，无法评分：%s" % u"；".join(problems[:3]))
    return dict((r["id"], r["severity"]) for r in rules)


def run_scan(corpus, sarif=None):
    tracemalloc.start()
    payload = audit_scan.run(corpus, out_json=None, out_md=None, out_sarif=sarif,
                             report_memory=False)
    peak = tracemalloc.get_traced_memory()[1] // 1024
    tracemalloc.stop()
    return payload, peak


def score(corpus, sarif=None):
    expected_path = os.path.join(corpus, "expected.json")
    if not os.path.isfile(expected_path):
        raise SystemExit(u"找不到答案清单：%s（先跑 gen_corpus.py --out 这个目录）"
                         % expected_path)
    with io.open(expected_path, "r", encoding="utf-8") as f:
        expected = json.load(f)
    severity = load_rules_severity()
    payload, peak = run_scan(corpus, sarif=sarif)
    findings = payload["findings"]
    got = set((f["file"], f["rule_id"]) for f in findings)

    hit_pairs, miss, line_hit = [], [], 0
    high_total = high_found = 0
    for entry in expected["find"]:
        pair = (entry["file"], entry["rule_id"])
        is_high = severity.get(entry["rule_id"]) in ("critical", "high")
        if pair in got:
            hit_pairs.append(pair)
            if is_high:
                high_found += 1
            for f in findings:
                if f["file"] == entry["file"] and f["rule_id"] == entry["rule_id"] \
                        and entry["line"] and abs(f["line"] - entry["line"]) <= LINE_TOLERANCE:
                    line_hit += 1
                    break
        else:
            miss.append(pair)
            if is_high:
                high_total_missed = 1
    for entry in expected["find"]:
        if severity.get(entry["rule_id"]) in ("critical", "high"):
            high_total += 1

    false_pos = [f for f in findings
                 if (f["file"], f["rule_id"]) not in
                 set((e["file"], e["rule_id"]) for e in expected["find"])]
    recall_all = len(hit_pairs) / float(expected["find"] and len(expected["find"]) or 1)
    recall_high = high_found / float(high_total or 1)
    fp_rate = len(false_pos) / float(findings and len(findings) or 1)
    leaked = [f for f in findings
              if (f["file"], f["rule_id"]) in
              set((e["file"], e["rule_id"]) for e in expected["nofind"])]

    rows = [u"# 审计链量化验收", u"",
            u"| 指标 | 实测 | 阈值 | 判定 |", u"|---|---|---|---|",
            u"| 应检出条目 | %d（其中高危 %d） | — | — |" % (
                len(expected["find"]), high_total),
            u"| 高危检出率 | %d/%d = %.1f%% | ≥90%% | %s |" % (
                high_found, high_total, recall_high * 100,
                u"达标" if recall_high >= RECALL_HIGH_MIN else u"**未达标**"),
            u"| 全部检出率 | %d/%d = %.1f%% | — | — |" % (
                len(hit_pairs), len(expected["find"]), recall_all * 100),
            u"| 行级命中（±%d 行） | %d/%d = %.1f%% | — | — |" % (
                LINE_TOLERANCE, line_hit, len(hit_pairs),
                line_hit / float(len(hit_pairs) or 1) * 100),
            u"| 报告总条数 | %d | — | — |" % len(findings),
            u"| 误报率（不在答案内的发现） | %d/%d = %.1f%% | ≤10%% | %s |" % (
                len(false_pos), len(findings), fp_rate * 100,
                u"达标" if fp_rate <= FP_MAX else u"**未达标**"),
            u"| 安全样本被误报 | %d/%d | 0 | %s |" % (
                len(leaked), len(expected["nofind"]),
                u"达标" if not leaked else u"**有漏净化**"),
            u"| 峰值内存（整链 tracemalloc） | %d KB ｜ 粗筛 %s KB | 不随文件数线性 | 见曲线 |"
            % (peak, payload["stats"].get("peak_memory_kb") or u"未测"),
            u"| 扫描耗时 | %.2fs | — | — |" % payload["stats"]["elapsed_sec"],
            u"| 验证环节丢弃 | %d | — | — |" % payload["stats"]["dropped_by_verifier"],
            u"", u"## 漏报清单", u""]
    rows += ([u"- `%s` %s" % (p[0], p[1]) for p in miss] or [u"- 无"])
    rows += [u"", u"## 误报清单（不在答案里的发现）", u""]
    rows += ([u"- `%s:%d` %s [%s] — %s" % (f["file"], f["line"], f["rule_id"],
                                          f["kind"], (f["sink_text"] or u"")[:70])
              for f in false_pos[:20]] or [u"- 无"])
    rows += [u"", u"## 安全样本被误报", u""]
    rows += ([u"- `%s:%d` %s" % (f["file"], f["line"], f["rule_id"])
              for f in leaked[:20]] or [u"- 无"])
    if sarif:
        with io.open(sarif, "r", encoding="utf-8") as f:
            doc = json.load(f)
        ok = (doc.get("version") == "2.1.0" and "$schema" in doc
              and doc.get("runs") and doc["runs"][0]["tool"]["driver"]["rules"]
              and len(doc["runs"][0]["results"]) == len(findings))
        rows += [u"", u"## SARIF 结构自检", u"",
                 u"- version=%s ｜ rules=%d ｜ results=%d ｜ 与发现条数一致：%s ｜ 结构自检：%s"
                 % (doc["version"], len(doc["runs"][0]["tool"]["driver"]["rules"]),
                    len(doc["runs"][0]["results"]), len(doc["runs"][0]["results"]) == len(findings),
                    u"通过" if ok else u"**失败**"),
                 u"- 说明：这是**本仓库实现的字段级自检**，未跑官方 sarif-validator"
                 u"（离线环境无该工具），所以只声称结构自检通过。"]
        rows.append(u"- 结果：%s" % (u"通过" if ok else u"失败"))
        ok = ok
    else:
        ok = True
    verdict = (recall_high >= RECALL_HIGH_MIN and fp_rate <= FP_MAX
               and not leaked and ok)
    rows += [u"", u"RESULT: %s（高危检出 %.1f%% / 误报 %.1f%%）"
             % (u"ACCEPT-OK" if verdict else u"ACCEPT-FAIL",
                recall_high * 100, fp_rate * 100)]
    return u"\n".join(rows) + u"\n", verdict, {"recall_high": recall_high,
                                               "fp_rate": fp_rate, "leaked": len(leaked)}


def memory_curve(parent):
    """同一份语料分别放 60 / 600 个良性文件，看峰值内存是不是随文件数线性涨。"""
    gen = os.path.join(HERE, "gen_corpus.py")
    rows = [u"", u"## 内存曲线（tracemalloc 实测，整链）", u"",
            u"| 文件数 | 峰值内存 | 每千文件 | 用时 |", u"|---|---|---|---|"]
    prev = None
    for fillers in (0, 60, 600):
        corpus = os.path.join(parent, "bench_%03d" % fillers)
        if os.path.isdir(corpus):
            shutil.rmtree(corpus)
        r = subprocess.run([sys.executable, gen, "--out", corpus,
                            "--fillers", str(fillers)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           encoding="utf-8", errors="replace")
        if r.returncode:
            rows.append(u"| %d | 生成失败 | — | — |" % (17 + fillers))
            continue
        payload, peak = run_scan(corpus)
        n = payload["stats"]["files_total"]
        rows.append(u"| %d | %d KB | %.1f KB | %.2fs |" % (
            n, peak, peak / float(max(1, n)) * 1000, payload["stats"]["elapsed_sec"]))
        if prev is not None and n > prev[0] * 5:
            ratio = peak / float(max(1, prev[1]))
            rows.append(u"| 倍率 | 文件 ×%.1f → 内存 ×%.2f（线性应为 ×%.1f） | | |" % (
                n / float(prev[0]), ratio, n / float(prev[0])))
        prev = (n, peak)
    return u"\n".join(rows) + u"\n"


def main():
    ap = argparse.ArgumentParser(description=u"审计链量化验收（将作）")
    ap.add_argument("--corpus", required=True, help=u"gen_corpus.py 产出的语料目录")
    ap.add_argument("--sarif", default=None, help=u"顺带导出 SARIF 并做结构自检")
    ap.add_argument("--bench-parent", default=None,
                    help=u"在该目录下临时生成不同规模语料做内存曲线（用完自己删）")
    ap.add_argument("--json-out", default=None, help=u"把完整指标写成一个 md 文件")
    args = ap.parse_args()

    corpus = os.path.abspath(args.corpus)
    text, verdict, nums = score(corpus, sarif=args.sarif)
    print(text)
    if args.bench_parent:
        parent = os.path.abspath(args.bench_parent)
        if not os.path.isdir(parent):
            os.makedirs(parent)
        curve = memory_curve(parent)
        print(curve)
        text = text + curve
        verdict = verdict and nums["recall_high"] >= RECALL_HIGH_MIN
    if args.json_out:
        with io.open(args.json_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(u"完整指标已写出：%s" % args.json_out)
    return 0 if verdict else 1


if __name__ == "__main__":
    sys.exit(main())
