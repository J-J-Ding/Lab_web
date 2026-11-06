# 日常运维

- `docker compose ps`、`curl --fail http://127.0.0.1:8000/api/health/`检查DB真实连接；`/api/ready/`额外检查私有卷可读写，响应不含密钥或连接串。AI故障不使官网全站不可用。
- 日志只有服务端生成request_id、方法、状态、耗时，不记路径查询/正文/Authorization/Cookie；Docker日志10MiB×3轮换。
- worker任务以lease/heartbeat_at持久化，超时CALLING不自动重发，UNKNOWN保留费用。检查队列积压、UNKNOWN、预算和容器健康；告警渠道未配置，不擅自发通知。
- AI与媒体清理默认命令dry-run，确认后--apply；AI worker周期执行其专属保留策略。Session `clearsessions`、认证bucket清理按服务器命令和维护窗口安排。不要重复安装多个破坏性清理定时器。
- 磁盘建议70%预警/85%处置；本次df仅记录实际值，不伪称已安装报警。证书到期/备份失败通知需配置接收人后授权测试。
- 身份异常先禁用具体账号并失效其Session；错误公开先unpublish/收紧隐私，再检查审计，不能清空数据库或抹历史。

当前服务器已启用运行/迁移角色分离。后续迁移使用 `docker compose --profile maintenance run --rm migrate`，不要给backend运行角色补超级权限来迁移。ClamAV接入是可选、显式启用且失败拒绝；真实引擎未配时维持结构检查说明，不报告“已杀毒”。worker健康探针除PID外检查/tmp心跳更新（最大300秒），无端口；长期无更新需排查任务/DB/供应商。
