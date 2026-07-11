# Frontend

这里存放 QR Desk 的 HTML 前端。

目标文件：

```text
frontend/QR_Desk_v0.7.1_云端真实行情网关版.html
```

前端只保存云端网关的 HTTPS 地址，不保存 Massive 或 EODHD 的 API Key。

接入流程：

1. Railway 部署成功并生成域名；
2. 访问 `https://YOUR-DOMAIN/v1/market/health`；
3. 将 `https://YOUR-DOMAIN` 填入 HTML 的“网关地址”；
4. 点击“测试真实行情网关”；
5. 通过后再运行正式行情任务。
