"""文件监控服务模块

使用 watchdog 监控文件系统变化并触发索引更新。
验证需求: 3.1, 3.2, 3.3, 3.5
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from app.config import settings
from app.db import get_connection
from app.indexer import index_file, remove_file_from_index


# 配置日志
logger = logging.getLogger(__name__)


class MdEventHandler(FileSystemEventHandler):
    """Markdown 文件事件处理器
    
    监听文件系统事件并自动更新索引。
    
    验证需求: 3.1 - 自动添加新创建的文件到索引
    验证需求: 3.2 - 自动更新修改的文件在索引中的内容
    验证需求: 3.3 - 自动从索引中移除删除的文件
    验证需求: 3.5 - 忽略非 Markdown 文件
    """
    
    def __init__(self):
        """初始化事件处理器"""
        super().__init__()
        self.conn: Optional[sqlite3.Connection] = None
    
    def _is_markdown_file(self, path: str) -> bool:
        """检查文件是否为 Markdown 文件
        
        验证需求: 3.5 - 只处理 .md 文件
        
        Args:
            path: 文件路径
            
        Returns:
            bool: 如果是 .md 文件返回 True
        """
        return path.endswith('.md')
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取或创建数据库连接
        
        Returns:
            sqlite3.Connection: 数据库连接
        """
        if self.conn is None:
            self.conn = get_connection()
        return self.conn
    
    def on_created(self, event: FileSystemEvent) -> None:
        """处理文件创建事件
        
        验证需求: 3.1 - 自动将新文件添加到搜索索引
        
        Args:
            event: 文件系统事件对象
        """
        # 忽略目录事件
        if event.is_directory:
            return
        
        # 过滤非 Markdown 文件 (需求 3.5)
        if not self._is_markdown_file(event.src_path):
            return
        
        try:
            path = Path(event.src_path)
            conn = self._get_connection()
            
            # 索引新文件 (需求 3.1)
            index_file(conn, path)
            logger.info(f"Indexed new file: {path}")
            
        except Exception as e:
            logger.error(f"Failed to index created file {event.src_path}: {e}")
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """处理文件修改事件
        
        验证需求: 3.2 - 自动更新修改的文件在索引中的内容
        
        Args:
            event: 文件系统事件对象
        """
        # 忽略目录事件
        if event.is_directory:
            return
        
        # 过滤非 Markdown 文件 (需求 3.5)
        if not self._is_markdown_file(event.src_path):
            return
        
        try:
            path = Path(event.src_path)
            conn = self._get_connection()
            
            # 更新文件索引 (需求 3.2)
            # index_file 使用 UPSERT，会自动更新现有记录
            index_file(conn, path)
            logger.info(f"Updated index for modified file: {path}")
            
        except Exception as e:
            logger.error(f"Failed to update index for modified file {event.src_path}: {e}")
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """处理文件删除事件
        
        验证需求: 3.3 - 自动从索引中移除删除的文件
        
        Args:
            event: 文件系统事件对象
        """
        # 忽略目录事件
        if event.is_directory:
            return
        
        # 过滤非 Markdown 文件 (需求 3.5)
        if not self._is_markdown_file(event.src_path):
            return
        
        try:
            path = Path(event.src_path)
            conn = self._get_connection()
            
            # 从索引中删除文件 (需求 3.3)
            remove_file_from_index(conn, path)
            logger.info(f"Removed deleted file from index: {path}")
            
        except Exception as e:
            logger.error(f"Failed to remove deleted file from index {event.src_path}: {e}")


def start_watcher(root: Path) -> Observer:
    """启动文件监听器
    
    创建并启动 watchdog Observer 监控指定目录。
    
    Args:
        root: 要监控的根目录
        
    Returns:
        Observer: watchdog Observer 实例
        
    Raises:
        ValueError: 如果根目录不存在
    """
    root = Path(root)
    
    # 验证目录存在
    if not root.exists():
        raise ValueError(f"Watch directory does not exist: {root}")
    
    if not root.is_dir():
        raise ValueError(f"Watch path is not a directory: {root}")
    
    # 创建事件处理器
    event_handler = MdEventHandler()
    
    # 创建 Observer
    observer = Observer()
    observer.schedule(
        event_handler,
        str(root),
        recursive=settings.watch_recursive
    )
    
    # 启动监听
    observer.start()
    logger.info(f"Started file watcher on: {root}")
    
    return observer
