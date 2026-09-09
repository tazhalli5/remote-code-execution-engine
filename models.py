from datetime import datetime,timezone
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    language = Column(String(50), nullable=False)
    code = Column(Text, nullable=False)
    stdin = Column(Text, nullable=True, default="")
    status = Column(String(20), nullable=False, default="PENDING")  
    output = Column(Text, nullable=True, default="")
    execution_time_ms = Column(Integer, nullable=True, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)