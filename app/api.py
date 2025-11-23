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
async def get_document(doc_id: int):
    """文档详情端点
    
    根据文档 ID 返回完整的 HTML 格式文档内容。
    
    验证需求: 4.3 - 请求的文档 ID 不存在时返回 404 错误
    验证需求: 4.4 - 文档文件在磁盘上不存在时返回 404 错误
    验证需求: 9.3 - API 请求参数无效时返回 4xx 状态码
    
    Args:
        doc_id: 文档 ID
        
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
    
    return HTMLResponse(content=html_content)
