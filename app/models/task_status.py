from sqlalchemy import Column, Integer, String, DateTime, Text, JSON
from app.core.database import Base


class TaskStatus(Base):
    __tablename__ = "task_status"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String(100), unique=True, index=True, nullable=False)
    task_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False)  # pending, running, completed, failed
    created_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    progress = Column(Integer, default=0)  # 0-100
    result = Column(JSON)
    error_message = Column(Text)
    params = Column(JSON)

    def __repr__(self):
        return f"<TaskStatus {self.task_id} {self.status}>"
