# Markdown 搜索引擎部署指南

本文档提供详细的生产环境部署说明。

## 目录

- [系统要求](#系统要求)
- [部署方案](#部署方案)
- [Systemd 部署（推荐）](#systemd-部署推荐)
- [Docker 部署](#docker-部署)
- [Nginx 配置](#nginx-配置)
- [性能优化](#性能优化)
- [监控和维护](#监控和维护)
- [故障排查](#故障排查)

## 系统要求

### 硬件要求

- **CPU**: 1 核心（最低），2+ 核心（推荐）
- **内存**: 512MB（最低），1GB+（推荐）
- **磁盘**: 100MB（应用） + 索引大小（约为文档大小的 1.5 倍）

### 软件要求

- **操作系统**: Linux（Ubuntu 20.04+, CentOS 7+, Debian 10+）
- **Python**: 3.9 或更高版本
- **SQLite**: 3.9.0 或更高版本（支持 FTS5）
- **Nginx**: 1.18+ （可选，用于反向代理）

### 网络要求

- 开放端口 80（HTTP）和 443（HTTPS）
- 如果使用防火墙，需要配置相应规则

## 部署方案

### 方案对比

| 方案 | 优点 | 缺点 | 适用场景 |
|------|------|------|----------|
| Systemd | 简单、原生、易管理 | 需要手动配置 | 单服务器部署 |
| Docker | 隔离、可移植、易扩展 | 需要 Docker 环境 | 容器化环境 |
| Gunicorn | 成熟、稳定 | 配置较复杂 | 高并发场景 |

## Systemd 部署（推荐）

### 步骤 1: 准备环境

```bash
# 更新系统
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
# 或
sudo yum update -y  # CentOS/RHEL

# 安装 Python 和必要工具
sudo apt install python3 python3-venv python3-pip git -y  # Ubuntu/Debian
# 或
sudo yum install python3 python3-pip git -y  # CentOS/RHEL

# 创建专用用户（安全最佳实践）
sudo useradd -r -m -s /bin/bash mdsearch
```

### 步骤 2: 安装应用

```bash
# 创建应用目录
sudo mkdir -p /opt/md-search
cd /opt/md-search

# 方式 1: 从 Git 克隆
sudo git clone https://github.com/your-repo/md-search.git .

# 方式 2: 手动上传
# 使用 scp 或 rsync 上传文件到服务器

# 创建虚拟环境
sudo python3 -m venv venv

# 激活虚拟环境并安装依赖
sudo venv/bin/pip install --upgrade pip
sudo venv/bin/pip install -r requirements.txt

# 设置权限
sudo chown -R mdsearch:mdsearch /opt/md-search
```

### 步骤 3: 配置应用

```bash
# 复制配置文件
sudo cp .env.example .env

# 编辑配置
sudo nano .env
```

配置示例：

```bash
# Markdown 文档根目录
MD_ROOT=/var/www/markdown-docs

# 数据库路径
DB_PATH=/opt/md-search/data/md_search.db

# 日志级别
LOG_LEVEL=INFO

# 搜索配置
MAX_SEARCH_LIMIT=100
SNIPPET_TOKENS=10
```

```bash
# 创建数据目录
sudo mkdir -p /opt/md-search/data
sudo mkdir -p /var/log/md-search

# 设置权限
sudo chown -R mdsearch:mdsearch /opt/md-search/data
sudo chown -R mdsearch:mdsearch /var/log/md-search
sudo chmod 600 .env
```

### 步骤 4: 初始化数据库

```bash
# 切换到 mdsearch 用户
sudo -u mdsearch /opt/md-search/venv/bin/python /opt/md-search/scripts/init_db.py
```

### 步骤 5: 配置 Systemd 服务

```bash
# 复制服务文件
sudo cp /opt/md-search/deployment/md-search.service /etc/systemd/system/

# 重新加载 systemd
sudo systemctl daemon-reload

# 启用服务（开机自启）
sudo systemctl enable md-search

# 启动服务
sudo systemctl start md-search

# 检查状态
sudo systemctl status md-search
```

### 步骤 6: 验证部署

```bash
# 检查服务是否运行
curl http://localhost:8000/

# 测试搜索功能
curl "http://localhost:8000/search?q=test"

# 查看日志
sudo journalctl -u md-search -f
```

## Docker 部署

### 步骤 1: 安装 Docker

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# 安装 Docker Compose
sudo apt install docker-compose -y

# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER
```

### 步骤 2: 准备配置

```bash
# 进入项目目录
cd /path/to/md-search

# 编辑 docker-compose.yml
nano deployment/docker-compose.yml
```

修改以下配置：

```yaml
volumes:
  # 修改为你的 Markdown 文档目录
  - /your/markdown/docs:/docs:ro
```

### 步骤 3: 构建和启动

```bash
# 构建镜像
docker-compose -f deployment/docker-compose.yml build

# 启动服务
docker-compose -f deployment/docker-compose.yml up -d

# 查看日志
docker-compose -f deployment/docker-compose.yml logs -f

# 检查状态
docker-compose -f deployment/docker-compose.yml ps
```

### 步骤 4: 初始化数据库

```bash
# 进入容器
docker exec -it md-search bash

# 运行初始化脚本
python scripts/init_db.py

# 退出容器
exit
```

### Docker 管理命令

```bash
# 停止服务
docker-compose -f deployment/docker-compose.yml stop

# 重启服务
docker-compose -f deployment/docker-compose.yml restart

# 查看日志
docker-compose -f deployment/docker-compose.yml logs --tail=100

# 更新应用
docker-compose -f deployment/docker-compose.yml pull
docker-compose -f deployment/docker-compose.yml up -d

# 清理
docker-compose -f deployment/docker-compose.yml down
```

## Nginx 配置

### 步骤 1: 安装 Nginx

```bash
# Ubuntu/Debian
sudo apt install nginx -y

# CentOS/RHEL
sudo yum install nginx -y

# 启动 Nginx
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 步骤 2: 配置站点

```bash
# 复制配置文件
sudo cp /opt/md-search/deployment/nginx.conf /etc/nginx/sites-available/md-search

# 编辑配置，修改域名
sudo nano /etc/nginx/sites-available/md-search

# 创建符号链接
sudo ln -s /etc/nginx/sites-available/md-search /etc/nginx/sites-enabled/

# 测试配置
sudo nginx -t

# 重载 Nginx
sudo systemctl reload nginx
```

### 步骤 3: 配置 SSL（推荐）

使用 Let's Encrypt 免费 SSL 证书：

```bash
# 安装 Certbot
sudo apt install certbot python3-certbot-nginx -y  # Ubuntu/Debian
# 或
sudo yum install certbot python3-certbot-nginx -y  # CentOS/RHEL

# 获取证书并自动配置 Nginx
sudo certbot --nginx -d your-domain.com -d www.your-domain.com

# 测试自动续期
sudo certbot renew --dry-run
```

### 步骤 4: 配置防火墙

```bash
# UFW (Ubuntu/Debian)
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

## 性能优化

### 1. Worker 进程配置

根据 CPU 核心数调整 worker 数量：

```bash
# 查看 CPU 核心数
nproc

# 推荐配置: workers = (2 × CPU 核心数) + 1
# 例如 2 核 CPU: --workers 5
```

编辑 systemd 服务文件：

```ini
ExecStart=/opt/md-search/venv/bin/uvicorn app.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 5 \
    --log-level info
```

### 2. 数据库优化

```bash
# 定期优化数据库
sqlite3 /opt/md-search/data/md_search.db "PRAGMA optimize;"
sqlite3 /opt/md-search/data/md_search.db "VACUUM;"

# 添加到 crontab（每周执行）
0 3 * * 0 sqlite3 /opt/md-search/data/md_search.db "PRAGMA optimize; VACUUM;"
```

### 3. 文件监控优化

对于大量文件，增加 inotify 限制：

```bash
# 检查当前限制
cat /proc/sys/fs/inotify/max_user_watches

# 增加限制
echo "fs.inotify.max_user_watches=524288" | sudo tee -a /etc/sysctl.conf
sudo sysctl -p
```

### 4. Nginx 缓存配置

在 Nginx 配置中添加缓存：

```nginx
# 在 http 块中添加
proxy_cache_path /var/cache/nginx/md-search levels=1:2 keys_zone=md_search_cache:10m max_size=100m inactive=60m;

# 在 location / 块中添加
proxy_cache md_search_cache;
proxy_cache_valid 200 5m;
proxy_cache_key "$scheme$request_method$host$request_uri";
add_header X-Cache-Status $upstream_cache_status;
```

## 监控和维护

### 健康检查

创建健康检查脚本：

```bash
#!/bin/bash
# /opt/md-search/scripts/health_check.sh

ENDPOINT="http://localhost:8000/"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" $ENDPOINT)

if [ $RESPONSE -eq 200 ]; then
    echo "OK: Service is healthy"
    exit 0
else
    echo "ERROR: Service returned $RESPONSE"
    exit 1
fi
```

添加到监控系统或 cron：

```bash
# 每 5 分钟检查一次
*/5 * * * * /opt/md-search/scripts/health_check.sh || systemctl restart md-search
```

### 日志管理

配置 logrotate：

```bash
# 创建配置文件
sudo nano /etc/logrotate.d/md-search
```

内容：

```
/var/log/md-search/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 mdsearch mdsearch
    sharedscripts
    postrotate
        systemctl reload md-search > /dev/null 2>&1 || true
    endscript
}
```

### 备份策略

创建备份脚本：

```bash
#!/bin/bash
# /opt/md-search/scripts/backup.sh

BACKUP_DIR="/backup/md-search"
DATE=$(date +%Y%m%d_%H%M%S)
DB_PATH="/opt/md-search/data/md_search.db"

mkdir -p $BACKUP_DIR

# 备份数据库
cp $DB_PATH $BACKUP_DIR/md_search_$DATE.db

# 压缩备份
gzip $BACKUP_DIR/md_search_$DATE.db

# 删除 30 天前的备份
find $BACKUP_DIR -name "*.db.gz" -mtime +30 -delete

echo "Backup completed: md_search_$DATE.db.gz"
```

添加到 crontab：

```bash
# 每天凌晨 2 点备份
0 2 * * * /opt/md-search/scripts/backup.sh
```

### 更新应用

```bash
# 1. 备份当前版本
sudo cp -r /opt/md-search /opt/md-search.backup

# 2. 停止服务
sudo systemctl stop md-search

# 3. 更新代码
cd /opt/md-search
sudo -u mdsearch git pull
# 或手动上传新文件

# 4. 更新依赖
sudo -u mdsearch venv/bin/pip install -r requirements.txt

# 5. 运行数据库迁移（如有）
# sudo -u mdsearch venv/bin/python scripts/migrate.py

# 6. 启动服务
sudo systemctl start md-search

# 7. 验证
curl http://localhost:8000/

# 8. 如果有问题，回滚
# sudo systemctl stop md-search
# sudo rm -rf /opt/md-search
# sudo mv /opt/md-search.backup /opt/md-search
# sudo systemctl start md-search
```

## 故障排查

### 服务无法启动

**症状**: `systemctl start md-search` 失败

**排查步骤**:

```bash
# 1. 查看详细日志
sudo journalctl -u md-search -n 100 --no-pager

# 2. 检查配置文件
cat /opt/md-search/.env

# 3. 验证路径存在
ls -la /opt/md-search/data
ls -la $MD_ROOT

# 4. 检查权限
sudo -u mdsearch ls /opt/md-search/data

# 5. 手动启动测试
sudo -u mdsearch /opt/md-search/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
```

**常见原因**:
- 配置文件中的路径不存在
- 权限不足
- 端口被占用
- Python 依赖缺失

### 搜索结果为空

**症状**: 搜索返回 0 结果

**排查步骤**:

```bash
# 1. 检查索引是否存在
sqlite3 /opt/md-search/data/md_search.db "SELECT COUNT(*) FROM docs;"

# 2. 检查文档目录
ls -la $MD_ROOT

# 3. 查看索引日志
sudo journalctl -u md-search | grep -i index

# 4. 手动重建索引
sudo -u mdsearch /opt/md-search/venv/bin/python /opt/md-search/scripts/init_db.py

# 5. 测试搜索
curl "http://localhost:8000/search?q=test"
```

### 文件监控不工作

**症状**: 新建或修改文件后搜索不到

**排查步骤**:

```bash
# 1. 检查 inotify 限制
cat /proc/sys/fs/inotify/max_user_watches

# 2. 查看监听器日志
sudo journalctl -u md-search | grep -i watch

# 3. 检查文件权限
ls -la $MD_ROOT

# 4. 手动触发索引
# 重启服务会重新扫描所有文件
sudo systemctl restart md-search
```

### 性能问题

**症状**: 响应缓慢

**排查步骤**:

```bash
# 1. 检查系统资源
top
free -h
df -h

# 2. 检查数据库大小
ls -lh /opt/md-search/data/md_search.db

# 3. 优化数据库
sqlite3 /opt/md-search/data/md_search.db "PRAGMA optimize; VACUUM;"

# 4. 检查 worker 数量
ps aux | grep uvicorn

# 5. 查看慢查询日志
sudo journalctl -u md-search | grep -i slow
```

### Nginx 502 错误

**症状**: Nginx 返回 502 Bad Gateway

**排查步骤**:

```bash
# 1. 检查后端服务是否运行
sudo systemctl status md-search
curl http://localhost:8000/

# 2. 检查 Nginx 错误日志
sudo tail -f /var/log/nginx/md-search-error.log

# 3. 检查 Nginx 配置
sudo nginx -t

# 4. 检查防火墙
sudo iptables -L
sudo ufw status

# 5. 检查 SELinux（CentOS/RHEL）
sudo getenforce
sudo setenforce 0  # 临时禁用测试
```

## 安全加固

### 1. 文件权限

```bash
# 应用目录
sudo chown -R mdsearch:mdsearch /opt/md-search
sudo chmod 755 /opt/md-search

# 配置文件
sudo chmod 600 /opt/md-search/.env

# 数据库文件
sudo chmod 600 /opt/md-search/data/md_search.db

# 日志目录
sudo chmod 755 /var/log/md-search
```

### 2. 防火墙配置

```bash
# UFW (Ubuntu/Debian)
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow ssh
sudo ufw allow 'Nginx Full'
sudo ufw enable

# Firewalld (CentOS/RHEL)
sudo firewall-cmd --set-default-zone=public
sudo firewall-cmd --permanent --add-service=ssh
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### 3. 限制访问（可选）

在 Nginx 配置中添加 IP 白名单：

```nginx
location / {
    allow 192.168.1.0/24;
    allow 10.0.0.0/8;
    deny all;
    
    proxy_pass http://127.0.0.1:8000;
}
```

### 4. 速率限制

在 Nginx 配置中添加速率限制：

```nginx
# 在 http 块中
limit_req_zone $binary_remote_addr zone=search_limit:10m rate=10r/s;

# 在 location / 块中
limit_req zone=search_limit burst=20 nodelay;
```

### 5. 定期更新

```bash
# 更新系统包
sudo apt update && sudo apt upgrade -y  # Ubuntu/Debian
sudo yum update -y  # CentOS/RHEL

# 更新 Python 依赖
cd /opt/md-search
sudo -u mdsearch venv/bin/pip list --outdated
sudo -u mdsearch venv/bin/pip install --upgrade package-name
```

## 支持和帮助

如果遇到问题：

1. 查看日志：`sudo journalctl -u md-search -f`
2. 检查 GitHub Issues
3. 查阅项目文档
4. 联系技术支持

## 附录

### 常用命令速查

```bash
# 服务管理
sudo systemctl start md-search      # 启动服务
sudo systemctl stop md-search       # 停止服务
sudo systemctl restart md-search    # 重启服务
sudo systemctl status md-search     # 查看状态
sudo systemctl enable md-search     # 开机自启
sudo systemctl disable md-search    # 禁用自启

# 日志查看
sudo journalctl -u md-search -f     # 实时日志
sudo journalctl -u md-search -n 100 # 最近 100 行
sudo journalctl -u md-search --since "1 hour ago"  # 最近 1 小时

# 数据库操作
sqlite3 /opt/md-search/data/md_search.db "SELECT COUNT(*) FROM docs;"
sqlite3 /opt/md-search/data/md_search.db "PRAGMA optimize; VACUUM;"

# Nginx 操作
sudo nginx -t                       # 测试配置
sudo systemctl reload nginx         # 重载配置
sudo systemctl restart nginx        # 重启 Nginx
```

### 性能基准

在标准配置下（2 核 CPU, 2GB RAM）：

- **索引速度**: 约 100-200 文件/秒
- **搜索延迟**: <100ms（10000 文档）
- **并发支持**: 100+ 并发请求
- **内存占用**: 基线 ~50MB + 索引大小

### 扩展阅读

- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [SQLite FTS5 文档](https://www.sqlite.org/fts5.html)
- [Nginx 文档](https://nginx.org/en/docs/)
- [Systemd 文档](https://www.freedesktop.org/software/systemd/man/)
