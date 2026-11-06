# V6 ECS 部署和回退

**下面命令尚未在生产执行。** 本次已按用户授权直接调整当前项目静态页面；正式 backend/db 容器未替换、生产库未迁移、Nginx 未修改，main 未合并。旧后端不提供 V6 公共 API，新页面会显示未公开/服务错误；部署前不能宣称完整动态站点已上线。

## 1. 确认提交、构建独立镜像

先批准部署的具体提交和维护窗口，保留用户 Dockerfile/README，不能 reset/clean 覆盖。以下只在获准后执行：

```bash
cd /opt/Lab_web
git status --short
git log -1 --oneline
umask 077
V6_RELEASE=$(git rev-parse --short HEAD)
V6_BACKUP=/opt/lab-web-backups/v6-$(date +%Y%m%d-%H%M%S)
mkdir -p "$V6_BACKUP"
chmod 700 "$V6_BACKUP"
cat > "$V6_BACKUP/release.yml" <<EOF_RELEASE
services:
  backend:
    image: lab-web-backend:v6-$V6_RELEASE
EOF_RELEASE
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" config --quiet
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" build backend
```

独立候选镜像不覆盖运行的旧标签；本地 Dockerfile 有用户设置的依赖镜像源，未纳入 V6 提交。构建缓存 parent snapshot 故障只对候选 build 加 --no-cache，不重启 Docker、不 prune。不要输出含密钥的完整 compose config。

## 2. 停写、数据库和媒体配套备份

```bash
sudo docker compose ps > "$V6_BACKUP/containers.txt"
sudo docker inspect lab-web-backend-1 --format '{{.Image}}' > "$V6_BACKUP/old-image.txt"
sudo docker inspect lab-web-backend-1 --format '{{range .Mounts}}{{println .Destination .Name}}{{end}}' > "$V6_BACKUP/mounts.txt"
git rev-parse HEAD > "$V6_BACKUP/source-commit.txt"
tar -cf "$V6_BACKUP/frontend-and-inventory.tar" frontend legacy_samples/inventory.json legacy_samples/manifest.json
sudo docker compose stop backend
sudo docker compose exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > "$V6_BACKUP/database.dump"
test -s "$V6_BACKUP/database.dump"
sudo docker compose exec -T db pg_restore --list < "$V6_BACKUP/database.dump" > "$V6_BACKUP/database-manifest.txt"
```

若 mounts.txt 已有 `/app/private_media`，必须备份对应的实际卷并记录文件清单后再迁移。设置下方实际卷名，确认属于正式项目后执行；首次从 V2 部署没有媒体卷则记录“升级前无媒体卷”：

```bash
# V6_MEDIA_VOLUME=已核对的正式私有卷名
# sudo docker run --rm --user 0 --entrypoint tar --mount "type=volume,src=$V6_MEDIA_VOLUME,dst=/media,readonly" "lab-web-backend:v6-$V6_RELEASE" -C /media -cf - . > "$V6_BACKUP/private-media.tar"
# tar -tf "$V6_BACKUP/private-media.tar" > "$V6_BACKUP/private-media-manifest.txt"
chmod 600 "$V6_BACKUP"/*
```

备份或校验失败时停止升级。真实文件/数据库备份只存服务器私有目录，不提交仓库。

## 3. 迁移、启动及现有 Nginx

```bash
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps backend python manage.py check
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps backend python manage.py makemigrations --check --dry-run
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --plan
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --noinput
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps backend python manage.py migrate --check
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" up -d --no-deps --no-build --wait backend
```

从旧 V2 环境升级会先补齐 V4/V5，再执行 V6 三个迁移。V6 增加三张导入/映射表及资产用途/删除请求字段；旧已批准且当前可公开的清洁头像转 PUBLIC，证明仍保持 PRIVATE，所有公共下载继续检查当前门禁。

仅在既有 `/etc/nginx/sites-available/default` 的 `/api/` location 内将 `client_max_body_size` 设为 `21m`，保留原 root、proxy_pass 和所有代理头，不启动第二个 Nginx。先备份配置，再 `sudo nginx -t`，成功后 `sudo systemctl reload nginx`。数据库仍不暴露宿主机端口，后端仍仅通过 127.0.0.1:8000 提供服务。

## 4. 更新后验证、示例导入和回退

```bash
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" ps
curl --fail http://127.0.0.1:8000/api/health/
curl --fail 'http://127.0.0.1:8000/api/public/content/?kind=PAPER&page_size=20'
curl --fail http://127.0.0.1:8000/api/public/members/
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" exec -T backend python manage.py migrate --check
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1;"'
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" logs --tail 80 backend
```

列表为空是未发布资料的正常状态；详细页/旧映射在获批前 404。示例先 dry-run，人工核验后按 [迁移手册](legacy-migration.md) 分批 apply，绝不自动发布。只用测试账号在回环或受控 HTTPS 验证上传、独立审核、三个成员成果/项目 UUID 一致、待审隔离、公开撤下和旧文件直链；不得在无 HTTPS 公网用真实账号测试。逐项对账清单不是仅看总数。

回退使用 old-image.txt 对应旧镜像建立 rollback override，然后以该 override `up -d --no-deps --no-build --wait backend`。关闭不兼容的新入口即可，不要把原始隐私正文或媒体复制回 frontend。保留扩展数据库表、历史与媒体，不反向迁移、不 drop、不对生产执行 down --volumes；数据库/文件恢复必须另行批准并使用匹配备份。后续升级命令持续携带 release override，避免误用默认旧镜像标签。
