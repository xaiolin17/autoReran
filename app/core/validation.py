import re
from typing import Optional

from fastapi import HTTPException


class InputValidator:
    @staticmethod
    def sanitize_string(value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        value = re.sub(r"[<>&\"']", "", value)
        return value

    @staticmethod
    def validate_stock_code(value: str) -> str:
        if not re.match(r"^[a-zA-Z0-9]{1,20}$", value):
            raise ValueError("股票代码格式无效")
        return value

    @staticmethod
    def validate_email(value: str) -> str:
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        if not re.match(email_regex, value):
            raise ValueError("邮箱格式无效")
        return value

    @staticmethod
    def validate_username(value: str) -> str:
        if len(value) < 3 or len(value) > 50:
            raise ValueError("用户名长度应在3-50个字符之间")
        if not re.match(r"^[a-zA-Z0-9_\u4e00-\u9fa5]+$", value):
            raise ValueError("用户名只能包含字母、数字、下划线和中文")
        return value

    @staticmethod
    def validate_password(value: str) -> str:
        if len(value) < 8:
            raise ValueError("密码长度至少8个字符")
        if not re.search(r"[A-Z]", value):
            raise ValueError("密码应包含大写字母")
        if not re.search(r"[a-z]", value):
            raise ValueError("密码应包含小写字母")
        if not re.search(r"[0-9]", value):
            raise ValueError("密码应包含数字")
        return value


def validate_safe_path(path: str, base_dir: str) -> str:
    import os

    safe_path = os.path.normpath(path)
    if safe_path.startswith("..") or os.path.isabs(safe_path):
        raise HTTPException(status_code=400, detail="无效的路径")
    return os.path.join(base_dir, safe_path)
