"""Markdown 索引器模块

提供 Markdown 文件扫描、解析和索引功能。
验证需求: 2.1, 2.2, 2.3, 2.4, 2.5
"""

import sqlite3
from pathlib import Path
from typing import Iterator, Tuple
import frontmatter
import os

from app.config import settings
from app.db import get_connection
from app.security import validate_path_traversal, SecurityError
import logging

logger = logging.getLogger(__name__)


def iter_md_files(root: Path) -> Iterator[Path]:
    """递归遍历目录下所有 .md 文件
    
    Args:
        root: 要扫描的根目录
        
    Yields:
        Path: Markdown 文件的路径对象
    """
    root = Path(root)
    if not root.exists():
        return
    
    if root.is_file() and root.suffix == '.md':
        yield root
        return
    
    if root.is_dir():
        for item in root.rglob('*.md'):
            if item.is_file():
                yield item


def _segment_chinese_text(text: str) -> str:
    """为中文文本添加字符级分隔，以支持 FTS5 搜索
    
    SQLite FTS5 的 unicode61 分词器不支持中文分词，因为中文没有空格分隔。
    此函数在每个中文字符后添加空格，使其可以被 unicode61 分词器正确索引。
    同时在中英文边界处添加空格。保留原有的空格。
    
    验证需求: 8.1 - 支持中文内容的索引和搜索
    
    Args:
        text: 原始文本
        
    Returns:
        str: 添加了分隔符的文本
    """
    if not text:
        return text
    
    result = []
    prev_is_cjk = False
    
    for char in text:
        is_cjk = '\u4e00' <= char <= '\u9fff'  # CJK Unified Ideographs
        is_whitespace = char in ' \t\n\r'
        
        # 在中英文边界处添加空格（如果还没有空格）
        if prev_is_cjk and not is_cjk and not is_whitespace and result and result[-1] != ' ':
            result.append(' ')
        elif not prev_is_cjk and is_cjk and result and result[-1] not in ' \t\n\r':
            result.append(' ')
        
        result.append(char)
        
        # 在中文字符后添加空格（除非下一个字符已经是空白）
        if is_cjk and not is_whitespace:
            result.append(' ')
        
        prev_is_cjk = is_cjk
    
    return ''.join(result)


def extract_text_from_md(path: Path) -> Tuple[str, str, str, str, str]:
    """解析 Markdown 文件
    
    解析文件的 frontmatter 和内容，提取标题、摘要和正文。
    返回原始版本和分词版本，以便正确存储和索引。
    
    验证需求: 2.1 - 解析 frontmatter 并提取标题
    验证需求: 2.2 - 使用文件名作为默认标题
    验证需求: 2.3 - 将 Markdown 正文转换为纯文本
    验证需求: 2.5 - 生成文档摘要（前 200 字符）
    验证需求: 8.1 - 支持中文内容的索引
    
    Args:
        path: Markdown 文件路径
        
    Returns:
        tuple: (title_original, title_segmented, summary, content_original, content_segmented)
            - title_original: 原始文档标题
            - title_segmented: 分词后的标题（用于FTS索引）
            - summary: 文档摘要（前 200 字符）
            - content_original: 原始正文内容
            - content_segmented: 分词后的正文（用于FTS索引）
    """
    try:
        # 读取文件内容，尝试多种编码
        content_text = None
        for encoding in ['utf-8', 'gbk', 'gb2312', 'latin-1']:
            try:
                with open(path, 'r', encoding=encoding) as f:
                    content_text = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue
        
        if content_text is None:
            # 如果所有编码都失败，使用二进制模式读取并忽略错误
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content_text = f.read()
        
        # 解析 frontmatter (需求 2.1)
        post = frontmatter.loads(content_text)
        
        # 提取标题：优先使用 frontmatter 中的 title，否则使用文件名 (需求 2.1, 2.2)
        title = post.get('title', None)
        if title is None:
            title = path.stem  # 文件名（不含扩展名）
        else:
            # 将非字符串类型转换为字符串（例如 YAML 可能将 '0' 解析为整数）
            title = str(title)
        
        # 提取正文内容 (需求 2.3)
        content = post.content.strip()
        
        # 对标题和内容进行中文分词处理 (需求 8.1)
        title_segmented = _segment_chinese_text(title)
        content_segmented = _segment_chinese_text(content)
        
        # 生成摘要：截取前 200 个字符 (需求 2.5)
        summary = content[:200] if content else ""
        
        return title, title_segmented, summary, content, content_segmented
        
    except Exception as e:
        # 解析失败时返回基本信息
        title = path.stem
        return title, title, "", "", ""


def index_file(conn: sqlite3.Connection, path: Path) -> None:
    """索引单个文件到数据库
    
    使用 UPSERT 操作避免重复记录。
    
    验证需求: 2.4 - 存储文件路径、标题、摘要和修改时间
    验证需求: 5.5 - 使用 UPSERT 操作避免重复记录
    验证需求: 8.1 - 支持中文内容的索引
    
    Args:
        conn: 数据库连接
        path: 要索引的文件路径
    """
    # 转换为相对路径（相对于 MD_ROOT）
    try:
        rel_path = path.relative_to(settings.md_root)
        path_str = str(rel_path)
    except ValueError:
        # 如果不在 MD_ROOT 下，使用绝对路径
        path_str = str(path)
    
    # 验证路径，防止路径遍历攻击（安全考虑）
    try:
        validated_path = validate_path_traversal(path_str)
    except SecurityError as e:
        logger.warning(f"Skipping file due to security validation failure: {path_str}")
        return
    
    # 提取文档信息（包含原始版本和分词版本）
    title_original, title_segmented, summary, content_original, content_segmented = extract_text_from_md(validated_path)
    
    # 获取文件修改时间 (需求 2.4)
    mtime = os.path.getmtime(validated_path)
    
    cursor = conn.cursor()
    
    # UPSERT 到 docs 表 (需求 5.5)
    # 存储原始标题（不带分词空格）
    cursor.execute("""
        INSERT INTO docs (path, title, summary, mtime)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            title = excluded.title,
            summary = excluded.summary,
            mtime = excluded.mtime
    """, (path_str, title_original, summary, mtime))
    
    # 获取文档 ID
    doc_id = cursor.lastrowid
    if doc_id == 0:
        # 如果是更新操作，需要查询 ID
        cursor.execute("SELECT id FROM docs WHERE path = ?", (path_str,))
        row = cursor.fetchone()
        if row:
            doc_id = row['id']
    
    # 删除旧的 FTS 记录（如果存在）
    cursor.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
    
    # 插入到 FTS 表（使用分词后的标题和内容）
    cursor.execute("""
        INSERT INTO docs_fts (doc_id, title, content, path)
        VALUES (?, ?, ?, ?)
    """, (doc_id, title_segmented, content_segmented, path_str))
    
    conn.commit()


def full_reindex(conn: sqlite3.Connection) -> None:
    """全量重建索引
    
    清空现有索引并重新扫描所有文件。
    
    验证需求: 5.3 - 扫描配置目录下的所有 Markdown 文件
    验证需求: 5.4 - 清空现有索引并重新构建
    
    Args:
        conn: 数据库连接
    """
    cursor = conn.cursor()
    
    # 清空现有索引 (需求 5.4)
    cursor.execute("DELETE FROM docs_fts")
    cursor.execute("DELETE FROM docs")
    conn.commit()
    
    # 扫描并索引所有文件 (需求 5.3)
    md_root = Path(settings.md_root)
    if not md_root.exists():
        raise ValueError(f"Markdown root directory does not exist: {md_root}")
    
    for md_file in iter_md_files(md_root):
        try:
            index_file(conn, md_file)
        except Exception as e:
            # 记录错误但继续处理其他文件
            print(f"Warning: Failed to index {md_file}: {e}")
            continue


def remove_file_from_index(conn: sqlite3.Connection, path: Path) -> None:
    """从索引中删除文件
    
    验证需求: 3.3 - 自动从索引中移除删除的文件
    
    Args:
        conn: 数据库连接
        path: 要删除的文件路径
    """
    # 转换为相对路径
    try:
        rel_path = path.relative_to(settings.md_root)
        path_str = str(rel_path)
    except ValueError:
        path_str = str(path)
    
    cursor = conn.cursor()
    
    # 获取文档 ID
    cursor.execute("SELECT id FROM docs WHERE path = ?", (path_str,))
    row = cursor.fetchone()
    
    if row:
        doc_id = row['id']
        
        # 从 FTS 表删除
        cursor.execute("DELETE FROM docs_fts WHERE doc_id = ?", (doc_id,))
        
        # 从 docs 表删除
        cursor.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        
        conn.commit()
