# 导入 FastAPI 路由核心组件
from fastapi import APIRouter, Depends, HTTPException, status

# OAuth2 密码流表单依赖（用于接收 username/password 表单数据）
from fastapi.security import OAuth2PasswordRequestForm

# SQLAlchemy 数据库会话类型
from sqlalchemy.orm import Session

# 依赖项（如获取当前用户）
from app.api import deps

# 数据库会话依赖函数（用于获取数据库会话）
from app.core.database import get_db

# JWT 令牌创建函数 & 密码验证函数
from app.core.security import create_access_token

# 令牌响应的 Pydantic 模型
from app.schemas.token import Token

# 用户相关的 Pydantic 模型（请求体和响应体）
from app.schemas.user import UserCreate, UserOut

# 用户业务逻辑层（数据库操作）
from app.services import user_service

# 创建一个路由处理器实例，后续的所有路由都注册在这个 router 对象上
router = APIRouter()


# 注册接口：POST /register
# response_model=UserOut 表示成功时返回 UserOut 结构的数据
# status_code=201 表示创建成功
@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
def register(user_in: UserCreate, db: Session = Depends(get_db)):
    """
    用户注册
    - user_in: 请求体自动解析为 UserCreate 对象（包含 email 和 password）
    - db: 数据库会话，通过 Depends(get_db) 依赖注入获得
    """
    # 调用 service 层，根据邮箱查询用户是否已存在
    existing_user = user_service.get_user_by_email(db, email=user_in.email)
    if existing_user:
        # 若邮箱已注册，抛出 400 错误，并给出明确提示
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    # 调用 service 层创建新用户（内部会哈希密码并存入数据库）
    user = user_service.create_user(db, user_in)
    # 自动将 user 转换为 UserOut 模型（不返回密码等信息）返回给客户端
    return user


# 登录接口：POST /login
# response_model=Token 表示成功时返回 access_token 和 token_type
@router.post("/login", response_model=Token)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    """
    用户登录（OAuth2 密码模式）
    - form_data: FastAPI 内置表单依赖，自动提取 username 和 password 字段
      注意：OAuth2PasswordRequestForm 要求前端发送 application/x-www-form-urlencoded
    - db: 数据库会话
    """
    # 调用 service 层验证用户凭证（根据邮箱和密码查找用户，密码验证在 service 内部完成）
    user = user_service.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        # 验证失败（用户不存在或密码错误），抛出 401 未授权错误
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            # 添加 WWW-Authenticate 响应头，提示客户端使用 Bearer 令牌认证
            headers={"WWW-Authenticate": "Bearer"},
        )
    # 验证成功，生成 JWT 访问令牌，sub（主题）字段存储用户邮箱
    access_token = create_access_token(data={"sub": user.email})
    # 按照 OAuth2 规范返回 token 和 token_type
    return {"access_token": access_token, "token_type": "bearer"}


# 获取当前登录用户信息：GET /me
# response_model=UserOut 表示返回用户公开信息
@router.get("/me", response_model=UserOut)
def read_current_user(current_user=Depends(deps.get_current_active_user)):
    """
    获取当前已认证的用户信息（需要携带 Bearer Token）
    - current_user: 通过 deps.get_current_active_user 依赖注入获得
      该依赖会解析请求头中的 Authorization: Bearer <token>，
      验证令牌有效性，并返回当前活跃的用户模型对象。
    """
    # 直接返回依赖解析出的用户对象，FastAPI 会自动将其转换为 UserOut 格式
    return current_user
