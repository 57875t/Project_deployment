# QR Desk · Experimental Market Lab

这是我们当前工作的统一仓库，目标是把 **QR Desk 前端、云端真实行情网关、审计工作流、Skills、部署配置和验收记录** 放在同一个地方管理。

## 当前主线

- 浏览器前端：QR Desk v0.7.1
- 后端：只读云端行情网关
- 数据源：Massive（美股）与 EODHD（港股/A股延迟或历史数据）
- 部署目标：Railway / Render 等 HTTPS 云服务
- 安全边界：不读取券商账户、不下单、不把 API Key 写进 HTML、不用模拟数据冒充真实行情

## 仓库结构

```text
app.py                         # Railway/云平台入口
requirements.txt              # Python 依赖
railway.toml                   # Railway 部署配置
qrdesk_gateway/               # 云端行情网关代码
frontend/                     # QR Desk HTML 前端
workflows/                    # Preview → Execute → Nitpick → Review → Acceptance
skills/                       # 项目专用 Skills
issues/                       # 任务、差距和验收清单
archive/                      # 历史方案与旧版本
```

## Railway 部署

1. 在 Railway 选择仓库 `57875t/Project_deployment`。
2. 分支选择 `agent/qrdesk-workspace-restructure`。
3. Railway 会读取根目录的 `railway.toml`。
4. 在 Variables 中配置：
   - `MASSIVE_API_KEY`
   - `EODHD_API_TOKEN`
   - `QRDESK_ALLOWED_ORIGINS`
5. 部署后访问 `/v1/market/health`。

## 当前状态

仓库整理已启动；真实行情端到端验收仍需云端 API Key 和部署后的 HTTPS 地址。任何未通过的环节都会明确标记为 `OPEN` 或 `NEEDS FIX`，不会伪装成完成。
