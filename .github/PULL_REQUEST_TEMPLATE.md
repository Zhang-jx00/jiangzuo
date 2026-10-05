## 改了什么

<!-- 一句话功能视角 + 关键文件清单 -->

## 为什么这么改

<!-- 方案要点；重要取舍请附 ADR -->

## 怎么验证的（必须有证据，不接受"已自测"）

- [ ] `python scripts/validate_skill.py .` → 0 错误（贴输出）
- [ ] `python scripts/preflight.py --all --strict` → 退出码 0
- [ ] 改了 SKILL.md description → 已重跑 evals/trigger-tests.md 全部用例
- [ ] 改了脚本 → 附实际运行输出摘要
- [ ] 改了纪律/分册规则 → 已在 evals/red-tests.md 补充或复跑对应场景

## 剩余风险与未竟事项

<!-- 没做的边界、已知小问题；无则写"无" -->
