from sqlalchemy import Column, Integer, String, DateTime
from .database import Base
import datetime

# Эта модель осталась от нашего старого плана с регистрацией,
# но она может пригодиться в будущем. Пока просто оставляем ее здесь.
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)

# Наша новая модель для хранения анонимных ключей доступа
class AccessKey(Base):
    __tablename__ = "keys"

    id = Column(Integer, primary_key=True, index=True)
    key_string = Column(String, unique=True, index=True)
    expires_at = Column(DateTime)
    plan_type = Column(String) # "monthly" или "yearly"