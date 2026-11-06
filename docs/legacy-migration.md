# V6 示例结构调整与迁移手册

用户明确确认现有全部内容为示例，允许调整结构。九个栏目 index 改为统一公共 API 列表；首页/关于页读取固定公开快照；通用 content.html/member.html 展示当前批准版本。旧深层 HTML 是无原正文的兼容壳。原媒体/PDF/README 与正文副本保存在 `legacy_samples/originals/`，位于 frontend 之外，不能通过原 Nginx 根目录访问。原媒体 URL 返回 404，不因新 API 失效回落旧数据。

`legacy_samples/inventory.json` 是逐条原路径、哈希、离线来源和处置清单；`manifest.json` 为虚构候选数据，当前 28 条，包括固定介绍、毕业去向与合成 PNG/PDF。它没有真实账号密码，不自动按姓名绑定成员/作者。导入只是建立候选稿，不代表资料已发布。旧栏目示例目录名可保留，但内容不再依赖目录命名。

## 1. 隔离演练与报告

先运行验收报告中的独立环境命令，不在生产跑 Django test。命令格式：

```bash
python manage.py import_legacy_content --manifest /legacy/manifest.json --source-root /legacy/originals --dry-run --report /app/private_media/import-reports/v6-dry.json
python manage.py import_legacy_content --manifest /legacy/manifest.json --source-root /legacy/originals --apply --batch-id <审核后的新批次UUID> --actor <现有管理账号ID> --report /app/private_media/import-reports/v6-apply.json
python manage.py verify_legacy_import --batch-id <批次UUID>
```

清单版本为 1。每行必填 source、sha256、kind、payload、legacy_paths、public_authorized=true；source 必须在指定来源根目录内、非符号链接、哈希相同。kind=MEMBER 的候选保持未绑定且不公开，可带允许的教育/方向/毕业去向字段；其他 kind 使用现有 typed detail 校验。可选 assets 描述来源/哈希/purpose/MIME，仍须通过上传检查，不接受客户端扫描结论。拒绝未知字段、重复 source、跨条目旧 URL 冲突及接管其他来源映射。

dry-run 不写数据库，执行清单结构、路径、哈希和字段验证；文件解码及数据库标识冲突在 apply 事务再次检查，因此 dry-run 成功不替代实际导入/审核。apply 需要已有且当前有效的管理者和明确 UUID；同批次 manifest 哈希不能变化。报告 0600，含每条 source、sha256、kind、status、target/错误、是否创建。设置或跨条目冲突直接中止；逐条失败写 ERROR，命令非零，成功条目保留，修复后重试，不抹掉失败记录。

重复成功条目不会再建对象；同来源在新批次发生变化会保留旧稿并创建新稿，不覆盖发布快照。已有待审内容或已发布/绑定成员需要人工工作流处理，不自动接管。DOI/ISBN/项目号沿用全局约束；同名不是绑定证据。核验命令检查批次成功记录和映射目标，源文件真实性另对照哈希清单，不用总数代替逐条报告。

## 2. 经批准后的 ECS 操作

本次未执行生产迁移或导入。部署先按 [V6 部署步骤](v6-deployment.md) 建候选镜像、停写和配套备份、迁移、启动、health 验证。镜像只包含 backend，示例来源通过只读挂载，不扩大静态根目录。以下命令使用部署手册创建的 release override：

```bash
sudo docker compose -f docker-compose.yml -f "$V6_BACKUP/release.yml" run --rm --no-deps -v /opt/Lab_web/legacy_samples:/legacy:ro backend python manage.py import_legacy_content --manifest /legacy/manifest.json --source-root /legacy/originals --dry-run --report /app/private_media/import-reports/v6-dry.json
```

私有报告存卷内，不提交 Git。人工检查并决定真实管理者 ID、批次 UUID 后，才执行对应 apply；先试点论文和两位成员，再根据逐条结果扩展。不要在命令中写默认密码，不创建真实账号或绕过审核。

成员候选须显式绑定/认领，由本人核实资料并提交公开授权，再由非编辑者审核；管理者导入的头像不能直接当作本人上传头像，需本人重传或专门审核过的迁移交接。内容候选需补齐贡献者/关联、确认必要署名，由非本次编辑者审批。身份/角色权限仍按 V2/V5；不能给导入成员默认开公开 gate。

## 3. URL 对账、发布和回退

逐条检查 inventory：api-list 是新列表；compatibility-shell 只能查询映射；offline-only 的原 URL 必须 404。再检查清单中每条已批准对象的新 URL、中文/空格编码、成员 alias、图片和允许公开附件。未发布映射 404 是安全状态，不应回退原文件。验证项目、论文及参与成员主页的成果 UUID 一致，待审新版本不改变公共输出。

页面调整已按用户授权写在当前项目；旧后端未更新时界面会显示尚无公开资料或服务错误。生产数据导入、后端部署和 main 合并仍另行授权。回退可恢复兼容后端/关闭入口，但不能将已经收紧隐私的旧正文/媒体复制回静态根目录。保留数据库、导入记录和配套文件；不要批次级联删除或反向迁移。数据库/媒体恢复必须作为明确的数据恢复操作处理。
