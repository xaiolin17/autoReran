# ==================== 依赖项模块 ====================
# 本文件存放 FastAPI 依赖项，用于：
# 1. 获取当前认证用户
# 2. 验证用户是否激活
# 3. 提供数据库会话的依赖（通常单独写在 database.py，这里导入 get_db）

# 导入 FastAPI 依赖注入核心组件
# OAuth2 密码流依赖：用于从请求头中提取 Bearer Token
from fastapi.security import OAuth2PasswordBearer

# ------------------------------------------------------------------
# OAuth2 方案配置
# ------------------------------------------------------------------
# 创建一个 OAuth2PasswordBearer 实例，它会产生一个可调用的依赖项。
# 当被 Depends() 使用时，它会自动从请求头 Authorization 中提取 Bearer token。
# tokenUrl 参数指向你的登录端点，用于 OpenAPI 文档自动生成（Swagger UI 会知道在哪里获取 token）。
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/users/login")


# ------------------------------------------------------------------
# 依赖项：获取当前用户（从 token 中解析）
# ------------------------------------------------------------------
# async def get_current_user(
#     # 这个参数会被 FastAPI 自动注入：
#     # token = Depends(oauth2_scheme)  → 从请求头中提取 token 字符串
#     token: str = Depends(oauth2_scheme),
#     # db = Depends(get_db)  → 获取一个新的数据库会话（请求结束后自动关闭）
#     db: Session = Depends(get_db),
# ):
#     # 定义一个统一的认证失败异常，后续多处可以复用此异常对象
#     credentials_exception = HTTPException(
#         status_code=status.HTTP_401_UNAUTHORIZED,  # 401 Unauthorized
#         detail="Could not validate credentials",  # 错误详情
#         headers={"WWW-Authenticate": "Bearer"},  # 提示客户端应使用 Bearer 令牌认证
#     )
#
#     # 1. 解码 token，获取 payload（字典）
#     payload = decode_access_token(token)  # 若 token 无效或过期，返回 None
#     if payload is None:
#         raise credentials_exception
#
#     # 2. 从 payload 中提取用户标识（这里使用 'sub' 字段存储邮箱）
#     email: str = payload.get("sub")  # payload 是一个字典，sub 字段通常存储用户标识
#     if email is None:
#         raise credentials_exception
#
#     # 3. 将邮箱包装到 TokenData 模型中（便于类型标注和数据传递）
#     token_data = TokenData(email=email)
#
#     # 4. 根据邮箱从数据库中查询用户
#     user = user_service.get_user_by_email(db, email=token_data.email)
#     if user is None:
#         raise credentials_exception
#
#     # 5. 返回用户对象（SQLAlchemy 模型实例）
#     #    此对象会被后续依赖项（例如 get_current_active_user）使用
#     return user


# ------------------------------------------------------------------
# 依赖项：获取当前激活的用户（在 get_current_user 基础上增加激活状态检查）
# ------------------------------------------------------------------
# async def get_current_active_user(
#     # 依赖 get_current_user 的结果，即上面解析出的用户对象
#     current_user=Depends(get_current_user),
# ):
#     # 检查用户是否被标记为激活（数据库中 is_active 字段）
#     if not current_user.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_400_BAD_REQUEST,  # 400 Bad Request
#             detail="Inactive user",  # 用户已被禁用
#         )
#     # 通过检查，返回当前激活的用户对象
#     return current_user
