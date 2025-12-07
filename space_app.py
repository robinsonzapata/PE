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
    "Pe": "Field",
    "Gcse Pe": "Classroom 1",
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
        if "Free" in val:
            return "color: #9ca3af; font-style: italic;"
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

    st.markdown("### 1. Scope")
    run_scope = st.radio(
        "Generate:", ["Both Weeks (A & B)", "Week A Only", "Week B Only"]
    )

    st.markdown("### 2. Timeline")
    start_date = st.date_input("Start Date (Monday)", date(2025, 9, 1))

    duration_mode = st.checkbox("Generate Full Term (Multi-week)", value=False)
    if duration_mode:
        num_weeks = st.slider("Weeks to Generate", 2, 12, 8)
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

            dates_to_run = []
            d = start_date

            total_days_needed = num_weeks * 5
            while len(dates_to_run) < total_days_needed:
                if d.weekday() < 5:
                    dates_to_run.append(d)
                d += timedelta(days=1)

            progress_bar = st.progress(0, text="Allocating Sports...")

            for i, curr_date in enumerate(dates_to_run):
                current_week_idx = i // 5
                is_even_week = current_week_idx % 2 == 0
                week_type_calc = "Week A" if is_even_week else "Week B"

                if run_scope == "Week A Only" and week_type_calc == "Week B":
                    continue
                if run_scope == "Week B Only" and week_type_calc == "Week A":
                    continue

                day_name = curr_date.strftime("%A")
                date_str = curr_date.strftime("%Y-%m-%d")

                daily_tt = df_tt[
                    (df_tt["Week"].str.upper() == week_type_calc.upper())
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
                                        "Week": week_type_calc,
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
            # ADD 'VIEW ALL' OPTION
            all_staff_glob = sorted(df["Staff"].unique().tolist())
            all_staff_opts = ["👀 VIEW ALL STAFF"] + all_staff_glob
            sel_teacher = st.selectbox("Select Teacher:", all_staff_opts)

        # Only show week options if NOT viewing all staff
        if sel_teacher != "👀 VIEW ALL STAFF":
            with c2:
                sel_week_type = st.radio(
                    "Select View:",
                    ["Both Weeks (Stacked)", "Week A", "Week B"],
                    horizontal=True,
                    index=0,
                )
            with c3:
                view_type = st.radio(
                    "View Mode:", ["🗺️ Grid View", "📄 List View"], horizontal=True
                )
        else:
            with c2:
                st.write("")  # Spacer
            with c3:
                # Force Grid view for master matrix usually, but allow list
                view_type = st.radio(
                    "View Mode:",
                    ["🗺️ Grid View (Matrix)", "📄 List View"],
                    horizontal=True,
                )

        # --- HELPER: DRAW WEEK GRID (INDIVIDUAL) ---
        def draw_week_grid(dataframe, title):
            if dataframe.empty:
                return

            dataframe = dataframe.copy()
            dataframe["Cell"] = dataframe.apply(
                lambda x: f"{x['Class']}\n{x['Activity']}\n({x['Space']})"
                if x["Space"] != "TBC"
                else f"{x['Class']}\n(TBC)",
                axis=1,
            )

            days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
            grid = dataframe.pivot_table(
                index="Period",
                columns="Day",
                values="Cell",
                aggfunc=lambda x: " / ".join(sorted(x.unique())),
            )
            grid = grid.reindex(
                columns=[d for d in days_order if d in grid.columns]
            ).sort_index()

            st.markdown(f"#### {title}")
            st.dataframe(grid.style.map(style_grid), use_container_width=True)

        # --- HELPER: DRAW MASTER MATRIX (ALL STAFF) ---
        def draw_master_matrix(dataframe, title, all_staff_list):
            st.markdown(f"#### 📅 Master Schedule: {title}")

            dataframe = dataframe.copy()
            dataframe["Cell"] = dataframe.apply(
                lambda x: f"{x['Class']} ({x['Space']})"
                if x["Space"] != "TBC"
                else f"{x['Class']} (TBC)",
                axis=1,
            )

            # Pivot
            grid = dataframe.pivot_table(
                index="Staff", columns="Period", values="Cell", aggfunc="first"
            )

            # REINDEX TO INCLUDE ALL STAFF (Even if free)
            grid = grid.reindex(all_staff_list)
            grid = grid.fillna("Free")  # Fill blanks with "Free"

            # Ensure all periods exist
            all_periods = ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5"]
            grid = grid.reindex(
                columns=[
                    p for p in all_periods if p in grid.columns or p in all_periods
                ],
                fill_value="Free",
            )

            # Sort columns
            grid = grid[sorted(grid.columns)]

            st.dataframe(
                grid.style.map(style_grid), use_container_width=True, height=600
            )

        # --- DISPLAY LOGIC ---

        if sel_teacher == "👀 VIEW ALL STAFF":
            # MASTER VIEW
            if view_type == "🗺️ Grid View (Matrix)":
                st.info(
                    "💡 **Master View:** Select a specific day to see where everyone is."
                )

                # Master Filters
                mc1, mc2 = st.columns(2)
                with mc1:
                    m_week = st.selectbox("Select Week", ["Week A", "Week B"])
                with mc2:
                    m_day = st.selectbox(
                        "Select Day",
                        ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                    )

                # Filter data for that day
                master_day_df = df[(df["Week"] == m_week) & (df["Day"] == m_day)]

                # Draw Matrix passing ALL staff so missing ones appear as "Free"
                draw_master_matrix(master_day_df, f"{m_day} ({m_week})", all_staff_glob)

            else:
                # List View for All
                st.dataframe(
                    df.sort_values(by=["Week", "Day", "Period", "Staff"]),
                    use_container_width=True,
                )

        else:
            # INDIVIDUAL TEACHER VIEW
            d_t = df[df["Staff"] == sel_teacher]

            if view_type == "🗺️ Grid View":
                if "Both" in sel_week_type:
                    # STACKED VIEW
                    df_a = d_t[d_t["Week"] == "Week A"]
                    df_b = d_t[d_t["Week"] == "Week B"]

                    draw_week_grid(df_a, "📅 Week A")
                    if not df_a.empty and not df_b.empty:
                        st.markdown("---")
                    draw_week_grid(df_b, "📅 Week B")
                else:
                    # SINGLE WEEK VIEW
                    d_sub = d_t[d_t["Week"] == sel_week_type]
                    if not d_sub.empty:
                        draw_week_grid(d_sub, f"📅 {sel_week_type}")
                    else:
                        st.info(f"No classes found for {sel_week_type}.")
            else:
                # List View
                if "Both" not in sel_week_type:
                    d_t = d_t[d_t["Week"] == sel_week_type]
                st.dataframe(d_t, use_container_width=True)

        # DOWNLOAD BUTTON
        b = io.BytesIO()
        with pd.ExcelWriter(b, engine="xlsxwriter") as w:
            if sel_teacher == "👀 VIEW ALL STAFF":
                df.to_excel(w, index=False)
                fname = "Master_Schedule.xlsx"
            else:
                df[df["Staff"] == sel_teacher].to_excel(w, index=False)
                fname = f"{sel_teacher}_Schedule.xlsx"

        st.download_button(f"📥 Download Excel", b.getvalue(), fname)

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
