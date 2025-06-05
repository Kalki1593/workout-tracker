
"""
Streamlit Workout Tracker
=========================
A simple Streamlit + Google Sheets app that lets Ninaad & Vasanta
log each workout set from the gym floor (works great on an iPhone)
and immediately see progression charts.

How it works
------------
1.  Google Sheets is the single source of truth (one row per set).
2.  Streamlit pulls the sheet into a DataFrame (cached) and
    automatically pivots it for charts.
3.  Users can log new sets via a friendly form – no Sheet editing
    required.
4.  Users can also add new exercises, which are saved to a separate
    "Exercises" tab in the same Google Sheet.
5.  Deployed on **Streamlit Community Cloud**, shareable at
    https://streamlit.app/… — the mobile UI adapts nicely.

Before you run
--------------
- **Python ≥ 3.10**
- `pip install streamlit gspread oauth2client pandas`
- Create a Google Cloud “Service Account”, enable *Google Sheets API*,
  download the JSON key, and store it in **Streamlit Secrets** as
  `gcp_service_account`.
- Create a Google Sheet with two tabs:
  • WorkoutLog
    `Date | Exercise | Set | Focus | Ninaad_Weight | Ninaad_Reps | Vasanta_Weight | Vasanta_Reps`
  • Exercises
    `Focus | Exercise`
- In Streamlit Secrets add `gsheet_id = "<your‑sheet‑id>"`.
"""
import streamlit as st
import pandas as pd
import datetime as dt
from google.oauth2.service_account import Credentials
import gspread

# ---------------------------  Google Sheets Access  ---------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

FOCUS_GROUPS = ["Back", "Shoulder", "Chest", "Biceps", "Legs", "Triceps"]

def _get_sheet(tab_name: str):
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["gsheet_id"])
    return sheet.worksheet(tab_name)

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    ws = _get_sheet("WorkoutLog")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["Date"], format='mixed')
    return df

@st.cache_data(ttl=10, show_spinner=False)
def load_exercises() -> dict:
    ws = _get_sheet("Exercises")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    return df.groupby("Focus")["Exercise"].apply(list).to_dict()

def append_row(row: list[str | int | float]):
    ws = _get_sheet("WorkoutLog")
    ws.append_row(row, value_input_option="USER_ENTERED")

def add_new_exercise(focus: str, exercise: str):
    ws = _get_sheet("Exercises")
    ws.append_row([focus, exercise], value_input_option="USER_ENTERED")

# ---------------------------  UI: Log Workout ---------------------------

def log_workout():
    st.subheader("Log today's workout")
    date = st.date_input("Date", dt.date.today())
    day_name = date.strftime("%A")
    default_focus = {
        "Monday": "Back",
        "Tuesday": "Shoulder",
        "Wednesday": "Chest",
        "Thursday": "Biceps",
        "Friday": "Legs",
        "Saturday": "Triceps",
    }.get(day_name, "")

    focus = st.selectbox("Focus Muscle Group", options=FOCUS_GROUPS, index=FOCUS_GROUPS.index(default_focus))
    exercises_map = load_exercises()
    default_exercises = exercises_map.get(focus, [])

    df = load_data()

    # New exercise input
    new_ex = st.text_input("Want to add a new exercise?")
    if new_ex and st.button("➕ Add Exercise"):
        add_new_exercise(focus, new_ex)
        st.success(f"Added '{new_ex}' to {focus}")
        st.rerun()

    # Workout logging inputs
    exercise = st.selectbox("Exercise", default_exercises)

    with st.form("log_form"):
        st.markdown("#### Ninaad's Log")
        col_n1, col_n2 = st.columns(2)
        with col_n1:
            n_weights = [st.number_input(f"Set {i+1} Weight (kg)", value=None, min_value=0.0, step=0.5, key=f"nw_{i}") for i in range(4)]
        with col_n2:
            n_reps = [st.number_input(f"Set {i+1} Reps", value=None, min_value=0, step=1, key=f"nr_{i}") for i in range(4)]

        st.markdown("#### Vasanta's Log")
        col_v1, col_v2 = st.columns(2)
        with col_v1:
            v_weights = [st.number_input(f"Set {i+1} Weight (kg)", value=None, min_value=0.0, step=0.5, key=f"vw_{i}") for i in range(4)]
        with col_v2:
            v_reps = [st.number_input(f"Set {i+1} Reps", value=None, min_value=0, step=1, key=f"vr_{i}") for i in range(4)]

        submitted = st.form_submit_button("Add to log")

    if submitted:
        for i in range(4):
            if any([
                n_weights[i] is not None and n_reps[i] is not None,
                v_weights[i] is not None and v_reps[i] is not None
            ]):
                append_row([
                    str(date),
                    exercise,
                    i + 1,
                    focus,
                    n_weights[i] if n_weights[i] else "",
                    n_reps[i] if n_reps[i] else "",
                    v_weights[i] if v_weights[i] else "",
                    v_reps[i] if v_reps[i] else "",
                ])
        st.success("✅  All sets logged!")
        st.rerun()

    # Show last session for selected focus
    past_sessions = df[df["Focus"] == focus]
    if not past_sessions.empty:
        last_date = past_sessions["Date"].max()
        st.write(f"Last recorded date for {focus}: {last_date}")
        past_sessions["Set"] = pd.to_numeric(past_sessions["Set"], errors="coerce")
        last_session = past_sessions[past_sessions["Date"] == last_date].sort_values(by=["Exercise", "Set"])

        # Build summary pivot for Ninaad
        ninaad_df = last_session.pivot_table(
            index="Exercise",
            columns="Set",
            values=["Ninaad_Weight", "Ninaad_Reps"],
            aggfunc="first"
        )
        ninaad_df = ninaad_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)
        ninaad_df.columns = [f"Set {s} {m.split('_')[1]}" for s, m in ninaad_df.columns]
        ninaad_df = ninaad_df.reset_index()
        ninaad_df.index = ninaad_df.index + 1

        # Build summary pivot for Vasanta
        vasanta_df = last_session.pivot_table(
            index="Exercise",
            columns="Set",
            values=["Vasanta_Weight", "Vasanta_Reps"],
            aggfunc="first"
        )
        vasanta_df = vasanta_df.reorder_levels([1, 0], axis=1).sort_index(axis=1)
        vasanta_df.columns = [f"Set {s} {m.split('_')[1]}" for s, m in vasanta_df.columns]
        vasanta_df = vasanta_df.reset_index()
        vasanta_df.index = vasanta_df.index + 1

        st.markdown("---")
        st.markdown("### Ninaad's Summary")
        st.dataframe(ninaad_df, use_container_width=True)

        st.markdown("### Vasanta's Summary")
        st.dataframe(vasanta_df, use_container_width=True)

# ---------------------------  Main Entry Point ---------------------------

def main():
    st.set_page_config(page_title="Workout Tracker", page_icon="🏋️‍♂️", layout="centered")
    mode = st.sidebar.radio("Mode", ["Log Workout"])
    if mode == "Log Workout":
        log_workout()

if __name__ == "__main__":
    main()
