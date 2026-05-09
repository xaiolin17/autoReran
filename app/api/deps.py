# ==================== 依赖项模块 ====================
# 本文件存放 FastAPI 依赖项，用于：
# 1. 获取当前认证用户
# 2. 验证用户是否激活
# 3. 提供数据库会话的依赖（通常单独写在 database.py，这里导入 get_db）
# 4. 权限检查（RBAC）

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
from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.user_role import UserRole
from app.models.role_permission import RolePermission

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

# ------------------------------------------------------------------
# 权限检查相关函数
# ------------------------------------------------------------------
def get_user_roles(db: Session, user_id: int) -> list[Role]:
    """获取用户的所有角色"""
    user_roles = db.query(UserRole).filter(UserRole.user_id == user_id).all()
    role_ids = [ur.role_id for ur in user_roles]
    return db.query(Role).filter(Role.id.in_(role_ids)).all()

def get_user_permissions(db: Session, user_id: int) -> list[Permission]:
    """获取用户的所有权限"""
    roles = get_user_roles(db, user_id)
    role_ids = [role.id for role in roles]
    role_permissions = db.query(RolePermission).filter(RolePermission.role_id.in_(role_ids)).all()
    permission_ids = [rp.permission_id for rp in role_permissions]
    return db.query(Permission).filter(Permission.id.in_(permission_ids)).all()

def has_permission(db: Session, user_id: int, codename: str) -> bool:
    """检查用户是否有指定权限"""
    permissions = get_user_permissions(db, user_id)
    return any(p.codename == codename for p in permissions)

def has_role(db: Session, user_id: int, role_name: str) -> bool:
    """检查用户是否有指定角色"""
    roles = get_user_roles(db, user_id)
    return any(r.name == role_name for r in roles)

# ------------------------------------------------------------------
# 依赖项：权限检查依赖
# ------------------------------------------------------------------
def require_permission(codename: str):
    """创建一个依赖项，检查用户是否有指定权限"""
    async def dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        if current_user.is_superuser:
            return current_user
        if not has_permission(db, current_user.id, codename):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return dependency

def require_role(role_name: str):
    """创建一个依赖项，检查用户是否有指定角色"""
    async def dependency(
        current_user: User = Depends(get_current_active_user),
        db: Session = Depends(get_db)
    ):
        if current_user.is_superuser:
            return current_user
        if not has_role(db, current_user.id, role_name):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not enough permissions"
            )
        return current_user
    return dependency

async def get_current_superuser(
    current_user: User = Depends(get_current_active_user)
):
    """获取当前超级用户"""
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The user doesn't have enough privileges"
        )
    return current_user