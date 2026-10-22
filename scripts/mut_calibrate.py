"""变异校准（将作）：把被测实现改坏，断言必须当场变红；随后按字节还原并自证。

**它是什么**：把每条判据的"承重处"改坏一次，看那条判据**当场变红**；
然后按字节还原并自证（sha1 逐字节一致 + 突变文本各出现 1 次 + 还原后 0 次）。
**为什么要有它**：一条永远绿的锁比没有锁更坏——它让人以为有人管，其实没有。

**怎么用**（在本仓库根下）：
    python scripts/mut_calibrate.py             # 跑全部用例（会临时改仓库文件，跑完自动还原）
    python scripts/mut_calibrate.py --check-only # 只核对锚点还准不准（秒级，不改文件）

**⚠️ 为什么 CI 只跑 `--check-only`**：完整校准要跑测试，其中个别用例的判据
**随平台换颜色**（索引路径锁在 Windows 是反斜杠、在 Linux 是正斜杠）⇒
在 CI 上跑完整校准会**误红**（E6 那轮"CI 连续 22 次红"就是这类平台差异）⇒
CI 只跑锚点核对（平台无关、秒级），完整校准留给本地。

**它只改本仓库的文件、只读被测代码、不联网、不碰被扫项目。**

原始文件：把被测实现改坏，断言必须当场变红；随后按字节还原并自证。

写这个文件的原因：还原语句 `open(p,"wb").write(open(p,"rb").read()...)`
会先按 "wb" 截断再读——同一个表达式里把被测文件清成了 0 字节。
所以这里强制"先读进内存、再落盘"，并且还原后比对 sha1。
"""
import hashlib
import io
import os
import re
import subprocess
import sys

# JSON 源码里的正则要写**两个**反斜杠，手写转义层数极易错一层
# （E25 改规则时被坑过两次）⇒ 让机器拼。
B = chr(92)

# 仓库根 = 本文件（scripts/）的上一级。E24 起校准器**随技能一起分发**。
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def sha(path):
    return hashlib.sha1(io.open(path, "rb").read()).hexdigest()


def run_judgement(test_id):
    """跑一条判据，返回 (rc, 输出, 测试是否存在)。

    ⚠️ **"找不到的测试 id"也会返回非零**：unittest 会造一个 `_FailedTest` 顶上，
    照样 `FAILED (errors=1)`、退出码非零 ⇒ **只看 rc 会把"恒红"当成"判据红"**。
    E29 那条 `xss-document-write-constant-back` 就中招了：它指向的测试被放进了
    别的类 ⇒ 跑出来是 AttributeError，不是判据红 ⇒ 那条校准什么都没证明。
    ⇒ 所以这里把"测试加载失败"单独标出来，不跟"判据红"混为一谈。
    """
    r = subprocess.run([sys.executable, "-m", "unittest", test_id], cwd=REPO,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", timeout=240)
    out = (r.stdout or "") + (r.stderr or "")
    missing = ("unittest.loader._FailedTest" in out) or ("has no attribute" in out)
    return r.returncode, out, missing


def baseline_ok(test_id):
    """这条判据在**未变异**代码上是不是本来就绿的。

    返回 (ok, 原因)。这是"新判据先证明能红"的另一面：**先证明它本来是绿的**——
    否则"测试 id 不存在"也会被当成"判据红"（假红灯）。
    """
    rc, _out, missing = run_judgement(test_id)
    if missing:
        return False, "测试 id 不存在"
    if rc != 0:
        return False, "判据在未变异代码上就是红的（rc=%d）" % rc
    return True, ""


def run_case(rel, old, new, label, test_id):
    """old/new 可以是单个字符串，也可以是**等长的列表**（多站点突变）。

    多站点是 E7 补的：有些判据有多道互相独立的兜底（`audit_rules` 里"全局标志
    写错位置"就有静态预检 / re.error 分支 / DeprecationWarning 分支三道），
    只废掉其中一道，测试照样绿——那不是锁有效，那是**这条校准用例自己失效了**。
    """
    path = os.path.join(REPO, rel)
    raw = io.open(path, "rb").read()          # 先读进内存
    # E13 实测：仓库里**有的文件是 CRLF**（auditlib.py）、有的是 LF（audit_graph.py）。
    # 锚点里的 "\n" 在 CRLF 文件上**永远匹配不上** ⇒ 校准会被**静默 SKIP**
    # （"锚点命中 0 次"），看着像跑过了，其实根本没跑 ⇒ 必须按文件的实际换行符归一。
    crlf = b"\r\n" in raw
    if crlf:
        raw = raw.replace(b"\r\n", b"\n")
    token = sha(path)
    pairs = list(zip(old, new)) if isinstance(old, (list, tuple)) else [(old, new)]
    for o, n in pairs:
        o, n = o.encode("utf-8"), n.encode("utf-8")
        if raw.count(o) != 1:
            print("SKIP %-22s 锚点命中 %d 次（校准无效，未改动文件）"
                  % (label, raw.count(o)))
            return "SKIP"
        # E7 实测出来的坑：**还原是全局替换**。若新文本在原文件别处已经存在，
        # 还原会把别处一起改掉（本轮就踩了：突变文本 `segs = set()` 在新函数里也有，
        # 还原时被连带替换 → 函数自我递归 → 还原后 sha1 不一致）。
        # 所以突变前必须断言：新文本在原文件里出现 0 次，还原后恰好 1 次。
        if raw.count(n) != 0:
            print("SKIP %-22s 突变文本在原文件里已存在 %d 次（还原会连带改坏，跳过）"
                  % (label, raw.count(n)))
            return "SKIP"

    # E29 新增：**先确认这条判据在未变异的代码上本来就是绿的**。
    # 理由见 `run_judgement` 的注释：unittest 对"找不到的测试 id"也返回非零 ⇒
    # 少了这一步，"恒红"会被当成"判据红"（**假红灯**）⇒ 校准白跑却看不出来。
    # 这就是"新判据先证明能红"的另一面：**先证明它本来是绿的**。
    ok, why = baseline_ok(test_id)
    if not ok:
        print("INVALID %-22s 判据在**未变异**代码上就不是绿的（%s）"
              "⇒ 这条校准证明不了任何东西，不能计入'全部 RED'"
              % (label, why))
        return "INVALID"
    for o, n in pairs:
        # 顺序不能反：`io.open(path,"wb")` 会**先截断**文件，同一表达式里再读就是
        # 读空文件（本轮真的踩了：把 auditlib.py 清成 0 字节，靠 git checkout 救回）。
        # 所以永远"先读进变量，再落盘"。
        cur = io.open(path, "rb").read()
        if crlf:
            cur = cur.replace(b"\r\n", b"\n")
        out = cur.replace(o.encode("utf-8"), n.encode("utf-8"))
        if crlf:
            out = out.replace(b"\n", b"\r\n")
        io.open(path, "wb").write(out)
    try:
        rc, out, missing = run_judgement(test_id)
        lines = [l for l in out.splitlines()
                 if l.startswith(("FAIL:", "ERROR:", "AssertionError"))]
        if missing:
            verdict = "INVALID（测试 id 不存在 ⇒ 假红灯）"
        elif rc != 0:
            verdict = "RED（锁有效）"
        else:
            verdict = "GREEN（锁无效！）"
        print("%-24s rc=%d %s | %s" % (label, rc, verdict,
                                       (lines[:1] or ["(无匹配行)"])[0][:150]))
        if missing:
            return "INVALID"
        return "RED" if rc != 0 else "GREEN"
    finally:
        mutated = io.open(path, "rb").read()     # 变异态原样读出
        if crlf:
            mutated = mutated.replace(b"\r\n", b"\n")
        now = mutated
        for o, n in reversed(pairs):
            now = now.replace(n.encode("utf-8"), o.encode("utf-8"))
        out = now
        if crlf:
            out = now.replace(b"\n", b"\r\n")
        io.open(path, "wb").write(out)
        # 还原证明：①sha1 与突变前逐字节一致 ②文件非空 ③还原后**不含**突变文本
        # ④变异态里每个突变文本恰好出现一次（否则"还原"可能还原到了别处）
        # E30：**失败时要说清是哪一条不满足** —— 只报"不一致"的话，
        # 还原失败（E30 那轮就撞上过一次，**只在全量跑时**才出现，单跑复现不了）
        # 根本无从下手。
        why = []
        if sha(path) != token:
            why.append("sha1 与突变前不一致（%s != %s）" % (sha(path)[:10], token[:10]))
        if len(io.open(path, "rb").read()) <= 0:
            why.append("还原后文件为空")
        for _o, n in pairs:
            if now.count(n.encode("utf-8")) != 0:
                why.append("还原后仍含突变文本 %d 次" % now.count(n.encode("utf-8")))
        for _o, n in pairs:
            if mutated.count(n.encode("utf-8")) != 1:
                why.append("变异态里突变文本出现 %d 次（应为 1）"
                           % mutated.count(n.encode("utf-8")))
        ok = not why
        print("%-24s 还原=%s（sha1 %s…）" % ("", "逐字节一致" if ok else "!! 不一致 !!",
                                             sha(path)[:10]))
        for w in why:
            print("%-24s   ↳ %s" % ("", w))
        if not ok:
            raise SystemExit("还原失败，停止后续用例")


CASES = [
    ("scripts/auditlib.py",
     'files.append({"path": rel, "bytes": size, "sha1": digest,',
     'files.append({"path": os.path.join(root, rel).replace(os.sep, "/"), "bytes": size, "sha1": digest,',
     "index-path-leak",
     "tests.test_scripts.TestAuditIndex.test_index_emits_relative_posix_paths_only"),
    ("scripts/audit_rules.py",
     "    pos = 0\n    while True:\n        m = GLOBAL_FLAG_RX.search(pat, pos)",
     "    return None\n    pos = 0\n    while True:\n        m = GLOBAL_FLAG_RX.search(pat, pos)",
     "flag-detector-neutered",
     "tests.test_scripts.TestAuditRules.test_misplaced_global_flag_detector_is_interpreter_independent"),
    # E7 修正：这条用例原来长期恒绿——"全局标志写错位置"在 audit_rules 里有**三道**
    # 互相独立的兜底（静态预检 87 行 / re.error 分支 100 行 / DeprecationWarning 分支
    # 105 行），废掉其中一道测试照样绿。恒绿的校准用例比没有用例更坏（它让人以为
    # 那道锁有人管），所以改成**三道同时废**（多站点突变）。
    ("scripts/audit_rules.py",
     ["        if misplaced_global_flag(pat):\n"
      "            # 自己认，不靠解释器：3.8 给 DeprecationWarning、3.11 可能直接 re.error、",
      "        except re.error as exc:\n"
      "            if misplaced_global_flag(pat):",
      "        except DeprecationWarning as exc:\n"
      "            problems.append(_flag_pat_message(where, pat) + u\"（%s）\" % exc)"],
     ["        if False and misplaced_global_flag(pat):\n"
      "            # 自己认，不靠解释器：3.8 给 DeprecationWarning、3.11 可能直接 re.error、",
      "        except re.error as exc:\n"
      "            if False and misplaced_global_flag(pat):",
      "        except DeprecationWarning as exc:\n"
      "            pass  # E7 校准：警告分支不再拦截"],
     "flag-check-all-three-off",
     "tests.test_scripts.TestAuditRules.test_mid_pattern_global_flag_blocks"),
    # ---- E7（v0.41.0）：语境档拆词 ----
    ("scripts/audit_scan.py",
     "        segs.add(seg)\n"
     "        for piece in re.split(r\"[-_]\", seg):\n"
     "            if piece:\n"
     "                segs.add(piece)",
     "        segs.add(seg)\n"
     "        for piece in ():\n"
     "            if piece:\n"
     "                segs.add(piece)",
     "context-nosplit",
     "tests.test_scripts.TestAuditContext.test_qualified_context_directory_is_recognised"),
    ("scripts/audit_scan.py",
     "        segs.add(seg)\n"
     "        for piece in re.split(r\"[-_]\", seg):\n"
     "            if piece:\n"
     "                segs.add(piece)",
     "        segs.add(seg)\n"
     "        for word in sorted(TEST_SEGMENTS | EXAMPLE_ONLY_SEGMENTS):\n"
     "            if word in seg:\n"
     "                segs.add(word)",
     "context-substring",
     "tests.test_scripts.TestAuditContext.test_component_split_still_requires_whole_words"),
    ("scripts/audit_scan.py",
     "    return segs\n\n\ndef code_context(rel):",
     "    return set()\n\n\ndef code_context(rel):",
     "context-neutered",
     "tests.test_scripts.TestAuditContext.test_test_and_example_paths_get_a_context_tag"),
    # ---- E8（v0.42.0）：期望值与实物对账 ----
    ("scripts/validate_skill.py",
     "            check_expected_numbers(skill_dir)\n",
     "            pass  # E8 校准：把期望值对账整项摘掉\n",
     "expected-check-removed",
     "tests.test_scripts.TestValidateExpectedNumbers."
     "test_wrong_expected_numbers_are_flagged"),
    ("scripts/validate_skill.py",
     "            if fence is not None:\n                yield rel, i, line",
     "            if True:\n                yield rel, i, line",
     "expected-scan-outside-blocks",
     "tests.test_scripts.TestValidateExpectedNumbers."
     "test_history_numbers_outside_code_blocks_are_not_flagged"),
    ("scripts/validate_skill.py",
     "            if kind not in per_file[rel]:\n",
     "            if False and kind not in per_file[rel]:\n",
     "expected-form-presence-off",
     "tests.test_scripts.TestValidateExpectedNumbers."
     "test_missing_expectation_form_is_flagged"),
    # ---- E9（v0.43.0）：PHP 请求体（php://input）作为 source ----
    ("scripts/audit-rules/injection.json",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    },\n"
     "    {\n"
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://input['\\\"]\"\n"
     "    }\n"
     "   ],",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    }\n"
     "   ],",
     "php-input-source-removed",
     "tests.test_scripts.TestAuditPhpRequestBody."
     "test_request_body_reaches_each_php_rule"),
    ("scripts/audit-rules/injection.json",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    },\n"
     "    {\n"
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://input['\\\"]\"\n"
     "    }\n"
     "   ],",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    },\n"
     "    {\n"
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\"\n"
     "    }\n"
     "   ],",
     "php-input-source-too-broad",
     "tests.test_scripts.TestAuditPhpRequestBody."
     "test_non_request_body_read_is_not_a_source"),
    # ⚠️ E30 修：这个锚点原来**跨进了 sanitizers 块** ⇒ E30 改了净化点后它就过期
    # （`--check-only` 当场报 STALE-ANCHOR —— 这正是这条机制的价值）。
    # ⇒ 改成只覆盖 sources 块的前缀（仍唯一），不再随净化点变动。
    ("scripts/audit-rules/injection.json",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    },\n"
     "    {\n"
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://input['\\\"]\"",
     "   \"sources\": [\n"
     "    {\n"
     "     \"pattern\": \"(?<!\\\\w)(?:request\\\\.getParameter|\\\\$_(?:GET|POST|REQUEST)|params\\\\[|c\\\\.Param)\"\n"
     "    },\n"
     "    {\n"
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://inputX['\\\"]\"",
     "php-input-literal-changed",
     "tests.test_scripts.TestAuditPhpRequestBody."
     "test_request_body_reaches_each_php_rule"),
    # ---- E10（v0.44.0）：PHP 跨函数形参污点（修复前整条是坏的）----
    ("scripts/audit_graph.py",
     "        if \"$\" in item:\n"
     "            m = re.search(r\"\\$([A-Za-z_]\\w*)\", item)",
     "        m = re.search(r\"([A-Za-z_$]\\w*)\", item.replace(\"$\", \"_\"))",
     "php-param-name-regression",
     "tests.test_scripts.TestAuditPhpCrossFunction."
     "test_param_taint_crosses_function_boundary_across_files"),
    ("scripts/audit_graph.py",
     "    if any(t.strip() and t.strip() not in (\"<?php\", \"<?\", \"?>\", \"<%\") for _n, t, _x in rest):",
     "    if len(rest) >= 3:",
     "php-module-scope-threshold-back",
     "tests.test_scripts.TestAuditPhpCrossFunction."
     "test_param_taint_crosses_function_boundary_same_file"),
    # ---- E11（v0.45.0）：返回值语义（实参 ≠ 返回值）----
    # 五道机制各配一条校准：每一道单独废掉都必须红。恒绿的校准用例比没有用例更坏。
    ("scripts/audit_graph.py",
     "                    dep_pos.add(param_pos[c])",
     "                    pass  # E11 校准：返回值不再依赖形参",
     "ret-dep-params-off",
     "tests.test_scripts.TestAuditPhpReturnValue."
     "test_return_value_inheriting_param_taint"),
    ("scripts/audit_graph.py",
     "                        calls = _iter_calls(code_expr, skip_members=True)",
     "                        calls = []  # E11 校准：摘要分支不触发",
     "ret-summary-branch-off",
     "tests.test_scripts.TestAuditPhpReturnValue."
     "test_return_value_not_inheriting_param_taint"),
    ("scripts/audit_graph.py",
     "                own.append({\"file\": fn[\"file\"], \"line\": lineno,\n"
     "                            \"kind\": \"source\", \"text\": text})",
     "                pass  # E11 校准：返回值不带自身污点",
     "ret-own-taint-off",
     "tests.test_scripts.TestAuditPhpReturnValue."
     "test_source_inside_callee_reaches_caller"),
    ("scripts/audit_graph.py",
     "            # 净化 ⇒ 这条赋值不再依赖任何形参（净化点按规则隔离，这里同规则同词表）。\n"
     "            deps[target] = (set(), [])\n"
     "            continue",
     "            # E11 校准：净化不再清空依赖\n"
     "            pass",
     "ret-sanitizer-in-callee-off",
     "tests.test_scripts.TestAuditPhpReturnValue."
     "test_sanitizer_inside_callee_blocks_taint"),
    # E11 校准实测的**测试盲区**（如实登记在验收记录与交接文档里）：
    # 「skip_members 不把对象方法当仓库内函数」＋「摘要分支仍记 __inline__」
    # 这两道机制在现有规则词表下**测不到**——JZ-SSRF-001 的 sink 要求 sink 调用
    # 内部内联 source，所以对象方法的检出必然走“同行”路径，而同行有**三重**独立
    # 兜底（skip_members / __inline__ / 摘要的 hops 机制）：单独废掉任何一道，
    # 判据照样绿。⇒ 那条判据是**恒绿**的，按“永远绿的锁比没有锁更坏”已删除，
    # 这里也就不配校准用例。两道机制本身保留（它们是语义正确性的前提），
    # 由靶场与三仓的零回退间接守住。
    # ---- E11 顺带核实：净化与输出同行（缺口 2 改判，把结论钉住）----
    ("scripts/audit_graph.py",
     "                    if guard:",
     "                    if False and guard:  # E11 校准：净化与输出同行不再拦",
"sanitize-inline-guard-off",
     "tests.test_scripts.TestAuditSanitizePlacement."
     "test_sanitizer_on_output_line_blocks_the_flow"),
    # ---- E12（v0.46.0）：注释里的代码不是代码 ----
    # 把图层主路径改回"全部行"（含注释）⇒ 判据必须红（证明这四条有牙齿）。
    ("scripts/audit_graph.py",
     "        lines = list(auditlib.iter_code_lines(abs_path, max_bytes=limit,\n"
     "                                           lang=rec[\"lang\"]))",
     "        lines = list(auditlib.iter_lines(abs_path, max_bytes=limit))",
     "comment-lines-included-back",
     "tests.test_scripts.TestAuditCommentNotCode."
     "test_php_hash_comment_line_is_not_code"),
    # ---- E13（v0.47.0）：行尾注释里的代码也不是代码 ----
    ("scripts/auditlib.py",
     "    line_tokens = LINE_COMMENT_TOKENS.get(lang, ())",
     "    line_tokens = ()  # E13 校准：不剥行尾注释",
     "tail-comment-strip-off",
     "tests.test_scripts.TestAuditTailComment."
     "test_php_slash_tail_comment_is_not_code"),
    ("scripts/auditlib.py",
     '    "python": ("#",),',
     '    "python": ("#", "//"),  # E13 校准：把整除当注释',
     "python-floor-division-as-comment",
     "tests.test_scripts.TestAuditTailComment."
     "test_python_floor_division_is_not_a_comment"),
    # ---- E14（v0.48.0）：块注释 /* … */（可跨行）里的代码也不是代码 ----
    ("scripts/auditlib.py",
     '    "php": ("/*", "*/"),',
     '    "php": (),  # E14 校准：不剥块注释',
     "block-comment-tokens-off",
     "tests.test_scripts.TestAuditBlockComment."
     "test_multiline_block_comment_is_not_code"),
    ("scripts/auditlib.py",
     "    for m in STRING_SPAN_RX.finditer(text):\n"
     "        seg, in_block = _cut_mixed(text[pos:m.start()], line_tokens, block_tokens,\n"
     "                                   in_block)",
     "    for m in []:  # E14 校准：不跳过字符串\n"
     "        seg, in_block = _cut_mixed(text[pos:m.start()], line_tokens, block_tokens,\n"
     "                                   in_block)",
     "block-comment-string-not-skipped",
     "tests.test_scripts.TestAuditBlockComment."
     "test_string_with_block_markers_is_not_a_comment"),
    # ---- E15（v0.49.0）：U+FFFD 替换字符（= 被损坏的字符）也要有判据 ----
    ("scripts/validate_skill.py",
     "                        if chr(0xFFFD) in line:",
     "                        if False and chr(0xFFFD) in line:  # E15 校准：不查坏字符",
     "replacement-char-check-off",
     "tests.test_scripts.TestValidateReplacementChars."
     "test_replacement_char_is_flagged"),
    # ---- E16（v0.50.0）：JZ-XSS-002 接上 php://input ----
    # 锚点必须**唯一**：那条 php://input pattern 在 injection.json 里有 7 处（7 条规则），
    # 单用 pattern 会命中 7 次 ⇒ 校准器直接 SKIP（E13 修过这个坑：SKIP 必须显式报错）。
    # ---- E16（v0.50.0）：JZ-XSS-002 接上 php://input ----
    # 变异 JZ-XSS-002 **自己的 sink pattern**（改成不存在的形态）⇒ 判据必须红。
    # 不用"删掉那条 source"是因为校准器不接受 new 文本已存在（原文件里就有那个
    # 少项版本，还原会连带改坏别处）⇒ 改 sink 效果等价且能表达。
    ("scripts/audit-rules/injection.json",
     "     \"pattern\": \"\\\\b(?:echo|print)\\\\b[^;]*\\\\$\"",
     "     \"pattern\": \"\\\\b(?:echo|print)\\\\b[^;]*\\\\$X\"",
     "php-input-xss-sink-off",
     "tests.test_scripts.TestAuditPhpInputXss."
     "test_request_body_reaches_xss_rule"),
    # ---- E17（v0.51.0）：PHP 的 exec() 是命令执行，不是动态代码执行 ----
    # 变异：把 exec 加回 JZ-CODE-001 ⇒ 判据必须红（证明它不再被 CODE-001 认领）。
    ("scripts/audit-rules/injection.json",
     "     \"pattern\": \"\\\\beval\\\\s*\\\\(\"",
     "\"pattern\": \"\\\\beval\\\\s*\\\\(|\\\\bexec\\\\s*\\\\(",
     "exec-back-to-code-rule",
     "tests.test_scripts.TestAuditExecClassification."
     "test_php_exec_is_command_execution_not_dynamic_code"),
    # ---- E18（v0.52.0）：赋值覆盖后要清掉目标原有的污点 ----
    # 变异：去掉 "tainted.pop(rtarget, None)" ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "                    tainted.pop(rtarget, None)",
     "                    pass  # E18 校准：不清掉旧污点",
     "overwrite-keeps-old-taint",
     "tests.test_scripts.TestAuditOverwriteClearsTaint."
     "test_overwrite_by_constant_returning_helper_drops_old_taint"),
    # ---- E19（v0.53.0）：PHP 成员方法 ->method( 不该借用同名仓库函数的摘要 ----
    # 变异：去掉 `->` 的排除（回到 E13 状态）⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "            if prev == \".\" or text[max(0, m.start() - 2):m.start()] == \"->\":",
     "            if prev == \".\":",
     "member-call-not-excluded",
     "tests.test_scripts.TestAuditPhpMemberCall."
     "test_member_call_not_treated_as_repo_function"),
    # ---- E21（v0.55.0）：SARIF 必须过官方 SARIF 2.1.0 schema ----
    # 变异①：把 conceptualName 塞回 physicalLocation（v0.54.0 的老样子，官方
    # sarif-multitool validate 报 JSON1005）⇒ 判据必须红。
    # 这条同时验出"自检没看 codeFlows"这个盲区：塞回去后自检立刻报出违规。
    ("scripts/audit_scan.py",
     '                {"location": {\n'
     '                    "physicalLocation": {\n'
     '                        "artifactLocation": {"uri": hop["file"], "uriBaseId": "%SRCROOT%"},\n'
     '                        "region": {"startLine": max(1, int(hop["line"]))}},\n'
     '                    "message": {"text": "[%s] %s" % (hop.get("kind", ""),\n'
     '                                                    hop.get("text", "")[:180])}}}\n',
     '                {"location": {"physicalLocation": {\n'
     '                    "artifactLocation": {"uri": hop["file"], "uriBaseId": "%SRCROOT%"},\n'
     '                    "region": {"startLine": max(1, int(hop["line"]))},\n'
     '                    "conceptualName": hop.get("kind", "")},\n'
     '                    "message": {"text": hop.get("text", "")[:200]}}}\n',
     "sarif-conceptual-name-back",
     "tests.test_scripts.TestAuditSarifSchema."
     "test_real_sarif_passes_and_keeps_flow_info"),
    # 变异②：把 message 塞进 physicalLocation（message 属于 location 层，
    # physicalLocation 层不允许）——这正是修 E21 时我自己第一版改错的地方。
    # test_id 必须指**真的经过 to_sarif 的那条测试**：原先挂的是
    # test_bad_properties_are_caught_including_codeflows，那条直接手搓坏 SARIF
    # 再喂自检，压根不走 to_sarif ⇒ 变异后照样绿（锁无效！校准器当场报 GREEN）。
    ("scripts/audit_scan.py",
     '                        "region": {"startLine": max(1, int(hop["line"]))}},\n'
     '                    "message": {"text": "[%s] %s" % (hop.get("kind", ""),\n'
     '                                                    hop.get("text", "")[:180])}}}\n',
     '                        "region": {"startLine": max(1, int(hop["line"]))},\n'
     '                    "message": {"text": "[%s] %s" % (hop.get("kind", ""),\n'
     '                                                    hop.get("text", "")[:180])}}}}\n',
     "sarif-message-in-physical-location",
     "tests.test_scripts.TestAuditSarifSchema."
     "test_real_sarif_passes_and_keeps_flow_info"),
    # ---- E22（v0.56.0）：能力边界表必须被夹具钉住 ----
    # 变异①：把净化点 pattern 改成能匹配 mysqli_real_escape_string ⇒
    # "转义处照报"这条边界不再成立 ⇒ 判据必须红（提醒改表）。
    ("scripts/audit-rules/injection.json",
     '     "pattern": "\\\\b(?:mysql|mysqli)_(?:real_)?escape_string\\\\s*\\\\(|\\\\breal_escape_string\\\\s*\\\\(",',
     '     "pattern": "\\\\b(?:mysql)_(?:real_)?escape_string\\\\s*\\\\(|\\\\breal_escape_string\\\\s*\\\\(",',
     "escape-sanitizer-back-to-dead",
     "tests.test_scripts.TestAuditSqlQuoteContext."
     "test_escape_sanitizer_actually_matches_mysqli"),
    # 变异②：把边界表一行的「代价」列**整列清空** ⇒ 结构判据必须红。
    # ⚠️ 第一版只抹掉了代价列里的**半句**，列仍非空 ⇒ 判据照样绿 ⇒ 校准器当场报 GREEN
    # （"锁无效"）—— 这条 GREEN 是真信号：判据只查"非空"，不查"内容"。
    # （old/new 都不含 ASCII 双引号：文档里用的是中文全角引号。）
    ("references/audit-rule-authoring.md",
     '| **JS 里 `//` 的歧义**（注释 / 正则字面量 / 除法） | 单遍静态扫描分不清'
     u'"正则里的 `//`"和"注释" ⇒ **两种做法都会漏报**：按代码处理会把真注释当代码，'
     u'按注释处理会把正则后同行的代码吃掉 | 我们选"按注释处理"（除法更常见）⇒ '
     u'**正则字面量同行之后的代码整段被漏掉**（真阳性丢失） | 夹具 '
     u'`var re = /\\/\\//; var x = request.query[\'q\']; eval(x);` ⇒ **0 条发现**；'
     u'同一行去掉正则字面量 ⇒ **1 条**（真阳性） |',
     '| **JS 里 `//` 的歧义**（注释 / 正则字面量 / 除法） | 单遍静态扫描分不清'
     u'"正则里的 `//`"和"注释" ⇒ **两种做法都会漏报**：按代码处理会把真注释当代码，'
     u'按注释处理会把正则后同行的代码吃掉 |  | 夹具 '
     u'`var re = /\\/\\//; var x = request.query[\'q\']; eval(x);` ⇒ **0 条发现**；'
     u'同一行去掉正则字面量 ⇒ **1 条**（真阳性） |',
     "boundary-table-cost-cell-empty",
     "tests.test_scripts.TestAuditCapabilityBoundaries."
     "test_boundary_table_has_why_and_cost"),
    # ---- E23（v0.57.0）：性能护栏不许退回单次测量 ----
    # 变异①：把 CI 诊断步的 bench 退回 --repeat 1 ⇒ 判据必须红。
    # ⚠️ 只突变**诊断步那一处**：正常步与诊断步的 `--files 400 --repeat 2 ...` 片段
    # 互相包含（诊断步那行前面多了 $RUNNER_TEMP/diag-bench），两条一起改会撞上
    # 校准器的"锚点必须恰好命中 1 次"与"突变文本必须只出现 1 次"两条自证规则。
    (".github/workflows/validate.yml",
     '--workdir "$RUNNER_TEMP/diag-bench" --files 400 --repeat 3 --max-ms-per-file 20 --max-mb 128',
     '--workdir "$RUNNER_TEMP/diag-bench" --files 400 --repeat 1 --max-ms-per-file 20 --max-mb 128',
     "ci-bench-back-to-single-measure",
     "tests.test_scripts.TestBenchAggregation."
     "test_ci_bench_uses_repeat_at_least_two"),
    # 变异②：把聚合从"最快一次"改回"累加" ⇒ 判据必须红。
    ("evals/audit-fixtures/bench.py",
     "        cur[0] = dt if cur[0] is None else min(cur[0], dt)\n",
     "        cur[0] += dt\n",
     "bench-aggregate-becomes-sum",
     "tests.test_scripts.TestBenchAggregation."
     "test_aggregate_rows_takes_fastest_not_mean_or_sum"),
    # ---- E24（v0.58.0）：校准器入库后，它自己的"存在 + 例数"也要有牙齿 ----
    # 变异：把 validate 的第 19 项改成永远通过 ⇒ 判据必须红
    # （"校准器在库里、但没人查它"是最典型的装饰性交付）。
    ("scripts/validate_skill.py",
     "def check_mut_calibrator(skill_dir):\n",
     "def check_mut_calibrator(skill_dir):\n    return  # E24 校准：这项永远通过\n",
     "mut-calibrator-check-neutered",
     "tests.test_scripts.TestMutCalibratorShipped."
     "test_validate_reports_mut_calibrator"),
    # ---- E25（v0.59.0）：收窄三条"规则过宽"的误报 ----
    # 下面三条用 chr(92) 拼反斜杠：JSON 源码里的正则要写两个反斜杠，
    # 手写转义层数极易错一层 ⇒ 让机器拼。
    ("scripts/audit-rules/injection.json",
     '     "pattern": "' + B + B + 'bcreate_function' + B + B + 's*' + B + B + '(' + '"',
     '     "pattern": "' + B + B + 'b(?:create_function|preg_replace)' + B + B + 's*' + B + B + '(' + '"',
     "code-rule-preg-replace-back",
     "tests.test_scripts.TestAuditOverbroadRuleNarrowing."
     "test_preg_replace_is_not_dynamic_code_execution"),
    ("scripts/audit-rules/webapp.json",
     '     "pattern": "display_errors' + B + B + 's*=' + B + B + 's*On'
     + '|show_error_msg' + B + B + 's*=' + B + B + 's*1"',
     '     "pattern": "display_errors' + B + B + 's*=' + B + B + 's*On'
     + '|error_reporting' + B + B + 's*' + B + B + '(' + B + B + 's*E_ALL' + B + B
     + 'b|show_error_msg' + B + B + 's*=' + B + B + 's*1"',
     "debug-rule-error-reporting-back",
     "tests.test_scripts.TestAuditOverbroadRuleNarrowing."
     "test_error_reporting_alone_is_not_a_leak"),
    ("scripts/audit-rules/webapp.json",
     '     "pattern": "(?i)' + B + B + 'b(?:save|write|store|move_uploaded_file|move)'
     + B + B + 's*' + B + B + '(' + '[^)]*'
     + '(?:filename|file' + B + B + '.name|originalname|' + B + B + '$_FILES)"\n    }',
     '     "pattern": "(?i)' + B + B + 'b(?:save|write|store|move_uploaded_file|move)'
     + B + B + 's*' + B + B + '(' + '[^)]*'
     + '(?:filename|file' + B + B + '.name|originalname|' + B + B + '$_FILES)"\n'
     '    },\n    {\n'
     '     "pattern": "(?i)content[_-]?type[^' + B + B + 'n]{0,40}'
     + '(?:==|in|is)' + B + B + 's*[' + B + '"' + "'" + ']?(?:image|application)"\n    }',
     "upload-rule-content-type-back",
     "tests.test_scripts.TestAuditOverbroadRuleNarrowing."
     "test_content_type_check_must_be_about_the_uploaded_file"),
    # ---- E26（v0.60.0）：给 innerHTML 赋纯字符串常量不是 XSS ----
    # 变异：让那条负向先行**永远不成立**（在 `;` 后多插一个字符）⇒ 回到"只认
    # `.innerHTML =`"的宽形态 ⇒ 判据必须红。
    # ⚠️ 不能把整条 sink 换回老形态：老形态是新形态的**前缀**（新文本已存在于
    # 文件里）⇒ 校准器会按"突变文本已存在 ⇒ 还原会连带改坏"直接 SKIP。
    ("scripts/audit-rules/webapp.json",
     '     "pattern": "' + B + B + '.innerHTML' + B + B + 's*=(?!' + B + B + 's*[' + B + '"'
     + "']['" + B + '"' + ']' + B + B + 's*;)',
     '     "pattern": "' + B + B + '.innerHTML' + B + B + 's*=(?!' + B + B + 's*[' + B + '"'
     + "']['" + B + '"' + ']' + B + B + 's*;X)',
     "xss-constant-innerhtml-back",
     "tests.test_scripts.TestAuditXssConstantAssignment."
     "test_constant_assignment_is_not_reported"),
    # ---- E27（v0.61.0）：交接文档必须在仓库内、章节完整、被 git 跟踪 ----
    # 变异①：把第 20 项改成永远通过 ⇒ 判据必须红（"文件在，但没人查它"）。
    ("scripts/validate_skill.py",
     "def check_handover_in_repo(skill_dir):\n",
     "def check_handover_in_repo(skill_dir):\n    return  # E27 校准：这项永远通过\n",
     "handover-check-neutered",
     "tests.test_scripts.TestHandoverInRepo."
     "test_validate_reports_handover_in_repo"),
    # 变异②：从必需章节列表里去掉 §8 ⇒ 缺章节的反例必须红
    # （它靠 validate 自己发现"缺章节"；列表少一项 ⇒ 它就发现不了）。
    ("scripts/validate_skill.py",
     'HANDOVER_SECTIONS = ("## 0. ", "## 5. ", "## 6. ", "## 8. ", "## 11. ", "## 13. ", "## 14. ")',
     'HANDOVER_SECTIONS = ("## 0. ", "## 5. ", "## 6. ", "## 11. ", "## 13. ", "## 14. ")',
     "handover-section-list-shortened",
     "tests.test_scripts.TestHandoverInRepo."
     "test_validate_flags_a_handover_with_a_missing_section"),
    # ---- E29（v0.63.0）：document.write 纯常量不是 XSS ----
    # 变异：给负向先行加一个尾字符 `x` ⇒ 这一支**整个不再匹配**（负向先行是零宽断言，
    # 尾字符落在它**后面** ⇒ 后面还必须真有个 `x` 才算命中）。
    # ⚠️ **这条判据要配「带变量仍要报」而不是「纯常量不报」**：
    # 变异让这一支整个失灵 ⇒ 纯常量照样不报（"纯常量不报"仍绿！），
    # 只有"带变量仍要报"会红。⚠️ 第一版配错了 ⇒ 全量校准当场报 GREEN（锁无效）
    # ⇒ 这就是"每条校准都要自己红过一次"的价值。
    # ⚠️ old/new 用 repr() 生成：**不手写任何反斜杠**（E28 在这上面踩了四次）。
    ("scripts/audit-rules/webapp.json",
     '\\\\s*(?!\\\\s*[\\"\'][\'\\"]\\\\s*\\\\)?;)',
     '\\\\s*(?!\\\\s*[\\"\'][\'\\"]\\\\s*\\\\)?;)x',
     "xss-document-write-constant-back",
     "tests.test_scripts.TestAuditXssConstantAssignment."
     "test_document_write_with_variable_is_still_reported"),
    # ---- E29（v0.63.0）：校准器自己的两道前置检查也必须有牙齿 ----
    # ① 静态检查（check_test_ids）被废掉 ⇒「test id 不存在」报不出来 ⇒ 判据必须红。
    ("scripts/mut_calibrate.py",
     '            print("MISSING-TEST %s :: %s.%s" % (label, cls, meth))\n            bad += 1',
     '            print("MISSING-TEST %s :: %s.%s" % (label, cls, meth))\n            bad += 0',
     "mut-calibrator-test-id-check-neutered",
     "tests.test_scripts.TestMutCalibratorShipped."
     "test_calibrator_flags_a_case_whose_test_id_is_missing"),
    # ② 运行时基线检查（baseline_ok）被废掉 ⇒「恒红」又被当成「判据红」⇒ 判据必须红。
    # ⚠️ 锚点必须**跨行**：单行锚点会在这条 CASES 字面量里**匹配到自己**
    #（"命中 2 次"）⇒ 锚点要写成源码里那种"缩进 + 换行"的组合。
    ("scripts/mut_calibrate.py",
     '    if missing:\n        return False, "测试 id 不存在"',
     '    if missing:\n        return True, "测试 id 不存在"',
     "mut-calibrator-baseline-check-neutered",
     "tests.test_scripts.TestMutCalibratorShipped."
     "test_calibrator_baseline_rejects_a_missing_test_id"),
    # ---- E29（v0.63.0）：validate 第 21 项（判定表自洽）此前一把都没验过 ----
    # ① 把「flask 等」的条数换回「静态可修」的条数（**这正是 E29 修掉的潜伏 bug**）
    #    ⇒ 第 21 项必须当场判错 ⇒ 判据必须红。
    #    ⚠️ 这条与判定表当前的数字**耦合**（静态可修=0 / flask=1 / DVWA=60 / 合计=61
    #    ⇒ 60+0 ≠ 61 才炸）⇒ 将来改了判定表的数字，这条会跑成 GREEN，
    #    校准器会当场报「锁无效」提醒重新设计变异点（不会静默放过）。
    ("scripts/validate_skill.py",
     "        if d_all + f_all != t_all:",
     "        if d_all + fixable_n != t_all:",
     "verdict-flask-count-reuses-fixable",
     "tests.test_scripts.TestVerdictTable."
     "test_validate_reports_the_verdict_table_check"),
    # ② 把「§二 逐行反推 vs §三 声明」的一道比较写反（!= 写成 ==）
    #    ⇒ §二 某行改了、§三 没改时必须报不出来 ⇒ 判据必须红。
    ("scripts/validate_skill.py",
     '        if rows["待能力升级"] != upgrade_n:',
     '        if rows["待能力升级"] == upgrade_n:',
     "verdict-section-two-row-count-neutered",
     "tests.test_scripts.TestVerdictTable."
     "test_section_two_rows_must_match_the_bucket_table"),
    # ---- E30（v0.64.0）：净化点按 sink 上下文生效（转义只在引号内有效）----
    # ① 上下文判定被改成"永远当引号外" ⇒ 引号内的真·误报又回来 ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     '            return "quoted" if (in_single or in_double) else "bare"',
     '            return "bare"',
     "sql-quote-context-always-bare",
     "tests.test_scripts.TestAuditSqlQuoteContext."
     "test_escaped_value_in_quotes_is_not_reported"),
    # ② 条件净化点又被当成了"守卫" ⇒ 引号外的**真阳性**被吃掉 ⇒ 判据必须红。
    # ⚠️ E31：锚点必须带上下文（原来只有 `if not s.get("context")` 一行 ⇒
    # E31 新增的 include-scope 检查里**也**有这串文本 ⇒ 命中变成 2 次 ⇒ 锚点过期）。
    ("scripts/audit_graph.py",
     '                    guard = [s for s in sanits\n'
     '                             if not s.get("context")',
     '                    guard = [s for s in sanits\n'
     '                             if True',
     "sql-quote-guard-blocks-conditional",
     "tests.test_scripts.TestAuditSqlQuoteContext."
     "test_escaped_value_outside_quotes_is_still_reported"),
    # ③ 整个上下文判定被跳过 ⇒ 条件净化点等于没有 ⇒ 引号内的误报又回来 ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "                        if cond_san and STR_SPAN_RX.search(rhs):",
     "                        if False:",
     "sql-quote-decision-neutered",
     "tests.test_scripts.TestAuditSqlQuoteContext."
     "test_escaped_value_in_quotes_is_not_reported"),
    # ---- E31（v0.65.0）：跨行字符串字面量折叠 + include-scope 认净化点 ----
    # ① 折叠被关掉 ⇒ 多行串首行的列别名又被当成变量读取 ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "        lines = _fold_multiline_strings(abs_path, lines, rec[\"lang\"])",
     "        pass  # E31 校准：跨行字符串折叠被关掉",
     "multiline-fold-neutered",
     "tests.test_scripts.TestAuditMultilineString."
     "test_column_alias_in_multiline_string_is_not_a_variable_read"),
    # ② include-scope 不再认被 include 文件里的净化点 ⇒ 已被净化的值又被带走 ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "                    if _first_code_match([s for s in rule[\"sanitizers\"]\n"
     "                                          if not s.get(\"context\")], text):\n"
     "                        continue",
     "                    if False:  # E31 校准：include-scope 的净化点检查被关掉\n"
     "                        continue",
     "include-scope-sanitizer-ignored",
     "tests.test_scripts.TestAuditMultilineString."
     "test_include_scope_honors_sanitizer_in_the_included_file"),
    # ③ PHP 插值不再算读取 ⇒ 多行串里的 `{$var}` 读不到 ⇒ 判据必须红。
    ("scripts/audit_graph.py",
     "            out.extend(PHP_INTERP_RX.findall(body))",
     "            pass  # E31 校准：PHP 插值不再算读取",
     "php-interpolation-not-a-read",
     "tests.test_scripts.TestAuditMultilineString."
     "test_interpolation_in_multiline_string_is_still_a_read"),
    # ---- E32（v0.66.0）：§四 口径拆解的自洽核对（validate 第 22 项）----
    # 把「全部产出」的加法比较关掉 ⇒ 口径不自洽时 validate 不再报错 ⇒ 判据必须红。
    ("scripts/validate_skill.py",
     "        if t_all != t_true + t_fp_num + t_other:",
     "        if False:  # E32 校准：口径加法的比较被关掉",
     "ledger-totals-addition-neutered",
     "tests.test_scripts.TestLedgerTotals."
     "test_broken_ledger_totals_must_be_flagged"),
    # ---- E32（v0.66.0）：§8 坑位编号连续性（validate 第 20 项里的一条守卫）----
    # 缺号检测被关掉 ⇒ 编号乱了也不报 ⇒ 判据必须红。
    ("scripts/validate_skill.py",
     "            gaps = [k for k in range(nums[0], nums[-1] + 1) if k not in set(nums)]",
     "            gaps = []  # E32 校准：§8 缺号检测被关掉",
     "handover-pitfall-numbering-neutered",
     "tests.test_scripts.TestHandoverInRepo."
     "test_broken_pitfall_numbering_must_be_flagged"),
]


def check_anchors():
    """只核对锚点：每个 old 必须恰好命中 1 次，每个 new 必须 0 次。

    锚点过期（实现演进后旧文本改掉了）会让校准**静默失效**——
    所以这件事本身要能被 CI 便宜地看见。
    """
    bad = 0
    for case in CASES:
        rel, old, new = case[0], case[1], case[2]
        path = os.path.join(REPO, rel)
        if not os.path.isfile(path):
            print("MISSING-FILE %s" % rel)
            bad += 1
            continue
        raw = io.open(path, "rb").read()
        crlf = b"\r\n" in raw
        if crlf:
            raw = raw.replace(b"\r\n", b"\n")
        olds = old if isinstance(old, (list, tuple)) else [old]
        news = new if isinstance(new, (list, tuple)) else [new]
        for o in olds:
            c = raw.count(o.encode("utf-8"))
            if c != 1:
                print("STALE-ANCHOR %s :: 命中 %d 次 :: %r" % (rel, c, o[:60]))
                bad += 1
        for n in news:
            c = raw.count(n.encode("utf-8"))
            if c != 0:
                print("DUPLICATE-MUTATION %s :: 已存在 %d 次 :: %r" % (rel, c, n[:60]))
                bad += 1
    return bad


def _class_body(src, cls):
    """取某个 class 的正文（从 class 行到下一个顶层 class 行之前）。"""
    m = re.search(r"^class\s+%s\b" % re.escape(cls), src, re.M)
    if not m:
        return None
    rest = src[m.end():]
    nxt = re.search(r"^class\s+\w", rest, re.M)
    return rest[:nxt.start()] if nxt else rest


def check_test_ids(cases=None):
    """E29：每条校准的 test_id 必须**真实存在**。

    为什么要有这一项：`unittest` 对"找不到的测试 id"也返回非零 ⇒ 校准器会把
    "恒红"当成"判据红"（**假红灯**）⇒ 那条校准什么都没证明，却照样被算进
    "全部 RED"。E29 那条 `xss-document-write-constant-back` 就中招了：它指向的
    测试被放进了别的类 ⇒ 跑出来是 AttributeError，不是判据红。
    ⇒ 这一项是**静态**的 ⇒ 能进 CI（`--check-only`），比运行时探测便宜得多。
    ⚠️ 它只查"存在"，查不了"本来是不是红的"——那件事由 `run_case` 的基线检查兜。
    """
    cases = CASES if cases is None else cases
    src = io.open(os.path.join(REPO, "tests", "test_scripts.py"),
                  encoding="utf-8").read()
    bad = 0
    for case in cases:
        label, test_id = case[3], case[4]
        parts = test_id.rsplit(".", 2)      # 模块.类.方法 ⇒ 取后两段
        if len(parts) != 3:
            print("BAD-TEST-ID %s :: %s" % (label, test_id))
            bad += 1
            continue
        cls, meth = parts[1], parts[2]
        body = _class_body(src, cls)
        if body is None:
            print("MISSING-CLASS %s :: %s" % (label, cls))
            bad += 1
            continue
        if not re.search(r"^\s+def\s+%s\s*\(" % re.escape(meth), body, re.M):
            print("MISSING-TEST %s :: %s.%s" % (label, cls, meth))
            bad += 1
    return bad


if __name__ == "__main__":
    if "--check-only" in sys.argv:
        bad = check_anchors()
        bad += check_test_ids()
        if bad:
            print("CALIBRATION-SET-BROKEN %d 处（锚点过期 / test id 不存在）" % bad)
            sys.exit(1)
        print("== %d 条校准用例的锚点全部命中、test id 全部存在（未执行测试） ==" % len(CASES))
        sys.exit(0)
    skipped = 0
    green = 0
    invalid = 0
    for case in CASES:
        st = run_case(*case)
        if st == "SKIP":
            skipped += 1
        elif st == "GREEN":
            green += 1
        elif st == "INVALID":
            invalid += 1
    bad = []
    if skipped:
        bad.append("%d 条校准被 SKIP（锚点未命中 ⇒ 校准未生效，判据有没有牙齿未验证）" % skipped)
    if green:
        bad.append("%d 条校准跑出 GREEN（锁无效！要么判据恒绿，要么锚点指到了不影响它的地方）" % green)
    if invalid:
        bad.append("%d 条校准是**假红灯**（判据在未变异代码上就不是绿的：test id 不存在，"
                   "或判据本来就是红的）⇒ 这几条什么都没证明" % invalid)
    if bad:
        for b in bad:
            print("!! " + b)
        sys.exit(1)
    print("== 全部校准用例均已实际执行，且全部 RED（无 SKIP、无 GREEN、无 INVALID） ==")
