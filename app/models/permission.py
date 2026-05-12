from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    code = Column(String(100), unique=True, nullable=False)
    description = Column(String(200))
    created_at = Column(DateTime, nullable=False)

    # 关联
    role_permissions = relationship("RolePermission", back_populates="permission", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Permission {self.name}>"
