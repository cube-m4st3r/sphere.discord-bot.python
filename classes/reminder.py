from sqlalchemy import Column, Integer, String, DateTime, Boolean
from base import Base
from datetime import datetime, timezone
from prefect_sqlalchemy import SqlAlchemyConnector
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from handlers.loki_logging import get_logger

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from utils.send_push_notification import send_notification_to_ntfy


loki_logger = get_logger(
    "sphere.discord.python",
    level="debug",
    labels={
        "app": "sphere",
        "env": "dev",
        "service": "discord_bot",
        "lang": "python",
        "class": "reminder"
    }
)


class Reminder(Base):
    __tablename__ = 'reminders'

    id = Column(Integer, primary_key=True)
    discord_user_id = Column(String, nullable=False)
    channel_id = Column(String, nullable=True)
    guild_id = Column(String, nullable=True)
    message = Column(String, nullable=False)
    remind_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sent = Column(Boolean, default=False)
    list_id = Column(Integer, nullable=False, default=0)

    def __repr__(self):
        return f"<Reminder(user_id={self.user_id}, remind_at={self.remind_at}, sent={self.sent})>"

    @classmethod
    def load_from_input(cls, discord_user_id: int, message: str, remind_at: datetime):
        return cls(discord_user_id=str(discord_user_id), message=message, remind_at=remind_at)
    
    @classmethod
    async def _load_due_reminders(cls, *selectables, filters=None, group_by=None, order_by=None, return_scalar=False):
        """Internal helper to load reminders with optional filters and scalar option."""
        connector = await SqlAlchemyConnector.load("spheredefaultasynccreds")
        async_engine = connector.get_engine()
        AsyncSessionLocal = sessionmaker(
            bind=async_engine,
            class_=AsyncSession,
        )
        try:
            async with AsyncSessionLocal() as session:
                stmt = select(*selectables)
                if filters:
                    stmt = stmt.where(*filters)
                if order_by:
                    stmt = stmt.order_by(*order_by)
                if group_by:
                    stmt = stmt.group_by(*group_by)
                result = await session.execute(stmt)
                if return_scalar:
                    # scalar_one_or_none raises if multiple rows; here scalar_one_or_none or scalar_one works for a single scalar
                    return result.scalar_one_or_none()
                
                return result.scalars().all()
        except Exception as e:
            loki_logger.error(f"Error loading due reminders with filters {filters}: {e}")
            return None if return_scalar else []


    @classmethod
    async def load_due_reminders(cls) -> list:
        """Load all due, unsent reminders (globally)."""
        now = datetime.now(timezone.utc)
        return await cls._load_due_reminders(cls, filters=(cls.sent == False, cls.remind_at <= now))
    
    @classmethod
    async def load_due_reminders_from_user(cls, user_id) -> list:
        """Load all due, unsent reminders for a specific user."""
        # now = datetime.now(timezone.utc) # used for dev purposes
        return await cls._load_due_reminders(cls, filters=(cls.sent == False, cls.discord_user_id==str(user_id)))
    
    @classmethod
    async def load_due_reminders_ordered_by_due_time(cls, user_id: str = None) -> list:
        """Load due reminders ordered by earliest remind_at time first, optionally for a user."""
        
        filters = [cls.sent == False]
        if user_id:
            filters.append(cls.discord_user_id == str(user_id))
        
        await cls._load_due_reminders(
            cls,
            filters=filters,
            order_by=(cls.remind_at.desc(),), 
            group_by=(cls.list_id)
        )

    @classmethod
    async def get_next_list_id_for_user(cls, user_id: str) -> int:
        """Return the next available list_id for a given user using abstraction."""
        max_id = await cls._load_due_reminders(
            func.max(cls.list_id),
            filters=(cls.discord_user_id == user_id, cls.sent == False),
            return_scalar=True
        )
        return (max_id or 0) + 1


    def is_due(self) -> bool:
        """Check if this reminder is due (synchronous)."""
        from sqlalchemy.exc import SQLAlchemyError
        try:
            connector = SqlAlchemyConnector.load("spheredefaultasynccreds")
            engine = connector.get_engine()
            with Session(engine) as session:
                result = session.execute(
                    select(self.remind_at)
                    .where(self.id == self.id, self.sent == False)
                )
                session.close()
                
                remind_at = result.scalar_one_or_none()
                if remind_at is None:
                    return False
                return datetime.now(timezone.utc) >= remind_at
        except SQLAlchemyError as e:
            loki_logger.error(f"Database error while checking is_due: {e}")
            return False

    async def store_into_db(self) -> None:
        """Store this reminder into the database (async)."""
        from sqlalchemy.exc import SQLAlchemyError
        connector = await SqlAlchemyConnector.load("spheredefaultcreds")
        engine = connector.get_engine()
        
        #self.list_id = await self.__class__.get_max_list_id_from_user(user_id=self.discord_user_id) + 1
        
        self.list_id = await self.__class__.get_next_list_id_for_user(user_id=self.discord_user_id)
        
        #Base.metadata.create_all(bind=engine) # dev purposes
        try:
            with Session(engine) as session:
                session.add(self)
                session.commit()
                session.close()
                loki_logger.info(f"Stored a reminder into the database.")
        except SQLAlchemyError as e:
            loki_logger.error(f"Failed to store reminder: {e}")

    async def mark_as_sent(self) -> None:
        """Mark this reminder as sent in the database (async)."""
        # from sqlalchemy.exc import SQLAlchemyError
        try:
            connector = await SqlAlchemyConnector.load("spheredefaultasynccreds")
            async_engine = connector.get_engine()
            async with AsyncSession(async_engine) as session:
                async with session.begin():
                    db_reminder = await session.get(Reminder, self.id)
                    if db_reminder:
                        db_reminder.sent = True
                await session.commit()
                await session.close()
        except Exception as e:
            loki_logger.error(f"Error marking reminder as sent: {e}")
            
    
    async def send_push_notification(self):
        send_notification_to_ntfy(ntfy_topic="/reminder_system", message=self.message)