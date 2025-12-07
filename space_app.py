# import streamlit as st
# import pandas as pd
# import re
# from datetime import datetime, timedelta, date  # Added 'date' to imports
# import io
# import xlsxwriter

# # ==========================================
# # 0. CONFIG & LOGIN
# # ==========================================
# st.set_page_config(page_title="PE Space Master", layout="wide", page_icon="🏅")
# CREDENTIALS = {"admin": "admin123", "teacher": "pe2025"}

# # Default "Sport" -> "Space" Mapping
# DEFAULT_FACILITIES = {
#     "Football": "Field",
#     "Rugby": "Field",
#     "Athletics": "Field",
#     "Cricket": "Field",
#     "Rounders": "Field",
#     "Netball": "Tennis Courts",
#     "Tennis": "Tennis Courts",
#     "Hockey": "Astro",
#     "Gymnastics": "Gym",
#     "Trampolining": "Gym",
#     "Basketball": "Sports Hall",
#     "Badminton": "Sports Hall",
#     "Volleyball": "Sports Hall",
#     "Dodgeball": "Sports Hall",
#     "Fitness": "Fitness Room",
#     "Theory": "Classroom 1",
#     "Dance": "Studio",
#     "Table Tennis": "Gym",
#     "Pe": "Field",  # Fallback
#     "Gcse Pe": "Classroom 1",  # Fallback
# }


# def login_system():
#     if "authenticated" not in st.session_state:
#         st.session_state.authenticated = False
#     if not st.session_state.authenticated:
#         c1, c2, c3 = st.columns([1, 2, 1])
#         with c2:
#             st.markdown("## 🏅 PE Space Master")
#             st.info("Log in to access the Allocation Engine")
#             u = st.text_input("Username")
#             p = st.text_input("Password", type="password")
#             if st.button("Log In", type="primary"):
#                 if u in CREDENTIALS and CREDENTIALS[u] == p:
#                     st.session_state.authenticated = True
#                     st.rerun()
#                 else:
#                     st.error("Invalid")
#         st.stop()


# login_system()


# # ==========================================
# # 1. HELPER FUNCTIONS
# # ==========================================
# def clean_columns(df):
#     if df is not None:
#         df.columns = df.columns.astype(str).str.strip().str.title()
#     return df


# def clean_year_column(val):
#     if pd.isna(val):
#         return ""
#     val_str = str(val).strip()
#     if val_str.endswith(".0"):
#         return val_str[:-2]
#     return val_str


# def read_file(uploaded_file, header_row):
#     try:
#         skip = header_row - 1
#         if uploaded_file.name.endswith(".csv"):
#             df = pd.read_csv(uploaded_file, header=skip)
#         else:
#             df = pd.read_excel(uploaded_file, header=skip, engine="openpyxl")

#         df = clean_columns(df)
#         if "Year" in df.columns:
#             df["Year"] = df["Year"].apply(clean_year_column)

#         # Clean text columns to ensure they are strings
#         for c in ["Class", "Day", "Sport", "Activity", "Start", "End"]:
#             if c in df.columns:
#                 df[c] = df[c].astype(str).str.strip()
#         return df
#     except Exception as e:
#         st.error(f"Read Error: {e}")
#         return None


# def style_grid(val):
#     if isinstance(val, str):
#         if "TBC" in val:
#             return (
#                 "background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;"
#             )
#         if val:
#             return (
#                 "background-color: #dcfce7; color: #166534; border: 1px solid #bbf7d0;"
#             )
#     return "color: #e5e7eb;"


# # ==========================================
# # 2. LOGIC ENGINE (FIXED DATE CHECK)
# # ==========================================
# def get_space_for_class(
#     class_code, date_obj, curriculum_records, facility_map, debug_mode=False
# ):
#     class_code = str(class_code).strip()
#     match = re.search(
#         r"^(?:Y|Year)?\s*(\d+)\s*([A-Za-z0-9]+)", class_code, re.IGNORECASE
#     )

#     if not match:
#         return "TBC", "None", "Invalid Class Format"

#     year, cls_str = match.groups()
#     specific_cls = cls_str.upper()[0]
#     day_name = date_obj.strftime("%A")

#     found_sport = None
#     rule_matched_type = None

#     reasons = []

#     for row in curriculum_records:
#         # 1. Year Check
#         if str(row["Year"]) != year:
#             continue

#         # 2. Day Check
#         if "Day" in row and str(row["Day"]).title() not in [
#             day_name,
#             "All",
#             "Nan",
#             "None",
#             "",
#         ]:
#             # Only log if debugging is strictly needed, usually noise
#             continue

#         # 3. Date Check (CRASH FIXED HERE)
#         try:
#             s_str = str(row["Start"])
#             e_str = str(row["End"])

#             # Robust parsing (handles errors gracefully)
#             ts_start = pd.to_datetime(s_str, dayfirst=True, errors="coerce")
#             ts_end = pd.to_datetime(e_str, dayfirst=True, errors="coerce")

#             if pd.isna(ts_start) or pd.isna(ts_end):
#                 if debug_mode:
#                     reasons.append(f"Invalid Date in Rule: {s_str}-{e_str}")
#                 continue

#             r_start = ts_start.date()
#             r_end = ts_end.date()

#             # FIX: Check if date_obj is 'datetime' (has .date()) or just 'date' (is .date())
#             current_d = date_obj
#             if isinstance(date_obj, datetime):
#                 current_d = date_obj.date()

#             if not (r_start <= current_d <= r_end):
#                 # Valid date, just not in range. Skip silently.
#                 continue
#         except Exception as e:
#             if debug_mode:
#                 reasons.append(f"Date Parse Error: {e}")
#             continue

#         # 4. Class Match
#         r_class = str(row["Class"]).upper()
#         if r_class == cls_str.upper():
#             found_sport = row.get("Sport", row.get("Activity"))
#             rule_matched_type = "Exact"
#             break
#         elif r_class == specific_cls and rule_matched_type != "Exact":
#             found_sport = row.get("Sport", row.get("Activity"))
#             rule_matched_type = "Letter"
#         elif r_class == "ALL" and not found_sport:
#             found_sport = row.get("Sport", row.get("Activity"))
#             rule_matched_type = "All"

#     if not found_sport:
#         debug_msg = f"No Rule found for Y{year}"
#         if debug_mode and reasons:
#             debug_msg += f" | Debug: {'; '.join(reasons[:2])}..."
#         return "TBC", "None", debug_msg

#     # 5. Facility Map
#     found_sport_clean = str(found_sport).title().strip()
#     assigned_space = "TBC"

#     if found_sport_clean in facility_map:
#         assigned_space = facility_map[found_sport_clean]
#     else:
#         for key_sport, val_space in facility_map.items():
#             if key_sport.lower() in found_sport_clean.lower():
#                 assigned_space = val_space
#                 break

#     if assigned_space == "TBC":
#         return "TBC", found_sport, f"Sport '{found_sport}' not in Facility List"

#     return assigned_space, found_sport, "Matched"


# # ==========================================
# # 3. UI LAYOUT
# # ==========================================
# st.title("🏅 PE Space Master Pro")

# if "results_df" not in st.session_state:
#     st.session_state.results_df = None
# if "run_complete" not in st.session_state:
#     st.session_state.run_complete = False

# # --- SIDEBAR ---
# with st.sidebar:
#     st.header("🎮 Controls")
#     start_date = st.date_input("Start Date", date(2025, 9, 1))  # Explicitly using date
#     debug_mode = st.checkbox("🐞 Debug Mode", value=False)
#     st.markdown("---")
#     run_btn = st.button("🚀 Run Allocation", type="primary", use_container_width=True)
#     if st.button("🔓 Log Out"):
#         st.session_state.authenticated = False
#         st.rerun()

# # --- CONFIGURATION ---
# expander_state = not st.session_state.run_complete
# with st.expander("⚙️ Setup & Configuration", expanded=expander_state):
#     tab_files, tab_facilities = st.tabs(["📂 1. Upload Data", "🏟️ 2. Facility Manager"])

#     with tab_files:
#         col_f1, col_f2 = st.columns(2)
#         with col_f1:
#             st.markdown("#### 1. Timetable")
#             file_tt = st.file_uploader(
#                 "Upload Timetable", type=["csv", "xlsx"], key="tt"
#             )
#         with col_f2:
#             st.markdown("#### 2. Curriculum")
#             file_curr = st.file_uploader(
#                 "Upload Curriculum (Rules)", type=["csv", "xlsx"], key="curr"
#             )
#         header_idx = st.number_input("Header Row Index", min_value=1, value=1)

#     with tab_facilities:
#         if "facility_map_df" not in st.session_state:
#             st.session_state.facility_map_df = pd.DataFrame(
#                 list(DEFAULT_FACILITIES.items()), columns=["Sport", "Space"]
#             )
#         edited_facilities = st.data_editor(
#             st.session_state.facility_map_df,
#             num_rows="dynamic",
#             use_container_width=True,
#             height=300,
#         )
#         FACILITY_MAP = dict(zip(edited_facilities["Sport"], edited_facilities["Space"]))
#         ALL_KNOWN_SPACES = sorted(list(set(FACILITY_MAP.values())))

# # ==========================================
# # 4. EXECUTION
# # ==========================================
# if run_btn:
#     if file_tt and file_curr:
#         df_tt = read_file(file_tt, header_idx)
#         df_curr = read_file(file_curr, header_idx)

#         if df_tt is not None and df_curr is not None:
#             results = []
#             curriculum_records = df_curr.to_dict("records")
#             dates_to_run = []
#             d = start_date  # This is a date object
#             while len(dates_to_run) < 10:
#                 if d.weekday() < 5:
#                     dates_to_run.append(d)
#                 d += timedelta(days=1)

#             progress_bar = st.progress(0, text="Allocating Sports...")

#             for i, curr_date in enumerate(dates_to_run):
#                 week_type = "Week A" if i < 5 else "Week B"
#                 day_name = curr_date.strftime("%A")
#                 date_str = curr_date.strftime("%Y-%m-%d")

#                 daily_tt = df_tt[
#                     (df_tt["Week"].str.upper() == week_type.upper())
#                     & (df_tt["Day"].str.upper() == day_name.upper())
#                 ]

#                 for _, row in daily_tt.iterrows():
#                     for p in range(1, 6):
#                         col = f"Period {p}"
#                         if col in row and pd.notna(row[col]):
#                             cls = str(row[col]).strip()
#                             if len(cls) > 1 and cls.lower() not in [
#                                 "lunch",
#                                 "free",
#                                 "break",
#                                 "nan",
#                             ]:
#                                 space, sport, reason = get_space_for_class(
#                                     cls,
#                                     curr_date,
#                                     curriculum_records,
#                                     FACILITY_MAP,
#                                     debug_mode,
#                                 )
#                                 results.append(
#                                     {
#                                         "Date": date_str,
#                                         "Week": week_type,
#                                         "Day": day_name,
#                                         "Period": f"Period {p}",
#                                         "Class": cls,
#                                         "Activity": sport,
#                                         "Space": space,
#                                         "Reason": reason,
#                                         "Staff": str(
#                                             row.get("Staff", "Unknown")
#                                         ).strip(),
#                                     }
#                                 )
#                 progress_bar.progress((i + 1) / 10)

#             progress_bar.empty()
#             st.session_state.results_df = pd.DataFrame(results)
#             st.session_state.run_complete = True
#             st.rerun()
#     else:
#         st.error("⚠️ Please upload files first.")

# # ==========================================
# # 5. DASHBOARD
# # ==========================================
# if st.session_state.results_df is not None:
#     df = st.session_state.results_df.copy()

#     st.markdown("## 📊 Allocation Dashboard")
#     tab_teacher, tab_space, tab_issues, tab_tools = st.tabs(
#         ["👩‍🏫 Teacher View", "🏟️ Space Master", "⚠️ TBC Issues", "🛠️ Tools"]
#     )

#     # === TAB 1: TEACHER VIEW ===
#     with tab_teacher:
#         c1, c2, c3 = st.columns([1, 1, 2])
#         with c1:
#             all_staff = sorted(df["Staff"].unique().tolist())
#             sel_teacher = st.selectbox("Select Teacher:", all_staff)
#         with c2:
#             sel_week = st.radio("Select Week:", ["Week A", "Week B"], horizontal=True)
#         with c3:
#             view_type = st.radio(
#                 "View Mode:", ["🗺️ Grid View", "📄 List View"], horizontal=True
#             )

#         d_t = df[(df["Staff"] == sel_teacher) & (df["Week"] == sel_week)].copy()

#         if view_type == "🗺️ Grid View":
#             if not d_t.empty:
#                 d_t["Cell"] = d_t.apply(
#                     lambda x: f"{x['Class']}\n{x['Activity']}\n({x['Space']})"
#                     if x["Space"] != "TBC"
#                     else f"{x['Class']}\n(TBC)",
#                     axis=1,
#                 )
#                 days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
#                 grid = d_t.pivot_table(
#                     index="Period",
#                     columns="Day",
#                     values="Cell",
#                     aggfunc=lambda x: " / ".join(x.unique()),
#                 )
#                 grid = grid.reindex(
#                     columns=[d for d in days_order if d in grid.columns]
#                 ).sort_index()
#                 st.dataframe(
#                     grid.style.map(style_grid), use_container_width=True, height=500
#                 )
#             else:
#                 st.info("No classes found.")
#         else:
#             st.dataframe(d_t, use_container_width=True)

#         b = io.BytesIO()
#         with pd.ExcelWriter(b, engine="xlsxwriter") as w:
#             d_t.to_excel(w, index=False)
#         st.download_button(
#             "📥 Download Schedule", b.getvalue(), f"{sel_teacher}_Schedule.xlsx"
#         )

#     # === TAB 3: TBC ISSUES ===
#     with tab_issues:
#         st.subheader("🚨 Why are classes TBC?")
#         tbc_df = df[df["Space"] == "TBC"]

#         if not tbc_df.empty:
#             st.error(f"Found {len(tbc_df)} unallocated classes.")
#             reasons = tbc_df["Reason"].value_counts().reset_index()
#             reasons.columns = ["Reason for Error", "Count"]
#             st.dataframe(reasons, use_container_width=True)
#             st.dataframe(
#                 tbc_df[["Week", "Day", "Period", "Class", "Activity", "Reason"]].head(
#                     20
#                 )
#             )
#         else:
#             st.success("✅ Perfection! All classes have been allocated a space.")


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

    # NEW: Scope Selector
    run_scope = st.radio(
        "Select Scope:",
        ["Both Weeks (Default)", "Week A Only", "Week B Only"],
        help="Choose whether to generate the schedule for the full 2-week cycle or just one specific week.",
    )

    start_date = st.date_input("Start Date (Monday)", date(2025, 9, 1))
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

            # --- NEW DATE GENERATION LOGIC ---
            dates_to_run = []
            d = start_date

            # Determine how many days to fetch based on selection
            days_needed = 10 if "Both" in run_scope else 5

            while len(dates_to_run) < days_needed:
                if d.weekday() < 5:
                    dates_to_run.append(d)
                d += timedelta(days=1)

            progress_bar = st.progress(0, text="Allocating Sports...")

            for i, curr_date in enumerate(dates_to_run):
                # --- NEW WEEK LABEL LOGIC ---
                if run_scope == "Week A Only":
                    week_type = "Week A"
                elif run_scope == "Week B Only":
                    week_type = "Week B"
                else:
                    # Default: First 5 days are A, next 5 are B
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
                progress_bar.progress((i + 1) / days_needed)

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
            # Only show Week Selector if we actually have both weeks
            available_weeks = sorted(df["Week"].unique().tolist())
            if len(available_weeks) > 1:
                sel_week = st.radio("Select Week:", available_weeks, horizontal=True)
            else:
                sel_week = available_weeks[0]
                st.info(f"Showing **{sel_week}**")

        with c3:
            view_type = st.radio(
                "View Mode:", ["🗺️ Grid View", "📄 List View"], horizontal=True
            )

        d_t = df[(df["Staff"] == sel_teacher) & (df["Week"] == sel_week)].copy()

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

        b = io.BytesIO()
        with pd.ExcelWriter(b, engine="xlsxwriter") as w:
            d_t.to_excel(w, index=False)
        st.download_button(
            "📥 Download Schedule", b.getvalue(), f"{sel_teacher}_Schedule.xlsx"
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