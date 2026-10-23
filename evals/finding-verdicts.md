# 结论区逐条判定表（将作 · 将作 jiangzuo）

> **这份表回答一个具体问题**：审计链报的每一条，到底是真漏洞还是误报？
> E20 逐条判过一次（`v0.54.0` 节），但那次的判定**有三处偏差**（见下），
> 且把一条**在另计档（测试语境）**的条目算进了分子。
> **E28（v0.62.0）把结论区 62 条全部重判一遍**（DVWA 61 + flask 1 + requests 0），
> 判定依据是**每条的完整证据链 + 必要时读源码**（不是只看 sink 行）。
> **E29（v0.63.0）修掉最后一条「静态可修」的误报**（纯常量 `document.write`）
> ⇒ 结论区 **61 条**、误报 **6 条**，**「静态可修」这一类归零 ⇒ 硬误报清零**。
> **E30（v0.64.0）做掉「净化点按 sink 上下文生效」**（转义类净化点按**引号内 / 引号外**两档生效）
> ⇒ 结论区 **60 条**、误报 **5 条**，**「待能力升级」从 2 降到 1**（只剩"净化点跨文件作用域" ⇒ E31）。
> **E31（v0.65.0）做掉「净化点跨文件作用域」**（并顺带修掉一类**既有的漏报**：多行字符串里的插值）
> ⇒ 结论区 **59 条**、误报 **4 条**，**「待能力升级」也归零** ⇒ 剩下的 4 条**全是能力边界型**。
>
> **口径声明**：分母＝**结论区条数**（＝正式代码语境里的发现；测试/示例语境另计，不进分母）。
> 分子＝**已判定为"检测错了"的条数**。**未判定 = 0**（E20 留下的 3 条已全部有结论）。
>
> **复现命令**（结论区条数会随规则/引擎变化 ⇒ 先取数再对表）：
> ```bash
> python scripts/audit_scan.py <第三方仓库> --json ../eval-runs/scan.json
> python -c "import json;d=json.load(open('../eval-runs/scan.json'));print(d['stats']['conclusions'])"
> ```

## 一、汇总（按规则）

| 规则 | 结论区条数 | 真阳性 | 误报 | 备注 |
|---|---|---|---|---|
| JZ-CMDI-001 | 7 | 7 | 0 | DVWA exec 模块 + `api/src/HealthController.php:88`（`php://input` → `exec`） |
| JZ-CODE-001 | 2 | 2 | 0 | `view_help.php:20,22`：`$_GET['id']` → `eval('?>' . file_get_contents(...))`（LFI→RCE） |
| JZ-SQLI-003 | 12 | 12 | 0 | 原 §二 #1（跨文件净化点）已由 E31 修掉；#2 已由 E30 修掉 |
| JZ-SECRET-001 | 1 | 0 | 1 | 误报见 §二 #3 |
| JZ-XSS-002 | 2 | 2 | 0 | `csp/source/jsonp.php:12`（JSONP 回调未校验）、`xss_r/source/low.php:8`（反射 XSS） |
| JZ-TRAVERSAL-001 | 1 | 1 | 0 | `fi/index.php:36`：`include($file)`，源在被 include 的文件里 |
| JZ-CRYPTO-003 | 5 | 5 | 0 | `aes-128-ecb` ×3、逐字符异或 ×2 |
| JZ-XSS-001 | 11 | 9 | 2 | 误报见 §二 #4、#5（#6 已由 E29 修掉，不再计入） |
| JZ-JSINSEC-001 | 2 | 2 | 0 | `javascript/source/high_unobfuscated.js:523,527`（客户端算令牌） |
| JZ-UPLOAD-001 | 1 | 1 | 0 | `upload/source/low.php:9`：`move_uploaded_file($_FILES[...]['tmp_name'], $target_path)` |
| JZ-REDIR-001 | 3 | 3 | 0 | `open_redirect/source/{low,medium,high}.php` |
| JZ-WEAKID-001 | 5 | 5 | 0 | `md5(uniqid())`、`$_SESSION['last_session_id']++`、`time()` |
| JZ-CSRF-001 | 6 | 6 | 0 | 六个 `<form method=post>` 无 token |
| **DVWA 小计** | **58** | **55** | **3** | |
| flask（`src/flask/json/tag.py:188`） | 1 | 0 | 1 | 误报见 §二 #7 |
| requests | 0 | 0 | 0 | 4 条全在 `library_feature` / `test` 语境 ⇒ 另计，不进分母 |
| **合计** | **59** | **55** | **4** | |

## 二、误报逐条（在册 4 条 + 已修 3 条留档；为什么是误报、归哪一类、怎么处置）

| # | 位置 | 形态 | 为什么是误报 | 归类 | 处置 |
|---|---|---|---|---|---|
| 1 | `vulnerabilities/bac/index.php:58` | 把一个**被 include 的文件**里用 `intval` 处理过的 id 拼进查询 | `intval` 确实把 `$id` 变成整数 ⇒ SQL 注入不成立 | **已修**（待能力升级，E31 清掉） ； ⚠️ **E28 的归因只对了一半**：净化点确实在另一个文件，但**近因其实是****多行 SQL 串的列别名被当成了变量读取**（`bac/index.php:51` 的 `"SELECT l.id, …` 没有闭合引号 ⇒ 逐行分析时整行被当代码 ⇒ `l.id` 里的 `id` 被当成"读了 $id"）⇒ 污点流进了一个**根本不含该值**的查询 | ✅ **E31 已修**（两处都修）：① **跨行字符串字面量折叠到首行**（⇒ 列别名不是读取、插值是读取）；② **include-scope 通道认被 include 文件里的无条件净化点**（`intval` 过的值不再被当污点带走）⇒ 这条误报消失，且**真阳性一条没丢**（A/B 逐条：DVWA 只少这一条、新增 0 条） |
| 2 | `vulnerabilities/csrf/source/high.php:44` | 更新语句里拼的口令字段，第 38 行先过了 `mysqli_real_escape_string` | 转义在**引号内**有效 ⇒ 不是注入；但引擎不知道这个 sink 的 SQL 上下文 | **已修**（待能力升级，E30 清掉） | ✅ **E30 已修**：引擎加 `sql_quote_context()`（按"输出串"重建引号状态）⇒ 转义类净化点**按引号内/引号外两档**生效（引号内 ⇒ 有效、不报；引号外 ⇒ 无效、仍报）⇒ 这条误报消失，且**真阳性一条没丢**（A/B 逐条：DVWA 只少这一条、新增 0 条；`sqli_blind/source/medium.php:15` 引号外 ⇒ **仍报**） |
| 3 | `vulnerabilities/sqli/test.php:4` | 口令字段被赋成一个**带四个星号**的字符串 | 那是**占位/脱敏值**，不是真凭据（⚠️ 原文里那一行长得像赋值真口令 ⇒ 本文档**不复制**它，免得被密钥扫描当泄露） | **静态消不掉** | 属**能力边界**：要认出"占位值"必须看**字符串内容**，而规则跑在**掩码桶**（字面量被剥）上 ⇒ 登记为边界 |
| 4 | `vulnerabilities/csp/source/high.js:9` | 把 JSONP 响应里的 answer 字段写进 innerHTML | `obj` 来自 `source/jsonp.php`，而那个 php 里 `$outp = array("answer" => "15")` 是**常量** ⇒ 插进 DOM 的永远是 `"15"` | **静态消不掉** | 属**能力边界**：要判"服务端返回什么"得读服务端代码 ⇒ 边界 |
| 5 | `vulnerabilities/csp/source/impossible.js:9` | 同上（修复档） | `source/jsonp_impossible.php` 里 `$outp` 同样是常量 ⇒ 修复档里同样插常量 | **静态消不掉** | 同上 |
| 6 | `vulnerabilities/xss_d/index.php:54` | 用 `document.write` 写一段**纯常量** HTML | 纯**字符串常量** ⇒ 不是 XSS（上一行 `:53` 才是带变量的那行） | **已修**（静态可修，E29 清零） | ✅ **E29 已修**：`document.write` 分支加**负向先行**（掩码形态 `document.write('');` ⇒ 负向要容忍 `''` 与 `;` 之间的 `)`）⇒ 这条误报消失，且**真阳性一条没丢**（A/B 逐条：DVWA 只少这一条、新增 0 条） |
| 7 | flask `src/flask/json/tag.py:188` | JSON 反序列化标签里把**已反序列化的对象**包回 Markup | 这是 `TagMarkup.to_python()`：JSON 反序列化时把**已反序列化的对象**包回 Markup（`check()` 要求对象已有 `__html__`）⇒ 不是"把不可信数据当 HTML" | **静态消不掉** | 属**能力边界**：`Markup(user_input)`（真阳性）与 `Markup(value)`（本条）**形态完全相同** ⇒ 静态不可区分 |

## 三、三类误报的口径（E28 建立，E29 把「静态可修」清零，E30/E31 把「待能力升级」也清零）

| 类别 | 条数 | 含义 | 能不能靠改规则消掉 |
|---|---|---|---|
| **静态可修** | 0 | E29 已把最后一条修掉 ⇒ 这一类**归零** | — |
| **待能力升级** | 0 | E31 把最后一条（净化点**跨文件**作用域）也修掉了 ⇒ 这一类**归零** | — |
| **静态消不掉（能力边界型）** | 4 | 形态与真阳性**完全相同**，静态无从区分 | **不能**（属"能力边界"，已写进 `references/audit-rule-authoring.md` 的边界表） |

⇒ **所以"硬误报"这个笼统的分子应当拆开**：
E20 说"硬误报 8 条"，其中 5 条是规则过宽（E25/E26 已修）、
1 条**根本不在结论区**（`csrf/test_credentials.php:22` 在**测试语境**⇒ 另计），
**真正在结论区且当时判错的只有 2 条**；E28 逐条重判后又挖出 **E20 没抓到的 4 条**（#1、#3、#4、#7）。

⇒ **现行口径**：
- 结论区 **59** 条＝真阳性 **55** + 误报 **4**
- 误报 4 条＝静态可修 **0** + 待能力升级 **0** + 静态消不掉 **4**
- ⇒ **"静态可修的硬误报"= 0 / 59 = 0%**（E20 的 8/69 ≈ 11.6% ⇒ 降了 100%）
- ⇒ **未判定 = 0**（E20 留下的一切皆有结论）

## 四、其余发现逐条判定（E32）—— 口径收口

§一–§三 判的是**结论区**（正式代码语境）。这一节判**剩下的全部发现**，
让「全部产出」口径也能说死 —— 此前只能说结论区口径（"硬误报 0/59"），
「全部产出误报率」一直是**未判定**（三份文档曾各写一个数：20 / 12 / "59 条里有 20 条"，
互相矛盾且都没说清口径 ⇒ E32 一律以**实测**为准）。

> **可复算**：`python evals/audit-fixtures/dvwa_coverage.py --json <DVWA扫描.json> --same-dir`
> 跑出下面 4.1 的同一张清单（E32 新增）。

### 4.1「同目录路过」16 条（规则类别 ≠ 该模块声明的漏洞类别）

| # | 位置 | 规则 | 该模块声明 | 判定 | 依据 |
|---|---|---|---|---|---|
| 1 | `vulnerabilities/api/src/HealthController.php:88` | JZ-CMDI-001 | api 声明 CSRF/XSS | **真阳性** | `exec("ping -c 4 " . $target)`，而 `$target` 来自 `file_get_contents('php://input')` 解出的 JSON ⇒ 外部输入直接进 shell ⇒ **命令注入**（这是个 API 控制器，不是 DVWA 的 api 漏洞模块 ⇒ 同目录、不同类） |
| 2 | `vulnerabilities/view_help.php:20` | JZ-CODE-001 | 不在模块目录里 | **真阳性** | `eval('?>' . file_get_contents("vulnerabilities/{$id}/help/help.php"))`，`$id = $_GET['id']` ⇒ 路径可穿越 ⇒ 读到的文件内容被 `eval` ⇒ **LFI→RCE** |
| 3 | `vulnerabilities/view_help.php:22` | JZ-CODE-001 | 不在模块目录里 | **真阳性** | 同上（`help.{$locale}.php` 那一支） |
| 4 | `vulnerabilities/bac/source/medium.php:22` | JZ-SQLI-003 | bac 声明越权 | **真阳性** | medium 档 `$id = $_GET['user_id']` **没转义**就拼进 `WHERE user_id = '$id'` ⇒ **SQL 注入成立** |
| 5 | `vulnerabilities/bac/source/medium.php:29` | JZ-SQLI-003 | bac 声明越权 | **真阳性** | 同上（`WHERE user_id = '$id'` 那一支） |
| 6 | `vulnerabilities/bac/source/medium.php:73` | JZ-SQLI-003 | bac 声明越权 | **真阳性** | 同上（`{$target_id}` 进 INSERT 那一支） |
| 7 | `vulnerabilities/sqli/test.php:4` | JZ-SECRET-001 | sqli 声明 SQLi | **误报** | 口令字段被赋成一个**带四个星号**的字符串 ⇒ **占位/脱敏值**，不是真凭据 （⚠️ 原文那一行长得像赋值真口令 ⇒ 本文档**不复制**它，免得被密钥扫描当泄露）⇒ 与 §二 #3 同一处（已判，不重复计入分子） |
| 8 | `vulnerabilities/authbypass/authbypass.js:43` | JZ-XSS-001 | authbypass 声明越权/SQLi | **真阳性** | 值来自 `JSON.parse(xhr.responseText)`（服务端用户表）⇒ 而 DVWA 的 authbypass 模块**允许改任意用户的 first_name/surname** ⇒ 名字可控 ⇒ 渲染进 `innerHTML` ⇒ **存储型 XSS** |
| 9 | `vulnerabilities/authbypass/authbypass.js:45` | JZ-XSS-001 | 同上 | **真阳性** | 同上（`first_name` 那一支） |
| 10 | `vulnerabilities/authbypass/authbypass.js:47` | JZ-XSS-001 | 同上 | **真阳性** | 同上（`surname` 那一支） |
| 11 | `vulnerabilities/authbypass/authbypass.js:49` | JZ-XSS-001 | 同上 | **真阳性** | 同上（`user_id` 进 onclick 那一支） |
| 12 | `vulnerabilities/cryptography/source/low.php:56` | JZ-CSRF-001 | cryptography 声明弱加密 | **真阳性** | `<form method='post'>` 周边 6 行内**没有** `csrf`/`csrfToken`/`X-Requested-With` 之类 ⇒ DVWA 低安全档确实**缺 CSRF 防护**（形式上成立，只是不是该模块的"声明漏洞"） |
| 13 | `vulnerabilities/cryptography/source/low.php:102` | JZ-CSRF-001 | 同上 | **真阳性** | 同上（`ecb` 那一支） |
| 14 | `vulnerabilities/cryptography/source/medium.php:100` | JZ-CSRF-001 | 同上 | **真阳性** | 同上 |
| 15 | `vulnerabilities/javascript/index.php:97` | JZ-CSRF-001 | javascript 声明 JS/客户端 | **真阳性** | 表单里的 `name="token"` 是**客户端 puzzle 的 token**、不是 CSRF token（规则只认 `csrf`/`csrfToken`/…）⇒ 服务端确实没有 CSRF 校验 ⇒ 形式上成立（影响极低） |
| 16 | `vulnerabilities/weak_id/index.php:42` | JZ-CSRF-001 | weak_id 声明弱会话/弱加密 | **真阳性** | `<form method="post">` 周边无 CSRF token ⇒ 形式上成立（影响是"被迫重新生成会话 id"） |

⇒ **16 条 = 真阳性 15 + 误报 1**（那 1 条与 §二 #3 是同一处，已判过，不重复计入分子）。

### 4.2「另计语境」16 条（测试 / 库 / CLI 语境 ⇒ 不是检测错，也不进结论区）

| 来源 | 条数 | 语境 | 判定依据 |
|---|---|---|---|
| flask `tests/*`（test_basic 6、test_json_tag 1、test_templating 1、test_reqctx 1） | 9 | test | **不是检测错**：测试夹具里的写法（如 `Markup(value)`、`innerHTML` 赋值）在测试语境无害 ⇒ 完整保留在 findings/JSON/SARIF 里，不进结论区 |
| flask `src/flask/cli.py:252,653,959` | 3 | console | **不是检测错**：CLI 的错误提示里回显输入 ⇒ 只在命令行语境出现 |
| requests `src/requests/adapters.py:99,344` | 2 | library_feature | **不是检测错**：库的默认行为（TLS 校验开关）由调用方决定 ⇒ 库语境不算漏洞 |
| requests `tests/test_requests.py:2949,3055` | 2 | test | **不是检测错** |

⚠️ **这个数从 17 变成了 16**：E28 那轮记的是"另计 17 条（DVWA 1 + flask 12 + requests 4）"，
其中 DVWA 那条（`csrf/test_credentials.php:22`）**已被 E30 修掉**（转义在引号内 ⇒ 不是注入）⇒ 变成 16。

### 4.3 口径收口（E32 的产出）

| 口径 | 条数 | 拆开 |
|---|---|---|
| 同目录路过 | 16 | 真阳性 15 + 误报 1 |
| 另计语境 | 16 | flask 12 + requests 4 |
| 全部产出 | 75 | 真阳性 55 + 误报 4 + 另计 16 |

⇒ **全部产出 75 条**（DVWA 58 + flask 13 + requests 4）＝ 真阳性 **55** ＋ 误报 **4** ＋ 另计 **16**
⇒ **「全部产出」口径的误报率 = 4 / 75 ≈ 5.3%**（此前只能说结论区口径）
⇒ 结论区口径：误报 4/59 ≈ 6.8%，但**「静态可修的硬误报」= 0 / 59 = 0%**
（那 4 条全是「静态消不掉（能力边界型）」⇒ 见 §三）
⇒ **两套口径现在都有完整判定，"未判定"在本项目已清零。**

⚠️ **口径纪律**：分子分母必须同范围；每改一次规则/引擎，**这张表要重判**（判定表不是永久有效的）。
