#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""进化信号采集器 —— 将作 (jiangzuo)

把"这个技能/这个项目该往哪改"从印象题变成证据题：读现有留痕，算出候选改进清单。

用法:
    python evolve_report.py [项目目录] [--since 提交数] [--top N]

采集的信号（全部来自磁盘上已有的留痕，不新增负担）：
  1. learnings.md：高置信度教训（候选升级为分册硬约束）、重复主题（候选上调置信度）、
     缺"置信度"字段的条目（格式漂移）。
  2. tech-debt.md：未清项数量与最老一条的年龄（老化债）。
  3. evals/*.md：出现"未红 / 无区分度 / 不通过"的场景（夹具失效，需重造或退役）。
  4. git churn：最近 N 个提交里改动最多的分册（反复改 = 规则没写清或场景在变）。
  5. 入口预算：SKILL.md 正文 tokens 与 5K 目标的差值（膨胀压力）。
  6. 分册规模：行数最高的分册（接近 160 行上限的要先拆再加）。

会做：读取、统计、排序、给证据与建议动作。
不会做：**不修改任何文件，不自动改技能**。进化提案必须走 references/self-evolution.md
       的六道闸门（观测→归因→假设→最小变异→验证→记账），并经理人工确认。

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import os
import re
import subprocess
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

LEARNING_RX = re.compile(r"^- \[(\d{4}-\d{2}-\d{2})\]\s*(.*)$")
CONF_RX = re.compile(r"置信度[:：]\s*(高|低|中)")
OPEN_ITEM_RX = re.compile(r"^- \[ \]")
STALE_EVAL_RX = re.compile(r"未红|无区分度|不通过|(臂|运行|波次|本轮).{0,6}作废|作废.{0,6}(重跑|臂|运行)")
TOKEN_TARGET = 5000
BOOKLET_LIMIT = 160


def read(path):
    if not os.path.isfile(path):
        return ""
    return io.open(path, encoding="utf-8", errors="replace").read()


def estimate_tokens(text):
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text))
    return cjk + (len(text) - cjk) // 4


def scan_learnings(root):
    """返回候选清单 + 统计摘要。"""
    path = os.path.join(root, "docs", "jiangzuo", "learnings.md")
    text = read(path)
    if not text:
        return [], "learnings.md 不存在"
    entries, high, loose, malformed = [], [], [], []
    for line in text.splitlines():
        m = LEARNING_RX.match(line.strip())
        if not m:
            continue
        date, body = m.group(1), m.group(2)
        conf = CONF_RX.search(body)
        entries.append((date, body, conf.group(1) if conf else None))
        if not conf:
            malformed.append(body[:60])
        elif conf.group(1) == "高":
            high.append(body[:70])
    topics = {}
    for _, body, _ in entries:
        key = re.sub(r"[：:，,。.\s]+", " ", body)[:12]
        topics[key] = topics.get(key, 0) + 1
    repeated = sorted([(k, v) for k, v in topics.items() if v >= 2],
                      key=lambda kv: -kv[1])[:3]
    out = []
    if high:
        out.append(("高置信度教训 %d 条仍留在 learnings 里" % len(high),
                    "第一条：%s" % high[0],
                    "评估升级为对应分册的硬约束（一次一条，走六道闸门）", "低"))
    if repeated:
        k, v = repeated[0]
        out.append(("同一主题教训重复 %d 次（%s…）" % (v, k),
                    "单次经验已被反复验证", "上调置信度或合并成一条规则", "低"))
    if malformed:
        out.append(("learnings 有 %d 条缺「置信度」字段" % len(malformed),
                    "示例：%s" % malformed[0],
                    "补齐格式；缺置信度=约束力不明，规则会时灵时不灵", "低"))
    return out, "共 %d 条（高置信 %d）" % (len(entries), len(high))


def scan_debt(root):
    path = os.path.join(root, "docs", "jiangzuo", "debts", "tech-debt.md")
    text = read(path)
    if not text:
        return [], "无技术债登记簿"
    opens = [l for l in text.splitlines() if OPEN_ITEM_RX.match(l.strip())]
    dates = [d for d in re.findall(r"(\d{4}-\d{2}-\d{2})", text) if d]
    note = "未清 %d 项" % len(opens)
    out = []
    if dates and len(opens) >= 5:
        out.append(("技术债 %d 项未清，最早登记于 %s" % (len(opens), min(dates)),
                    "债会随代码演化变成坑", "挑 1-2 项排进下个迭代，或在登记簿标注「暂不处理」并说明代价", "中"))
    return out, note


def scan_evals(root):
    evdir = os.path.join(root, "evals")
    if not os.path.isdir(evdir):
        return [], "无 evals/ 目录"
    hits = []
    for name in sorted(os.listdir(evdir)):
        if not name.endswith(".md"):
            continue
        for line in read(os.path.join(evdir, name)).splitlines():
            if STALE_EVAL_RX.search(line) and len(line) > 12:
                hits.append((name, line.strip()[:90]))
    out = []
    if hits:
        out.append(("评测记录有 %d 行标着「未红/无区分度/不通过」" % len(hits),
                    "例：%s：%s" % (hits[0][0], hits[0][1][:60]),
                    "失效场景要么重造夹具（压力不成立就是题错了），要么退役为哨兵并写明无区分度", "中"))
    return out, "%d 条失效标记" % len(hits)


def scan_churn(root, since):
    try:
        p = subprocess.run(["git", "log", "-%d" % since, "--name-only", "--pretty=format:%x00"],
                           cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        if p.returncode != 0:
            return [], "非 git 仓库，跳过改动热度"
    except (OSError, subprocess.TimeoutExpired):
        return [], "git 不可用，跳过改动热度"
    counts = {}
    for line in p.stdout.decode("utf-8", "replace").splitlines():
        f = line.strip().replace("\\", "/")
        if f.endswith(".md") and (f.startswith("references/") or f == "SKILL.md"):
            counts[f] = counts.get(f, 0) + 1
    hot = sorted(counts.items(), key=lambda kv: -kv[1])[:5]
    out = []
    for name, n in hot:
        if n >= 3:
            out.append(("%s 在最近 %d 个提交里改了 %d 次" % (name, since, n),
                        "反复改通常意味着规则没写清，或场景在变",
                        "读它的变更历史找共性，一次改到位；不要继续小修小补", "中"))
    return out, ("最热 %s×%d" % (hot[0][0], hot[0][1]) if hot else "无分册改动")


def scan_budget(root):
    skill = os.path.join(root, "SKILL.md")
    text = read(skill)
    if not text:
        return [], "无 SKILL.md"
    parts = text.split("---", 2)
    body = parts[2] if len(parts) >= 3 else text
    tokens = estimate_tokens(body)
    note = "正文 ~%d tokens（目标 ≤%d）" % (tokens, TOKEN_TARGET)
    out = []
    if tokens > TOKEN_TARGET:
        out.append(("入口正文 %d tokens，超目标 %d（%.1f%%）" % (tokens, tokens - TOKEN_TARGET,
                    (tokens - TOKEN_TARGET) * 100.0 / TOKEN_TARGET),
                    "常驻上下文膨胀本身就是致错源", "本次若要加入口内容，先删等量行数", "低"))
    return out, note


def scan_booklet_size(root):
    d = os.path.join(root, "references")
    if not os.path.isdir(d):
        return [], "无 references/"
    rows = []
    for name in sorted(os.listdir(d)):
        if name.endswith(".md"):
            rows.append((name, len(read(os.path.join(d, name)).splitlines())))
    rows.sort(key=lambda kv: -kv[1])
    near = [r for r in rows if r[1] > BOOKLET_LIMIT - 25]
    out = []
    for name, n in near:
        out.append(("%s 已 %d 行（上限 %d）" % (name, n, BOOKLET_LIMIT),
                    "分册越长，被跳读的概率越高", "按主题拆一本，或把示例移到模板", "中"))
    return out, ("最大 %s %d 行" % (rows[0][0], rows[0][1]) if rows else "空")


def main():
    ap = argparse.ArgumentParser(
        description="进化信号采集器（将作）：从已有留痕算出候选改进清单，只读不改。")
    ap.add_argument("path", nargs="?", default=".", help="项目目录（默认当前目录）")
    ap.add_argument("--since", type=int, default=60, help="统计改动热度的提交数（默认 60）")
    ap.add_argument("--top", type=int, default=8, help="最多列出多少条候选（默认 8）")
    args = ap.parse_args()

    root = os.path.abspath(args.path)
    if not os.path.isdir(root):
        print("目录不存在：%s\n下一步：确认路径，或先 cd 到项目根目录" % root)
        return 2

    scanners = [("learnings", lambda: scan_learnings(root)),
                ("技术债", lambda: scan_debt(root)),
                ("评测集", lambda: scan_evals(root)),
                ("改动热度", lambda: scan_churn(root, args.since)),
                ("入口预算", lambda: scan_budget(root)),
                ("分册规模", lambda: scan_booklet_size(root))]
    candidates, summaries = [], []
    for label, fn in scanners:
        items, summary = fn()
        summaries.append((label, summary))
        candidates.extend(items)

    print("# 进化信号报告（%s）\n" % root)
    print("## 观测面")
    for label, summary in summaries:
        print("  %-6s %s" % (label + "：", summary))

    print("\n## 候选改进（按证据强度排序，最多 %d 条）" % args.top)
    if not candidates:
        print("  （无信号：现有留痕没暴露出值得改的地方。别为了进化而进化。）")
        print("\nRESULT: EVOLVE-NONE（0 项候选）")
        return 0
    for i, (finding, evidence, action, cost) in enumerate(candidates[:args.top], 1):
        print("  %d. %s" % (i, finding))
        print("     证据：%s" % evidence)
        print("     建议：%s（成本：%s）" % (action, cost))
    print("\n配额提醒：一次只改一个假设；新增 ≤40 行必须同时给出可删候选。")
    print("本工具不改文件。落地请走 references/self-evolution.md 的六道闸门，并跑回归三件套。")
    print("\nRESULT: EVOLVE-CANDIDATES（%d 项，已列 %d 项）" % (len(candidates), min(args.top, len(candidates))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
