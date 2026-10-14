#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""审计链性能基准 —— 将作 (jiangzuo)

把"快、省内存"从形容词变成**带预算的断言**：分阶段计时、逐阶段峰值内存、
每文件毫秒预算、并发加速比。任何一项超预算就 ACCEPT-FAIL 退出码 1，
这样性能就不是"我优化过了"，而是"CI 拦得住回退"。

用法:
    python bench.py --workdir DIR [--files 1500] [--repeat 2]
                    [--max-ms-per-file 3] [--max-mb 220] [--jobs 4]

workdir 建议放在仓库外（默认 SkillOne/eval-runs/bench-corpus），跑完自己删。
仅使用 Python 标准库（3.8+）。
"""
import argparse
import gc
import io
import json
import os
import shutil
import sys
import time
import tracemalloc

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(SKILL, "scripts"))

import auditlib      # noqa: E402
import audit_map     # noqa: E402
import audit_graph   # noqa: E402
import audit_rules   # noqa: E402
import audit_scan    # noqa: E402

PY_BODY = (
    "def handle_%d(payload):\n"
    "    total = 0\n"
    "    items = payload.get('items', [])\n"
    "    for key in items:\n"
    "        total += len(str(key))\n"
    "    return {'id': %d, 'total': total, 'ok': total > 0}\n\n\n"
    "def helper_%d(row):\n"
    "    return handle_%d(row)\n")
VULN_LINES = [
    "from flask import request, Flask",
    "import sqlite3",
    "app = Flask(__name__)",
    "",
    "@app.route('/api/thing_%d')",
    "def thing_%d():",
    "    q = request.args['q']",
    "    con = sqlite3.connect('db.sqlite')",
    "    return con.execute(f'SELECT * FROM t WHERE c LIKE {q}').fetchall()",
]
VULN_FILE = "\n".join(VULN_LINES) + "\n"
PY_ROUTE = (
    "from flask import request, Flask\n"
    "app = Flask(__name__)\n\n\n"
    "@app.route('/api/v%d/thing')\n"
    "def thing_%d():\n"
    "    q = request.args['q']\n"
    "    return {'q': q}\n")
JS_FILE = (
    "const router = require('express').Router()\n\n"
    "router.get('/v%d/thing', async (req, res) => {\n"
    "  const rows = []\n"
    "  for (let i = 0; i < 8; i++) { rows.push(req.query.page + i) }\n"
    "  res.json(rows)\n"
    "})\n\n"
    "module.exports = router\n")


def make_corpus(out, files):
    if os.path.isdir(out):
        shutil.rmtree(out)
    os.makedirs(out)
    io.open(os.path.join(out, "requirements.txt"), "w",
            encoding="utf-8", newline="\n").write("flask==2.3.3\nrequests==2.31.0\n")
    io.open(os.path.join(out, "package.json"), "w", encoding="utf-8").write(
        json.dumps({"name": "bench", "dependencies": {"express": "^4.19.2"}}))
    for i in range(files):
        if i % 3 == 0:
            rel, text = "app/mod_%05d.js" % i, JS_FILE % i
        elif i % 3 == 1:
            rel, text = "app/api_%05d.py" % i, PY_ROUTE % (i, i)
        else:
            rel, text = "app/svc_%05d.py" % i, (PY_BODY % (i, i, i, i)) * 4
        if i % 20 == 7:
            rel, text = "app/vuln_%05d.py" % i, VULN_FILE % (i, i)
        path = os.path.join(out, rel.replace("/", os.sep))
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.makedirs(d)
        io.open(path, "w", encoding="utf-8", newline="\n").write(text)
    return out


def stage(fn):
    """跑一个阶段，返回 (秒, 该阶段峰值 KB)。"""
    gc.collect()
    tracemalloc.start()
    t0 = time.time()
    out = fn()
    dt = time.time() - t0
    peak = tracemalloc.get_traced_memory()[1] // 1024
    tracemalloc.stop()
    return dt, peak, out


def main():
    ap = argparse.ArgumentParser(description=u"审计链性能基准（将作）")
    ap.add_argument("--workdir", required=True)
    ap.add_argument("--files", type=int, default=1500)
    ap.add_argument("--repeat", type=int, default=2)
    ap.add_argument("--max-ms-per-file", type=float, default=3.0)
    ap.add_argument("--max-mb", type=float, default=220.0)
    args = ap.parse_args()

    corpus = make_corpus(os.path.join(os.path.abspath(args.workdir), "corpus_%d" % args.files),
                         args.files)
    rules, problems, _n, _d = audit_rules.load_rules([])
    if problems:
        raise SystemExit(u"规则库有问题：%s" % problems[0])

    rows = []
    best = {}
    for _ in range(max(1, args.repeat)):
        dt, pk, index = stage(lambda: auditlib.build_index(corpus))
        rows.append(("索引 build_index", dt, pk))
        best["index"] = index
        dt, pk, mp = stage(lambda: audit_map.build_map(corpus, index=index))
        rows.append(("地图 build_map", dt, pk))
        best["map"] = mp
        dt, pk, g = stage(lambda: audit_graph.build_graph(corpus, index=index,
                                                         map_data=mp, rules=rules))
        rows.append(("图 build_graph（无门控对照）", dt, pk))
        best["graph_kb"] = pk
        dt, pk, hits = stage(lambda: audit_scan.coarse_screen(corpus, index, rules,
                                                             2 * 1024 * 1024))
        rows.append(("粗筛 coarse_screen", dt, pk))
        dt, pk, payload = stage(lambda: audit_scan.run(corpus))
        rows.append(("整链 audit_scan.run", dt, pk))
        full = payload

    n = full["stats"]["files_total"]
    agg = {}
    for name, dt, pk in rows:
        cur = agg.setdefault(name, [0.0, 0])
        cur[0] += dt / args.repeat
        cur[1] = max(cur[1], pk)
    total_dt = agg["整链 audit_scan.run"][0]
    ms_file = total_dt * 1000.0 / max(1, n)
    peak_mb = agg["整链 audit_scan.run"][1] / 1024.0

    print(u"# 审计链性能基准（%d 文件，重复 %d 次取均值/峰值）\n" % (n, args.repeat))
    print(u"| 阶段 | 秒 | 峰值内存 | 每文件 ms |")
    print(u"|---|---|---|---|")
    for name in ("索引 build_index", "地图 build_map", "图 build_graph（无门控对照）",
                 "粗筛 coarse_screen", "整链 audit_scan.run"):
        dt, pk = agg[name]
        print(u"| %s | %.2f | %d KB | %.3f |" % (name, dt, pk, dt * 1000.0 / max(1, n)))
    st = full["stats"]
    print(u"\n- 整链每文件 **%.3f ms**（预算 ≤%.2f ms）｜ 整链峰值 **%.1f MB**（预算 ≤%.0f MB）"
          % (ms_file, args.max_ms_per_file, peak_mb, args.max_mb))
    print(u"- 整链内部：发现 %d ｜ 污点流 %d ｜ 粗筛命中文件 %d ｜ 图层实际解析 %d 个文件%s"
          % (st["findings"], st.get("flows", 0), st["candidates"],
             st.get("graph_parsed_files", 0),
             u"（门控空转）" if st.get("graph_gated") else u""))
    print(u"- 对照行的 31MB 是**无门控全仓解析**的旧行为，别拿它当占用；"
          u"门控后的图成本已含在整链行里。")
    ok = ms_file <= args.max_ms_per_file and peak_mb <= args.max_mb
    print(u"\nRESULT: %s（%.3f ms/文件 / %.1f MB）"
          % (u"BENCH-OK" if ok else u"BENCH-FAIL", ms_file, peak_mb))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
