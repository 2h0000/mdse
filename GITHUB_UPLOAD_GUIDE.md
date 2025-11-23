# GitHub 上传指南

## 准备工作已完成 ✅

- ✅ 创建了 `.gitignore` 文件
- ✅ 清理了数据库文件 (`data/*.db`)
- ✅ 清理了测试缓存 (`.hypothesis/`, `.pytest_cache/`)
- ✅ 清理了 Python 缓存 (`__pycache__/`)
- ✅ 创建了 `LICENSE` 文件
- ✅ `.env` 文件已被 `.gitignore` 排除

## 上传步骤

### 1. 初始化 Git 仓库

```bash
git init
git add .
git commit -m "Initial commit: Markdown Search Engine"
```

### 2. 在 GitHub 创建仓库

1. 访问 https://github.com/new
2. 填写仓库名称（如：`markdown-search-engine`）
3. 选择 Public 或 Private
4. **不要**勾选 "Initialize with README"（我们已经有了）
5. 点击 "Create repository"

### 3. 关联远程仓库并推送

```bash
# 替换 YOUR_USERNAME 和 YOUR_REPO_NAME
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
git branch -M main
git push -u origin main
```

## 使用者安装指南

其他人克隆你的仓库后，需要执行：

```bash
# 1. 克隆仓库
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
cd YOUR_REPO_NAME

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境
copy .env.example .env
# 编辑 .env 文件，设置 MD_ROOT 路径

# 4. 初始化数据库
python scripts/init_db.py

# 5. 启动服务
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

## 注意事项

- `.env` 文件不会被上传（包含在 `.gitignore` 中）
- 数据库文件不会被上传（每个用户需要自己初始化）
- 测试缓存不会被上传
- 使用者需要 Python 3.9+ 环境

## 后续更新

当你修改代码后，使用以下命令更新：

```bash
git add .
git commit -m "描述你的修改"
git push
```

---

完成后可以删除此文件：`del GITHUB_UPLOAD_GUIDE.md`
