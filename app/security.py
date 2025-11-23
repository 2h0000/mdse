"""安全模块

提供安全相关的验证和防护功能。
验证需求: 安全考虑章节
"""

import logging
from pathlib import Path
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


# 安全配置常量
MAX_QUERY_LENGTH = 500  # 查询字符串最大长度
MAX_PATH_LENGTH = 1000  # 文件路径最大长度


class SecurityError(Exception):
    """安全错误异常类
    
    用于表示安全验证失败的情况。
    """
    pass


def validate_query_length(query: str) -> None:
    """验证查询字符串长度
    
    防止过长的查询字符串导致性能问题或潜在的攻击。
    
    Args:
        query: 查询字符串
        
    Raises:
        SecurityError: 如果查询字符串超过最大长度
    """
    if len(query) > MAX_QUERY_LENGTH:
        logger.warning(
            f"Query string too long: {len(query)} characters (max: {MAX_QUERY_LENGTH})"
        )
        raise SecurityError(
            f"Query string too long. Maximum length is {MAX_QUERY_LENGTH} characters."
        )


def validate_path_traversal(file_path: str) -> Path:
    """验证文件路径，防止路径遍历攻击
    
    确保请求的文件路径在配置的文档根目录内，
    防止访问系统中的其他文件。
    
    Args:
        file_path: 相对文件路径
        
    Returns:
        Path: 验证通过的绝对路径
        
    Raises:
        SecurityError: 如果路径不在允许的目录内
    """
    # 验证路径长度
    if len(file_path) > MAX_PATH_LENGTH:
        logger.warning(
            f"File path too long: {len(file_path)} characters (max: {MAX_PATH_LENGTH})"
        )
        raise SecurityError(
            f"File path too long. Maximum length is {MAX_PATH_LENGTH} characters."
        )
    
    # 构建完整路径
    md_root = Path(settings.md_root).resolve()
    full_path = (md_root / file_path).resolve()
    
    # 检查路径是否在允许的根目录内
    try:
        full_path.relative_to(md_root)
    except ValueError:
        logger.warning(
            f"Path traversal attempt detected: {file_path}",
            extra={
                "requested_path": file_path,
                "resolved_path": str(full_path),
                "md_root": str(md_root)
            }
        )
        raise SecurityError(
            "Access denied: Path is outside the allowed document directory"
        )
    
    return full_path


def sanitize_error_message(error_message: str, is_production: bool = True) -> str:
    """清理错误信息，避免泄露敏感信息
    
    在生产环境中，不应该暴露内部路径、堆栈信息等敏感数据。
    
    Args:
        error_message: 原始错误信息
        is_production: 是否为生产环境
        
    Returns:
        str: 清理后的错误信息
    """
    if not is_production:
        # 开发环境返回完整错误信息
        return error_message
    
    # 生产环境返回通用错误信息
    # 避免暴露内部路径、数据库结构等信息
    sensitive_keywords = [
        str(settings.md_root),
        str(settings.db_path),
        "sqlite",
        "database",
        "traceback",
        "exception",
    ]
    
    sanitized = error_message
    for keyword in sensitive_keywords:
        if keyword.lower() in sanitized.lower():
            sanitized = "An internal error occurred. Please contact the administrator."
            break
    
    return sanitized


def check_database_permissions() -> bool:
    """检查数据库文件权限
    
    确保数据库文件具有适当的权限（仅所有者可读写）。
    
    Returns:
        bool: 权限是否正确
    """
    import stat
    import os
    
    db_path = Path(settings.db_path)
    
    # 如果数据库文件不存在，返回 True（将在创建时设置权限）
    if not db_path.exists():
        return True
    
    try:
        # 获取文件权限
        file_stat = db_path.stat()
        file_mode = stat.S_IMODE(file_stat.st_mode)
        
        # 期望的权限：0o600 (仅所有者可读写)
        expected_mode = stat.S_IRUSR | stat.S_IWUSR  # 0o600
        
        if file_mode != expected_mode:
            logger.warning(
                f"Database file has incorrect permissions: {oct(file_mode)} "
                f"(expected: {oct(expected_mode)})"
            )
            
            # 尝试修正权限（仅在 Unix 系统上）
            if os.name != 'nt':  # 不是 Windows
                try:
                    os.chmod(db_path, expected_mode)
                    logger.info(f"Database file permissions corrected to {oct(expected_mode)}")
                    return True
                except OSError as e:
                    logger.error(f"Failed to correct database file permissions: {e}")
                    return False
            else:
                # Windows 系统，权限管理不同
                logger.info("Running on Windows, skipping Unix permission check")
                return True
        
        return True
        
    except Exception as e:
        logger.error(f"Error checking database permissions: {e}")
        return False


def set_database_permissions() -> None:
    """设置数据库文件权限为 600（仅所有者可读写）
    
    在创建数据库文件后调用此函数设置安全权限。
    """
    import os
    import stat
    
    db_path = Path(settings.db_path)
    
    # 如果数据库文件不存在，无需设置权限
    if not db_path.exists():
        return
    
    # 仅在 Unix 系统上设置权限
    if os.name == 'nt':  # Windows
        logger.info("Running on Windows, skipping Unix permission setting")
        return
    
    try:
        # 设置权限为 0o600 (仅所有者可读写)
        expected_mode = stat.S_IRUSR | stat.S_IWUSR  # 0o600
        os.chmod(db_path, expected_mode)
        logger.info(f"Database file permissions set to {oct(expected_mode)}")
    except OSError as e:
        logger.error(f"Failed to set database file permissions: {e}")
