# 生产安全验收状态

已实现：Session/CSRF/角色校验、私有文件/受控下载、版本与审核审计、AI授权与预算、未知计费处理、公开门禁、CSV公式防护、服务端request_id脱敏日志、默认不信任代理、恢复项目隔离与备份摘要、无数据库宿主公网端口。

必须补齐后才能宣布V9整体验收：真实域名HTTPS/证书续期、Secure Cookie与严格Origin实测、完整病毒扫描服务（当前为受限结构校验，不等同杀毒）、加密异机备份与保留调度、告警渠道、Firefox/WebKit及真实Android/iOS设备、规定10分钟30读/5写并发负载与实际SLA。

禁止以模板/占位/单次探针代替真实验证。真实环境缺配置时保持“未验证”，不将check --deploy警告静默过滤。密钥/.env真实值不入Git；真实文件和数据库备份在0700私有目录；用户原Dockerfile/README不覆盖。

文件库提供可选本机ClamAV UNIX socket INSTREAM接入（FILE_SCAN_REQUIRED=True），要求扫描原始及清洗字节，服务不可用/检出风险一律拒绝入可用资产库。当前服务器未安装/运行完整签名引擎，默认结构检查模式不冒称杀毒完成。启用前需配置受控socket挂载与引擎签名更新，独立隔离文件样本实测；不可把mock病毒响应当真实杀毒验收。

生产运行角色分权已实际完成：backend/worker使用非superuser/CREATEDB/CREATEROLE角色，maintenance服务保留管理员；隔离SQL写入验证通过，运行backend读/健康/就绪验证通过。

当前可信代理网段与实际系统 Nginx 覆盖转发头已验证，伪造客户端头未改变限流归属；公开 HTTP 不作为真实账号 HTTPS 验收。
