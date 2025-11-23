"""API 路由模块

定义 RESTful API 端点，提供搜索和文档检索功能。
验证需求: 1.4, 4.3, 4.4, 9.3
"""

import logging
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from app.models import SearchResponse, SearchResult as SearchResultModel, ErrorResponse
from app.search_service import search_documents, get_document_by_id, render_document_html
from app.config import settings
from app.security import validate_query_length, SecurityError


# 创建日志记录器
logger = logging.getLogger(__name__)

# 创建 API 路由器
router = APIRouter()

# 配置模板
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def search_page(
    request: Request,
    q: Optional[str] = Query(None, description="搜索查询字符串"),
    limit: int = Query(20, ge=1, le=100, description="每页结果数"),
    offset: int = Query(0, ge=0, description="结果偏移量")
):
    """搜索页面路由
    
    显示搜索界面和搜索结果。
    
    验证需求: 6.1 - 用户访问根路径时显示搜索页面
    验证需求: 6.3 - 显示搜索结果时展示文档标题、路径和高亮片段
    验证需求: 6.5 - 搜索无结果时显示友好的提示信息
    
    Args:
        request: FastAPI Request 对象
        q: 搜索查询字符串（可选）
        limit: 每页返回的结果数量（默认 20）
        offset: 结果偏移量（默认 0）
        
    Returns:
        HTMLResponse: 搜索页面 HTML
    """
    # 如果没有查询参数，显示空搜索页面
    if not q or q.strip() == "":
        return templates.TemplateResponse(
            request=request,
            name="search.html",
            context={
                "query": None,
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset
            }
        )
    
    try:
        # 执行搜索
        results, total = search_documents(query=q, limit=limit, offset=offset)
        
        # 转换结果为字典列表
        result_dicts = [
            {
                "id": r.id,
                "title": r.title,
                "path": r.path,
                "snippet": r.snippet
            }
            for r in results
        ]
        
        # 渲染搜索结果页面
        return templates.TemplateResponse(
            request=request,
            name="search.html",
            context={
                "query": q,
                "results": result_dicts,
                "total": total,
                "limit": limit,
                "offset": offset,
                "min": min,  # 提供 min 函数给模板
                "max": max   # 提供 max 函数给模板
            }
        )
        
    except Exception as e:
        # 如果搜索失败，显示错误信息
        return templates.TemplateResponse(
            request=request,
            name="search.html",
            context={
                "query": q,
                "results": [],
                "total": 0,
                "limit": limit,
                "offset": offset,
                "error": f"搜索失败: {str(e)}"
            }
        )


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=1, description="搜索查询字符串"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="每页结果数"),
    offset: int = Query(0, ge=0, description="结果偏移量")
):
    """搜索端点
    
    执行全文搜索并返回匹配的文档列表。
    
    验证需求: 1.4 - 搜索查询为空或仅包含空白字符时拒绝查询
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    
    Args:
        q: 搜索查询字符串（必需，不能为空）
        limit: 每页返回的结果数量（可选，默认 20，最大 100）
        offset: 结果偏移量，用于分页（可选，默认 0）
        
    Returns:
        SearchResponse: 包含搜索结果和分页信息的响应
        
    Raises:
        HTTPException: 422 如果查询参数无效
    """
    # 验证查询字符串不为空或仅包含空白字符 (需求 1.4)
    if not q or q.strip() == "":
        logger.warning(f"Empty query string rejected")
        raise HTTPException(
            status_code=422,
            detail="Query string cannot be empty or contain only whitespace"
        )
    
    # 验证查询字符串长度（安全考虑）
    try:
        validate_query_length(q)
    except SecurityError as e:
        raise HTTPException(
            status_code=422,
            detail=str(e)
        )
    
    try:
        # 执行搜索
        results, total = search_documents(query=q, limit=limit, offset=offset)
        
        # 转换为 Pydantic 模型
        result_models = [
            SearchResultModel(
                id=r.id,
                title=r.title,
                path=r.path,
                snippet=r.snippet
            )
            for r in results
        ]
        
        # 构建响应
        response = SearchResponse(
            total=total,
            results=result_models,
            query=q,
            limit=limit if limit is not None else 20,
            offset=offset
        )
        
        return response
        
    except Exception as e:
        # 处理数据库或其他错误
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get("/docs/{doc_id}", response_class=HTMLResponse)
async def get_document(
    doc_id: int,
    q: Optional[str] = Query(None, description="搜索关键词，用于高亮显示")
):
    """文档详情端点
    
    根据文档 ID 返回完整的 HTML 格式文档内容。
    
    验证需求: 4.3 - 请求的文档 ID 不存在时返回 404 错误
    验证需求: 4.4 - 文档文件在磁盘上不存在时返回 404 错误
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    
    Args:
        doc_id: 文档 ID
        q: 搜索关键词（可选），用于在文档中高亮显示
        
    Returns:
        HTMLResponse: HTML 格式的文档内容
        
    Raises:
        HTTPException: 404 如果文档不存在或文件不存在
    """
    # 验证 doc_id 为正整数
    if doc_id <= 0:
        raise HTTPException(
            status_code=422,
            detail="Document ID must be a positive integer"
        )
    
    # 获取文档元数据
    document = get_document_by_id(doc_id)
    
    # 检查文档是否存在 (需求 4.3)
    if document is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document with ID {doc_id} not found"
        )
    
    # 渲染文档为 HTML
    html_content = render_document_html(doc_id)
    
    # 检查文件是否存在 (需求 4.4)
    if html_content is None:
        raise HTTPException(
            status_code=404,
            detail=f"Document file not found on disk: {document.path}"
        )
    
    # 如果提供了搜索关键词，在 HTML 中高亮显示
    if q and q.strip():
        import re
        
        query = q.strip()
        
        # 智能提取关键词，按优先级排序
        # 优先级：完整查询 > 词组片段 > 单个字符
        keywords_by_priority = []
        
        # 1. 完整查询（最高优先级）
        # 移除多余空格，但保留中文词组
        full_query = ' '.join(query.split())
        if full_query:
            keywords_by_priority.append(('full', full_query))
        
        # 2. 提取词组片段（中等优先级）
        # 按空格分割，每个片段作为一个词组
        phrases = []
        current_phrase = []
        
        for char in query:
            if char in ' \t\n\r':
                if current_phrase:
                    phrase = ''.join(current_phrase)
                    if len(phrase) > 1:  # 只保留多字符词组
                        phrases.append(phrase)
                    current_phrase = []
            else:
                current_phrase.append(char)
        
        if current_phrase:
            phrase = ''.join(current_phrase)
            if len(phrase) > 1:
                phrases.append(phrase)
        
        # 添加词组到关键词列表
        for phrase in phrases:
            keywords_by_priority.append(('phrase', phrase))
        
        # 3. 提取单个字符（最低优先级）
        # 只在没有找到完整匹配时才使用
        single_chars = []
        for char in query:
            is_cjk = '\u4e00' <= char <= '\u9fff'
            if is_cjk:
                single_chars.append(char)
            elif char.isalnum():
                # 英文字符不单独作为关键词
                pass
        
        # 去重单字符
        single_chars = list(set(single_chars))
        for char in single_chars:
            keywords_by_priority.append(('char', char))
        
        # 按优先级高亮
        # 使用占位符避免重复高亮
        MARK_PLACEHOLDER = '___MARK_START___'
        MARK_END_PLACEHOLDER = '___MARK_END___'
        
        # 先高亮完整查询和词组
        for priority, keyword in keywords_by_priority:
            if priority in ['full', 'phrase']:
                # 转义特殊字符
                escaped_keyword = re.escape(keyword)
                
                # 检查是否包含中文
                has_chinese = any('\u4e00' <= c <= '\u9fff' for c in keyword)
                
                if has_chinese:
                    # 中文词组：直接匹配
                    pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
                else:
                    # 英文词组：使用词边界
                    pattern = re.compile(f'\\b({escaped_keyword})\\b', re.IGNORECASE)
                
                # 替换为占位符（避免重复高亮）
                def replace_with_placeholder(match):
                    # 检查是否已经被标记
                    text_before = html_content[:match.start()]
                    if MARK_PLACEHOLDER in text_before[max(0, len(text_before)-50):]:
                        last_start = text_before.rfind(MARK_PLACEHOLDER)
                        last_end = text_before.rfind(MARK_END_PLACEHOLDER)
                        if last_start > last_end:
                            return match.group(0)
                    
                    # 检查是否在 HTML 标签内
                    open_tags = text_before.count('<') - text_before.count('>')
                    if open_tags > 0:
                        return match.group(0)
                    
                    return f'{MARK_PLACEHOLDER}{match.group(1)}{MARK_END_PLACEHOLDER}'
                
                html_content = pattern.sub(replace_with_placeholder, html_content)
        
        # 检查是否有高亮内容
        has_highlights = MARK_PLACEHOLDER in html_content
        
        # 如果没有找到完整匹配，才使用单字符高亮
        if not has_highlights:
            for priority, keyword in keywords_by_priority:
                if priority == 'char':
                    escaped_keyword = re.escape(keyword)
                    pattern = re.compile(f'({escaped_keyword})', re.IGNORECASE)
                    
                    def replace_char(match):
                        text_before = html_content[:match.start()]
                        if MARK_PLACEHOLDER in text_before[max(0, len(text_before)-50):]:
                            last_start = text_before.rfind(MARK_PLACEHOLDER)
                            last_end = text_before.rfind(MARK_END_PLACEHOLDER)
                            if last_start > last_end:
                                return match.group(0)
                        
                        open_tags = text_before.count('<') - text_before.count('>')
                        if open_tags > 0:
                            return match.group(0)
                        
                        return f'{MARK_PLACEHOLDER}{match.group(1)}{MARK_END_PLACEHOLDER}'
                    
                    html_content = pattern.sub(replace_char, html_content)
        
        # 将占位符替换为真实的 mark 标签
        html_content = html_content.replace(MARK_PLACEHOLDER, '<mark>')
        html_content = html_content.replace(MARK_END_PLACEHOLDER, '</mark>')
    
    return HTMLResponse(content=html_content)
