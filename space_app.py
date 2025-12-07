import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import xlsxwriter

# ==========================================
# 0. CONFIG & LOGIN
# ==========================================
st.set_page_config(page_title="PE Space Master", layout="wide", page_icon="🏅")
CREDENTIALS = {"admin": "admin123", "teacher": "pe2025"}

# Default "Sport" -> "Space" Mapping
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
    "Table Tennis": "Gym",
}


def login_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if not st.session_state.authenticated:
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.markdown("## 🏅 PE Space Master")
            st.info("Log in to access the Allocation Engine")
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
            return (
                "background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;"
            )
        if val:
            return (
                "background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0;"
            )
    return "color: #e5e7eb;"


# ==========================================
# 2. LOGIC ENGINE
# ==========================================
def get_space_for_class(class_code, date_obj, df_curriculum, facility_map):
    """
    Returns: (Assigned Space, Sport Found, Debug Reason)
    """
    curriculum = df_curriculum.to_dict("records")
    class_code = str(class_code).strip()

    match = re.search(
        r"^(?:Y|Year)?\s*(\d+)\s*([A-Za-z0-9]+)", class_code, re.IGNORECASE
    )
    if not match:
        return "TBC", "Unknown", "Invalid Class Format"

    year, cls_str = match.groups()
    specific_cls = cls_str.upper()[0]
    day_name = date_obj.strftime("%A")

    # 1. FIND SPORT IN CURRICULUM
    found_sport = None
    for row in curriculum:
        try:
            r_start = pd.to_datetime(row["Start"], dayfirst=True).date()
            r_end = pd.to_datetime(row["End"], dayfirst=True).date()
            if not (r_start <= date_obj.date() <= r_end):
                continue
        except:
            continue

        if str(row["Year"]) != year:
            continue
        if "Day" in row and str(row["Day"]).title() not in [day_name, "All"]:
            continue

        r_class = str(row["Class"]).upper()
        # Priority: Exact -> Letter -> All
        if r_class == cls_str.upper():
            found_sport = row.get("Sport", row.get("Activity"))
            break
        elif r_class == specific_cls:
            found_sport = row.get("Sport", row.get("Activity"))
            break
        elif r_class == "ALL":
            if not found_sport:
                found_sport = row.get("Sport", row.get("Activity"))

    if not found_sport:
        return "TBC", "None", f"No Curriculum Rule for Y{year}"

    # 2. FIND SPACE IN FACILITY MAP
    found_sport_clean = str(found_sport).title().strip()
    assigned_space = "TBC"

    # Exact Match
    if found_sport_clean in facility_map:
        assigned_space = facility_map[found_sport_clean]
    else:
        # Fuzzy Match (e.g. "Girls Football" matches "Football")
        for key_sport, val_space in facility_map.items():
            if key_sport.lower() in found_sport_clean.lower():
                assigned_space = val_space
                break

    if assigned_space == "TBC":
        return "TBC", found_sport, f"Sport '{found_sport}' not in Facility List"

    return assigned_space, found_sport, "Matched"


# ==========================================
# 3. UI LAYOUT
# ==========================================
st.title("🏅 PE Space Master Pro")

if "results_df" not in st.session_state:
    st.session_state.results_df = None
if "run_complete" not in st.session_state:
    st.session_state.run_complete = False

# --- SIDEBAR ---
with st.sidebar:
    st.header("🎮 Controls")
    start_date = st.date_input("Start Date", datetime(2025, 9, 1))
    st.markdown("---")
    run_btn = st.button("🚀 Run Allocation", type="primary", use_container_width=True)
    st.markdown("---")
    if st.button("🔓 Log Out", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()

# --- CONFIGURATION (Files & Facilities) ---
expander_state = not st.session_state.run_complete
with st.expander("⚙️ Setup & Configuration", expanded=expander_state):
    tab_files, tab_facilities = st.tabs(["📂 1. Upload Data", "🏟️ 2. Facility Manager"])

    with tab_files:
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            st.markdown("#### 1. Timetable")
            file_tt = st.file_uploader(
                "Upload Timetable", type=["csv", "xlsx"], key="tt"
            )
        with col_f2:
            st.markdown("#### 2. Curriculum")
            file_curr = st.file_uploader(
                "Upload Curriculum (Rules)", type=["csv", "xlsx"], key="curr"
            )
        header_idx = st.number_input("Header Row Index", min_value=1, value=1)

    with tab_facilities:
        st.info(
            "💡 Map Sports to Spaces. Example: If curriculum says 'Soccer', ensure 'Soccer' is mapped below."
        )
        if "facility_map_df" not in st.session_state:
            st.session_state.facility_map_df = pd.DataFrame(
                list(DEFAULT_FACILITIES.items()), columns=["Sport", "Space"]
            )

        edited_facilities = st.data_editor(
            st.session_state.facility_map_df,
            num_rows="dynamic",
            use_container_width=True,
            height=300,
        )
        FACILITY_MAP = dict(zip(edited_facilities["Sport"], edited_facilities["Space"]))
        ALL_KNOWN_SPACES = sorted(list(set(FACILITY_MAP.values())))

# ==========================================
# 4. EXECUTION
# ==========================================
if run_btn:
    if file_tt and file_curr:
        df_tt = read_file(file_tt, header_idx)
        df_curr = read_file(file_curr, header_idx)

        if df_tt is not None and df_curr is not None:
            if "Sport" not in df_curr.columns and "Activity" not in df_curr.columns:
                st.error("❌ Curriculum File needs a 'Sport' or 'Activity' column.")
            else:
                results = []
                # 2-Week Logic
                dates_to_run = []
                d = start_date
                while len(dates_to_run) < 10:
                    if d.weekday() < 5:
                        dates_to_run.append(d)
                    d += timedelta(days=1)

                progress_bar = st.progress(0, text="Allocating Sports...")

                for i, curr_date in enumerate(dates_to_run):
                    week_type = "Week A" if i < 5 else "Week B"
                    day_name = curr_date.strftime("%A")
                    date_str = curr_date.strftime("%Y-%m-%d")

                    daily_tt = df_tt[
                        (df_tt["Week"].str.upper() == week_type.upper())
                        & (df_tt["Day"].str.upper() == day_name.upper())
                    ]

                    for _, row in daily_tt.iterrows():
                        for p in range(1, 6):
                            col = f"Period {p}"
                            if col in row and pd.notna(row[col]):
                                cls = str(row[col]).strip()
                                if len(cls) > 1 and cls.lower() not in [
                                    "lunch",
                                    "free",
                                    "break",
                                ]:
                                    # GET SPACE + DEBUG REASON
                                    space, sport, reason = get_space_for_class(
                                        cls, curr_date, df_curr, FACILITY_MAP
                                    )

                                    results.append(
                                        {
                                            "Date": date_str,
                                            "Week": week_type,
                                            "Day": day_name,
                                            "Period": f"Period {p}",
                                            "Class": cls,
                                            "Activity": sport,
                                            "Space": space,
                                            "Reason": reason,  # Saving the reason
                                            "Staff": str(
                                                row.get("Staff", "Unknown")
                                            ).strip(),
                                        }
                                    )
                    progress_bar.progress((i + 1) / 10)

                progress_bar.empty()
                st.session_state.results_df = pd.DataFrame(results)
                st.session_state.run_complete = True
                st.rerun()
    else:
        st.error("⚠️ Please upload files first.")

# ==========================================
# 5. DASHBOARD
# ==========================================
if st.session_state.results_df is not None:
    df = st.session_state.results_df.copy()

    st.markdown("## 📊 Allocation Dashboard")

    tab_teacher, tab_space, tab_issues, tab_tools = st.tabs(
        ["👩‍🏫 Teacher View", "🏟️ Space Master", "⚠️ TBC Issues", "🛠️ Tools"]
    )

    # === TAB 1: TEACHER VIEW ===
    with tab_teacher:
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            all_staff = sorted(df["Staff"].unique().tolist())
            sel_teacher = st.selectbox("Select Teacher:", all_staff)
        with c2:
            sel_week = st.radio("Select Week:", ["Week A", "Week B"], horizontal=True)
        with c3:
            view_type = st.radio(
                "View Mode:", ["🗺️ Grid View", "📄 List View"], horizontal=True
            )

        d_t = df[(df["Staff"] == sel_teacher) & (df["Week"] == sel_week)].copy()

        st.markdown(f"### 📅 Schedule: **{sel_teacher}** ({sel_week})")

        if view_type == "🗺️ Grid View":
            if not d_t.empty:
                # SAFE STRING CREATION
                d_t["Cell"] = d_t.apply(
                    lambda x: f"{x['Class']}\n{x['Activity']}\n({x['Space']})"
                    if x["Space"] != "TBC"
                    else f"{x['Class']}\n(TBC)",
                    axis=1,
                )
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                # SAFE AGGREGATION TO PREVENT "TBCTBCTBC"
                grid = d_t.pivot_table(
                    index="Period",
                    columns="Day",
                    values="Cell",
                    aggfunc=lambda x: " / ".join(x.unique()),
                )
                grid = grid.reindex(
                    columns=[d for d in days_order if d in grid.columns]
                ).sort_index()
                st.dataframe(
                    grid.style.map(style_grid), use_container_width=True, height=500
                )
            else:
                st.info("No classes.")
        else:
            st.dataframe(d_t, use_container_width=True)

        # Excel Download
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine="xlsxwriter") as w:
            d_t.to_excel(w, index=False)
        st.download_button(
            "📥 Download Schedule", b.getvalue(), f"{sel_teacher}_Schedule.xlsx"
        )

    # === TAB 2: SPACE MASTER ===
    with tab_space:
        w_sel = st.selectbox(
            "Select Week Scope", ["Week A", "Week B"], key="space_week"
        )
        df_heat = df[df["Week"] == w_sel]
        if not df_heat.empty:
            mat = (
                df_heat.pivot_table(
                    index="Space", columns="Period", values="Class", aggfunc="count"
                )
                .fillna(0)
                .astype(int)
            )
            st.subheader(f"🔥 Space Utilization ({w_sel})")
            st.dataframe(mat, use_container_width=True)

    # === TAB 3: TBC ISSUES (NEW) ===
    with tab_issues:
        st.subheader("🚨 Why are classes TBC?")
        tbc_df = df[df["Space"] == "TBC"]

        if not tbc_df.empty:
            st.error(f"Found {len(tbc_df)} unallocated classes.")

            # Show summary of reasons
            reasons = tbc_df["Reason"].value_counts().reset_index()
            reasons.columns = ["Reason for Error", "Count"]
            st.dataframe(reasons, use_container_width=True)

            st.markdown("#### Detailed List")
            st.dataframe(
                tbc_df[["Week", "Day", "Period", "Class", "Activity", "Reason"]]
            )
        else:
            st.success("✅ Perfection! All classes have been allocated a space.")

    # === TAB 4: TOOLS ===
    with tab_tools:
        st.subheader("Department Tools")
        t1, t2 = st.tabs(["Free Space Finder", "Conflict Report"])

        with t1:
            c1, c2, c3 = st.columns(3)
            with c1:
                f_day = st.selectbox(
                    "Day", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                )
            with c2:
                f_per = st.selectbox(
                    "Period",
                    ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5"],
                )
            with c3:
                f_wk = st.selectbox("Week", ["Week A", "Week B"])

            if st.button("Check Availability"):
                used = df[
                    (df["Week"] == f_wk)
                    & (df["Day"] == f_day)
                    & (df["Period"] == f_per)
                ]["Space"].unique()
                free = set(ALL_KNOWN_SPACES) - set(used)
                if free:
                    st.success(f"✅ {len(free)} Spaces Free")
                    st.write(sorted(list(free)))
                else:
                    st.error("❌ Full House (No spaces)")

        with t2:
            dupes = df[df.duplicated(subset=["Date", "Period", "Space"], keep=False)]
            dupes = dupes[(dupes["Space"] != "TBC") & (dupes["Space"] != "nan")]
            if not dupes.empty:
                st.error(f"⚠️ {len(dupes)} Conflicts")
                st.dataframe(dupes.sort_values(by=["Date", "Period"]))
            else:
                st.success("✅ No conflicts.")
