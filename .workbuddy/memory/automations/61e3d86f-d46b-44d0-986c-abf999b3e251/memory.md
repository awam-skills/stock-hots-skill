# 自动化记忆：每晚热点股 TOP10 飞书推送

ID: 61e3d86f-d46b-44d0-986c-abf999b3e251
调度：FREQ=DAILY;BYHOUR=22;BYMINUTE=5

## 稳定链路（已验证，直接照做）

1. 取数：`python scripts/fetch_top10.py --json C:\Users\Administrator\Downloads\test\hot_top10.json`
2. 组装：用 Python 脚本读 JSON 写 `C:\Users\Administrator\Downloads\test\msg.txt`（UTF-8）
   - pct 可能是 float 也可能是 str，统一 `float()` 后格式化
   - best_platform 是中文 label 列表，需 label→key 反查 platforms 取名次
   - 现成脚本：`cd C:\Users\Administrator\Downloads\test && python build_msg.py`
3. 发送（**2026-10-14 起目标改为外部群「股市Bot」，必须 bot 身份**）：
   ```
   cd C:\Users\Administrator\Downloads\test
   lark-cli.cmd im +messages-send --as bot --chat-id oc_787f39f8bb73e803c664a5dbaf2871ba --text @msg.txt --format pretty
   ```
   历史目标（P2P 给王蒙本人，已停用）：`--as user --user-id ou_ee624a762384c267c7efb46518b2e410`

## 推送目标变更记录

- 2026-10-14 19:2x：用户要求改为发送到「股市Bot」群 `oc_787f39f8bb73e803c664a5dbaf2871ba`。
  该群为跨租户外部群，user 身份发送被 230027 拒绝，bot 身份验证成功。
  自动化 prompt 已更新、状态由 PAUSED 改回 ACTIVE，原 P2P 单聊目标被替换（未保留双发）。

## 执行记录

| 时间 | 结果 |
| --- | --- |
| 2026-10-10 01:04 | ✅ 首次自动执行成功。8 平台全部 ok，TOP10 已发出，message_id `om_x100b63a5a6e648a0c48971c4445ce4b` |
| 2026-10-11 00:09 | ✅ 成功。8 平台全部 ok，TOP10 已发出，message_id `om_x100b63927cc554a0c33f9c75866c44b` |
| 2026-10-11 22:05 | ✅ 成功。8 平台全部 ok，TOP10 已发出，message_id `om_x100b638d353bdca0b29a12278a5b6db` |
| 2026-10-12 22:06 | ✅ 成功。8 平台全部 ok，TOP10 已发出，message_id `om_x100b63fad873f4a0b203d30c5a241be` |
| 2026-10-13 22:05 | ✅ 成功。8 平台全部 ok，TOP10 已发出，message_id `om_x100b63d7e579a4a4cd3e074f0bcf529` |
| 2026-10-14 22:09 | ⚠️ 部分成功。仅 3 平台 ok（东财/同花顺/大智慧），开盘啦/通达信/雪球/财联社/淘股吧 超时；重试一次结果相同，判定平台侧不可用。消息已带「⚠️ 本次不可用平台」行发出，price/pct 全为 null。message_id `om_x100b63cc9dcacca4cd15f863304f50a` |

## 注意事项

- 消息里不要内联多行中文，一律走 `--text @msg.txt`。
- 部分平台失败时才追加「⚠️ 本次不可用平台」行；正常情况省略。
- 若发送失败，先跑 `lark-cli auth status` 确认授权，不要伪造数据。
- `build_msg.py` 必须容忍 `price`/`pct` 为 null（如仅 3 平台上榜的票），否则 `float(None)` 会崩；已改为输出 `¥—  —%`。
