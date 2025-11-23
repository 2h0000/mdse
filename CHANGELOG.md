# 更新日志

本文档记录了 MDSE-Markdown 搜索引擎的所有重要变更。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

## [0.2.0] - 2025-11-23

### 新增

- **智能优先级高亮系统**
  - 实现三级优先级高亮算法（完整查询 > 词组片段 > 单个字符）
  - 优先高亮完整关键词，提供更清晰的搜索结果
  - 支持中英文混合搜索高亮
  
- **文档预览功能**
  - 点击搜索结果即可在右侧面板预览文档
  - 自动滚动到第一个高亮位置
  - 支持 ESC 键关闭预览
  
- **视觉效果优化**
  - 黄色高亮背景，带脉冲动画
  - 优化的预览面板设计
  - 响应式布局支持

- **功能文档**
  - 添加 `docs/features/HIGHLIGHT_FEATURE.md` - 高亮功能说明
  - 添加 `docs/features/SMART_HIGHLIGHT.md` - 智能高亮详解
  - 添加 `docs/features/HIGHLIGHT_EXAMPLES.md` - 高亮示例

- **测试文件**
  - 添加 `tests/test_highlight.py` - 高亮功能测试
  - 添加 `tests/test_smart_highlight.py` - 智能高亮测试

### 改进

- **搜索体验**
  - 改进中文关键词提取逻辑
  - 优化高亮匹配算法，减少误报
  - 提升搜索结果的可读性

- **前端交互**
  - 优化 JavaScript 代码结构
  - 改进错误处理和加载状态显示
  - 增强键盘快捷键支持

- **代码质量**
  - 重构高亮逻辑，提高可维护性
  - 添加详细的代码注释
  - 改进错误处理机制

### 修复

- 修复中文搜索时过度高亮的问题
- 修复文档预览时关键词不高亮的问题
- 修复重复高亮标签的问题

### 技术细节

**后端变更**：
- `app/api.py`: 实现智能优先级高亮算法
- `app/search_service.py`: 优化中文分词处理

**前端变更**：
- `app/static/script.js`: 添加文档预览和自动滚动功能
- `app/static/style.css`: 优化高亮样式和动画效果

**文档变更**：
- `README.md`: 添加新功能说明和使用指南
- 新增功能文档目录 `docs/features/`

## [0.1.0] - 2025-11-XX

### 新增

- **核心搜索功能**
  - 基于 SQLite FTS5 的全文搜索
  - BM25 排名算法
  - 搜索结果高亮片段生成
  - 分页支持

- **文档索引**
  - Markdown 文件自动扫描和索引
  - Frontmatter 解析支持
  - 文档摘要生成
  - 文件修改时间记录

- **实时监控**
  - 基于 watchdog 的文件监控
  - 自动增量更新索引
  - 支持文件新增、修改、删除

- **中文支持**
  - 中文字符级分词
  - 中文关键词搜索
  - 中英文混合搜索

- **Web 界面**
  - 简洁的搜索界面
  - 搜索结果列表展示
  - 响应式设计

- **RESTful API**
  - `/search` - 搜索端点
  - `/docs/{doc_id}` - 文档详情端点
  - API 文档（Swagger UI）

- **配置管理**
  - 基于 .env 的配置
  - 配置验证和错误提示
  - 灵活的参数配置

- **安全特性**
  - 路径遍历防护
  - 查询字符串长度限制
  - CORS 策略配置
  - 数据库文件权限控制

- **部署支持**
  - Docker 部署配置
  - Systemd 服务配置
  - Nginx 反向代理配置
  - 生产环境部署指南

### 文档

- `README.md` - 项目说明和快速开始
- `docs/SECURITY.md` - 安全文档
- `deployment/DEPLOYMENT.md` - 部署指南
- `GITHUB_UPLOAD_GUIDE.md` - GitHub 上传指南

### 测试

- 基础功能测试套件
- 配置验证测试
- 搜索功能测试
- 索引器测试

---

## 版本说明

### 版本号格式

版本号格式：`主版本号.次版本号.修订号`

- **主版本号**：不兼容的 API 修改
- **次版本号**：向下兼容的功能性新增
- **修订号**：向下兼容的问题修正

### 变更类型

- **新增**：新功能
- **改进**：对现有功能的改进
- **修复**：问题修复
- **废弃**：即将移除的功能
- **移除**：已移除的功能
- **安全**：安全相关的修复

---

## 贡献指南

如果你想为项目做出贡献，请：

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 开启 Pull Request

---

## 联系方式

如有问题或建议，请通过以下方式联系：

- 提交 Issue
- 发起 Discussion
- 提交 Pull Request

---

**注意**：本项目遵循 [MIT 许可证](LICENSE)。
