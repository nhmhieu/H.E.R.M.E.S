from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


class DialogueState(Enum):
    IDLE = "IDLE"
    AWAITING_GRADES = "AWAITING_GRADES"
    AWAITING_SCHEDULE = "AWAITING_SCHEDULE"
    AWAITING_CLARIFICATION = "AWAITING_CLARIFICATION"


class ConversationSession:
    def __init__(self, session_id: str):
        self.session_id: str = session_id
        self.state: DialogueState = DialogueState.IDLE
        self.slots: Dict[str, Any] = {}
        self.history: List[Dict[str, str]] = []
        self.last_active: datetime = datetime.now()

    def is_expired(self, timeout_minutes: int = 15) -> bool:
        return datetime.now() - self.last_active > timedelta(minutes=timeout_minutes)

    def add_message(self, role: str, content: str):
        self.history.append({"role": role, "content": content})
        self.last_active = datetime.now()

    def set_state(
        self,
        new_state: DialogueState,
        initial_slots: Optional[Dict[str, Any]] = None,
    ):
        self.state = new_state
        if initial_slots:
            self.slots.update(initial_slots)
        self.last_active = datetime.now()

    def fill_slot(self, slot_name: str, value: Any):
        self.slots[slot_name] = value
        self.last_active = datetime.now()

    def get_slot(self, slot_name: str, default: Any = None) -> Any:
        return self.slots.get(slot_name, default)

    def reset(self):
        self.state = DialogueState.IDLE
        self.slots.clear()
        self.last_active = datetime.now()


class SessionManager:
    def __init__(self):
        self._sessions: Dict[str, ConversationSession] = {}

    def get_or_create(self, session_id: str = "default_user") -> ConversationSession:
        if session_id not in self._sessions or self._sessions[session_id].is_expired():
            self._sessions[session_id] = ConversationSession(session_id)
        return self._sessions[session_id]

    def remove_session(self, session_id: str):
        if session_id in self._sessions:
            del self._sessions[session_id]
