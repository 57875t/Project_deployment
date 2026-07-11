# Frontend

这里存放 QR Desk 的 HTML 前端。

## v0.8 Phase 3 目标文件

```text
frontend/QR_Desk_v0.8.0_K线真值接线版.html
```

当前完整 HTML 已完成本地交付与浏览器验收；由于文件体积较大，尚未通过 GitHub 连接器写入本分支。仓库内以 `docs/V0.8_PHASE3_HTML_WIRING_AUDIT.md` 记录接线合同、门禁和验收结果。

## 数据真实性合同

- 前端只保存云端网关的 HTTPS 地址，不保存 Massive 或 EODHD API Key；
- `quality.verdict = FAIL` 时禁止绘制 K 线；
- 真实响应必须明确 `provenance.syntheticBars = 0`；
- Provider 失败时只显示不可用或最后可信真实快照，不自动生成模拟 K 线；
- 校准模拟只能由用户手动选择并明确标注；
- `quote.lastPrice` 在当前网关中表示最后已完成 K 线收盘价，不是独立逐笔报价；
- `provider-start-assumed` 在真实样本核验前只能显示 DEGRADED，不能显示 LIVE PASS。

## 后续接入流程

1. 部署 v0.8 网关并生成 HTTPS 域名；
2. 访问 `https://YOUR-DOMAIN/v1/market/health`；
3. 将 `https://YOUR-DOMAIN` 填入 HTML 的“网关地址”；
4. 点击“测试真实行情网关”；
5. 运行 US、HK、CN 代表标的；
6. 对照授权 Provider 或参考终端核验时间戳、涨跌幅和最后已完成 K 线；
7. 只有真实权限、延迟和参考对账通过后，才允许标记 LIVE PASS。
