import streamlit as st
import pandas as pd
import datetime as dt
from google.oauth2.service_account import Credentials
import gspread
import json

# ---------------------------  Google Sheets Access ---------------------------
SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

FOCUS_GROUPS = ["Back", "Shoulder", "Chest", "Biceps", "Legs", "Triceps"]

def _get_sheet(tab_name: str):
    service_account_info = st.secrets["GOOGLE_CREDS"]
    creds = Credentials.from_service_account_info(service_account_info, scopes=SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key("1MS0TYrMP_7rrsf9Trv50sqxJnk_837rLebtKXbpHKxA")
    return sheet.worksheet(tab_name)

@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    ws = _get_sheet("WorkoutLog")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce").dt.strftime("%m/%d/%Y")
    df["Exercise"] = df["Exercise"].str.strip()
    df["Focus"] = df["Focus"].str.strip()
    return df

@st.cache_data(ttl=10, show_spinner=False)
def load_exercises() -> dict:
    ws = _get_sheet("Exercises")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()
    df["Focus"] = df["Focus"].str.strip()
    df["Exercise"] = df["Exercise"].str.strip()
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
    recent = recent.groupby(["Exercise", "Set"])[[f"{person}_Weight", f"{person}_Reps"]].first().reset_index()
    if recent.empty:
        return pd.DataFrame()
    wide = recent.pivot(index="Exercise", columns="Set")
    flat_columns = []
    for s in sorted(set(s for _, s in wide.columns)):
        for m in ["Weight", "Reps"]:
            flat_columns.append(f"Set {int(s)} {m}")
    wide.columns = flat_columns
    wide.columns.name = None
    wide.reset_index(inplace=True)
    return wide

def safe(x, is_weight=True):
    return float(x) if (x is not None and is_weight) else int(x) if x is not None else 0

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

    new_ex = st.text_input("Want to add a new exercise?")
    if new_ex and st.button("➕ Add Exercise"):
        add_new_exercise(focus, new_ex)
        st.success(f"Added '{new_ex}' to {focus}")
        st.rerun()

    exercise = st.selectbox("Exercise", default_exercises)

    with st.form("log_form"):
        st.markdown("### Ninaad's Log")
        n_cols = st.columns(8)
        import time
        uid = "static_uid"  # Prevent rerun from regenerating keys
        ninaad_inputs = [
            n_cols[i].number_input(
                f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}",
                min_value=0.0 if i%2==0 else 0,
                step=0.5 if i%2==0 else 1,
                key=f"n_{i}_{exercise}_{focus}_{uid}",
                value=None,
                placeholder=""
            ) for i in range(8)
        ]

        st.markdown("### Vasanta's Log")
        v_cols = st.columns(8)
        vasanta_inputs = [
            v_cols[i].number_input(
                f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}",
                min_value=0.0 if i%2==0 else 0,
                step=0.5 if i%2==0 else 1,
                key=f"v_{i}_{exercise}_{focus}_{uid}",
                value=None,
                placeholder=""
            ) for i in range(8)
        ]

        submitted = st.form_submit_button("Add to log")

    if submitted:
        count = 0
        for i in range(4):
            nw, nr = ninaad_inputs[2*i], ninaad_inputs[2*i+1]
            vw, vr = vasanta_inputs[2*i], vasanta_inputs[2*i+1]
            if any(x is not None and x > 0 for x in [nw, nr, vw, vr]):
                append_row([
                    str(date), exercise, i+1, focus,
                    safe(nw), safe(nr, is_weight=False), safe(vw), safe(vr, is_weight=False)
                ])
                count += 1

        if count:
            st.success(f"✅ {count} sets logged!")
            time.sleep(0.5)
            all_keys = [k for k in st.session_state.keys() if k.startswith("n_") or k.startswith("v_")]
            for k in all_keys:
                del st.session_state[k]
            st.rerun()

    if st.session_state.get("should_rerun"):
        st.success(f"✅ {st.session_state['logged_sets']} sets logged!")
        for k in list(st.session_state.keys()):
            if k.startswith("n_") or k.startswith("v_"):
                del st.session_state[k]
        del st.session_state["should_rerun"]
        del st.session_state["logged_sets"]

    if "logged_sets" in st.session_state:
        st.success(f"✅ {st.session_state['logged_sets']} sets logged!")
        del st.session_state["logged_sets"]

    df = load_data()
    if not df.empty:
        last_focus = df[df["Focus"] == focus]
        if not last_focus.empty:
            st.markdown("---")
            st.subheader(f"Summary for {focus} - {last_focus['Date'].max()}")
            st.markdown("### Ninaad's Summary")
            st.dataframe(build_summary_table("Ninaad", df, focus), use_container_width=True, hide_index=True)
            st.markdown("### Vasanta's Summary")
            st.dataframe(build_summary_table("Vasanta", df, focus), use_container_width=True, hide_index=True)

def main():
    st.set_page_config(page_title="Workout Tracker", page_icon="🏋️‍♂️", layout="wide")
    st.title("Log today's workout")
    log_workout()

if __name__ == "__main__":
    main()

    # Updated to use GOOGLE_CREDS from secrets