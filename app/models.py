"""Pydantic 数据模型

定义 API 请求和响应的数据模型。
验证需求: 9.1
"""

from datetime import datetime
from typing import List
from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    """单个搜索结果模型
    
    表示搜索返回的单个文档结果。
    """
    id: int = Field(..., description="文档 ID")
    title: str = Field(..., description="文档标题")
    path: str = Field(..., description="文档路径")
    snippet: str = Field(..., description="包含高亮关键词的文本片段")


class SearchResponse(BaseModel):
    """搜索响应模型
    
    包含搜索结果列表和分页信息。
    验证需求: 6.3 - 搜索响应包含必需字段
    """
    total: int = Field(..., description="总结果数")
    results: List[SearchResult] = Field(..., description="搜索结果列表")
    query: str = Field(..., description="搜索查询字符串")
    limit: int = Field(..., description="每页结果数")
    offset: int = Field(..., description="结果偏移量")


class Document(BaseModel):
    """文档模型
    
    表示完整的文档元数据。
    """
    id: int = Field(..., description="文档 ID")
    path: str = Field(..., description="文档路径")
    title: str = Field(..., description="文档标题")
    summary: str = Field(..., description="文档摘要")
    mtime: float = Field(..., description="文件修改时间戳")


class ErrorResponse(BaseModel):
    """错误响应模型
    
    统一的错误响应格式。
    """
    error: str = Field(..., description="错误类型")
    detail: str = Field(..., description="错误详细信息")
    timestamp: datetime = Field(default_factory=datetime.now, description="错误发生时间")
