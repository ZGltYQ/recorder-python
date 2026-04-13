"""Database models and management for conversation storage."""

import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from sqlalchemy import create_engine, Column, String, DateTime, Text, ForeignKey, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session

from ..utils.logger import get_logger
from ..utils.config import get_config

logger = get_logger(__name__)

Base = declarative_base()


class ConversationSession(Base):
    """Represents a conversation session."""

    __tablename__ = "conversations"

    id = Column(String, primary_key=True)
    title = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship(
        "ConversationMessage", back_populates="session", cascade="all, delete-orphan"
    )


class ConversationMessage(Base):
    """Represents a message in a conversation."""

    __tablename__ = "messages"

    id = Column(String, primary_key=True)
    session_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    speaker = Column(String, nullable=True)
    text = Column(Text, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    is_question = Column(Boolean, default=False)
    ai_response = Column(Text, nullable=True)
    message_id = Column(String, nullable=True)  # External message ID for tracking

    session = relationship("ConversationSession", back_populates="messages")


@dataclass
class MessageData:
    """Data class for message information."""

    id: str
    speaker: Optional[str]
    text: str
    timestamp: datetime
    is_question: bool
    ai_response: Optional[str]
    message_id: Optional[str]


@dataclass
class SessionData:
    """Data class for session information."""

    id: str
    title: Optional[str]
    created_at: datetime
    updated_at: datetime
    messages: List[MessageData]


class DatabaseManager:
    """Manages database operations for conversations."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            config = get_config()
            db_path = config.get_data_dir() / "conversations.db"

        self.db_path = db_path
        self.engine = None
        self.SessionLocal = None

    def initialize(self):
        """Initialize the database connection."""
        try:
            # Ensure directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create engine
            self.engine = create_engine(f"sqlite:///{self.db_path}", echo=False)

            # Create tables
            Base.metadata.create_all(self.engine)

            # Create session factory
            self.SessionLocal = sessionmaker(bind=self.engine)

            logger.info("Database initialized", path=str(self.db_path))
            return True

        except Exception as e:
            logger.error("Failed to initialize database", error=str(e))
            return False

    def get_db_session(self) -> Session:
        """Get a database session."""
        if self.SessionLocal is None:
            raise RuntimeError("Database not initialized")
        return self.SessionLocal()

    def create_session(self, title: Optional[str] = None) -> str:
        """Create a new conversation session."""
        session_id = str(uuid.uuid4())

        with self.get_db_session() as db:
            session = ConversationSession(
                id=session_id,
                title=title or f"Recording {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            )
            db.add(session)
            db.commit()

        logger.info("Created conversation session", session_id=session_id, title=title)
        return session_id

    def add_message(
        self,
        session_id: str,
        text: str,
        speaker: Optional[str] = None,
        message_id: Optional[str] = None,
        is_question: bool = False,
        ai_response: Optional[str] = None,
    ) -> str:
        """Add a message to a session."""
        msg_id = str(uuid.uuid4())

        with self.get_db_session() as db:
            message = ConversationMessage(
                id=msg_id,
                session_id=session_id,
                speaker=speaker,
                text=text,
                is_question=is_question,
                ai_response=ai_response,
                message_id=message_id,
            )
            db.add(message)

            # Update session timestamp
            session = db.query(ConversationSession).filter_by(id=session_id).first()
            if session:
                session.updated_at = datetime.utcnow()

            db.commit()

        return msg_id

    def update_message_speaker(self, message_id: str, speaker: str) -> bool:
        """Update the speaker for a message."""
        with self.get_db_session() as db:
            message = db.query(ConversationMessage).filter_by(message_id=message_id).first()
            if message:
                message.speaker = speaker
                db.commit()
                logger.debug("Updated message speaker", message_id=message_id, speaker=speaker)
                return True
            else:
                # Try by internal ID
                message = db.query(ConversationMessage).filter_by(id=message_id).first()
                if message:
                    message.speaker = speaker
                    db.commit()
                    return True

        logger.warning("Message not found for speaker update", message_id=message_id)
        return False

    def update_ai_response(self, message_id: str, response: str) -> bool:
        """Update the AI response for a message."""
        with self.get_db_session() as db:
            message = db.query(ConversationMessage).filter_by(message_id=message_id).first()
            if message:
                message.ai_response = response
                db.commit()
                return True
        return False

    def get_session_messages(self, session_id: str) -> List[MessageData]:
        """Get all messages for a session."""
        with self.get_db_session() as db:
            messages = (
                db.query(ConversationMessage)
                .filter_by(session_id=session_id)
                .order_by(ConversationMessage.timestamp)
                .all()
            )

            return [
                MessageData(
                    id=m.id,
                    speaker=m.speaker,
                    text=m.text,
                    timestamp=m.timestamp,
                    is_question=m.is_question,
                    ai_response=m.ai_response,
                    message_id=m.message_id,
                )
                for m in messages
            ]

    def get_all_sessions(self) -> List[Dict[str, Any]]:
        """Get all sessions with message counts."""
        with self.get_db_session() as db:
            sessions = (
                db.query(ConversationSession).order_by(ConversationSession.updated_at.desc()).all()
            )

            return [
                {
                    "id": s.id,
                    "title": s.title,
                    "created_at": s.created_at.isoformat(),
                    "updated_at": s.updated_at.isoformat(),
                    "message_count": len(s.messages),
                }
                for s in sessions
            ]

    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session with all its messages."""
        with self.get_db_session() as db:
            session = db.query(ConversationSession).filter_by(id=session_id).first()

            if not session:
                return None

            return SessionData(
                id=session.id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                messages=[
                    MessageData(
                        id=m.id,
                        speaker=m.speaker,
                        text=m.text,
                        timestamp=m.timestamp,
                        is_question=m.is_question,
                        ai_response=m.ai_response,
                        message_id=m.message_id,
                    )
                    for m in sorted(session.messages, key=lambda x: x.timestamp)
                ],
            )

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages."""
        with self.get_db_session() as db:
            session = db.query(ConversationSession).filter_by(id=session_id).first()
            if session:
                db.delete(session)
                db.commit()
                logger.info("Deleted session", session_id=session_id)
                return True
        return False

    def export_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Export a session to a dictionary."""
        session = self.get_session(session_id)

        if not session:
            return None

        return {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "speaker": m.speaker,
                    "text": m.text,
                    "timestamp": m.timestamp.isoformat(),
                    "is_question": m.is_question,
                    "ai_response": m.ai_response,
                }
                for m in session.messages
            ],
        }

    def close(self):
        """Close the database connection."""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")


# Global database instance
_db_manager: Optional[DatabaseManager] = None


def get_database() -> DatabaseManager:
    """Get the global database manager."""
    global _db_manager
    if _db_manager is None:
        _db_manager = DatabaseManager()
        _db_manager.initialize()
    return _db_manager
