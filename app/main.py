"""FastAPI 应用入口

创建和配置 FastAPI 应用实例。
验证需求: 9.5
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from watchdog.observers import Observer

from app.api import router
from app.db import init_db
from app.config import settings
from app.watcher import start_watcher
from app.middleware import ErrorHandlingMiddleware, AccessLoggingMiddleware
from app.security import check_database_permissions, set_database_permissions


# 配置日志
# 验证需求: 10.2 - 配置日志记录（INFO、WARNING、ERROR）
def setup_logging():
    """配置应用日志系统
    
    设置日志格式、级别和处理器。
    """
    # 获取日志级别
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)
    
    # 配置根日志记录器
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            # 控制台处理器
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    # 设置第三方库的日志级别（避免过多日志）
    logging.getLogger("watchdog").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    
    return logging.getLogger(__name__)


logger = setup_logging()


# 全局变量存储 watcher observer
_observer: Optional[Observer] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理
    
    在应用启动时初始化数据库和文件监听器，
    在应用关闭时清理资源。
    
    验证需求: 9.5 - 配置启动和关闭事件
    """
    global _observer
    
    # 启动事件
    logger.info("Starting Markdown Search Engine...")
    
    try:
        # 初始化数据库
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
        
        # 设置数据库文件权限（安全考虑）
        set_database_permissions()
        
        # 检查数据库文件权限
        if not check_database_permissions():
            logger.warning("Database file permissions are not secure")
        
        # 验证 Markdown 根目录存在
        md_root = Path(settings.md_root)
        if not md_root.exists():
            logger.error(f"Markdown root directory does not exist: {md_root}")
            raise ValueError(f"Markdown root directory does not exist: {md_root}")
        
        # 启动文件监听器
        logger.info(f"Starting file watcher on: {md_root}")
        _observer = start_watcher(md_root)
        logger.info("File watcher started successfully")
        
        logger.info("Application startup complete")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise
    
    # 应用运行期间
    yield
    
    # 关闭事件
    logger.info("Shutting down Markdown Search Engine...")
    
    # 停止文件监听器
    if _observer is not None:
        logger.info("Stopping file watcher...")
        _observer.stop()
        _observer.join(timeout=5)
        logger.info("File watcher stopped")
    
    logger.info("Application shutdown complete")


# 创建 FastAPI 应用实例
app = FastAPI(
    title="Markdown Search Engine",
    description="基于 FastAPI 和 SQLite FTS5 的全文搜索系统",
    version="0.1.0",
    lifespan=lifespan
)

# 添加错误处理中间件（验证需求: 10.2）
app.add_middleware(ErrorHandlingMiddleware)

# 添加访问日志中间件（验证需求: 10.2）
app.add_middleware(AccessLoggingMiddleware)

# 配置 CORS（安全考虑）
# 在生产环境中，应该配置具体的允许源而不是使用 "*"
# 可以通过环境变量 CORS_ORIGINS 配置允许的源
import os
cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else ["*"]
cors_origins = [origin.strip() for origin in cors_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # 只允许必要的方法
    allow_headers=["Content-Type", "Authorization"],  # 只允许必要的头
    max_age=600,  # 预检请求缓存时间（秒）
)

# 配置静态文件
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# 配置模板
templates = Jinja2Templates(directory="app/templates")

# 注册 API 路由
app.include_router(router)


# 将 templates 导出供 api.py 使用
app.state.templates = templates
