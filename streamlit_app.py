
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
  download the JSON key and **convert it to secrets.toml** format.
- Inside `.streamlit/secrets.toml`, add:

```toml
[gcp_service_account]
type = "service_account"
project_id = "workout-tracker-461712"
private_key_id = "your-private-key-id"
private_key = "-----BEGIN PRIVATE KEY-----\nMIIEv...\n-----END PRIVATE KEY-----\n"
client_email = "streamlit-sheets-access@workout-tracker-461712.iam.gserviceaccount.com"
client_id = "your-client-id"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
client_x509_cert_url = "https://www.googleapis.com/robot/v1/metadata/x509/streamlit-sheets-access%40workout-tracker-461712.iam.gserviceaccount.com"
gsheet_id = "your-google-sheet-id"
```

- Create a Google Sheet with two tabs:
  • WorkoutLog
    `Date | Exercise | Set | Focus | Ninaad_Weight | Ninaad_Reps | Vasanta_Weight | Vasanta_Reps`
  • Exercises
    `Focus | Exercise`
"""

import streamlit as st
import pandas as pd
import datetime as dt
from google.oauth2.service_account import Credentials
import gspread

SCOPE = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive",
]

FOCUS_GROUPS = ["Back", "Shoulder", "Chest", "Biceps", "Legs", "Triceps"]


def _get_sheet(tab_name: str):
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPE)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["gcp_service_account"]["gsheet_id"])
    return sheet.worksheet(tab_name)


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    ws = _get_sheet("WorkoutLog")
    rows = ws.get_all_records()
    df = pd.DataFrame(rows)
    df.columns = df.columns.str.strip()
    if df.empty:
        return df
    df["Date"] = pd.to_datetime(df["Date"], errors='coerce')
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

    past_sessions = df[df["Focus"] == focus]
    if not past_sessions.empty:
        last_date = past_sessions["Date"].max()
        st.markdown(f"#### Last recorded session: {last_date.date() if pd.notnull(last_date) else 'None'}")
        last_session = past_sessions[past_sessions["Date"] == last_date].sort_values(by=["Exercise", "Set"])

        def build_summary_table(prefix):
            summary = (
                last_session
                .pivot_table(index="Exercise", columns="Set", values=[f"{prefix}_Weight", f"{prefix}_Reps"], aggfunc="first")
            )
            columns = []
            for i in range(1, 5):
                columns.append((f"{prefix}_Weight", i))
                columns.append((f"{prefix}_Reps", i))
            valid_cols = [c for c in columns if c in summary.columns]
            summary = summary[valid_cols].copy()
            summary.columns = [f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}" for i in range(len(valid_cols))]
            return summary.reset_index()

        st.markdown("#### Ninaad's Summary")
        st.dataframe(build_summary_table("Ninaad"), use_container_width=True)

        st.markdown("#### Vasanta's Summary")
        st.dataframe(build_summary_table("Vasanta"), use_container_width=True)

    new_ex = st.text_input("Want to add a new exercise?")
    if new_ex and st.button("\u2795 Add Exercise"):
        add_new_exercise(focus, new_ex)
        st.success(f"Added '{new_ex}' to {focus}")
        st.rerun()

    exercise = st.selectbox("Exercise", default_exercises)
    with st.form(key="log_form"):
        st.markdown("#### Ninaad's Log")
        n_cols = st.columns(8)
        ninaad_inputs = [(n_cols[i].number_input(f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}", min_value=0.0 if i%2==0 else 0, step=0.5 if i%2==0 else 1, key=f"n_{i}")) for i in range(8)]

        st.markdown("#### Vasanta's Log")
        v_cols = st.columns(8)
        vasanta_inputs = [(v_cols[i].number_input(f"Set {i//2+1} {'Weight' if i%2==0 else 'Reps'}", min_value=0.0 if i%2==0 else 0, step=0.5 if i%2==0 else 1, key=f"v_{i}")) for i in range(8)]

        submitted = st.form_submit_button("Add to log")
        if submitted:
            logged_any = False
            for i in range(4):
                nw, nr = ninaad_inputs[2 * i], ninaad_inputs[2 * i + 1]
                vw, vr = vasanta_inputs[2 * i], vasanta_inputs[2 * i + 1]
                if any([nw, nr, vw, vr]):
                    append_row([
                        str(date),
                        exercise,
                        i + 1,
                        focus,
                        nw,
                        nr,
                        vw,
                        vr,
                    ])
                    logged_any = True
            if logged_any:
                st.success("✅ All sets logged!")
                st.rerun()
            else:
                st.warning("No values entered to log.")


def main():
    st.set_page_config(page_title="Workout Tracker", page_icon="🏋️‍♂️", layout="centered")
    mode = st.sidebar.radio("Mode", ["Log Workout"])
    if mode == "Log Workout":
        log_workout()


if __name__ == "__main__":
    main()
