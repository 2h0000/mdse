"""数据库连接和初始化模块

提供 SQLite 数据库连接管理和表结构初始化功能。
验证需求: 5.1, 5.2
"""

import sqlite3
from pathlib import Path
from typing import Optional

from app.config import settings


def get_connection() -> sqlite3.Connection:
    """获取数据库连接
    
    创建并配置 SQLite 数据库连接，设置 row_factory 为 sqlite3.Row
    以支持字典式访问查询结果。
    
    Returns:
        sqlite3.Connection: 配置好的数据库连接对象
    """
    # 确保数据库目录存在
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 创建连接
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    return conn


def init_db(conn: Optional[sqlite3.Connection] = None) -> None:
    """初始化数据库表结构
    
    创建 docs 表用于存储文档元数据，创建 docs_fts 虚拟表用于全文搜索。
    如果表已存在则不会重复创建。
    
    验证需求: 5.1 - 创建 docs 表
    验证需求: 5.2 - 创建 docs_fts 虚拟表
    
    Args:
        conn: 可选的数据库连接，如果不提供则创建新连接
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        
        # 创建 docs 表 (需求 5.1)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS docs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                summary TEXT,
                mtime REAL NOT NULL
            )
        """)
        
        # 创建 docs_fts 虚拟表 (需求 5.2)
        # 使用 unicode61 分词器支持中文搜索 (需求 8.1)
        cursor.execute(f"""
            CREATE VIRTUAL TABLE IF NOT EXISTS docs_fts USING fts5(
                doc_id UNINDEXED,
                title,
                content,
                path,
                tokenize = '{settings.fts_tokenizer}'
            )
        """)
        
        conn.commit()
    finally:
        if should_close:
            conn.close()


def close_connection(conn: sqlite3.Connection) -> None:
    """关闭数据库连接
    
    Args:
        conn: 要关闭的数据库连接
    """
    if conn:
        conn.close()
