#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""技能结构校验器 —— 将作 (jiangzuo)

按 Agent Skills 开放规范（agentskills.io）与渐进式披露实践校验技能目录，
可用作本地自检或 CI 门禁。

校验项：
  1. SKILL.md 存在且 frontmatter 可解析，name/description 必填
  2. name 规范（≤64 字符，建议小写 kebab-case）；description ≤1024 字符
  3. SKILL.md 正文行数 ≤500（超限降级为警告）
  4. 正文中引用的 references/ templates/ scripts/ 文件必须存在（路径含反斜杠即报错）
  5. scripts/*.py 语法可编译
  6. 分册之间不再互相引用（保持引用一层深，超深仅警告）

用法:
    python validate_skill.py [技能目录]      # 退出码 0=通过 1=有错误

仅使用 Python 标准库（3.8+）。
"""
import argparse
import io
import os
import re
import sys

RECOGNIZED_KEYS = {"name", "description", "when_to_use", "license", "metadata"}
TOLERATED_KEYS = {"version", "allowed-tools", "compatibility", "argument-hint",
                  "user-invocable", "disable-model-invocation"}
REF_RX = re.compile(r"(?:references|templates|scripts|assets|evals)/[A-Za-z0-9][A-Za-z0-9_\-./]*")
ERRORS = []
WARNINGS = []
INFOS = []


def err(msg):
    ERRORS.append(msg)


def warn(msg):
    WARNINGS.append(msg)


def info(msg):
    INFOS.append(msg)


def parse_frontmatter(text):
    """极简 frontmatter 解析：key: value + 两空格缩进的二级 key。"""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, None
    try:
        end = lines.index("---", 1)
    except ValueError:
        return None, None
    meta = {}
    current = None
    for line in lines[1:end]:
        if not line.strip() or line.strip().startswith("#"):
            continue
        if line.startswith("  ") and ":" in line and current:
            k, _, v = line.strip().partition(":")
            meta.setdefault(current, {})[k.strip()] = v.strip().strip("\"'")
        elif ":" in line:
            k, _, v = line.partition(":")
            current = k.strip()
            v = v.strip().strip("\"'")
            # 空值先按字典占位（可能是嵌套块的父键），避免二级键写入字符串
            meta[current] = {} if v == "" else v
        else:
            current = None
    return meta, lines[end + 1:]


def check_frontmatter(skill_dir, text):
    meta, _ = parse_frontmatter(text)
    if meta is None:
        err("SKILL.md 缺少可解析的 frontmatter（首行应为 --- 且有配对闭合）")
        return None
    name = meta.get("name", "")
    desc = meta.get("description", "")
    if not name:
        err("frontmatter 缺少 name")
    else:
        if len(name) > 64:
            err("name 超过 64 字符（规范上限）")
        if not re.match(r"^[a-z0-9][a-z0-9-]*$", name):
            warn("name 含大写/下划线/中文（agentskills.io 规范要求小写 kebab-case；"
                 "部分宽松解析器可接受，跨平台分发前建议确认）")
        dir_name = os.path.basename(os.path.abspath(skill_dir))
        if dir_name != name:
            warn("目录名 %r 与 name %r 不一致（规范要求一致）" % (dir_name, name))
    if not desc:
        err("frontmatter 缺少 description（description 是触发的唯一依据，必填）")
    else:
        if len(desc) > 1024:
            err("description %d 字符，超过 1024 上限（超限的技能会被直接丢弃）" % len(desc))
        else:
            info("description %d 字符（≤1024 ✓）" % len(desc))
        # 部分客户端（Claude Code）对 description+when_to_use 合计在 ~1536 字符处截断
        wtu = meta.get("when_to_use", "")
        if wtu and len(desc) + len(wtu) > 1536:
            warn("description+when_to_use 合计 %d 字符，超过约 1536 的截断阈值，"
                 "关键触发信息请放前面" % (len(desc) + len(wtu)))
    unknown = [k for k in meta if k not in RECOGNIZED_KEYS | TOLERATED_KEYS]
    if unknown:
        warn("未识别的 frontmatter 字段：%s（不同平台可能忽略）" % ", ".join(unknown))
    return meta


def check_refs(skill_dir, body):
    refs = sorted(set(REF_RX.findall(body)))
    missing = []
    for ref in refs:
        if "\\" in ref:
            err("路径含 Windows 反斜杠（跨平台会失效）：%s" % ref)
            continue
        if not os.path.isfile(os.path.join(skill_dir, ref.replace("/", os.sep))):
            missing.append(ref)
    if missing:
        for m in missing:
            err("引用的文件不存在：%s" % m)
    else:
        info("正文引用的 %d 个文件全部存在，路径为正斜杠 ✓" % len(refs))
    return refs


def check_one_level(skill_dir, refs):
    """阅读链保持一层深：分册不再引用其他分册。
    分册指向 templates/ 与 scripts/ 是正常用法（模板是复制使用的产物，
    脚本是执行的产物，不会形成递归阅读链），不算违规。"""
    deep = []
    for ref in refs:
        if not ref.startswith("references/"):
            continue
        path = os.path.join(skill_dir, ref.replace("/", os.sep))
        if not os.path.isfile(path):
            continue
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        for inner in set(REF_RX.findall(content)):
            if inner.startswith("references/") and inner != ref:
                deep.append("%s → %s" % (ref, inner))
    if deep:
        warn("分册之间互相引用形成阅读链（建议一层深，必要时由 SKILL.md 统一路由）：%s"
             % "; ".join(deep))
    else:
        info("分册间无嵌套阅读链（一层深 ✓）")


def check_scripts(skill_dir):
    scripts_dir = os.path.join(skill_dir, "scripts")
    if not os.path.isdir(scripts_dir):
        return
    found = False
    for fn in sorted(os.listdir(scripts_dir)):
        if not fn.endswith(".py"):
            continue
        found = True
        path = os.path.join(scripts_dir, fn)
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        try:
            compile(src, fn, "exec")
        except SyntaxError as e:
            err("脚本语法错误：%s（%s）" % (fn, e))
    if found:
        info("scripts/ 下全部 Python 脚本语法可编译 ✓")


def estimate_tokens(text):
    """粗略 token 估算：CJK 字符约 1 token/字，其余约 4 字符/token。"""
    cjk = len(re.findall(r"[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]", text))
    return cjk + (len(text) - cjk) // 4


def print_stats(skill_dir):
    """占用报告：常驻成本（SKILL.md 全文）与按需成本（分册）分开计量。"""
    import glob
    print("\n# 占用报告（估算 token：CJK≈1/字，ASCII≈4 字符/token）\n")

    skill_md = os.path.join(skill_dir, "SKILL.md")
    with io.open(skill_md, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    idx = text.index("\n---", 4) if text.startswith("---") else 0
    front, body = (text[:idx + 4], text[idx + 4:]) if idx else ("", text)
    meta, _ = parse_frontmatter(text)
    print("常驻（每次触发都进上下文）:")
    print("  SKILL.md 全文    ~%5d tokens（frontmatter ~%d + 正文 ~%d）"
          % (estimate_tokens(text), estimate_tokens(front), estimate_tokens(body)))
    if meta:
        print("  description      ~%5d tokens" % estimate_tokens(meta.get("description", "")))
        if meta.get("when_to_use"):
            print("  when_to_use      ~%5d tokens" % estimate_tokens(meta.get("when_to_use", "")))

    refs = sorted(glob.glob(os.path.join(skill_dir, "references", "*.md")))
    if refs:
        rows = []
        for p in refs:
            with io.open(p, "r", encoding="utf-8", errors="replace") as f:
                rows.append((os.path.basename(p), estimate_tokens(f.read())))
        rows.sort(key=lambda r: -r[1])
        total = sum(est for _, est in rows)
        print("\n按需（进入对应阶段才读取）: references/ 共 %d 本，合计 ~%d tokens" % (len(rows), total))
        for name, est in rows[:5]:
            print("  最大 %-30s ~%5d tokens" % (name, est))
        if rows:
            print("  典型任务读取 1-3 本 ≈ %d-%d tokens" % (rows[0][1], sum(e for _, e in rows[:3])))


def main():
    parser = argparse.ArgumentParser(
        description="技能结构校验器（将作）：按 Agent Skills 规范校验技能目录，可作 CI 门禁。")
    parser.add_argument("skill_dir", nargs="?", default=".", help="技能目录（默认当前目录）")
    parser.add_argument("--stats", action="store_true", help="打印上下文占用报告后退出（不做校验）")
    args = parser.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)
    if args.stats:
        if not os.path.isfile(os.path.join(skill_dir, "SKILL.md")):
            print("错误：找不到 SKILL.md：%s" % skill_dir, file=sys.stderr)
            return 2
        print_stats(skill_dir)
        return 0

    skill_md = os.path.join(skill_dir, "SKILL.md")
    if not os.path.isfile(skill_md):
        err("找不到 SKILL.md：%s" % skill_md)
    else:
        with io.open(skill_md, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        meta, rest = parse_frontmatter(text)
        if meta is not None and rest is not None:
            body = "\n".join(rest)
            body_lines = len(rest)
            if body_lines > 500:
                warn("SKILL.md 正文 %d 行，超过建议的 500 行——考虑把内容外移到 references/" % body_lines)
            else:
                info("SKILL.md 正文 %d 行（≤500 ✓）" % body_lines)
            if re.search(r"\b[A-Za-z]:[\\/]\S|/Users/\S|/home/\S", body):
                err("正文含本机绝对路径（跨环境会失效，应使用相对路径）")
            check_frontmatter(skill_dir, text)
            version = (meta.get("metadata") or {}).get("version", "")
            if version:
                changelog = os.path.join(skill_dir, "CHANGELOG.md")
                if os.path.isfile(changelog):
                    with io.open(changelog, "r", encoding="utf-8", errors="replace") as f:
                        m = re.search(r"^##\s*\[?(\d+\.\d+\.\d+)\]?", f.read(), re.M)
                    if m and m.group(1) != version:
                        warn("metadata.version (%s) 与 CHANGELOG 最新版本 (%s) 不一致"
                             % (version, m.group(1)))
                    elif m:
                        info("metadata.version 与 CHANGELOG 一致（%s ✓）" % version)
            if os.path.isdir(os.path.join(skill_dir, "evals")):
                info("含 evals/ 评测集 ✓")
            refs = check_refs(skill_dir, text)
            check_one_level(skill_dir, refs)
            check_scripts(skill_dir)

    print("# 技能结构校验：%s\n" % os.path.basename(skill_dir))
    for i in INFOS:
        print("  ✔ %s" % i)
    for w in WARNINGS:
        print("  ⚠ %s" % w)
    for e in ERRORS:
        print("  ✘ %s" % e)
    print("\n结果：%d 条信息 / %d 条警告 / %d 条错误 —— %s" % (
        len(INFOS), len(WARNINGS), len(ERRORS),
        "通过" if not ERRORS else "未通过"))
    return 0 if not ERRORS else 1


if __name__ == "__main__":
    sys.exit(main())
