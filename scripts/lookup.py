#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""分册检索器 —— 将作 (jiangzuo)

在 references/ 的 17 本分册中按关键词定位"该读哪本分册、规则在哪一行"，
避免为找一条规则而整册载入。CJK 感知：按子串计频 + 标题/清单行加权
（ui-ux-pro-max 检索模式的中文适配——BM25 无中文分词会失效，故用加权子串）。

用法:
    python lookup.py <关键词> [关键词2 ...] [--top 3] [--lines 3]

输出（token 优化）:
    按得分排序的分册清单，每本附 ≤N 行命中摘录（截断 120 字符）。

会做：全分册关键词检索、标题/检查清单行加权、命中行摘录。
不会做：理解语义（只做字面匹配，同义词需多给几个关键词）、
        修改任何文件、读取 references/ 之外的目录。
仅使用 Python 标准库（3.8+）。
"""
import argparse
import glob
import io
import os
import re
import sys

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
    "references/security.md": "安全 越权 注入 密钥 权限",
    "references/debugging.md": "调试 bug 报错 排查 根因",
    "references/incident.md": "事故 线上 止血 回滚",
    "references/testing.md": "测试 单元 集成 断言",
    "references/code-review.md": "审查 评审 提交前 自查",
    "references/refactor-performance.md": "重构 性能 优化 测量",
    "references/devops.md": "部署 环境 CI CD 发布",
    "references/docs-delivery.md": "文档 交付 报告",
    "references/skill-orchestration.md": "技能协同 分包商 编排 其他技能",
}


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
    lines = read_lines(path)
    score = 0
    hits = []
    for i, line in enumerate(lines, 1):
        low = line.lower()
        w = weight_of(line)
        hits_here = sum(1 for kw in keywords if kw.lower() in low)
        if hits_here:
            score += w * hits_here
            hits.append((i, line))
    return score, hits


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

    results = []
    for path in sorted(glob.glob(os.path.join(REF_DIR, "*.md"))):
        score, hits = score_file(path, args.keywords)
        if score > 0:
            results.append((score, os.path.basename(path), hits))

    results.sort(key=lambda r: -r[0])
    if not results:
        print("无命中。提示：换同义词（如 根因/排查/定位；部署/上线/发布），或直接查 SKILL.md 路由表。")
        return 1

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
