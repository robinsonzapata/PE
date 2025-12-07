import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta, date
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
    "Pe": "Field",  # Fallback
    "Gcse Pe": "Classroom 1",  # Fallback
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


def clean_year_column(val):
    if pd.isna(val):
        return ""
    val_str = str(val).strip()
    if val_str.endswith(".0"):
        return val_str[:-2]
    return val_str


def read_file(uploaded_file, header_row):
    try:
        skip = header_row - 1
        if uploaded_file.name.endswith(".csv"):
            df = pd.read_csv(uploaded_file, header=skip)
        else:
            df = pd.read_excel(uploaded_file, header=skip, engine="openpyxl")

        df = clean_columns(df)
        if "Year" in df.columns:
            df["Year"] = df["Year"].apply(clean_year_column)

        for c in ["Class", "Day", "Sport", "Activity", "Start", "End"]:
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
def get_space_for_class(
    class_code, date_obj, curriculum_records, facility_map, debug_mode=False
):
    class_code = str(class_code).strip()
    match = re.search(
        r"^(?:Y|Year)?\s*(\d+)\s*([A-Za-z0-9]+)", class_code, re.IGNORECASE
    )

    if not match:
        return "TBC", "None", "Invalid Class Format"

    year, cls_str = match.groups()
    specific_cls = cls_str.upper()[0]
    day_name = date_obj.strftime("%A")

    found_sport = None
    rule_matched_type = None
    reasons = []

    for row in curriculum_records:
        if str(row["Year"]) != year:
            continue

        if "Day" in row and str(row["Day"]).title() not in [
            day_name,
            "All",
            "Nan",
            "None",
            "",
        ]:
            continue

        try:
            s_str = str(row["Start"])
            e_str = str(row["End"])
            ts_start = pd.to_datetime(s_str, dayfirst=True, errors="coerce")
            ts_end = pd.to_datetime(e_str, dayfirst=True, errors="coerce")

            if pd.isna(ts_start) or pd.isna(ts_end):
                if debug_mode:
                    reasons.append(f"Invalid Date in Rule")
                continue

            r_start = ts_start.date()
            r_end = ts_end.date()

            current_d = date_obj
            if isinstance(date_obj, datetime):
                current_d = date_obj.date()

            if not (r_start <= current_d <= r_end):
                continue
        except Exception as e:
            if debug_mode:
                reasons.append(f"Date Error: {e}")
            continue

        r_class = str(row["Class"]).upper()
        if r_class == cls_str.upper():
            found_sport = row.get("Sport", row.get("Activity"))
            rule_matched_type = "Exact"
            break
        elif r_class == specific_cls and rule_matched_type != "Exact":
            found_sport = row.get("Sport", row.get("Activity"))
            rule_matched_type = "Letter"
        elif r_class == "ALL" and not found_sport:
            found_sport = row.get("Sport", row.get("Activity"))
            rule_matched_type = "All"

    if not found_sport:
        debug_msg = f"No Rule found for Y{year}"
        if debug_mode and reasons:
            debug_msg += f" | Debug: {'; '.join(reasons[:2])}..."
        return "TBC", "None", debug_msg

    found_sport_clean = str(found_sport).title().strip()
    assigned_space = "TBC"

    if found_sport_clean in facility_map:
        assigned_space = facility_map[found_sport_clean]
    else:
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

    # 1. Date Selection
    start_date = st.date_input("Start Date (Monday)", date(2025, 9, 1))

    # 2. Scope / Duration Selection (NEW)
    st.markdown("### ⏱️ Duration")
    duration_mode = st.radio("Generate for:", ["Custom Weeks", "Standard 2-Week Cycle"])

    if duration_mode == "Custom Weeks":
        num_weeks = st.slider(
            "Number of Weeks to Generate",
            min_value=1,
            max_value=12,
            value=8,
            help="Useful for generating a whole Half-Term schedule (e.g., 6-8 weeks).",
        )
    else:
        num_weeks = 2

    debug_mode = st.checkbox("🐞 Debug Mode", value=False)

    st.markdown("---")
    run_btn = st.button("🚀 Run Allocation", type="primary", use_container_width=True)
    if st.button("🔓 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

# --- CONFIGURATION ---
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
            results = []
            curriculum_records = df_curr.to_dict("records")

            # --- DATE GENERATION LOGIC ---
            dates_to_run = []
            d = start_date

            # Calculate total school days needed (5 days per week)
            total_days_needed = num_weeks * 5

            while len(dates_to_run) < total_days_needed:
                if d.weekday() < 5:
                    dates_to_run.append(d)
                d += timedelta(days=1)

            progress_bar = st.progress(0, text="Allocating Sports...")

            for i, curr_date in enumerate(dates_to_run):
                # WEEK A / B LOGIC
                # Assuming simple alternation starting from the user's start date
                # You might want to adjust logic if Start Date isn't Week A

                # Logic: Every 5 days, the week type flips.
                # (i // 5) gives 0 for first week, 1 for second week, etc.
                is_even_week = (i // 5) % 2 == 0
                week_type = "Week A" if is_even_week else "Week B"

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
                                "nan",
                            ]:
                                space, sport, reason = get_space_for_class(
                                    cls,
                                    curr_date,
                                    curriculum_records,
                                    FACILITY_MAP,
                                    debug_mode,
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
                                        "Reason": reason,
                                        "Staff": str(
                                            row.get("Staff", "Unknown")
                                        ).strip(),
                                    }
                                )

                # Update progress
                progress_bar.progress((i + 1) / total_days_needed)

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
            # Dropdown for Week Selection (Since we might have 8 weeks now)
            # Create a nice label like "Week 1 (Week A)", "Week 2 (Week B)"
            df["Week_Label"] = (
                df["Date"].apply(lambda x: pd.to_datetime(x).strftime("%b %d"))
                + " ("
                + df["Week"]
                + ")"
            )
            available_weeks = sorted(df["Week_Label"].unique().tolist())

            sel_week_label = st.selectbox("Select Week Scope:", available_weeks)

        with c3:
            view_type = st.radio(
                "View Mode:", ["🗺️ Grid View", "📄 List View"], horizontal=True
            )

        d_t = df[
            (df["Staff"] == sel_teacher) & (df["Week_Label"] == sel_week_label)
        ].copy()

        if view_type == "🗺️ Grid View":
            if not d_t.empty:
                d_t["Cell"] = d_t.apply(
                    lambda x: f"{x['Class']}\n{x['Activity']}\n({x['Space']})"
                    if x["Space"] != "TBC"
                    else f"{x['Class']}\n(TBC)",
                    axis=1,
                )
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
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
                st.info("No classes found.")
        else:
            st.dataframe(d_t, use_container_width=True)

        # Download Button (Full Term or Selected Week?)
        # Let's download the FULL term for that teacher
        d_full = df[df["Staff"] == sel_teacher].copy()
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine="xlsxwriter") as w:
            d_full.to_excel(w, index=False)
        st.download_button(
            "📥 Download Full Term Schedule",
            b.getvalue(),
            f"{sel_teacher}_Term_Schedule.xlsx",
        )

    # === TAB 3: TBC ISSUES ===
    with tab_issues:
        st.subheader("🚨 Why are classes TBC?")
        tbc_df = df[df["Space"] == "TBC"]

        if not tbc_df.empty:
            st.error(f"Found {len(tbc_df)} unallocated classes.")
            reasons = tbc_df["Reason"].value_counts().reset_index()
            reasons.columns = ["Reason for Error", "Count"]
            st.dataframe(reasons, use_container_width=True)
            st.dataframe(
                tbc_df[["Week", "Day", "Period", "Class", "Activity", "Reason"]].head(
                    20
                )
            )
        else:
            st.success("✅ Perfection! All classes have been allocated a space.")
