# 部署文件说明

本目录包含 Markdown 搜索引擎的部署配置文件和文档。

## 文件列表

### 配置文件

- **`md-search.service`** - Systemd 服务配置文件
  - 用于在 Linux 系统上将应用配置为系统服务
  - 支持开机自启、自动重启等功能
  - 使用方法：复制到 `/etc/systemd/system/` 目录

- **`nginx.conf`** - Nginx 反向代理配置
  - 提供 HTTP/HTTPS 反向代理配置
  - 包含静态文件服务、SSL 配置、负载均衡等示例
  - 使用方法：复制到 `/etc/nginx/sites-available/` 目录

- **`Dockerfile`** - Docker 镜像构建文件
  - 用于构建应用的 Docker 镜像
  - 基于 Python 3.11 slim 镜像
  - 包含健康检查配置

- **`docker-compose.yml`** - Docker Compose 配置
  - 用于快速启动容器化应用
  - 包含卷挂载、环境变量等配置
  - 可选的 Nginx 容器配置

### 文档

- **`DEPLOYMENT.md`** - 详细部署指南
  - 完整的生产环境部署步骤
  - 包含 Systemd、Docker、Nginx 等多种部署方案
  - 性能优化、监控维护、故障排查等内容

- **`README.md`** - 本文件
  - 部署文件的说明和快速参考

## 快速开始

### 方案 1: Systemd 部署（推荐用于 Linux 服务器）

```bash
# 1. 复制服务文件
sudo cp md-search.service /etc/systemd/system/

# 2. 重载 systemd
sudo systemctl daemon-reload

# 3. 启动服务
sudo systemctl start md-search
sudo systemctl enable md-search

# 4. 配置 Nginx（可选）
sudo cp nginx.conf /etc/nginx/sites-available/md-search
sudo ln -s /etc/nginx/sites-available/md-search /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 方案 2: Docker 部署（推荐用于容器环境）

```bash
# 1. 构建镜像
docker build -f Dockerfile -t md-search:latest ..

# 2. 使用 Docker Compose 启动
docker-compose up -d

# 3. 查看日志
docker-compose logs -f
```

## 配置说明

### Systemd 服务配置

需要修改的关键配置：

```ini
# 工作目录（根据实际安装路径修改）
WorkingDirectory=/opt/md-search

# 环境变量文件
EnvironmentFile=/opt/md-search/.env

# 启动命令中的 workers 数量（根据 CPU 核心数调整）
--workers 4
```

### Nginx 配置

需要修改的关键配置：

```nginx
# 域名
server_name your-domain.com www.your-domain.com;

# 静态文件路径
location /static {
    alias /opt/md-search/app/static;
}

# 后端服务地址（如果不是默认的 127.0.0.1:8000）
proxy_pass http://127.0.0.1:8000;
```

### Docker Compose 配置

需要修改的关键配置：

```yaml
volumes:
  # Markdown 文档目录（修改为实际路径）
  - /path/to/your/markdown/docs:/docs:ro

environment:
  # 文档根目录
  - MD_ROOT=/docs
  # 数据库路径
  - DB_PATH=/app/data/md_search.db
```

## 部署检查清单

部署前请确认：

- [ ] Python 3.9+ 已安装
- [ ] 所有依赖已安装（`pip install -r requirements.txt`）
- [ ] `.env` 配置文件已创建并正确配置
- [ ] Markdown 文档目录存在且可访问
- [ ] 数据目录已创建且有写权限
- [ ] 数据库已初始化（`python scripts/init_db.py`）
- [ ] 防火墙规则已配置（如需要）
- [ ] SSL 证书已配置（如使用 HTTPS）

部署后请验证：

- [ ] 服务正常启动（`systemctl status md-search` 或 `docker ps`）
- [ ] Web 界面可访问（http://localhost:8000）
- [ ] 搜索功能正常工作
- [ ] 文件监控正常工作（创建/修改文件后能搜索到）
- [ ] 日志正常记录
- [ ] 健康检查通过

## 常见问题

### Q: 服务启动失败怎么办？

A: 查看日志排查问题：
```bash
sudo journalctl -u md-search -n 100
```

常见原因：
- 配置文件路径错误
- 权限不足
- 端口被占用
- 依赖缺失

### Q: 如何调整 worker 数量？

A: 编辑 `md-search.service` 文件中的 `--workers` 参数。推荐值：
```
workers = (2 × CPU 核心数) + 1
```

### Q: 如何配置 HTTPS？

A: 使用 Let's Encrypt：
```bash
sudo certbot --nginx -d your-domain.com
```

### Q: 如何备份数据？

A: 备份数据库文件：
```bash
cp /opt/md-search/data/md_search.db /backup/
```

### Q: 如何更新应用？

A: 
```bash
# Systemd 部署
sudo systemctl stop md-search
cd /opt/md-search && git pull
sudo systemctl start md-search

# Docker 部署
docker-compose pull
docker-compose up -d
```

## 性能优化建议

1. **调整 worker 数量**：根据 CPU 核心数配置
2. **启用 Nginx 缓存**：缓存静态文件和搜索结果
3. **优化数据库**：定期运行 `PRAGMA optimize` 和 `VACUUM`
4. **增加 inotify 限制**：对于大量文件的监控
5. **使用 SSD**：提高数据库读写性能

## 安全建议

1. **使用非 root 用户**：创建专用用户运行服务
2. **配置防火墙**：只开放必要端口
3. **启用 HTTPS**：使用 SSL/TLS 加密传输
4. **限制文件权限**：配置文件和数据库设置为 600
5. **定期更新**：保持系统和依赖包最新
6. **配置速率限制**：防止 API 滥用
7. **启用访问日志**：记录所有访问请求

## 监控建议

1. **服务监控**：使用 systemd 或 Docker 健康检查
2. **日志监控**：配置日志轮转和告警
3. **性能监控**：监控 CPU、内存、磁盘使用
4. **可用性监控**：配置外部健康检查
5. **备份监控**：确保备份任务正常执行

## 获取帮助

- 详细部署指南：查看 `DEPLOYMENT.md`
- 项目文档：查看主目录 `README.md`
- 问题反馈：提交 GitHub Issue
- 技术支持：联系项目维护者

## 许可证

与主项目相同（MIT）
