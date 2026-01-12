import streamlit as st
import pandas as pd
from datetime import date
from utils import parse_excel_schedule, ShiftOptimizer, DataManager
from models import User

# --- Session State Initialization ---
if 'users' not in st.session_state:
    st.session_state.users = DataManager.load_users()

# Ensure we have at least one admin if empty
if not st.session_state.users:
    # Create default admin
    admin = User("Admin", "admin@email.com", "000", "Admin", password="admin")
    st.session_state.users.append(admin)
    DataManager.save_users(st.session_state.users)

if 'current_user' not in st.session_state:
    st.session_state.current_user = None

if 'lessons' not in st.session_state:
    st.session_state.lessons = []
if 'shifts' not in st.session_state:
    st.session_state.shifts = []
    # Try loading from DB
    loaded = DataManager.load_shifts(st.session_state.users)
    if loaded:
        st.session_state.shifts = loaded
        # Also reconstruct lessons from shifts if empty
        if 'lessons' not in st.session_state or not st.session_state.lessons:
             st.session_state.lessons = [s.lesson for s in loaded]

if 'supervision_subjects' not in st.session_state:
    st.session_state.supervision_subjects = []

# --- DB CONNECTION CHECK ---
sb_status = DataManager._get_supabase()
if not sb_status:
    st.warning("⚠️ ATTENZIONE: Database non connesso! Assicurati di aver impostato i Secrets su Streamlit Cloud.")
    # Debug info
    if "SUPABASE_URL" not in st.secrets:
         st.error("Secret 'SUPABASE_URL' mancante.")
    try:
        from supabase import create_client
    except ImportError:
        st.error("Libreria 'supabase' non installata corretamente.")

st.set_page_config(page_title="Sbobina Manager", layout="wide", page_icon="📱")

# --- CUSTOM CSS FOR MOBILE UX & HIDING TOOLBAR ---
st.markdown("""
<style>
    [data-testid="stToolbar"] {
        visibility: hidden;
        height: 0px;
    }
    footer {
        visibility: hidden;
    }
    #MainMenu {
        visibility: hidden;
    }
    header {
        visibility: hidden;
    }
    .shift-card {
        background-color: #f0f2f6;
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 10px;
        border-left: 5px solid #ff4b4b;
    }
    .shift-header {
        font-weight: bold;
        font-size: 1.1em;
        color: #31333F;
    }
    .shift-sub {
        color: #555;
        font-size: 0.9em;
    }
    .contact-info {
        font-size: 0.85em;
        margin-top: 5px;
        padding-left: 10px;
        border-left: 2px solid #ddd;
    }
</style>
""", unsafe_allow_html=True)

# --- AUTHENTICATION FLOW ---

def login_page():
    st.title("🏥 Sbobina Manager - Login")
    
    tab_login, tab_register = st.tabs(["Accedi", "Registrati"])
    
    with tab_login:
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.button("Login"):
            user = next((u for u in st.session_state.users if u.email == email and u.password == password), None)
            if user:
                st.session_state.current_user = user
                st.rerun()
            else:
                st.error("Credenziali non valide")

    with tab_register:
        new_name = st.text_input("Nome e Cognome")
        new_email = st.text_input("Email (Registrazione)")
        new_phone = st.text_input("Telefono")
        new_password = st.text_input("Password (Nuova)", type="password")
        new_role = st.selectbox("Ruolo", ["Sbobinatore", "Revisore"])
        
        if st.button("Crea Account"):
            if any(u.email == new_email for u in st.session_state.users):
                st.error("Email già registrata")
            elif new_name and new_email and new_password:
                new_user = User(new_name, new_email, new_phone, new_role, password=new_password)
                st.session_state.users.append(new_user)
                DataManager.save_users(st.session_state.users)
                st.success("Registrato! Ora puoi fare login.")
            else:
                st.warning("Compila tutti i campi.")

# --- MAIN APP FLOW ---

if not st.session_state.current_user:
    login_page()
else:
    # LOGGED IN
    user = st.session_state.current_user
    
    # Header & Logout
    c1, c2 = st.columns([8, 1])
    c1.title(f"Benvenuto, {user.name} ({user.role})")
    if c2.button("Logout"):
        st.session_state.current_user = None
        st.rerun()
        
    # ROUTING BASED ON ROLE
    if user.role == "Admin":
        # ================= ADMIN DASHBOARD =================
        st.header("Admin Dashboard")
        
        # Tabs for Admin
        ad_tab1, ad_tab2, ad_tab3 = st.tabs(["⚡ Gestione Turni", "👥 Gestione Utenti", "🗓️ Calendario Pubblico"])
        
        with ad_tab1:
            # Sub-tabs for Shifts
            shift_mode = st.radio("Modalità", ["🪄 Generatore Automatico", "🛠️ Editor Manuale"], horizontal=True)
            
            if shift_mode == "🪄 Generatore Automatico":
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.subheader("1. Carica Calendario")
                    uploaded_file = st.file_uploader("Upload Excel Calendario", type=["xlsx"])
                    if uploaded_file and st.button("Analizza File"):
                        st.session_state.lessons = parse_excel_schedule(uploaded_file)
                        st.success(f"Trovate {len(st.session_state.lessons)} lezioni!")
                        
                    st.subheader("3. Configura Materie")
                    if st.session_state.lessons:
                        all_subjects = sorted(list(set(l.subject for l in st.session_state.lessons)))
                        
                        c1_sub, c2_sub = st.columns(2)
                        with c1_sub:
                            st.session_state.supervision_subjects = st.multiselect(
                                "Materie 'Supervisione'", 
                                options=all_subjects,
                                default=st.session_state.supervision_subjects
                            )
                        with c2_sub:
                            if 'excluded_subjects' not in st.session_state:
                                st.session_state.excluded_subjects = []
                            st.session_state.excluded_subjects = st.multiselect(
                                "Materie ESCLUSE", 
                                options=all_subjects,
                                default=st.session_state.excluded_subjects
                            )
                        
                    st.subheader("4. Generazione")
                    if st.button("Genera Turni 🎲"):
                        if not st.session_state.lessons:
                            st.error("Prima carica un calendario!")
                        else:
                            optimizer = ShiftOptimizer(
                                st.session_state.users, 
                                st.session_state.supervision_subjects,
                                st.session_state.get('excluded_subjects', [])
                            )
                            st.session_state.shifts = optimizer.generate_shifts(st.session_state.lessons)
                            if DataManager.save_shifts(st.session_state.shifts):
                                st.success("Turni generati e SALVATI nel database!")
                            else:
                                st.error("Errore nel salvataggio!")
                
                with col2:
                    st.subheader("2. Anteprima")
                    if st.session_state.shifts:
                        st.write("### Turni Generati")
                        data = []
                        for s in st.session_state.shifts:
                            sbob_names = ", ".join([u.name for u in s.sbobinatori])
                            rev_names = ", ".join([u.name for u in s.revisori])
                            data.append({
                                "Date": s.lesson.date.strftime('%d/%m/%Y'),
                                "Materia": s.lesson.subject,
                                "Orario": f"{s.lesson.start_time}-{s.lesson.end_time}",
                                "Sbobinatori": sbob_names,
                                "Revisori": rev_names
                            })
                        st.dataframe(pd.DataFrame(data), use_container_width=True)
                        
                    elif st.session_state.lessons:
                        st.write("### Lezioni Caricate")
                        df_lessons = pd.DataFrame([vars(l) for l in st.session_state.lessons])
                        st.dataframe(df_lessons, use_container_width=True)
                    else:
                        st.info("Attesa file...")
            
            else:
                # === MANUAL EDITOR ===
                st.subheader("🛠️ Gestione Manuale Turni")
                
                c_edit, c_add = st.columns([2, 1])
                
                with c_add:
                    st.markdown("### ➕ Aggiungi Nuovo Turno")
                    with st.form("add_shift_form"):
                        new_date = st.date_input("Data", date.today())
                        new_subj = st.text_input("Materia")
                        new_start = st.text_input("Ora Inizio", "09:00")
                        new_end = st.text_input("Ora Fine", "11:00")
                        
                        if st.form_submit_button("Aggiungi Turno"):
                            if new_subj:
                                # Create Lesson
                                l = Lesson(new_date, new_subj, new_start, new_end, "", 2.0)
                                s = Shift(l, [], [])
                                st.session_state.shifts.append(s)
                                DataManager.save_shifts(st.session_state.shifts)
                                st.success("Turno Aggiunto!")
                                st.rerun()
                            else:
                                st.warning("Compila materia")

                with c_edit:
                    st.markdown("### ✏️ Modifica Esistente")
                    if st.session_state.shifts:
                        # Sort for easier finding
                        shifts_list = sorted(st.session_state.shifts, key=lambda x: (x.lesson.date, x.lesson.start_time))
                        # Create labels
                        shift_options = {f"{s.lesson.date.strftime('%d/%m/%Y')} - {s.lesson.subject}": s for s in shifts_list}
                        
                        selected_label = st.selectbox("Seleziona Turno", list(shift_options.keys()))
                        if selected_label:
                            target_shift = shift_options[selected_label]
                            
                            with st.form("edit_shift_manual"):
                                c1, c2 = st.columns(2)
                                with c1:
                                    e_date = st.date_input("Data", target_shift.lesson.date)
                                    e_subj = st.text_input("Materia", target_shift.lesson.subject)
                                with c2:
                                    e_start = st.text_input("Inizio", target_shift.lesson.start_time)
                                    e_end = st.text_input("Fine", target_shift.lesson.end_time)
                                
                                st.markdown("**Assegnazioni**")
                                all_user_names = [u.name for u in st.session_state.users]
                                
                                # Current assigned
                                cur_sbob = [u.name for u in target_shift.sbobinatori]
                                cur_rev = [u.name for u in target_shift.revisori]
                                
                                new_sbob_names = st.multiselect("Sbobinatori", all_user_names, default=cur_sbob)
                                new_rev_names = st.multiselect("Revisori", all_user_names, default=cur_rev)
                                
                                c_save, c_del = st.columns([4, 1])
                                saved = c_save.form_submit_button("Salva Modifiche")
                                
                                if saved:
                                    # Update Lesson
                                    target_shift.lesson.date = e_date
                                    target_shift.lesson.subject = e_subj
                                    target_shift.lesson.start_time = e_start
                                    target_shift.lesson.end_time = e_end
                                    
                                    # Update Users (Map names back to objects)
                                    target_shift.sbobinatori = [u for u in st.session_state.users if u.name in new_sbob_names]
                                    target_shift.revisori = [u for u in st.session_state.users if u.name in new_rev_names]
                                    
                                    if DataManager.save_shifts(st.session_state.shifts):
                                        st.success("Modifiche Salvate!")
                                        st.rerun()
                                    else:
                                        st.error("Errore salvataggio")

                            # Delete button check
                            with st.expander("🗑️ Rimuovi questo turno"):
                                if st.button("Elimina Turno", key=f"del_{target_shift.lesson.key}"):
                                    st.session_state.shifts.remove(target_shift)
                                    DataManager.save_shifts(st.session_state.shifts)
                                    st.success("Cancellato!")
                                    st.rerun()
                    else:
                        st.info("Nessun turno presente.")
        
        with ad_tab2:
            st.subheader("Gestione Utenti Avanzata")
            
            tab_list, tab_edit, tab_create = st.tabs(["Lista Utenti", "Modifica Utente", "➕ Crea Nuovo Utente"])
            
            with tab_list:
                # Added Password to the view as requested
                st.dataframe(pd.DataFrame([{"Nome": u.name, "Email": u.email, "Ruolo": u.role, "Password": u.password} for u in st.session_state.users]), use_container_width=True)
                
            with tab_edit:
                user_to_edit_name = st.selectbox("Seleziona Utente da Modificare", [u.name for u in st.session_state.users])
                user_to_edit = next((u for u in st.session_state.users if u.name == user_to_edit_name), None)
                
                if user_to_edit:
                    with st.form("edit_user_form"):
                        st.write(f"Modifica dati di: **{user_to_edit.name}**")
                        # ... (keep existing edit form logic)
                        new_role = st.selectbox("Ruolo", ["Sbobinatore", "Revisore", "Admin"], index=["Sbobinatore", "Revisore", "Admin"].index(user_to_edit.role))
                        new_email = st.text_input("Email", user_to_edit.email)
                        new_password = st.text_input("Password", user_to_edit.password) # Added password edit
                        new_phone = st.text_input("Telefono", user_to_edit.phone)
                        
                        st.write("---")
                        st.write("**Date Indisponibili**")
                        current_dates = user_to_edit.unavailable_dates
                        dates_to_remove = st.multiselect("Rimuovi date esistenti", options=current_dates, format_func=lambda x: x.strftime('%d/%m/%Y'))
                        new_date = st.date_input("Aggiungi nuova data", value=None)
                        
                        st.write("**Materie Blacklist**")
                        if st.session_state.lessons:
                            all_subjects = sorted(list(set(l.subject for l in st.session_state.lessons)))
                            new_blacklist = st.multiselect("Seleziona materie proibite", options=all_subjects, default=user_to_edit.blacklist_subjects)
                        else:
                            st.warning("Carica calendario per vedere materie")
                            new_blacklist = user_to_edit.blacklist_subjects
                        
                        col_save, col_del = st.columns([4, 1])
                        
                        saved = col_save.form_submit_button("💾 Salva Modifiche")
                        
                        if saved:
                            user_to_edit.role = new_role
                            user_to_edit.email = new_email
                            user_to_edit.password = new_password
                            user_to_edit.phone = new_phone
                            for d in dates_to_remove: 
                                if d in user_to_edit.unavailable_dates: user_to_edit.unavailable_dates.remove(d)
                            if new_date and new_date not in user_to_edit.unavailable_dates: user_to_edit.unavailable_dates.append(new_date)
                            user_to_edit.blacklist_subjects = new_blacklist
                            DataManager.save_users(st.session_state.users)
                            st.success(f"Utente {user_to_edit.name} aggiornato!")
                            st.rerun()

                    # Delete button outside the form to avoid submission conflicts or accidental submits
                    st.write("---")
                    with st.expander("🗑️ Zona Pericolo: Elimina Utente"):
                        st.warning(f"Stai per eliminare definitivamente {user_to_edit.name}.")
                        if st.button("Conferma Eliminazione Utente", type="primary"):
                            try:
                                # Remove from Session State
                                st.session_state.users.remove(user_to_edit)
                                # Remove from DB
                                DataManager.delete_user(user_to_edit)
                                # Save state (this helps sync JSON fallback if used, though delete_user handles Supabase separately)
                                DataManager.save_users(st.session_state.users)
                                st.success("Utente eliminato.")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Errore: {e}")

            with tab_create:
                st.subheader("Crea Nuovo Utente (Admin)")
                with st.form("admin_create_user"):
                    c_name = st.text_input("Nome e Cognome")
                    c_email = st.text_input("Email")
                    c_phone = st.text_input("Telefono")
                    c_role = st.selectbox("Ruolo", ["Sbobinatore", "Revisore", "Admin"])
                    c_pass = st.text_input("Password", value="1234")
                    
                    if st.form_submit_button("Crea Utente"):
                        if any(u.email == c_email for u in st.session_state.users):
                            st.error("Esiste già un utente con questa email.")
                        elif c_name and c_email:
                            new_u = User(c_name, c_email, c_phone, c_role, password=c_pass)
                            st.session_state.users.append(new_u)
                            DataManager.save_users(st.session_state.users)
                            st.success(f"Utente {c_name} creato con successo!")
                            st.rerun()
                        else:
                            st.warning("Compila almeno Nome ed Email.")

        with ad_tab3:
            st.subheader("🗓️ Calendario Pubblico Completo")
            if st.session_state.shifts:
                # Helper to create view
                data = []
                for s in st.session_state.shifts:
                    sbob_names = ", ".join([u.name for u in s.sbobinatori])
                    rev_names = ", ".join([u.name for u in s.revisori])
                    data.append({
                        "Data": s.lesson.date.strftime('%d/%m/%Y'),
                        "Materia": s.lesson.subject,
                        "Orario": f"{s.lesson.start_time} ({s.lesson.duration_hours}h)",
                        "Sbobinatori": sbob_names,
                        "Revisori": rev_names
                    })
                st.dataframe(pd.DataFrame(data), use_container_width=True, height=600)
            else:
                st.info("Nessun turno generato.")


    else:
        # ================= USER DASHBOARD (Sbobinatore/Revisore) =================
        st.header("Area Personale")
        
        # Tabs for better mobile navigation
        u_tab1, u_tab2, u_tab3 = st.tabs(["📅 I Miei Turni", "🗓️ Calendario Completo", "⚙️ Preferenze"])
        
        with u_tab2:
            st.subheader("Calendario Generale")
            if st.session_state.shifts:
                st.caption("Griglia Settimanale Completa")
                
                shifts_data = []
                for s in st.session_state.shifts:
                    staff = []
                    if s.sbobinatori:
                        staff.append(f"✍️ {', '.join([u.name for u in s.sbobinatori])}")
                    if s.revisori:
                        staff.append(f"👀 {', '.join([u.name for u in s.revisori])}")
                    
                    staff_str = " | ".join(staff)
                    if not staff: staff_str = "⚠ NON ASSEGNATO"
                    
                    shifts_data.append({
                        "Data": s.lesson.date, # Keep object for sorting
                        "Giorno": s.lesson.date.strftime('%d/%m/%Y'),
                        "Orario": f"{s.lesson.start_time}",
                        "Materia": s.lesson.subject,
                        "Assegnazioni": staff_str
                    })
                
                df_view = pd.DataFrame(shifts_data).sort_values(by=["Data", "Orario"])
                # Hide raw date object
                st.dataframe(
                    df_view[["Giorno", "Orario", "Materia", "Assegnazioni"]], 
                    use_container_width=True, 
                    height=600,
                    hide_index=True,
                    column_config={
                        "Giorno": st.column_config.TextColumn("Data", width="small"),
                        "Orario": st.column_config.TextColumn("Ora", width="small"),
                        "Materia": st.column_config.TextColumn("Materia", width="medium"),
                        "Assegnazioni": st.column_config.TextColumn("Team Assegnato", width="large"),
                    }
                )
            else:
                st.info("I turni non sono ancora stati generati.")

        with u_tab3:
            st.subheader("Le mie Preferenze")
            st.info(f"Stai operando come: **{user.role}**")
            
            # Unavailable Dates
            with st.expander("Gioni Indisponibili", expanded=False):
                d = st.date_input("Aggiungi data", value=None)
                if st.button("Segna Indisponibilità"):
                    if d and d not in user.unavailable_dates:
                        user.unavailable_dates.append(d)
                        DataManager.save_users(st.session_state.users)
                        st.success("Salvato!")
                        st.rerun()
                
                if user.unavailable_dates:
                    st.write("Date salvate:")
                    for date_obj in user.unavailable_dates:
                        col_d1, col_d2 = st.columns([4,1])
                        col_d1.text(date_obj.strftime('%d/%m/%Y'))
                        if col_d2.button("❌", key=f"del_{date_obj}"):
                            user.unavailable_dates.remove(date_obj)
                            DataManager.save_users(st.session_state.users)
                            st.rerun()
                else:
                    st.caption("Nessuna data segnata.")
            
            # Blacklist
            with st.expander("Materie Blacklist", expanded=False):
                if st.session_state.lessons:
                    all_subjects = sorted(list(set(l.subject for l in st.session_state.lessons)))
                    blacklist = st.multiselect(
                        "Materie da evitare",
                        options=all_subjects,
                        default=user.blacklist_subjects
                    )
                    if st.button("Aggiorna Blacklist"):
                        user.blacklist_subjects = blacklist
                        DataManager.save_users(st.session_state.users)
                        st.success("Salvato!")
                else:
                    st.warning("Calendario non ancora caricato dall'admin.")

        with u_tab1:
            st.subheader(f"Turni di {user.name}")
            
            if st.session_state.shifts:
                my_user_shifts = []
                for s in st.session_state.shifts:
                    if user in s.sbobinatori or user in s.revisori:
                        my_user_shifts.append(s)
                
                if my_user_shifts:
                    # Sort by date
                    my_user_shifts.sort(key=lambda x: x.lesson.date)
                    
                    for s in my_user_shifts:
                        role_in_shift = "Sbobinatore" if user in s.sbobinatori else "Revisore"
                        
                        # --- CARD UI ---
                        with st.container():
                            st.markdown(f"""
                            <div class="shift-card">
                                <div class="shift-header">{s.lesson.date.strftime('%d/%m/%Y')} | {s.lesson.start_time}</div>
                                <div class="shift-header" style="color:#000;">{s.lesson.subject}</div>
                                <div class="shift-sub">Ruolo: <b>{role_in_shift}</b> | Durata: {s.lesson.duration_hours}h</div>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            with st.expander("👥 Vedi Colleghi & Contatti"):
                                st.markdown("**Il tuo Team:**")
                                
                                # Gather all people in this shift excluding self
                                team = []
                                for u in s.sbobinatori:
                                    if u != user: team.append((u, "Sbobinatore"))
                                for u in s.revisori:
                                    if u != user: team.append((u, "Revisore"))
                                
                                if team:
                                    for mate, mate_role in team:
                                        icon = "📝" if mate_role == "Sbobinatore" else "👀"
                                        st.markdown(f"**{icon} {mate.name}** ({mate_role})")
                                        st.markdown(f"<div class='contact-info'>📧 {mate.email}<br>📞 {mate.phone}</div>", unsafe_allow_html=True)
                                else:
                                    st.caption("Sei l'unico assegnato (o gli altri sei tu).")
                            st.markdown("---") # Separator
                else:
                    st.info("🎉 Nessun turno assegnato (o calendario non generato).")
            else:
                st.info("I turni non sono ancora stati generati dall'admin.")
