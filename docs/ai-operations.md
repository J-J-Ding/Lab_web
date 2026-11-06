# V7 AI 运维与费用

默认 AI_ENABLED=False，缺密钥/有效价格配置时拒绝创建任务。Compose明确传环境变量，浏览器永不接触key。worker使用与backend相同镜像，profile=ai，无宿主端口，512MiB/1CPU/64pids，私有媒体卷；启用前先迁移。

```bash
docker compose --profile ai config --quiet
docker compose run --rm --no-deps backend python manage.py migrate --check
docker compose --profile ai up -d --no-deps worker
docker compose exec worker python manage.py cleanup_ai_imports
```

.env只在服务器私有0600配置。AI_PRICE_INPUT_CNY_PER_MILLION、AI_PRICE_OUTPUT_CNY_PER_MILLION、AI_PRICE_EFFECTIVE_DATE必须人工核对官方价并填写（有效30天）；使用高峰/缓存未命中价保守预留。2026-11-06核对官方Flash输入2元/百万、输出8元/百万作为上界，不声称长期固定。官方：[价格](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/)、[接口](https://api-docs.deepseek.com/api/create-chat-completion/)。

每人10次/日、全站100次/日、并发每人1/全站2、默认全站预算10元。数据库锁内先预留，网络/解析不持锁；保守输入字节预算包括提示模板，输出明确max_tokens，关闭thinking和tools。仅明确429且未接受请求时最多2次有限退避；超时/5xx/异常响应一律UNKNOWN，不盲目重发计费请求。连续故障熔断5分钟。模型固定官方HTTPS deepseek-flash，不跳转、不自动换模型。

worker `python manage.py run_ai_worker --once` 可逐任务处理；持续进程每60秒执行到期清理，`cleanup_ai_imports`默认dry-run，`--apply`才删除过期内容/原件。UNKNOWN保留预算等待核对。服务器ROOT经供应商核账后用 `reconcile_ai_usage --actor <ROOT-id> --job <uuid> --input-tokens N --output-tokens N --reason <核对说明>`，只存理由摘要，不重发请求。不要在参数、日志或截图传key。

回退先 AI_ENABLED=False 并重建相关服务，停止新领取；等待在途请求完成，保留未知账本、业务草稿和媒体。真实付费启用不等于本次0.10元虚构测试授权，正式日预算由负责人决定。worker挂掉不使官网健康检查失败；队列和心跳/租约可由运维查账本，不提供公开简历状态。
