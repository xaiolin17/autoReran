# ==================== 依赖项模块 ====================
# 本文件存放 FastAPI 依赖项，用于：
# 1. 获取当前认证用户
# 2. 验证用户是否激活
# 3. 提供数据库会话的依赖（通常单独写在 database.py，这里导入 get_db）

# 导入 FastAPI 依赖注入核心组件
from fastapi import Depends, HTTPException, status
# OAuth2 密码流依赖：用于从请求头中提取 Bearer Token
from fastapi.security import OAuth2PasswordBearer
# SQLAlchemy 数据库会话类型
from sqlalchemy.orm import Session
# 数据库会话依赖函数（返回一个可用的 Session 对象）
from app.core.database import get_db
# JWT 令牌解码函数（将 token 解析为 payload 字典）
from app.core.security import decode_access_token
# 用户业务逻辑层（提供数据库查询方法）
from app.services import user_service
# TokenData Pydantic 模型（用于承载解码后的用户邮箱）
from app.schemas.user import TokenData

# ------------------------------------------------------------------
# OAuth2 方案配置
# ------------------------------------------------------------------
oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"/api/v1/auth/login")

# ------------------------------------------------------------------
# 依赖项：获取当前用户（从 token 中解析）
# ------------------------------------------------------------------
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    token_data = TokenData(email=email)

    user = user_service.get_user_by_email(db, email=token_data.email)
    if user is None:
        raise credentials_exception

    return user

# ------------------------------------------------------------------
# 依赖项：获取当前激活的用户
# ------------------------------------------------------------------
async def get_current_active_user(
    current_user = Depends(get_current_user)
):
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    return current_user