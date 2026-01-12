import pandas as pd
import numpy as np
import json
import os
import re
from datetime import datetime, date
from typing import List, Dict, Tuple
from models import User, Lesson, Shift

import streamlit as st
try:
    from supabase import create_client, Client
except ImportError:
    create_client = None

DATA_FILE = "users.json"

class DataManager:
    @staticmethod
    def _get_supabase():
        """Returns Supabase client if secrets are set, else None."""
        try:
            # Check if secrets exist
            if "SUPABASE_URL" in st.secrets and "SUPABASE_KEY" in st.secrets:
                return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])
        except FileNotFoundError:
            pass # No secrets file
        except Exception as e:
            print(f"Supabase init error: {e}")
        return None

    @staticmethod
    def load_users() -> List[User]:
        sb = DataManager._get_supabase()
        if sb:
            try:
                # Fetch all users
                response = sb.table("users").select("*").execute()
                users_data = response.data
                
                # Convert back to User objects
                # Note: Supabase might return dates as strings, which from_dict handles
                return [User.from_dict(u) for u in users_data]
            except Exception as e:
                st.error(f"Errore caricamento Database: {e}")
                return []
        
        # Fallback to Local JSON
        if not os.path.exists(DATA_FILE):
            return []
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                return [User.from_dict(u) for u in data]
        except Exception as e:
            print(f"Error loading users: {e}")
            return []

    @staticmethod
    def save_users(users: List[User]):
        sb = DataManager._get_supabase()
        if sb:
            try:
                # Upsert all users
                # We convert all users to dicts
                users_data = [u.to_dict() for u in users]
                
                # Perform upsert
                # 'email' should be the primary key in Supabase
                sb.table("users").upsert(users_data).execute()
            except Exception as e:
                st.error(f"Errore salvataggio Database: {e}")
        else:
            # Fallback to Local JSON
            try:
                with open(DATA_FILE, 'w') as f:
                    json.dump([u.to_dict() for u in users], f, indent=4)
            except Exception as e:
                print(f"Error saving users: {e}")

def parse_excel_schedule(file) -> List[Lesson]:
    try:
        df = pd.read_excel(file, header=None)
    except Exception as e:
        print(f"Error reading excel: {e}")
        return []

    lessons = []
    
    # Map column index to current date for the block
    col_to_date = {} 
    
    # Italian days mapping for robustness
    # Looking for pattern "day dd/mm"
    date_pattern = r"(lun|mar|mer|gio|ven|sab|dom).*?(\d{1,2})/(\d{1,2})"

    for index, row in df.iterrows():
        # Check if this is a "Header Row" containing dates
        row_is_header = False
        new_dates_found = {}
        
        for col_idx, cell_value in enumerate(row):
            if pd.isna(cell_value):
                continue
            
            s_val = str(cell_value).lower().strip()
            # Check for date pattern
            match = re.search(date_pattern, s_val)
            if match:
                try:
                    day = int(match.group(2))
                    month = int(match.group(3))
                    
                    # Guess Year (MVP: Current Year)
                    today = date.today()
                    year = today.year
                    # Simple heuristic for Academic Year crossing (e.g. Jan 2026 vs Sept 2025)
                    if month < 8 and today.month > 8:
                        year += 1 
                        
                    d_obj = date(year, month, day)
                    new_dates_found[col_idx] = d_obj
                    row_is_header = True
                except ValueError:
                    pass
        
        if row_is_header:
            col_to_date = new_dates_found
            continue
            
        # Parse Content Rows
        if not col_to_date:
            continue
            
        for col_idx, cell_value in enumerate(row):
            # Only look at columns that have a date assigned in this block
            if col_idx not in col_to_date or pd.isna(cell_value):
                continue
                
            text = str(cell_value).strip()
            if len(text) < 5: # Skip noise
                continue
                
            # Parse Cell: Subject \n Info \n Time
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            if not lines:
                continue
                
            # Regex for Time (e.g., 09:30 - 13:30 or 09.30-13.30)
            time_pattern = r"(\d{1,2}[:\.]\d{2})\s*-\s*(\d{1,2}[:\.]\d{2})"
            found_time = False
            duration = 2.0
            start_str = "00:00"
            
            # Scan lines for time (usually at end)
            for i in range(len(lines)-1, -1, -1):
                t_match = re.search(time_pattern, lines[i])
                if t_match:
                    start_str = t_match.group(1).replace('.', ':')
                    end_str = t_match.group(2).replace('.', ':')
                    found_time = True
                    
                    try:
                        fmt = "%H:%M"
                        t1 = datetime.strptime(start_str, fmt)
                        t2 = datetime.strptime(end_str, fmt)
                        duration = (t2 - t1).total_seconds() / 3600
                    except:
                        pass
                    break
            
            if found_time:
                # Subject is usually Line 0
                subject = lines[0]
                
                # Filter out generic terms if needed
                l = Lesson(
                    date=col_to_date[col_idx],
                    subject=subject,
                    start_time=start_str,
                    end_time=end_str,
                    location=" ".join(lines[1:-1]) if len(lines) > 2 else "",
                    duration_hours=duration
                )
                lessons.append(l)
            
    return lessons

class ShiftOptimizer:
    def __init__(self, users: List[User], supervision_subjects: List[str], excluded_subjects: List[str] = None):
        self.users = users
        self.supervision_subjects = supervision_subjects
        self.excluded_subjects = excluded_subjects if excluded_subjects else []
        self.supervision_counters: Dict[str, int] = {s: 0 for s in supervision_subjects} 

    def sort_users_by_load(self, user_list: List[User]) -> List[User]:
        # Sort by: 1. Shifts Assigned (asc)
        import random
        random.shuffle(user_list) 
        return sorted(user_list, key=lambda u: u.shifts_assigned)

    def is_user_available(self, user: User, lesson: Lesson) -> bool:
        # 1. Unavailability Dates
        if lesson.date in user.unavailable_dates:
            return False
            
        # 2. Blacklist
        if lesson.subject in user.blacklist_subjects:
            return False
            
        # 3. Distance constraint (e.g. max 1 shift per day)
        if user.last_shift_date == lesson.date:
            return False
            
        return True

    def generate_shifts(self, lessons: List[Lesson]) -> List[Shift]:
        shifts = []
        
        # In a real app, sorting lessons chronologically is crucial here
        # lessons.sort(key=...)

        for lesson in lessons:
            if lesson.subject in self.excluded_subjects:
                continue

            is_supervision = lesson.subject in self.supervision_subjects
            lesson.is_supervision = is_supervision
            
            needed_sbob = 0
            needed_rev = 0
            
            # Determine needs
            if is_supervision:
                # Supervision Rules:
                # 0 Sbobinatori (implied by "Supervision Format")
                # <= 3 hours: 1 Supervisor
                # > 3 hours (aka 4): 2 Supervisors
                needed_sbob = 0
                if lesson.duration_hours <= 3.0:
                    needed_rev = 1
                else:
                    needed_rev = 2
            else:
                # Standard
                if lesson.duration_hours <= 2:
                    needed_sbob = 2
                    needed_rev = 1
                elif lesson.duration_hours <= 3:
                    needed_sbob = 3
                    needed_rev = 1
                else:
                    needed_sbob = 4
                    needed_rev = 2
            
            # Find candidates
            candidates = [u for u in self.users if self.is_user_available(u, lesson)]
            candidates = self.sort_users_by_load(candidates)
            
            assigned_sbob = []
            assigned_rev = []
            
            # Assign Sbobinatori
            for _ in range(needed_sbob):
                # Filter for Sbobinatori
                valid_c = [c for c in candidates if c.role == "Sbobinatore" and c not in assigned_sbob and c not in assigned_rev]
                if valid_c:
                    selected = valid_c[0]
                    selected.shifts_assigned += 1
                    selected.last_shift_date = lesson.date
                    assigned_sbob.append(selected)
            
            # Assign Revisori
            for _ in range(needed_rev):
                # Filter for Revisore
                valid_c = [c for c in candidates if c.role == "Revisore" and c not in assigned_sbob and c not in assigned_rev]
                if valid_c:
                    selected = valid_c[0]
                    selected.shifts_assigned += 1
                    selected.last_shift_date = lesson.date
                    assigned_rev.append(selected)
            
            shifts.append(Shift(lesson, assigned_sbob, assigned_rev))
            
        return shifts
