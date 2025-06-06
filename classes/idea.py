from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Table
from base import Base
from prefect_sqlalchemy import SqlAlchemyConnector
from sqlalchemy.orm import Session
from datetime import datetime, timezone
#from sqlalchemy import select, func
from handlers.loki_logging import get_logger


from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession


loki_logger = get_logger(
    "sphere.discord.python",
    level="debug",
    labels={
        "app": "sphere",
        "env": "dev",
        "service": "discord_bot",
        "lang": "python",
    }
)

# @future-schema idea_catcher

idea_tag_association = Table(
    'idea_tag_association',
    Base.metadata,
    Column('idea_id', Integer, ForeignKey('idea.id')),
    Column('tag_id', Integer, ForeignKey('tag.id'))
)

class Category(Base):
    __tablename__ = 'category'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    
    ideas = relationship("Idea", back_populates="category")

    def __repr__(self):
        return f"<Category(name={self.name})>"

    @classmethod
    async def get_or_create(cls, name: str) -> "Category":
        """Get an existing Category by name or create a new one if it doesn't exist."""
        connector = await SqlAlchemyConnector.load("spheredefaultasynccreds")
        engine = connector.get_engine()

        try:
            async with AsyncSession(engine) as session:
                result = await session.execute(select(cls).where(cls.name == name))
                existing = result.scalars().first()
                if existing:
                    return existing

                new_category = cls(name=name)
                session.add(new_category)
                await session.commit()
                await session.refresh(new_category)
                loki_logger.info(f"Created new category: {new_category}")
                return new_category

        except SQLAlchemyError as e:
            loki_logger.error(f"Error during fetching or creating a category named '{name}': {e}")
            raise

    
class Tag(Base):
    __tablename__ = 'tag'
    
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True)
    
    ideas = relationship(
        "Idea",
        secondary=idea_tag_association,
        back_populates="tags"
    )

    def __repr__(self):
        return f"<Tag(name={self.name})>"
    
    @classmethod
    async def get_or_create(cls, name: str) -> "Tag":
        """Returns an existing tag or creates a new one."""
        connector = await SqlAlchemyConnector.load("spheredefaultasynccreds")
        engine = connector.get_engine()

        try:
            async with AsyncSession(engine) as session:
                result = await session.execute(select(cls).where(cls.name == name))
                existing = result.scalars().first()
                if existing:
                    return existing

                new_tag = cls(name=name)
                session.add(new_tag)
                await session.commit()
                await session.refresh(new_tag)
                loki_logger.info(f"Created new tag: {new_tag}")
                return new_tag

        except SQLAlchemyError as e:
            loki_logger.error(f"Error during fetching or creating a tag named '{name}': {e}")
            raise

class Idea(Base):
    __tablename__ = 'idea'
    
    id = Column(Integer, primary_key=True)
    title = Column(String, nullable=False)
    content = Column(String, nullable=True)

    category_id = Column(Integer, ForeignKey('category.id'), nullable=False)
    category = relationship("Category", back_populates="ideas")

    tags = relationship(
        "Tag",
        secondary=idea_tag_association,
        back_populates="ideas"
    )

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    reminder_id = Column(Integer, ForeignKey('reminders.id'))
    reminder = relationship("Reminder", back_populates="idea", uselist=False)

    archived = Column(Boolean, nullable=False, default=False)
    pinned = Column(Boolean, nullable=False, default=False)
    source = Column(String, nullable=True)

    def __repr__(self):
        return f"<Idea(title={self.title})>"
    
    async def store_into_db(self) -> None:
        """Store this idea in the database (async.)"""
        from sqlalchemy.exc import SQLAlchemyError
        connector = await SqlAlchemyConnector.load("spheredefaultcreds")
        engine = connector.get_engine()
        
        Base.metadata.create_all(bind=engine) # dev purposes
        
        try:
            with Session(engine) as session:
                session.add(self)
                session.commit()
                session.close()
                loki_logger.info(f"Stored an idea into the database.")
        except SQLAlchemyError as e:
            loki_logger.error(f"Failed to store idea: {e}")