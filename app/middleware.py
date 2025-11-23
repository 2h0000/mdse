"""中间件模块

提供统一的错误处理和访问日志中间件。
验证需求: 10.2
"""

import logging
import time
from typing import Callable
from datetime import datetime

from fastapi import Request, Response, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.models import ErrorResponse


logger = logging.getLogger(__name__)


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """统一错误处理中间件
    
    捕获所有未处理的异常并返回格式化的错误响应。
    验证需求: 10.2 - 实现统一错误处理
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """处理请求并捕获异常
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
            
        Returns:
            Response: 响应对象
        """
        try:
            response = await call_next(request)
            return response
            
        except Exception as exc:
            # 记录错误日志
            logger.error(
                f"Unhandled exception: {exc}",
                exc_info=True,
                extra={
                    "path": request.url.path,
                    "method": request.method,
                    "client": request.client.host if request.client else None
                }
            )
            
            # 构建错误响应
            error_response = ErrorResponse(
                error="Internal Server Error",
                detail=str(exc),
                timestamp=datetime.now()
            )
            
            # 返回 JSON 格式的错误响应
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content=error_response.model_dump(mode='json')
            )


class AccessLoggingMiddleware(BaseHTTPMiddleware):
    """访问日志中间件
    
    记录所有 HTTP 请求的访问日志。
    验证需求: 10.2 - 添加访问日志
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """记录请求和响应信息
        
        Args:
            request: FastAPI 请求对象
            call_next: 下一个中间件或路由处理器
            
        Returns:
            Response: 响应对象
        """
        # 记录请求开始时间
        start_time = time.time()
        
        # 获取客户端信息
        client_host = request.client.host if request.client else "unknown"
        
        # 记录请求信息
        logger.info(
            f"Request started: {request.method} {request.url.path}",
            extra={
                "method": request.method,
                "path": request.url.path,
                "query": str(request.query_params),
                "client": client_host
            }
        )
        
        # 处理请求
        try:
            response = await call_next(request)
            
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录响应信息
            logger.info(
                f"Request completed: {request.method} {request.url.path} - "
                f"Status: {response.status_code} - Duration: {process_time:.3f}s",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration": process_time,
                    "client": client_host
                }
            )
            
            # 添加处理时间到响应头
            response.headers["X-Process-Time"] = str(process_time)
            
            return response
            
        except Exception as exc:
            # 计算处理时间
            process_time = time.time() - start_time
            
            # 记录错误
            logger.error(
                f"Request failed: {request.method} {request.url.path} - "
                f"Error: {exc} - Duration: {process_time:.3f}s",
                exc_info=True,
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "duration": process_time,
                    "client": client_host
                }
            )
            
            # 重新抛出异常，让 ErrorHandlingMiddleware 处理
            raise
