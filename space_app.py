import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import xlsxwriter

# ==========================================
# 0. CONFIG & LOGIN
# ==========================================
st.set_page_config(page_title="PE Sport Allocator", layout="wide", page_icon="🏅")
CREDENTIALS = {"admin": "admin123", "teacher": "pe2025"}

# --- DEFAULT SPORT ZONES (The "Where") ---
# This maps Activities to Default Spaces
DEFAULT_FACILITIES = {
    "Football": "Field",
    "Rugby": "Field",
    "Athletics": "Field",
    "Cricket": "Field",
    "Rounders": "Field",
    "Netball": "Tennis Courts",
    "Tennis": "Tennis Courts",
    "Hockey": "Astro",
    "Gymnastics": "Gym",
    "Trampolining": "Gym",
    "Basketball": "Sports Hall",
    "Badminton": "Sports Hall",
    "Volleyball": "Sports Hall",
    "Dodgeball": "Sports Hall",
    "Fitness": "Fitness Room",
    "Theory": "Classroom 1",
    "Dance": "Studio",
}


def login_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("## 🏅 PE Sport Allocator")
            st.info("Log in to access the Sport-Based Engine")
            u = st.text_input("Username")
            p = st.text_input("Password", type="password")
            if st.button("Log In", type="primary"):
                if u in CREDENTIALS and CREDENTIALS[u] == p:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Invalid")
        st.stop()


login_system()


# ==========================================
# 1. HELPER FUNCTIONS
# ==========================================
def clean_columns(df):
    if df is not None:
        df.columns = df.columns.astype(str).str.strip().str.title()
    return df


def read_file(uploaded_file, header_row):
    try:
        skip = header_row - 1
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, header=skip)
        else:
            df = pd.read_excel(uploaded_file, header=skip, engine="openpyxl")

        df = clean_columns(df)
        # Ensure critical columns are strings
        for c in ["Year", "Class", "Day", "Sport", "Activity"]:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"Read Error: {e}")
        return None


def style_grid(val):
    if isinstance(val, str):
        if "TBC" in val:
            return "background-color: #fee2e2; color: #991b1b;"
        if val:
            return (
                "background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0;"
            )
    return "color: #e5e7eb;"


# ==========================================
# 2. LOGIC ENGINE (SPORT BASED)
# ==========================================
def get_space_for_class(class_code, date_obj, df_curriculum, facility_map):
    """
    1. Finds what SPORT the class is doing (from Curriculum File).
    2. Finds where that SPORT is played (from Facility Map).
    """
    curriculum = df_curriculum.to_dict("records")
    class_code = str(class_code).strip()

    # 1. Parse Class (e.g. "7Hope" -> Year 7, H)
    match = re.search(
        r"^(?:Y|Year)?\s*(\d+)\s*([A-Za-z0-9]+)", class_code, re.IGNORECASE
    )
    if not match:
        return "TBC", "Invalid Class Format"

    year, cls_str = match.groups()
    specific_cls = cls_str.upper()[0]  # First letter
    day_name = date_obj.strftime("%A")

    # 2. Find the SPORT from Curriculum
    found_sport = None

    # Search Priority: Exact Match -> Letter Match -> All Match
    for row in curriculum:
        # Check Date Range
        try:
            r_start = pd.to_datetime(row["Start"], dayfirst=True).date()
            r_end = pd.to_datetime(row["End"], dayfirst=True).date()
            if not (r_start <= date_obj.date() <= r_end):
                continue
        except:
            continue

        # Check Year & Day
        if str(row["Year"]) != year:
            continue
        if "Day" in row and str(row["Day"]).title() not in [day_name, "All"]:
            continue

        # Check Class (Exact, Letter, or All)
        r_class = str(row["Class"]).upper()

        if r_class == cls_str.upper():  # Exact (e.g. 7Hope)
            found_sport = row.get("Sport", row.get("Activity"))
            break
        elif r_class == specific_cls:  # Letter (e.g. H)
            found_sport = row.get("Sport", row.get("Activity"))
            break
        elif r_class == "ALL":  # Wildcard
            found_sport = row.get("Sport", row.get("Activity"))
            # Keep looking in case there is a specific override later?
            # Ideally we break on specific, but for 'All' we might want to wait.
            # For simplicity, let's take the first 'All' if no specific found yet.
            if not found_sport:
                found_sport = row.get("Sport", row.get("Activity"))

    if not found_sport:
        return "TBC", f"No Sport defined for Y{year}"

    # 3. Find the SPACE from Facility Map
    # Fuzzy match sport name (e.g. "Year 7 Football" -> "Football")
    found_sport_clean = found_sport.title()
    assigned_space = "TBC"

    # Direct Lookup
    if found_sport_clean in facility_map:
        assigned_space = facility_map[found_sport_clean]
    else:
        # Keyword Lookup (e.g. "Boys Football" contains "Football")
        for key_sport, val_space in facility_map.items():
            if key_sport.lower() in found_sport_clean.lower():
                assigned_space = val_space
                break

    if assigned_space == "TBC":
        return "TBC", f"Unknown Sport: {found_sport}"

    return assigned_space, found_sport


# ==========================================
# 3. UI SETUP
# ==========================================
st.title("🏅 PE Sport Allocator")

if "results_df" not in st.session_state:
    st.session_state.results_df = None

# --- SIDEBAR: FACILITIES CONFIG ---
with st.sidebar:
    st.header("1. Facility Manager")
    st.info("Define where each sport is played here.")

    # Editable Dataframe for Facilities
    df_facilities_input = pd.DataFrame(
        list(DEFAULT_FACILITIES.items()), columns=["Sport", "Space"]
    )
    edited_facilities = st.data_editor(
        df_facilities_input,
        num_rows="dynamic",
        use_container_width=True,
        hide_index=True,
    )

    # Convert back to dict
    FACILITY_MAP = dict(zip(edited_facilities["Sport"], edited_facilities["Space"]))

    st.markdown("---")
    st.header("2. Upload Data")
    header_idx = st.number_input("Header Row:", min_value=1, value=1)
    file_tt = st.file_uploader("Timetable (CSV/Excel)", type=["csv", "xlsx"])
    file_curr = st.file_uploader("Curriculum Plan (CSV/Excel)", type=["csv", "xlsx"])

# --- MAIN APP ---
if file_tt and file_curr:
    df_tt = read_file(file_tt, header_idx)
    df_curr = read_file(file_curr, header_idx)

    if df_tt is not None and df_curr is not None:
        # Validation
        if "Sport" not in df_curr.columns and "Activity" not in df_curr.columns:
            st.error("❌ Curriculum File needs a 'Sport' or 'Activity' column.")
            st.stop()

        if st.button("🚀 Auto-Allocate by Sport", type="primary"):
            results = []

            # Simple Date Loop
            start_date = datetime(2025, 9, 1)  # Default start
            # Try to infer dates or just run a sample week
            # For this demo, let's run a standard 2-week cycle from Sept 1st
            dates_to_run = [
                start_date + timedelta(days=i)
                for i in range(14)
                if (start_date + timedelta(days=i)).weekday() < 5
            ]

            progress_bar = st.progress(0, text="Matching Sports to Spaces...")

            for i, curr_date in enumerate(dates_to_run):
                week_type = "Week A" if i < 5 else "Week B"  # Simple toggle for demo
                day_name = curr_date.strftime("%A")

                # Filter Timetable
                daily_tt = df_tt[
                    (df_tt["Week"].str.upper() == week_type.upper())
                    & (df_tt["Day"].str.upper() == day_name.upper())
                ]

                for _, row in daily_tt.iterrows():
                    for p in range(1, 6):
                        col = f"Period {p}"
                        if col in row and pd.notna(row[col]):
                            cls = str(row[col]).strip()
                            if len(cls) > 1 and cls.lower() not in ["lunch", "free"]:
                                # === CALL THE LOGIC ===
                                space, sport = get_space_for_class(
                                    cls, curr_date, df_curr, FACILITY_MAP
                                )

                                results.append(
                                    {
                                        "Week": week_type,
                                        "Day": day_name,
                                        "Period": f"P{p}",
                                        "Class": cls,
                                        "Activity": sport,  # The "What"
                                        "Space": space,  # The "Where"
                                        "Staff": row.get("Staff", ""),
                                    }
                                )

                progress_bar.progress((i + 1) / len(dates_to_run))

            progress_bar.empty()
            st.session_state.results_df = pd.DataFrame(results)
            st.success("✅ Allocation Complete!")

# --- DISPLAY RESULTS ---
if st.session_state.results_df is not None:
    df = st.session_state.results_df

    t1, t2, t3 = st.tabs(["📋 Main Schedule", "🤸 Sport View", "⚠️ Issues"])

    with t1:
        st.subheader("Master Schedule")
        # Filters
        c1, c2 = st.columns(2)
        with c1:
            f_staff = st.multiselect("Filter Staff:", df["Staff"].unique())
        with c2:
            f_day = st.multiselect("Filter Day:", df["Day"].unique())

        df_show = df.copy()
        if f_staff:
            df_show = df_show[df_show["Staff"].isin(f_staff)]
        if f_day:
            df_show = df_show[df_show["Day"].isin(f_day)]

        st.dataframe(df_show, use_container_width=True)

    with t2:
        st.subheader("Allocations by Sport")
        # Pivot to show how many classes are doing what
        pivot = df.pivot_table(
            index="Activity", columns="Space", values="Class", aggfunc="count"
        ).fillna(0)
        st.dataframe(pivot, use_container_width=True)

    with t3:
        st.subheader("Unallocated Classes")
        errs = df[df["Space"] == "TBC"]
        if not errs.empty:
            st.error(f"{len(errs)} Classes could not be matched.")
            st.write(
                "Check your Curriculum File covers these classes, AND your Facility Manager covers these sports."
            )
            st.dataframe(errs)
        else:
            st.success("All classes allocated successfully!")

else:
    st.info(
        "👈 Please define your facilities in the sidebar, then upload your Timetable and Curriculum."
    )
