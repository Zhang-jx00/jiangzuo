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
import subprocess
import sys

# 仓库根 = 本文件（scripts/）的上一级。E24 起校准器**随技能一起分发**。
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def sha(path):
    return hashlib.sha1(io.open(path, "rb").read()).hexdigest()


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
            return None
        # E7 实测出来的坑：**还原是全局替换**。若新文本在原文件别处已经存在，
        # 还原会把别处一起改掉（本轮就踩了：突变文本 `segs = set()` 在新函数里也有，
        # 还原时被连带替换 → 函数自我递归 → 还原后 sha1 不一致）。
        # 所以突变前必须断言：新文本在原文件里出现 0 次，还原后恰好 1 次。
        if raw.count(n) != 0:
            print("SKIP %-22s 突变文本在原文件里已存在 %d 次（还原会连带改坏，跳过）"
                  % (label, raw.count(n)))
            return None
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
        r = subprocess.run([sys.executable, "-m", "unittest", test_id], cwd=REPO,
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=240)
        lines = [l for l in (r.stdout or "").splitlines()
                 if l.startswith(("FAIL:", "ERROR:", "AssertionError"))]
        verdict = "RED（锁有效）" if r.returncode != 0 else "GREEN（锁无效！）"
        print("%-24s rc=%d %s | %s" % (label, r.returncode, verdict,
                                       (lines[:1] or ["(无匹配行)"])[0][:150]))
        return r.returncode
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
        ok = (sha(path) == token
              and len(io.open(path, "rb").read()) > 0
              and all(now.count(n.encode("utf-8")) == 0 for _, n in pairs)
              and all(mutated.count(n.encode("utf-8")) == 1 for _, n in pairs))
        print("%-24s 还原=%s（sha1 %s…）" % ("", "逐字节一致" if ok else "!! 不一致 !!",
                                             sha(path)[:10]))
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
    ("scripts/audit-rules/injection.json",
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://input['\\\"]\"\n"
     "    }\n"
     "   ],\n"
     "   \"sanitizers\": [\n"
     "    {\n"
     "     \"pattern\": \"\\\\b(?:setString|setInt|bindValue)\\\\s*\\\\(|\\\\breal_escape_string\\\\b|\\\\bPreparedStatement\\\\b|\\\\$\\\\d\"",
     "     \"pattern\": \"file_get_contents\\\\s*\\\\(\\\\s*['\\\"]php://inputX['\\\"]\"\n"
     "    }\n"
     "   ],\n"
     "   \"sanitizers\": [\n"
     "    {\n"
     "     \"pattern\": \"\\\\b(?:setString|setInt|bindValue)\\\\s*\\\\(|\\\\breal_escape_string\\\\b|\\\\bPreparedStatement\\\\b|\\\\$\\\\d\"",
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
     "\\\\breal_escape_string\\\\b",
     "\\\\bmysqli_?real_escape_string\\\\b",
     "escape-sanitizer-now-matches",
     "tests.test_scripts.TestAuditCapabilityBoundaries."
     "test_escaped_string_is_not_treated_as_sanitizer"),
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


if __name__ == "__main__":
    if "--check-only" in sys.argv:
        bad = check_anchors()
        if bad:
            print("ANCHORS-BROKEN %d 处" % bad)
            sys.exit(1)
        print("== %d 条校准用例的锚点全部命中（未执行测试） ==" % len(CASES))
        sys.exit(0)
    skipped = 0
    green = 0
    for case in CASES:
        rc = run_case(*case)
        if rc is None:
            skipped += 1
        elif rc == 0:
            green += 1
    bad = []
    if skipped:
        bad.append("%d 条校准被 SKIP（锚点未命中 ⇒ 校准未生效，判据有没有牙齿未验证）" % skipped)
    if green:
        bad.append("%d 条校准跑出 GREEN（锁无效！要么判据恒绿，要么锚点指到了不影响它的地方）" % green)
    if bad:
        for b in bad:
            print("!! " + b)
        sys.exit(1)
    print("== 全部校准用例均已实际执行，且全部 RED（无 SKIP、无 GREEN） ==")
