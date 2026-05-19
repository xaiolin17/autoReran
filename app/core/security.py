# ==================== 安全相关逻辑模块 ====================
# 本文件实现认证与授权的核心函数：
# - 密码哈希（bcrypt 算法）
# - JWT token 的创建与解码验证
# - 配置读取（从 core.config 导入 settings）

# 导入日期时间处理模块
from datetime import datetime, timedelta
# Optional 用于类型注解，表示返回值可能为 None
from typing import Optional

# jose 库：处理 JWT（JSON Web Token）的编码与解码
from jose import JWTError, jwt
# passlib 库：处理密码哈希（bcrypt 等算法）
from passlib.context import CryptContext

# 从同级的 config 模块导入配置对象（包含 SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES）
from app.core.config import settings

# ------------------------------------------------------------------
# 1. 密码哈希上下文配置
# ------------------------------------------------------------------
# CryptContext 是一个密码哈希管理器，支持多种哈希算法，并处理算法升级和验证。
# schemes=["bcrypt"]：指定使用 bcrypt 算法（当前最安全的密码哈希算法之一）。
# deprecated="auto"：自动处理弃用的算法，当验证旧哈希时能自动识别。
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ------------------------------------------------------------------
# 2. 密码验证函数
# ------------------------------------------------------------------
def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    验证明文密码是否与哈希密码匹配。

    参数:
        plain_password: 用户输入的明文密码（字符串）
        hashed_password: 数据库中存储的 bcrypt 哈希字符串

    返回:
        bool: 匹配返回 True，否则返回 False
    """
    # pwd_context.verify 自动处理哈希的算法识别和比对（常量时间比较，防止时序攻击）
    return pwd_context.verify(plain_password, hashed_password)


# ------------------------------------------------------------------
# 3. 密码哈希生成函数
# ------------------------------------------------------------------
def get_password_hash(password: str) -> str:
    """
    将明文密码转换为 bcrypt 哈希字符串。

    参数:
        password: 用户注册时输入的明文密码

    返回:
        str: bcrypt 哈希字符串（包含盐、迭代次数等信息），可直接存入数据库
    """
    # pwd_context.hash 自动生成随机盐并进行哈希，返回格式如：
    # $2b$12$KxHk.ZX3qUz.9XqUqUqUqUqUqUqUqUqUqUqUqUqUqUqUqUqUqUqUqU.
    return pwd_context.hash(password)


# ------------------------------------------------------------------
# 4. JWT 访问令牌创建函数
# ------------------------------------------------------------------
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    生成一个 JWT 访问令牌（Access Token）。

    参数:
        data: 需要编码到 token 中的声明（claims），通常包含用户标识，如 {"sub": user.email}
        expires_delta: 可选，自定义 token 有效期（timedelta 对象），若不提供则使用配置的默认值

    返回:
        str: 编码后的 JWT 字符串，形如 "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    """
    # 复制一份原始字典，避免修改传入的 data
    to_encode = data.copy()

    # 确定 token 的过期时间（exp 声明）
    if expires_delta:
        # 如果调用者指定了有效期，则使用当前 UTC 时间加上该时长
        expire = datetime.utcnow() + expires_delta
    else:
        # 否则使用配置文件中设定的默认过期分钟数
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    # 将过期时间添加到待编码的字典中（标准 JWT 声明使用 "exp" 字段）
    to_encode.update({"exp": expire})

    # 使用 jose 库的 jwt.encode 进行编码
    # 参数: payload, secret key, 算法（默认为 HS256）
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    return encoded_jwt


# ------------------------------------------------------------------
# 5. JWT 令牌解码与验证函数
# ------------------------------------------------------------------
def decode_access_token(token: str) -> Optional[dict]:
    """
    解码并验证 JWT token 的有效性。

    参数:
        token: 客户端提交的 JWT 字符串（通常来自 Authorization 头）

    返回:
        Optional[dict]: 如果 token 有效且签名正确，返回 payload 字典（包含用户数据如 sub, exp 等）；
                       如果 token 无效（过期、签名错误、格式错误等），返回 None
    """
    try:
        # jwt.decode 会验证签名、检查 exp 声明是否已过期，并返回解码后的 payload
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,  # 使用相同的密钥验证签名
            algorithms=[settings.ALGORITHM],  # 预期使用的算法列表
        )
        return payload
    except JWTError:
        # JWTError 是 jose 库中所有 JWT 相关异常的基类（包括过期、签名错误、格式错误等）
        # 发生任何错误时，返回 None，保持调用方简单处理
        return None
