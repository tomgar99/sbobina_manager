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

    def to_dict(self):
        return {
            "date": self.date.isoformat(),
            "subject": self.subject,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "location": self.location,
            "duration_hours": self.duration_hours,
            "is_supervision": self.is_supervision
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            date=date.fromisoformat(data["date"]),
            subject=data["subject"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            location=data["location"],
            duration_hours=data["duration_hours"],
            is_supervision=data.get("is_supervision", False)
        )

@dataclass
class Shift:
    lesson: Lesson
    sbobinatori: List[User]
    revisori: List[User]

    def to_dict(self):
        return {
            "lesson": self.lesson.to_dict(),
            "sbobinatori_emails": [u.email for u in self.sbobinatori],
            "revisori_emails": [u.email for u in self.revisori]
        }

    @classmethod
    def from_dict(cls, data, all_users: List[User]):
        # Reconstruct users from emails
        sbob = [u for u in all_users if u.email in data["sbobinatori_emails"]]
        rev = [u for u in all_users if u.email in data["revisori_emails"]]
        return cls(
            lesson=Lesson.from_dict(data["lesson"]),
            sbobinatori=sbob,
            revisori=rev
        )
