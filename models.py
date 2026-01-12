from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime, date

@dataclass
class User:
    name: str
    email: str
    phone: str
    role: str  # "Sbobinatore", "Revisore", "Admin"
    password: str = "password123" # Default for migration
    unavailable_dates: List[date] = field(default_factory=list)
    blacklist_subjects: List[str] = field(default_factory=list)
    shifts_assigned: int = 0
    last_shift_date: Optional[date] = None

    def to_dict(self):
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "role": self.role,
            "password": self.password,
            "unavailable_dates": [d.isoformat() for d in self.unavailable_dates],
            "blacklist_subjects": self.blacklist_subjects,
            "shifts_assigned": self.shifts_assigned,
            "last_shift_date": self.last_shift_date.isoformat() if self.last_shift_date else None
        }

    @classmethod
    def from_dict(cls, data):
        u = cls(
            name=data["name"],
            email=data["email"],
            phone=data["phone"],
            role=data["role"],
            password=data.get("password", "password123")
        )
        u.unavailable_dates = [date.fromisoformat(d) for d in data.get("unavailable_dates", [])]
        u.blacklist_subjects = data.get("blacklist_subjects", [])
        u.shifts_assigned = data.get("shifts_assigned", 0)
        if data.get("last_shift_date"):
            u.last_shift_date = date.fromisoformat(data["last_shift_date"])
        return u

@dataclass
class Lesson:
    date: date
    subject: str
    start_time: str
    end_time: str
    location: str
    duration_hours: float
    is_supervision: bool = False
    
    @property
    def key(self):
        return f"{self.date}_{self.subject}"

@dataclass
class Shift:
    lesson: Lesson
    sbobinatori: List[User]
    revisori: List[User]
