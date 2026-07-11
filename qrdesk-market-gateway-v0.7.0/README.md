# QR Desk v0.7.0 · Moomoo OpenD 只读真实行情网关

这是一层**只读**本地网关，把 Moomoo OpenD 的行情接口转换成 QR Desk HTML 已经约定的 JSON：

- `GET /v1/market/health`
- `GET /v1/market/bundle`

网关只创建 `OpenQuoteContext`，不会创建交易上下文，不读取交易密码，也不下单。

## 1. 前置条件

1. 安装并启动 Moomoo OpenD，默认监听 `127.0.0.1:11111`。
2. 登录 OpenD，并确认账号拥有目标市场的行情权限。
3. 安装 Python 3.10+。

## 2. 安装

```bash
python -m venv .venv
```

Windows：

```powershell
.venv\Scripts\activate
pip install -r requirements.txt
```

macOS / Linux：

```bash
. .venv/bin/activate
pip install -r requirements.txt
```

## 3. 启动

Windows 双击：

```text
start_gateway.bat
```

或命令行：

```bash
python -m uvicorn qrdesk_gateway.app:app --host 127.0.0.1 --port 8787
```

然后在 QR Desk 的“真实行情网关”里填写：

```text
http://127.0.0.1:8787
```

先点击“测试真实行情网关”，再刷新行情。

## 4. 验证

```bash
curl http://127.0.0.1:8787/v1/market/health
```

```bash
curl "http://127.0.0.1:8787/v1/market/bundle?instrument=US.AAPL&symbol=AAPL&range=1d&interval=5m&extended=false"
```

只有返回 `ok: true`，且 `provenance.provider` 为 `moomoo OpenD` 时，前端才应把数据视为券商真实行情。

## 5. 数据策略

- K 线：`request_history_kline`
- 行情快照：`get_market_snapshot`
- OpenD 状态：`get_global_state`
- 复权：前复权（`AuType.QFQ`）
- 盘中未闭合 K 线：从 K 线序列剔除，最新价格仍由 quote 快照展示
- 跨域：默认仅建议网关绑定 `127.0.0.1`；远程部署必须使用 HTTPS，并把 `QRDESK_ALLOWED_ORIGINS` 改成精确域名

## 6. 当前边界

- 行情是否实时、是否延迟，取决于账号权限、市场和 OpenD 返回；网关不会伪造“实时”。
- 部分基本面字段在某些市场/标的可能为空，网关保持 `null`，不使用模拟值填补。
- 本版本是轮询式只读行情网关，不包含下单、持仓或账户接口。

## 7. 测试

```bash
pytest -q
```
