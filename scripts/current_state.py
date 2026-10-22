#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「当前状态」的机器可读真源（将作 jiangzuo）。

为什么要有它
------------
本项目吃过两次亏，**都是同一类**：

  * E32：同一个数（「同目录路过」多少条）在三份文档里分别写了 **20 / 12 / "59 条里有 20 条"**
    ⇒ 互相矛盾，且都没说清是哪个口径。
  * E33：Release 总数把「补发那批 64 个」和「现在的 65 个」写成了同一个数。

根因是**同一个数散落在多处散文里，而没有任何东西把它们对账**：
`validate_skill.py` 的期望值校验（第 14 项）**只扫代码块**——因为代码块是"复制即跑"的契约，
正文与表格里的历史数字是**当时真值**（交付报告 §3 的 "Ran 124 tests" 是 v0.36.1 当时的数），
管到历史记录上就是误伤。⇒ 这个取舍是对的，**但代价是散文里的"当前状态"没人守**。

本模块补上那一块，办法不是"把散文也当代码块扫"（那会误伤历史），而是：

  1. **真源**：`evals/current-state.json` —— 「当前状态」这件事的**唯一**机器可读出处。
     · `static` 段：**能当场推出来**的数（用例数 / 语料分母 / 规则条数 / 校准例数）
       ⇒ 校验器每跑一次就重推一遍，**推不出来就报** ⇒ 真源自己不会腐烂。
     · `reported` 段：校验器自己报的条数（由 main() 收尾时对账）。
     · `measured` 段：**跑出来的**数（三仓检出、覆盖、语料、性能）——静态推不出来，
       由 `--refresh` 从扫描产物写进来；**文档必须与它一致**。
  2. **载体**：文档里用 `<!-- current-state:begin -->` … `<!-- current-state:end -->`
     圈出"这里描述的是**当前**状态"的一段。**只有标记区受管**，标记区外是历史，不红。
  3. **对账**：校验器拿真源里的数，逐个去载体的标记区里按 `patterns` 找出来比对。
     ⇒ 载体里手抄的数一旦与真源不同，当场红并点名是哪个文件的哪个指标。

用法
----
    python scripts/current_state.py --derive     # 打印能当场推出来的 static 段
    python scripts/current_state.py --check      # 核对真源（推不出的数是否已过期）
    python scripts/current_state.py --print      # 打印「当前状态」摘要（给人看 / 往文档里贴）
    python scripts/current_state.py --refresh --scans <目录> [--extras <json>]

只使用 Python 3.8+ 标准库、**不联网**。`--refresh` 只读扫描产物，不跑扫描。
"""
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

SOURCE_REL = "evals/current-state.json"
BEGIN_MARK = "<!-- current-state:begin -->"
END_MARK = "<!-- current-state:end -->"

# 「这是不是将作自己的仓库」——用来决定本项是否适用。
# 判据用**结构**（校准器 + 判定表）而不是路径，别的技能目录不该被要求提供真源。
JIANGZUO_MARKERS = (
    os.path.join("scripts", "mut_calibrate.py"),
    os.path.join("evals", "finding-verdicts.md"),
)

REQUIRED_STATIC = ("tests", "must_find", "must_not_find", "rules_active", "rules_disabled")
REQUIRED_MEASURED = (
    "dvwa_findings", "dvwa_conclusions", "dvwa_dropped", "dvwa_flows",
    "flask_findings", "flask_conclusions",
    "requests_findings", "requests_conclusions",
    "self_findings", "self_conclusions", "self_context_excluded",
    "coverage_hit", "coverage_total",
    "corpus_must_find", "corpus_must_not_find",
    "bench_ms_per_file",
)


# --------------------------------------------------------------------------
# 基础 IO
# --------------------------------------------------------------------------
def source_path(skill_dir):
    return os.path.join(skill_dir, SOURCE_REL.replace("/", os.sep))


def load_source(skill_dir):
    """读真源。读不到返回 None（**不假装通过**：由调用方决定是"不适用"还是"缺文件"）。"""
    p = source_path(skill_dir)
    if not os.path.isfile(p):
        return None
    try:
        with io.open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def is_jiangzuo_repo(skill_dir):
    return all(os.path.isfile(os.path.join(skill_dir, m)) for m in JIANGZUO_MARKERS)


def derive(skill_dir):
    """**当场推出来**的 static 段：推不出来的键**直接不出现**（不是填 0、也不是填 None）。

    ⚠️ 刻意不自己实现推导：`validate_skill._expected_truth()` 才是既有的唯一推导实现，
    两边各写一份就会漂（那正是本轮要治的病）。这里**惰性** import 它，
    避免模块加载期的循环 import。
    """
    import validate_skill

    truth = validate_skill._expected_truth(skill_dir)
    out = {}
    for k in REQUIRED_STATIC:
        v = truth.get(k)
        if v is not None:
            out[k] = v
    # 校准例数：静态数 CASES（不执行被测脚本）
    mut = os.path.join(skill_dir, "scripts", "mut_calibrate.py")
    if os.path.isfile(mut):
        with io.open(mut, "r", encoding="utf-8", errors="replace") as f:
            n = validate_skill._mut_case_count(f.read())
        if n is not None:
            out["mutation_cases"] = n
    return out


def marked_regions(text):
    """找出所有 `current-state` 标记区：返回 [(块文本, 起始行号)]。"""
    lines = text.split("\n")
    regions = []
    i = 0
    while i < len(lines):
        if BEGIN_MARK in lines[i]:
            start = i + 1
            j = i + 1
            while j < len(lines) and END_MARK not in lines[j]:
                j += 1
            if j < len(lines):
                regions.append(("\n".join(lines[start:j]), start))
                i = j + 1
                continue
        i += 1
    return regions


def _same_number(got, want):
    """两个"数"是不是同一个 —— **按数值比**，不是按字符串比。

    为什么：JSON 里的 `4.300` 会被解析成浮点 `4.3`，而文档里写的是
    bench 自己的输出格式 `4.300` ⇒ 纯字符串比较会**误红**。
    ⇒ 两边都能解析成数字时按数值比（带极小容差），否则按字符串比。
    """
    try:
        return abs(float(got) - float(want)) < 1e-9
    except (TypeError, ValueError):
        return str(got) == str(want)


def value_of(src, metric, version=None):
    """取某个指标的值。

    `version` 为 None ⇒ 取**当前**值（static/reported/measured）。
    `version` 给了 ⇒ 取**那一版的历史快照** ⇒ CHANGELOG / 验收记录这类
    **历史文档**对账的是它自己那一版的事实，**不会因为下一轮变了就变红**
    （否则这条判据就会逼着人篡改历史）。
    """
    if version:
        hist = (src.get("history") or {}).get(version)
        if not isinstance(hist, dict):
            return None
        for group in ("static", "reported", "measured"):
            v = (hist.get(group) or {}).get(metric)
            if v is not None:
                return v
        return None
    for group in ("static", "reported", "measured"):
        v = (src.get(group) or {}).get(metric)
        if v is not None:
            return v
    return None


# --------------------------------------------------------------------------
# 校验
# --------------------------------------------------------------------------
def check(skill_dir, err, info):
    """校验器的第 23 项：`当前状态` 真源与载体必须对得上。

    返回 True/False 表示本项是否适用（不适用时不产出任何信息）。
    """
    src = load_source(skill_dir)
    if src is None and not is_jiangzuo_repo(skill_dir):
        return False          # 别的技能目录 ⇒ 本项不适用（按事实判，不按路径判）
    if src is None:
        err(u"%s 不见了——它是「当前状态」的唯一真源（缺了它，文档里的数就没人对账了）"
            % SOURCE_REL)
        return True

    problems = []

    # ① schema 与必填项
    if src.get("schema") != 1:
        problems.append(u"真源的 schema 字段是 %r（应为 1）——格式变了要同步改校验器"
                        % (src.get("schema"),))
    for k in REQUIRED_STATIC:
        if k not in (src.get("static") or {}):
            problems.append(u"真源缺 static.%s（这是能当场推出来的数，必须有）" % k)
    for k in REQUIRED_MEASURED:
        if k not in (src.get("measured") or {}):
            problems.append(u"真源缺 measured.%s（跑出来的数，必须有出处）" % k)

    # ② static 段必须与「当场推出来的」一致 ⇒ 真源自己不会腐烂
    derived = derive(skill_dir)
    st = src.get("static") or {}
    for k in sorted(set(list(st.keys()) + list(derived.keys()))):
        if k not in st:
            problems.append(u"真源缺 static.%s（实物能推出来：%s）" % (k, derived[k]))
        elif k not in derived:
            problems.append(u"真源里的 static.%s 在本仓库**推不出来**（要么键名错了，要么该删）" % k)
        elif st[k] != derived[k]:
            problems.append(u"真源的 static.%s = %s，**实物是 %s**——真源过期了，重新推一遍"
                            % (k, st[k], derived[k]))

    # ③ 载体对账
    pats = src.get("patterns") or {}
    carriers = src.get("carriers") or {}
    if not carriers:
        problems.append(u"真源没列任何载体（carriers）——那就没有东西可对账")
    for rel in sorted(carriers):
        spec = carriers[rel]
        zones = spec.get("zones") if isinstance(spec, dict) else None
        if not zones:
            # 兼容旧写法：整个载体当一个区
            zones = [spec if isinstance(spec, dict) else {"metrics": spec or []}]
        path = os.path.join(skill_dir, rel.replace("/", os.sep))
        if not os.path.isfile(path):
            problems.append(u"载体 %s 不存在" % rel)
            continue
        with io.open(path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        regions = marked_regions(text)
        for zi, zone in enumerate(zones):
            metrics = zone.get("metrics") or []
            version = zone.get("version")
            idx = zone.get("index", 0)
            if idx < 0:
                idx = len(regions) + idx
            if not regions:
                problems.append(u"载体 %s 里没有 current-state 标记区（应至少有一个）" % rel)
                break
            if idx >= len(regions):
                problems.append(u"载体 %s 的第 %d 个标记区不存在（实际 %d 个）"
                                % (rel, zi, len(regions)))
                continue
            if version and not isinstance((src.get("history") or {}).get(version), dict):
                problems.append(u"真源里没有 %s 的历史快照（history.%s）——"
                                u"历史载体必须对账它自己那一版的事实" % (version, version))
                continue
            region = regions[idx][0]
            for m in metrics:
                if isinstance(metrics, dict):
                    spec2 = metrics.get(m)
                else:
                    spec2 = pats.get(m)
                if not spec2:
                    problems.append(u"真源没给 %s 的匹配式（patterns.%s）" % (m, m))
                    continue
                if isinstance(spec2, dict):
                    forms = [spec2] + list(spec2.get("also") or [])
                else:
                    forms = [{"rx": spec2, "group": 1}]
                want = value_of(src, m, version)
                if want is None:
                    problems.append(u"真源里没有 %s%s 的值"
                                    % (m, u"（%s 版）" % version if version else u""))
                    continue
                for form in forms:
                    rx = form.get("rx")
                    grp = form.get("group", 1)
                    mm = re.search(rx, region)
                    if not mm:
                        problems.append(u"载体 %s 的标记区里找不到 %s（匹配式 %s）" % (rel, m, rx))
                        continue
                    got = mm.group(grp)
                    # ⚠️ **数值要按数值比**：JSON 里的 4.300 存成 4.3（浮点），
                    #    而文档里写的是 bench 自己的输出格式 "4.300" ⇒ 纯字符串比较会误红。
                    #    ⇒ 两边都能解析成数字时按数值比（带极小容差），否则按字符串比。
                    if _same_number(got, want):
                        continue
                    problems.append(u"载体 %s：%s 写的是 **%s**，真源是 **%s**——同一个数不能两处不同"
                                    % (rel, m, got, want))

    for p in problems:
        err(u"[当前状态] " + p)
    if not problems:
        info(u"当前状态真源与载体对账通过（%d 个真源键、%d 个载体，%s）"
             % (len(st) + len(src.get("measured") or {}), len(carriers), SOURCE_REL))
    return True


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------
def _read_extras(path):
    with io.open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_refresh(skill_dir, scans, extras):
    """从扫描产物重算 `measured` 段并写回真源。**只读产物，不跑扫描。**"""
    src = load_source(skill_dir)
    if src is None:
        print(u"没有真源可刷新：%s" % SOURCE_REL, file=sys.stderr)
        return 2
    m = dict(src.get("measured") or {})
    for name, prefix in (("DVWA", "dvwa"), ("flask", "flask"),
                          ("requests", "requests"), ("self", "self")):
        p = os.path.join(scans, name + ".json")
        if not os.path.isfile(p):
            print(u"扫描产物缺 %s" % p, file=sys.stderr)
            return 2
        with io.open(p, "r", encoding="utf-8") as f:
            st = json.load(f)["stats"]
        m["%s_findings" % prefix] = st["findings"]
        m["%s_conclusions" % prefix] = st["conclusions"]
        m["%s_context_excluded" % prefix] = st.get("context_excluded", 0)
        m["%s_dropped" % prefix] = st.get("dropped_by_verifier", 0)
        m["%s_flows" % prefix] = st.get("flows", 0)
    if extras:
        ex = _read_extras(extras)
        for k, v in ex.items():
            m[k] = v
    src["measured"] = m
    with io.open(source_path(skill_dir), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(src, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(u"已刷新 measured 段（%d 项）→ %s" % (len(m), SOURCE_REL))
    return 0


def cmd_sync(skill_dir):
    """把 `static` 段重推一遍写回真源（**只改 static**，其余原样保留）。

    用法：加了/删了测试用例、校准例之后跑一次 ⇒ 真源的 static 段不会过期。
    """
    src = load_source(skill_dir)
    if src is None:
        print(u"没有真源可同步：%s" % SOURCE_REL, file=sys.stderr)
        return 2
    src["static"] = derive(skill_dir)
    with io.open(source_path(skill_dir), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(src, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(u"已同步 static 段（%d 项）→ %s" % (len(src["static"]), SOURCE_REL))
    return 0


def cmd_snapshot(skill_dir, version):
    """把**当前**值抄成某一版的**历史快照**（history.<version>）。

    为什么要有它：CHANGELOG / 验收记录是**历史文档** ⇒ 它们对账的必须是
    "它自己那一版的事实"，而不是"现在的值"。
    少了这一层，下一轮数字一变，历史条目的标记区就会变红
    ⇒ 那等于逼着人**篡改历史** ⇒ 判据会变成逼人做坏事的东西。
    """
    src = load_source(skill_dir)
    if src is None:
        print(u"没有真源可快照：%s" % SOURCE_REL, file=sys.stderr)
        return 2
    hist = dict(src.get("history") or {})
    hist[version] = {
        "static": dict(src.get("static") or {}),
        "reported": dict(src.get("reported") or {}),
        "measured": dict(src.get("measured") or {}),
    }
    src["history"] = hist
    with io.open(source_path(skill_dir), "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(src, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(u"已写入历史快照 history.%s" % version)
    return 0


def cmd_print(skill_dir):
    src = load_source(skill_dir)
    if src is None:
        print(u"没有真源：%s" % SOURCE_REL, file=sys.stderr)
        return 2
    st = src.get("static") or {}
    ms = src.get("measured") or {}
    rp = src.get("reported") or {}
    print(u"| 项 | 值 |")
    print(u"|---|---|")
    for k in sorted(st):
        print(u"| %s | %s |" % (k, st[k]))
    for k in sorted(rp):
        print(u"| %s | %s |" % (k, rp[k]))
    for k in sorted(ms):
        print(u"| %s | %s |" % (k, ms[k]))
    return 0


def main():
    import argparse

    ap = argparse.ArgumentParser(description="将作：「当前状态」机器可读真源")
    ap.add_argument("skill_dir", nargs="?", default=REPO, help="技能目录（默认本仓库）")
    ap.add_argument("--derive", action="store_true", help="打印能当场推出来的 static 段")
    ap.add_argument("--check", action="store_true", help="核对真源是否过期")
    ap.add_argument("--print", action="store_true", help="打印当前状态摘要")
    ap.add_argument("--refresh", action="store_true", help="从扫描产物刷新 measured 段")
    ap.add_argument("--sync", action="store_true", help="重推 static 段写回真源")
    ap.add_argument("--snapshot", help="把当前值抄成该版本的历史快照（history.<版本>）")
    ap.add_argument("--scans", help="扫描产物目录（--refresh 用）")
    ap.add_argument("--extras", help="额外的 measured 值（JSON 文件，--refresh 用）")
    args = ap.parse_args()

    skill_dir = os.path.abspath(args.skill_dir)

    if args.refresh:
        if not args.scans:
            print(u"--refresh 需要 --scans <扫描产物目录>", file=sys.stderr)
            return 2
        return cmd_refresh(skill_dir, args.scans, args.extras)

    if args.sync:
        return cmd_sync(skill_dir)

    if args.snapshot:
        return cmd_snapshot(skill_dir, args.snapshot)

    if args.derive:
        print(json.dumps(derive(skill_dir), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    if args.print:
        return cmd_print(skill_dir)

    if args.check:
        errs = []
        warns = []
        infos = []
        ok = check(skill_dir, errs.append, infos.append)
        for m in infos:
            print(u"  ✔ " + m)
        for m in errs:
            print(u"  ✘ " + m)
        if not ok:
            print(u"（本仓库不适用本项）")
            return 0
        print(u"结果：%d 条错误" % len(errs))
        return 1 if errs else 0

    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
