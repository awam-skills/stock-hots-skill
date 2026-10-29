# stock-hots 项目长期记忆

## 定时推送链路（每晚热点股）

标准三步：

1. 取数：`python scripts/fetch_top10.py --json C:\Users\Administrator\Downloads\test\hot_top10.json`
   （python 走 PATH 即可，managed 3.14.3；输出含 top10[] / platform_top{} / snapshot_time / platform_status）
2. 组装消息：每支列 排名、名称、代码、最新价、涨跌幅、最佳平台及名次；末尾标 snapshot_time + 8 平台来源。
3. 发送（**2026-10-14 起目标 = 外部群「股市Bot」，必须 bot 身份**）：

```bash
cd C:\Users\Administrator\Downloads\test
lark-cli.cmd im +messages-send --as bot \
  --chat-id oc_787f39f8bb73e803c664a5dbaf2871ba \
  --text @msg.txt --format pretty
```
（历史目标 P2P 给王蒙本人 `--as user --user-id ou_ee624a762384c267c7efb46518b2e410` 已停用。）

## 群聊推送（2026-10-14 验证）

- 目标群：`oc_787f39f8bb73e803c664a5dbaf2871ba` = 「股市Bot」**外部**私密群（external=true，2 用户 + 3 bot，王蒙是群管理员/owner 为另一 open_id）。
- **以 user 身份（王蒙）向该群发送 → 230027 拒绝**（跨租户外部群，租户策略限制；token 有效、scope 含 im:message.send_as_user，排除授权问题）。
- **以 bot 身份（`--as bot`）发送 → 成功**，已验证群内收到（api_boy，2026-10-14 19:22）。
- bot 读该群消息同样 230027；user 身份可读该群消息。
- 结论：要往这个外部群推送，一律 `--as bot`。

## 环境事实

- `lark-cli` 已装在 `C:\Users\Administrator\.local\npm-global\`；配置目录 `~/.lark-cli`。
- 飞书连接器已 connected，user identity openId = `ou_ee624a762384c267c7efb46518b2e410`。
- **IM 工具（`im_list_conversations` 等）被主机策略阻断**，不可用 → 走 lark-cli。
- **OpenClaw 网关不可达**（tail7a6991.ts.net:18789/18684 无响应，本机 18790/8684 均 502），`~/.openclaw` 不存在 → 目前不能靠它发文件。
- **东财 `push2.eastmoney.com` 所有子域被本环境代理 TLS 重协商阻断**（curl/urllib 均 RemoteDisconnected；`datacenter-web.eastmoney.com` 正常可用）。东财行业板块排名(`m:90+t:2`)、个股资金流分钟级等 push2 接口在此环境取不到；且 push2 只返最新交易日，历史日期需另寻 datacenter 报表。
- **行业板块替代数据源（已验证可用）= 新浪财经 `https://money.finance.sina.com.cn/q/view/newSinaHy.php`**：返回 `var S_Finance_bankuai_sinaindustry = {…}`，含 49 个行业，字段 `名称,?,成分股数,?,?,涨跌幅%,成交量,成交额(元),领涨股代码,领涨股涨跌幅%,领涨股价格,领涨股换手,领涨股名称`（逗号分隔，无 `;` 结尾，需用「首个 `{`→末尾 `}`」截取再正则 `"([^"]+)":"([^"]*)"`）。可取到涨跌幅排名/领涨行业/领跌行业/领涨股/成分股数/成交额，但**无上涨下跌家数**。
- managed python(`3.14.3`) 无 requests/pandas，且 `pip install` 被沙箱 SIGTERM → 抓取改用标准库 `urllib` + 自建节流，无需第三方包。
- 已装连接器：tdx-connector（bound 但 disabled）、feishu（connected）。

## 口径说明

综合名次 = 上榜平台名次平均值（越小越热），候选须 ≥3 平台上榜，同分则上榜平台数多者优先。
这是公开算法，与 WzSLinker 聚合页私有加权名次存在序位差异，属正常。
