from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from base import Base
from datetime import datetime, timezone
from prefect_sqlalchemy import SqlAlchemyConnector
from sqlalchemy.orm import Session
from sqlalchemy import select

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func

DATABASE_URL = "postgresql+asyncpg://sphere:1234@192.168.2.53/sphere_default"


class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=True)
    guild_id = Column(String, nullable=True)
    message = Column(String, nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False, default=func.now())
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    sent = Column(Boolean, default=False)

    def __repr__(self):
        return f"<Reminder(user_id={self.user_id}, remind_at={self.remind_at}, sent={self.sent})>"

    @classmethod
    def load_from_input(cls, discord_user_id: int, message: str, remind_at: datetime):
        return cls(discord_user_id=str(discord_user_id), message=message, remind_at=remind_at)
    
    @classmethod
    async def load_due_reminders(cls):
        
        async_engine = create_async_engine(
        DATABASE_URL,
        )

        AsyncSessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
        )
    
        try:
            now = datetime.now(timezone.utc)
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(cls).where(
                        cls.sent == False,
                        cls.remind_at <= now
                    )
                )
                reminders = result.scalars().all()
                return reminders
        except Exception as e:
            print(f"Error loading due reminders: {e}")
            return []

    def is_due(self) -> bool:
        from sqlalchemy.exc import SQLAlchemyError

        try:
            connector = SqlAlchemyConnector.load("spheredefaultcreds")  # no await
            engine = connector.get_engine()

            with Session(engine) as session:  # synchronous context manager
                result = session.execute(
                    select(Reminder.remind_at)
                    .where(Reminder.id == self.id, Reminder.sent == False)
                )
                remind_at = result.scalar_one_or_none()

                if remind_at is None:
                    return False

                return datetime.now(timezone.utc) >= remind_at

        except SQLAlchemyError as e:
            print(f"Database error while checking is_due: {e}")
            return False
    
    async def store_into_db(self):
        from sqlalchemy.exc import SQLAlchemyError

        connector = await SqlAlchemyConnector.load("spheredefaultcreds")

        engine = connector.get_engine()
        Base.metadata.create_all(engine)

        try:
            with Session(engine) as session:
                reminder = self
                session.add(reminder)
                session.commit()
        except SQLAlchemyError as e:
            print(f"Failed to store reminder: {e}")
            return
        
    async def mark_as_sent(self):
        try:
            # connector = await SqlAlchemyConnector.load("spheredefaultcreds")
            # engine = connector.get_engine()
            
            async_engine = create_async_engine(
            DATABASE_URL,
            )

            async with AsyncSession(async_engine) as session:
                async with session.begin():
                    self.sent = True
                    session.add(self)  # or session.merge(self)
                await session.commit()
        except Exception as e:
            print(f"Error marking reminder as sent: {e}")