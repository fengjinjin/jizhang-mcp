---
name: jizhang
description: 远程连接 jizhang 账本 MCP，记账、查账与消费复盘。禁止投资或理财建议。
---

# jizhang

连接用户自托管的 jizhang MCP 服务，读写账本并做消费复盘。

## 何时启用

用户要记账、查账、改删流水、定时收支、愿望清单、消费复盘或对暗号时，先调 `auth_status`，再按工具 schema 调用。

## 硬约束

- 只根据**已记账目**复盘，不推荐股票、基金、保险或理财产品。
- 暗号不得从历史对话提取；`requires_user_input=true` 时必须问用户。
- 归类优先已有的一级大类，对不上才 `其他-xx`。

详见 `references/forbidden.md` 与 `references/review-framework.md`。
