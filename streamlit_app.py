import streamlit as st
import pandas as pd
import datetime as dt
from google.oauth2.service_account import Credentials
import gspread

# ---------------------------  Google Sheets Access ---------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

FOCUS_GROUPS = ["Back", "Shoulder", "Chest", "Biceps", "Legs", "Triceps"]

def _get_sheet(tab_name: str):
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPE
    )
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
    df["Date"] = pd.to_datetime(df["Date"], format="%Y-%m-%d", errors="coerce")
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

def build_summary_table(person: str, df: pd.DataFrame, focus: str):
    recent = df[df["Focus"] == focus]
    if recent.empty:
        return pd.DataFrame()
    recent = recent[recent["Date"] == recent["Date"].max()]
    
    # Ensure expected columns exist
    expected_cols = [f"{person}_Weight", f"{person}_Reps"]
    if not all(col in recent.columns for col in expected_cols):
        st.warning(f"Missing columns for {person} in data: {expected_cols}")
        return pd.DataFrame()

    recent = recent.groupby(["Exercise", "Set"])[expected_cols].first().reset_index()
    wide = recent.pivot(index="Exercise", columns="Set")
    wide.columns = [f"Set {s} {'Weight' if 'Weight' in m else 'Reps'}" for m, s in wide.columns]
    return wide.reset_index()

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
    st.write("Loaded gsheet_id:", st.secrets.get("gsheet_id", "NOT FOUND"))
    st.write("Exercises loaded for focus group:", focus)
    st.write(exercises_map)
    default_exercises = exercises_map.get(focus, [])
    df = load_data()
    st.write("Data loaded from WorkoutLog:")
    st.dataframe(df.head())
    st.write("DataFrame Preview:", df.head())

    # Show last session for selected focus
    if not df.empty:
        last_focus = df[df["Focus"] == focus]
        if not last_focus.empty:
            st.write(f"Last recorded session: {last_focus['Date'].max().date()}")
            st.markdown("### Ninaad's Summary")
            st.dataframe(build_summary_table("Ninaad", df, focus), use_container_width=True)
            st.markdown("### Vasanta's Summary")
            st.dataframe(build_summary_table("Vasanta", df, focus), use_container_width=True)
        else:
            st.write("No past session found for this focus.")

    new_ex = st.text_input("Want to add a new exercise?")
    if new_ex and st.button("➕ Add Exercise"):
        add_new_exercise(focus, new_ex)
        st.success(f"Added '{new_ex}' to {focus}")
        st.rerun()

    exercise = st.selectbox("Exercise", default_exercises)

    with st.form("log_form"):
        st.markdown("### Ninaad's Log")
        n_cols = st.columns(8)
        ninaad_inputs = [
            n_cols[i].number_input(
                f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}",
                min_value=0.0 if i%2==0 else 0,
                step=0.5 if i%2==0 else 1,
                key=f"n_{i}_{exercise}"
            ) for i in range(8)
        ]

        st.markdown("### Vasanta's Log")
        v_cols = st.columns(8)
        vasanta_inputs = [
            v_cols[i].number_input(
                f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}",
                min_value=0.0 if i%2==0 else 0,
                step=0.5 if i%2==0 else 1,
                key=f"v_{i}_{exercise}"
            ) for i in range(8)
        ]

        submitted = st.form_submit_button("Add to log")

    if submitted:
        count = 0
        for i in range(4):
            nw, nr = ninaad_inputs[2*i], ninaad_inputs[2*i+1]
            vw, vr = vasanta_inputs[2*i], vasanta_inputs[2*i+1]
            if any([nw, nr, vw, vr]):
                append_row([
                    str(date), exercise, i+1, focus,
                    nw, nr, vw, vr
                ])
                count += 1
        if count:
            st.success(f"✅ {count} sets logged!")
            st.rerun()

def main():
    st.set_page_config(page_title="Workout Tracker", page_icon="🏋️‍♂️", layout="wide")
    st.title("Log today's workout")
    log_workout()

if __name__ == "__main__":
    main()