"""搜索服务模块

提供全文搜索和文档检索功能。
验证需求: 1.1, 1.2, 1.3, 1.5
"""

import sqlite3
from typing import List, Tuple, Optional
from pathlib import Path
import markdown

from app.config import settings
from app.db import get_connection
from app.security import validate_path_traversal, SecurityError


class SearchResult:
    """搜索结果数据类"""
    
    def __init__(self, id: int, title: str, path: str, snippet: str, rank: float):
        self.id = id
        self.title = title
        self.path = path
        self.snippet = snippet
        self.rank = rank
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'title': self.title,
            'path': self.path,
            'snippet': self.snippet
        }


class Document:
    """文档数据类"""
    
    def __init__(self, id: int, path: str, title: str, summary: str, mtime: float):
        self.id = id
        self.path = path
        self.title = title
        self.summary = summary
        self.mtime = mtime
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'path': self.path,
            'title': self.title,
            'summary': self.summary,
            'mtime': self.mtime
        }


def _segment_chinese_query(query: str) -> str:
    """为中文查询添加字符级分隔
    
    为了与索引时的分词方式保持一致，需要对查询字符串进行相同的处理。
    在每个中文字符后添加空格，并在中英文边界处添加空格。
    
    验证需求: 8.2 - 支持中文关键词搜索
    
    Args:
        query: 原始查询字符串
        
    Returns:
        str: 添加了分隔符的查询字符串
    """
    if not query:
        return query
    
    result = []
    prev_is_cjk = False
    
    for char in query:
        is_cjk = '\u4e00' <= char <= '\u9fff'  # CJK Unified Ideographs
        
        # 在中英文边界处添加空格
        if prev_is_cjk and not is_cjk and char not in ' \t\n\r':
            result.append(' ')
        elif not prev_is_cjk and is_cjk and result and result[-1] not in ' \t\n\r':
            result.append(' ')
        
        result.append(char)
        
        # 在中文字符后添加空格
        if is_cjk:
            result.append(' ')
        
        prev_is_cjk = is_cjk
    
    return ''.join(result).strip()


def search_documents(
    query: str,
    limit: int = None,
    offset: int = 0,
    conn: Optional[sqlite3.Connection] = None
) -> Tuple[List[SearchResult], int]:
    """执行全文搜索
    
    使用 SQLite FTS5 进行全文搜索，支持 BM25 排序和高亮片段生成。
    
    验证需求: 1.1 - 在 SQLite FTS5 索引中执行全文搜索
    验证需求: 1.2 - 按相关性排序结果并使用 BM25 算法
    验证需求: 1.3 - 提供包含匹配关键词的高亮片段
    验证需求: 1.5 - 返回指定范围的结果子集（分页）
    验证需求: 8.2 - 支持中文关键词搜索
    
    Args:
        query: 搜索查询字符串
        limit: 返回结果数量限制（默认使用配置值）
        offset: 结果偏移量，用于分页（默认 0）
        conn: 可选的数据库连接
        
    Returns:
        tuple: (结果列表, 总数)
            - 结果列表: SearchResult 对象列表
            - 总数: 匹配的文档总数
    """
    # 使用默认 limit 如果未指定
    if limit is None:
        limit = settings.default_limit
    
    # 限制最大 limit
    if limit > settings.max_search_limit:
        limit = settings.max_search_limit
    
    # 对查询进行中文分词处理 (需求 8.2)
    segmented_query = _segment_chinese_query(query)
    
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        
        # 首先获取总数
        count_query = """
            SELECT COUNT(*) as total
            FROM docs_fts
            WHERE docs_fts MATCH ?
        """
        cursor.execute(count_query, (segmented_query,))
        total = cursor.fetchone()['total']
        
        # 执行 FTS5 全文搜索 (需求 1.1)
        # 使用 BM25 排序 (需求 1.2)
        # 生成高亮片段 (需求 1.3)
        # 支持分页 (需求 1.5)
        # snippet 参数: (table, column_index, start_mark, end_mark, ellipsis, max_tokens)
        # column_index: 0=doc_id, 1=title, 2=content, 3=path
        search_query = f"""
            SELECT 
                d.id,
                d.title,
                d.path,
                snippet(docs_fts, 2, '<mark>', '</mark>', '...', ?) AS snippet,
                bm25(docs_fts) AS rank
            FROM docs_fts
            JOIN docs d ON d.id = docs_fts.doc_id
            WHERE docs_fts MATCH ?
            ORDER BY rank
            LIMIT ? OFFSET ?
        """
        
        cursor.execute(
            search_query,
            (settings.snippet_tokens, segmented_query, limit, offset)
        )
        
        results = []
        for row in cursor.fetchall():
            result = SearchResult(
                id=row['id'],
                title=row['title'],
                path=row['path'],
                snippet=row['snippet'],
                rank=row['rank']
            )
            results.append(result)
        
        return results, total
        
    finally:
        if should_close:
            conn.close()


def get_document_by_id(
    doc_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[Document]:
    """根据 ID 获取文档
    
    验证需求: 4.1 - 根据文档 ID 返回完整的文档内容
    
    Args:
        doc_id: 文档 ID
        conn: 可选的数据库连接
        
    Returns:
        Document: 文档对象，如果不存在则返回 None
    """
    should_close = False
    if conn is None:
        conn = get_connection()
        should_close = True
    
    try:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, path, title, summary, mtime
            FROM docs
            WHERE id = ?
        """, (doc_id,))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        document = Document(
            id=row['id'],
            path=row['path'],
            title=row['title'],
            summary=row['summary'],
            mtime=row['mtime']
        )
        
        return document
        
    finally:
        if should_close:
            conn.close()


def render_document_html(
    doc_id: int,
    conn: Optional[sqlite3.Connection] = None
) -> Optional[str]:
    """渲染文档为 HTML
    
    根据文档 ID 获取文档，读取文件内容并将 Markdown 转换为 HTML。
    支持代码块和表格扩展语法。
    
    验证需求: 4.2 - 将 Markdown 转换为 HTML 格式
    验证需求: 4.4 - 文档文件在磁盘上不存在时返回 None
    验证需求: 4.5 - 支持代码块和表格扩展语法
    
    Args:
        doc_id: 文档 ID
        conn: 可选的数据库连接
        
    Returns:
        str: HTML 格式的文档内容，如果文档不存在或文件不存在则返回 None
    """
    # 获取文档元数据
    document = get_document_by_id(doc_id, conn)
    if document is None:
        return None
    
    # 验证路径，防止路径遍历攻击（安全考虑）
    try:
        file_path = validate_path_traversal(document.path)
    except SecurityError:
        # 路径验证失败，返回 None
        return None
    
    # 检查文件是否存在 (需求 4.4)
    if not file_path.exists():
        return None
    
    try:
        # 读取文件内容
        content = file_path.read_text(encoding='utf-8')
        
        # 将 Markdown 转换为 HTML (需求 4.2)
        # 支持代码块和表格扩展 (需求 4.5)
        md = markdown.Markdown(extensions=[
            'fenced_code',  # 支持代码块
            'tables',       # 支持表格
            'codehilite',   # 代码高亮
        ])
        html_content = md.convert(content)
        
        return html_content
        
    except (IOError, OSError, UnicodeDecodeError):
        # 文件读取失败
        return None
