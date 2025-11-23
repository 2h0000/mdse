# 安全加固文档

本文档描述了 Markdown 搜索引擎实施的安全措施和最佳实践。

## 安全措施概览

系统实施了以下安全加固措施：

1. **查询字符串长度限制** - 防止过长查询导致的性能问题
2. **路径遍历防护** - 防止访问文档根目录外的文件
3. **CORS 策略配置** - 控制跨域资源共享
4. **数据库文件权限** - 限制数据库文件访问权限

## 1. 查询字符串长度限制

### 目的
防止恶意用户提交超长查询字符串，导致：
- 数据库查询性能下降
- 内存占用过高
- 潜在的拒绝服务攻击

### 实现
- 最大查询长度：**500 字符**
- 验证位置：API 端点 `/search`
- 超长查询返回：`422 Unprocessable Entity`

### 示例
```python
# 有效查询
GET /search?q=markdown

# 无效查询（超过 500 字符）
GET /search?q=aaaa...（501+ 字符）
# 返回: 422 - "Query string too long. Maximum length is 500 characters."
```

### 配置
查询长度限制在 `app/security.py` 中定义：
```python
MAX_QUERY_LENGTH = 500  # 可根据需要调整
```

## 2. 路径遍历防护

### 目的
防止攻击者通过路径遍历访问系统中的敏感文件，例如：
- `/etc/passwd`
- `../../../config/secrets.yml`
- 其他系统文件

### 实现
- 所有文件路径必须在配置的 `MD_ROOT` 目录内
- 使用 `Path.resolve()` 解析真实路径
- 使用 `Path.relative_to()` 验证路径在允许范围内
- 最大路径长度：**1000 字符**

### 验证逻辑
```python
def validate_path_traversal(file_path: str) -> Path:
    """验证文件路径，防止路径遍历攻击"""
    md_root = Path(settings.md_root).resolve()
    full_path = (md_root / file_path).resolve()
    
    # 检查路径是否在允许的根目录内
    try:
        full_path.relative_to(md_root)
    except ValueError:
        raise SecurityError("Access denied: Path is outside the allowed directory")
    
    return full_path
```

### 示例
```python
# 有效路径
validate_path_traversal("docs/readme.md")  # ✓ 通过

# 无效路径
validate_path_traversal("../../../etc/passwd")  # ✗ 拒绝
validate_path_traversal("/etc/passwd")  # ✗ 拒绝
```

### 应用位置
- 文档检索：`search_service.render_document_html()`
- 文件索引：`indexer.index_file()`

## 3. CORS 策略配置

### 目的
控制哪些域名可以访问 API，防止：
- 跨站请求伪造（CSRF）
- 未授权的跨域访问
- 数据泄露

### 默认配置
```python
# 开发环境（默认）
CORS_ORIGINS=*  # 允许所有源

# 生产环境（推荐）
CORS_ORIGINS=https://example.com,https://app.example.com
```

### 实现细节
```python
# app/main.py
cors_origins = os.getenv("CORS_ORIGINS", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # 只允许必要的方法
    allow_headers=["Content-Type", "Authorization"],
    max_age=600  # 预检请求缓存 10 分钟
)
```

### 配置方法

#### 方法 1: 环境变量
```bash
export CORS_ORIGINS="https://example.com,https://app.example.com"
```

#### 方法 2: .env 文件
```bash
# .env
CORS_ORIGINS=https://example.com,https://app.example.com
```

### 生产环境建议
1. **明确指定允许的源**，不要使用 `*`
2. **使用 HTTPS** 协议
3. **限制允许的 HTTP 方法**（已实现：GET, POST, OPTIONS）
4. **限制允许的请求头**（已实现：Content-Type, Authorization）

## 4. 数据库文件权限

### 目的
保护数据库文件不被未授权访问或修改：
- 防止其他用户读取数据库内容
- 防止数据库被篡改
- 符合最小权限原则

### 实现
- **Unix/Linux 系统**：自动设置权限为 `600`（仅所有者可读写）
- **Windows 系统**：跳过 Unix 权限设置（使用 NTFS 权限）

### 权限说明
```bash
# Unix 权限 600 表示：
# - 所有者：读写（rw-）
# - 组：无权限（---）
# - 其他：无权限（---）
-rw------- 1 user user 1024 Nov 23 10:00 md_search.db
```

### 自动设置
系统启动时自动检查和设置数据库文件权限：
```python
# app/main.py - startup event
set_database_permissions()  # 设置权限
check_database_permissions()  # 验证权限
```

### 手动设置（如需要）
```bash
# Unix/Linux
chmod 600 data/md_search.db

# 验证权限
ls -l data/md_search.db
```

## 5. 错误信息清理

### 目的
防止错误信息泄露敏感信息：
- 内部文件路径
- 数据库结构
- 系统配置

### 实现
```python
def sanitize_error_message(error_message: str, is_production: bool = True) -> str:
    """清理错误信息，避免泄露敏感信息"""
    if not is_production:
        return error_message  # 开发环境返回完整信息
    
    # 生产环境返回通用错误信息
    sensitive_keywords = [
        str(settings.md_root),
        str(settings.db_path),
        "sqlite", "database", "traceback"
    ]
    
    for keyword in sensitive_keywords:
        if keyword.lower() in error_message.lower():
            return "An internal error occurred. Please contact the administrator."
    
    return error_message
```

## 6. 输入验证

### 已实施的验证
1. **查询字符串**
   - 不能为空或仅包含空白字符
   - 长度不超过 500 字符

2. **分页参数**
   - `limit`: 1-100 之间
   - `offset`: 非负整数

3. **文档 ID**
   - 必须是正整数

4. **文件路径**
   - 必须在 MD_ROOT 目录内
   - 长度不超过 1000 字符

## 7. 安全最佳实践

### 部署建议

#### 1. 使用 HTTPS
```nginx
# nginx.conf
server {
    listen 443 ssl;
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://127.0.0.1:8000;
    }
}
```

#### 2. 配置防火墙
```bash
# 只允许必要的端口
ufw allow 80/tcp
ufw allow 443/tcp
ufw enable
```

#### 3. 限制文件系统访问
```bash
# 设置 MD_ROOT 目录权限
chmod 755 /path/to/markdown/docs
chown -R appuser:appuser /path/to/markdown/docs

# 设置数据库目录权限
chmod 700 /path/to/data
chown appuser:appuser /path/to/data
```

#### 4. 使用专用用户运行应用
```bash
# 创建专用用户
useradd -r -s /bin/false mdsearch

# 使用 systemd 以专用用户运行
[Service]
User=mdsearch
Group=mdsearch
```

#### 5. 启用速率限制（可选）
```python
# 使用 slowapi 限制请求频率
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.get("/search")
@limiter.limit("10/minute")
async def search(...):
    ...
```

### 监控和日志

#### 1. 监控安全事件
系统会记录以下安全相关事件：
- 路径遍历尝试
- 超长查询字符串
- 无效的 API 请求
- 数据库权限问题

#### 2. 日志级别
```bash
# 生产环境建议使用 INFO 或 WARNING
LOG_LEVEL=INFO
```

#### 3. 日志审计
定期检查日志中的安全警告：
```bash
# 查找路径遍历尝试
grep "Path traversal attempt" /var/log/mdsearch.log

# 查找超长查询
grep "Query string too long" /var/log/mdsearch.log
```

## 8. 安全检查清单

部署前请确认：

- [ ] 已配置具体的 CORS_ORIGINS（不使用 `*`）
- [ ] 数据库文件权限设置为 600
- [ ] MD_ROOT 目录权限正确设置
- [ ] 使用 HTTPS 协议
- [ ] 应用以非 root 用户运行
- [ ] 防火墙规则已配置
- [ ] 日志级别设置为 INFO 或 WARNING
- [ ] 定期备份数据库文件
- [ ] 监控系统日志中的安全警告

## 9. 已知限制

1. **SQLite 并发限制**
   - SQLite 支持多读单写
   - 高并发写入可能导致锁等待
   - 建议：使用连接池或考虑 PostgreSQL

2. **文件系统监控**
   - 依赖 watchdog 库
   - 大量文件变化可能导致延迟
   - 建议：定期全量重建索引

3. **中文分词**
   - 使用字符级分词
   - 不支持智能分词
   - 建议：考虑集成 jieba 等分词库

## 10. 报告安全问题

如果发现安全漏洞，请：
1. **不要**公开披露
2. 发送邮件至安全团队
3. 提供详细的复现步骤
4. 等待安全团队响应

## 11. 更新日志

- **2024-11-23**: 初始版本
  - 实现查询长度限制
  - 实现路径遍历防护
  - 配置 CORS 策略
  - 设置数据库文件权限
