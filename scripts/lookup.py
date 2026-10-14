#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分册检索器 —— 将作 (jiangzuo)

在 references/ 的分册中定位"该读哪本分册、规则在哪一行"，避免为找一条规则而整册载入。
CJK 感知：把自然短语切成 2-gram 再匹配（"数据库迁移回滚"也能命中），并用
BOOKLET_ALIASES 这层人工路由词表加权（BM25 无中文分词会失效，故用加权子串）。

用法:
    python lookup.py <关键词或自然短语> [更多关键词] [--top 3] [--lines 3]

输出（token 优化）:
    按得分排序的分册清单，每本附 ≤N 行命中摘录（截断 120 字符）。

会做：中文短语切分、全分册检索、别名词表加权、标题/检查清单行加权、命中行摘录。
不会做：真正的语义理解（同义改写仍靠词表与切分兜住，改述差异过大时看 SKILL.md 路由表）、
        修改任何文件、读取 references/ 之外的目录。
仅使用 Python 标准库（3.8+）。
"""
import argparse
import glob
import io
import os
import re
import sys

# Windows GBK 控制台打印中文/符号会 UnicodeEncodeError 或乱码（2026-10-07 实跑实测，CI 在 Linux 未暴露）
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
REF_DIR = os.path.normpath(os.path.join(HERE, "..", "references"))

BOOKLET_ALIASES = {
    "references/onboarding.md": "摸底 接手 陌生项目",
    "references/requirements.md": "需求 澄清 验收 拆任务",
    "references/design.md": "选型 架构 分层 设计",
    "references/api-design.md": "接口 API REST 契约",
    "references/frontend.md": "前端 页面 组件 联调",
    "references/ui-design.md": "UI UI设计 视觉 走查 设计系统",
    "references/backend.md": "后端 业务逻辑 接口实现",
    "references/database.md": "数据库 表 迁移 SQL",
    "references/security.md": "安全 越权 注入 密钥 权限 鉴权",
    "references/security-audit.md": "审计 体检 全项目 整个项目 项目审计 安全审计 漏洞审计 代码审计 扫描 SARIF 污点 调用图 依赖漏洞 检出率 误报",
    "references/debugging.md": "调试 bug 报错 排查 根因",
    "references/incident.md": "事故 线上 止血 回滚",
    "references/testing.md": "测试 单元 集成 断言 金字塔 覆盖率 分层",
    "references/code-review.md": "审查 评审 提交前 自查",
    "references/refactor-performance.md": "重构 性能 优化 测量",
    "references/devops.md": "部署 环境 CI CD 发布",
    "references/docs-delivery.md": "文档 交付 报告",
    "references/skill-orchestration.md": "技能协同 分包商 编排 其他技能",
    "references/self-evolution.md": "自进化 进化 加规则 删规则 规则膨胀 复盘 账本 回滚",
}

CJK_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\u3040-\u30ff]+")


def expand_terms(keywords):
    """自然短语 → 可命中的词：整词 + 中文串滑窗 2-gram。

    "数据库迁移回滚" 作为一个整词在任何分册里都不存在（必然无命中），
    切成 数据/据库/库迁/迁移/移回/回滚 后才能命中 database.md。
    """
    out, seen = [], set()

    def add(term):
        key = term.lower()
        if term and key not in seen:
            seen.add(key)
            out.append(term)

    for kw in keywords:
        add(kw.strip())
        for run in CJK_RUN.findall(kw):
            if len(run) >= 3:
                for i in range(len(run) - 1):
                    add(run[i:i + 2])
    return out


def alias_bonus(rel_path, query_blob):
    """人工维护的路由词表命中一次 +4 分——它比正文碰巧出现更值得信。"""
    aliases = BOOKLET_ALIASES.get(rel_path, "")
    if not aliases:
        return 0
    return 4 * sum(1 for a in aliases.split() if len(a) >= 2 and a.lower() in query_blob)


def read_lines(path):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read().splitlines()
    except OSError:
        return []


def weight_of(line):
    s = line.strip()
    if s.startswith("#"):
        return 3
    if s.startswith(("|", "-", ">")) or re.match(r"^\d+\.", s):
        return 2
    return 1


def score_file(path, keywords):
    """返回 (得分, 命中行, 命中的不同词数)。"""
    lines = read_lines(path)
    score = 0
    hits = []
    matched = set()
    for i, line in enumerate(lines, 1):
        low = line.lower()
        w = weight_of(line)
        here = [kw for kw in keywords if kw.lower() in low]
        if here:
            score += w * len(here)
            matched.update(h.lower() for h in here)
            hits.append((i, line))
    return score, hits, len(matched)


def main():
    parser = argparse.ArgumentParser(
        description="分册检索器（将作）：按关键词定位该读哪本分册、规则在哪一行。")
    parser.add_argument("keywords", nargs="+", help="关键词（可多个，同义词都给上命中率更高）")
    parser.add_argument("--top", type=int, default=3, help="返回前 N 本分册（默认 3）")
    parser.add_argument("--lines", type=int, default=3, help="每本最多摘录行数（默认 3）")
    args = parser.parse_args()

    if not os.path.isdir(REF_DIR):
        print("错误：找不到 references/ 目录（技能目录不完整？）", file=sys.stderr)
        return 2

    raw = [k.strip() for k in args.keywords if k.strip()]
    query_blob = " ".join(args.keywords).lower()
    paths = sorted(glob.glob(os.path.join(REF_DIR, "*.md")))

    def retrieve(terms, min_distinct):
        """min_distinct：只靠切词命中时要求命中的不同词数下限（防泛词带偏）。"""
        out = []
        for path in paths:
            base = os.path.basename(path)
            score, hits, distinct = score_file(path, terms)
            bonus = alias_bonus("references/" + base, query_blob)
            score += bonus
            if score > 0 and (bonus > 0 or distinct >= min_distinct):
                out.append((score, base, hits))
        out.sort(key=lambda r: -r[0])
        return out

    results = retrieve(raw, 1)
    shingled = False
    if not results:
        # 切词重试前先丢掉"哪本都有"的泛词（df 过高的双字串没有路由价值），
        # 否则 "不存在的词" 会靠"存在"两个字命中任意分册，把检索带偏。
        corpus = ["\\n".join(read_lines(path)).lower() for path in paths]
        limit = max(3, len(corpus) // 3)
        extra = [t for t in expand_terms(raw) if t not in raw
                 and sum(1 for text in corpus if t.lower() in text) <= limit]
        results = retrieve(extra, 2)
        shingled = bool(results)

    if not results:
        print("无命中。已尝试词：%s" % " ".join(expand_terms(raw)[:12]))
        print("提示：换说法再试（如 根因/排查/定位；部署/上线/发布），或直接查 SKILL.md 路由表。")
        return 1

    if shingled:
        print("（整词未命中，已按中文切词重试）\n")

    print("# 检索结果（按相关度）\n")
    for score, name, hits in results[: args.top]:
        print("## %s（得分 %d）" % (name, score))
        shown = 0
        seen = set()
        for ln, line in hits:
            if shown >= args.lines:
                break
            text = line.strip().lstrip("#|-|> ").strip()
            text = re.sub(r"^[*\s]+|[`\[\]]", "", text)[:120]
            if not text or text in seen:
                continue
            seen.add(text)
            print("  L%d: %s" % (ln, text))
            shown += 1
        print()
    print("读分册原文获取完整步骤与检查清单；多个关键词无命中时改用同义词再试。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
