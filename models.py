import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from database import Base

class Submission(Base):
    __tablename__ = "submissions"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(Text, nullable=False)
    language = Column(String(50), nullable=False, default="python")
    output = Column(Text, nullable=True)
    success = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))