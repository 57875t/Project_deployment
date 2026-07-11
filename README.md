# QR Desk Market Lab

QR Desk 是一个只读量化工作台。当前主线是 **v0.8 K-line Core**：先把K线真实性、交易时段、未完成K线、涨跌幅和质量审计做正确，再继续扩展界面。

## 当前架构

```text
QR Desk HTML
    ↓ HTTPS
QR Desk Cloud Market Gateway
    ↓
Licensed market-data providers
```

浏览器不保存供应商密钥，网关没有账户、持仓、余额或下单接口。

## v0.8 已实现

- OHLCV 数值和结构校验；
- 重复时间戳处理；
- 未来时间记录拒绝；
- 供应商本地时间按交易所时区解析；
- XNYS、XHKG、XSHG 交易日历；
- 周末、节假日、午休和常规交易时段识别；
- 盘外K线剔除；
- 正在形成的分钟线和日线剔除；
- 5分钟到15分钟严格聚合，不完整桶不输出；
- 隔夜、休市和午休不误报为数据缺口；
- 昨收涨跌与上一根K线涨跌分离；
- `syntheticBars: 0` 数据真实性边界；
- 质量计数器、市场状态、来源与时效字段。

## 关键目录

```text
qrdesk_gateway/       云端行情网关
frontend/             QR Desk HTML 工作区
skills/               项目 Skills
workflows/            六阶段交付工作流
docs/                 审计与验收记录
tests/                K线与交易时段测试
```

## 本地验证

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
pip install pytest
pytest -q
```

当前确定性测试结果：`9 passed`。

## 状态

当前结论为 **PARTIAL PASS / Draft**。

还不能宣称 LIVE PASS，直到完成：

- 授权供应商真实数据接入；
- US、HK、CN 时间戳约定实测；
- 早收市和特殊交易日样本；
- 复权与公司行动对账；
- 双源交叉校验；
- HTML 接入 `marketSession`、`quality`、`change` 和 `barChange`。

详细审计见：`docs/V0.8_KLINE_CORE_AUDIT.md`。
