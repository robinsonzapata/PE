import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import xlsxwriter

# ==========================================
# 0. CONFIG & LOGIN SYSTEM
# ==========================================
st.set_page_config(page_title="PE Space Master Pro", layout="wide", page_icon="🏆")

# Simple login credentials
CREDENTIALS = {"admin": "admin123", "teacher": "pe2025"}


def login_system():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if not st.session_state.authenticated:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.markdown("## 🔒 PE Space Master Login")
            st.info("Please log in to access the allocation engine.")
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            if st.button("Log In", type="primary"):
                if username in CREDENTIALS and CREDENTIALS[username] == password:
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("❌ Invalid Username or Password")
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

        # Force columns to strings to avoid matching errors
        cols_to_str = ["Year", "Class", "Day", "Space"]
        for c in cols_to_str:
            if c in df.columns:
                df[c] = df[c].astype(str).str.strip()
        return df
    except Exception as e:
        st.error(f"❌ Read Error: {e}")
        return None


def style_grid(val):
    if isinstance(val, str):
        if "TBC" in val:
            return "background-color: #fee2e2; color: #991b1b; border: 1px solid #fca5a5;"  # Red for TBC
        if val != "":
            return "background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;"  # Blue for allocated
    return "color: #e5e7eb;"


# ==========================================
# 2. LOGIC ENGINE
# ==========================================
def check_space(class_code, date_obj, df_rules):
    """
    Allocates space based on rules.
    Handles '7Hope' -> '7H' and wildcard 'All'.
    """
    rules = df_rules.to_dict("records")
    class_code = str(class_code).strip()

    # REGEX: Extracts Year and First Letter of Class Name
    # Example: "7Hope" -> Year=7, Letter=H
    # Example: "10a PE1" -> Year=10, Letter=A
    match = re.search(r"^(\d+)\s*([A-Za-z]+)", class_code)

    if not match:
        return "TBC"

    year, cls_str = match.groups()
    specific_cls = cls_str.upper()[0]  # Take first letter (H for Hope)
    day_name = date_obj.strftime("%A")

    # --- PASS 1: SPECIFIC MATCH ---
    for rule in rules:
        try:
            r_start = pd.to_datetime(rule["Start"], dayfirst=True).date()
            r_end = pd.to_datetime(rule["End"], dayfirst=True).date()

            if (
                str(rule["Year"]) == year
                and str(rule["Class"]).upper() == specific_cls
                and str(rule["Day"]).title() == day_name
                and r_start <= date_obj.date() <= r_end
            ):
                return rule["Space"]
        except:
            continue

    # --- PASS 2: WILDCARD MATCH ('All') ---
    for rule in rules:
        try:
            r_start = pd.to_datetime(rule["Start"], dayfirst=True).date()
            r_end = pd.to_datetime(rule["End"], dayfirst=True).date()

            if (
                str(rule["Year"]) == year
                and str(rule["Class"]).title() == "All"
                and str(rule["Day"]).title() == day_name
                and r_start <= date_obj.date() <= r_end
            ):
                return rule["Space"]
        except:
            continue

    return "TBC"


# ==========================================
# 3. UI SETUP
# ==========================================
st.title("🏆 PE Space Master Pro")

if "results_df" not in st.session_state:
    st.session_state.results_df = None

df_timetable, df_rules = None, None

# --- SIDEBAR ---
with st.sidebar:
    if st.button("🔓 Log Out"):
        st.session_state.authenticated = False
        st.rerun()

    st.markdown("---")
    st.header("1. Upload Files")
    header_idx = st.number_input("Header Row:", min_value=1, value=1)

    file_tt = st.file_uploader("Timetable (CSV/Excel)", type=["csv", "xlsx"])
    file_rules = st.file_uploader("Rules (CSV/Excel)", type=["csv", "xlsx"])

    # --- TEST MODE SWITCH ---
    use_test_rules = st.checkbox(
        "🧪 Inject Test Rules (Fix TBCs)",
        value=False,
        help="Adds temporary rules for 7Hope, 9Peace etc.",
    )

    if file_tt and file_rules:
        df_timetable = read_file(file_tt, header_idx)
        df_rules = read_file(file_rules, header_idx)

        # --- INJECT TEST RULES IF CHECKED ---
        if use_test_rules and df_rules is not None:
            st.info("🧪 Test Rules Active: Adding rules for 'Hope', 'Peace' etc.")
            new_rules = [
                # 7Hope -> 7H
                {
                    "Year": "7",
                    "Class": "H",
                    "Day": "Tuesday",
                    "Start": "2025-09-01",
                    "End": "2025-12-20",
                    "Space": "Tennis Courts",
                },
                # 9Peace -> 9P
                {
                    "Year": "9",
                    "Class": "P",
                    "Day": "Tuesday",
                    "Start": "2025-09-01",
                    "End": "2025-12-20",
                    "Space": "Gym",
                },
                # 10a PE1 -> 10A
                {
                    "Year": "10",
                    "Class": "A",
                    "Day": "Thursday",
                    "Start": "2025-09-01",
                    "End": "2025-12-20",
                    "Space": "Field",
                },
                # Fallback for Year 7 (Only used if no other match)
                {
                    "Year": "7",
                    "Class": "All",
                    "Day": "Tuesday",
                    "Start": "2025-09-01",
                    "End": "2025-12-20",
                    "Space": "Classroom 1",
                },
            ]
            df_test = pd.DataFrame(new_rules)
            df_rules = pd.concat([df_rules, df_test], ignore_index=True)
            st.success("✅ Files Loaded (Test Rules Added)")
        elif df_timetable is not None and df_rules is not None:
            st.success("✅ Files Loaded")

    st.header("2. Settings")
    start_date = st.date_input("Start Date", datetime(2025, 9, 5))
    end_date = st.date_input("End Date", datetime(2025, 12, 19))
    start_week = st.radio("Start Week Type", ["Week A", "Week B"])

# --- MAIN LOGIC ---
if df_timetable is not None and df_rules is not None:
    # Validation
    tt_missing = [c for c in ["Week", "Day", "Staff"] if c not in df_timetable.columns]
    if tt_missing:
        st.error(f"❌ Timetable Error: Missing columns {tt_missing}")
        st.stop()

    # --- EXECUTION BUTTON ---
    if st.button("🚀 Run Allocation Engine", type="primary"):
        results = []
        try:
            current_date, week_toggle = start_date, 0 if start_week == "Week A" else 1
            days_count = (end_date - start_date).days + 1
            my_bar = st.progress(0, text="Allocating...")

            for i in range(days_count):
                curr = start_date + timedelta(days=i)
                my_bar.progress(
                    (i + 1) / days_count, text=f"Processing {curr.strftime('%d-%b')}"
                )

                if curr.weekday() < 5:  # Mon-Fri
                    if curr.weekday() == 0 and curr != start_date:
                        week_toggle = 1 - week_toggle

                    wk_label = "Week A" if week_toggle == 0 else "Week B"
                    day_label = curr.strftime("%A")

                    # Filter Timetable
                    daily = df_timetable[
                        (df_timetable["Week"].str.upper() == wk_label.upper())
                        & (df_timetable["Day"].str.upper() == day_label.upper())
                    ]

                    for _, row in daily.iterrows():
                        for p in range(1, 6):
                            col = f"Period {p}"
                            if col in row and pd.notna(row[col]):
                                cls = str(row[col]).strip()
                                # Filter out non-class text like "Lunch" or "Free"
                                if len(cls) > 1 and cls.lower() not in [
                                    "lunch",
                                    "break",
                                    "free",
                                ]:
                                    space = check_space(
                                        cls,
                                        datetime.combine(curr, datetime.min.time()),
                                        df_rules,
                                    )
                                    results.append(
                                        {
                                            "Date": curr.strftime("%Y-%m-%d"),
                                            "Week": wk_label,
                                            "Day": day_label,
                                            "Period": f"Period {p}",
                                            "Class": cls,
                                            "Space": space,
                                            "Staff": str(
                                                row.get("Staff", "Unknown")
                                            ).strip(),
                                        }
                                    )
            my_bar.empty()
            st.session_state.results_df = pd.DataFrame(results) if results else None

            if results:
                tbc_count = len([x for x in results if x["Space"] == "TBC"])
                if tbc_count > 0:
                    st.warning(
                        f"⚠️ Done, but {tbc_count} classes are 'TBC'. Check 'Analytics' tab."
                    )
                else:
                    st.success("🎉 Allocation Complete! 100% Matched.")

        except Exception as e:
            st.error(f"Run Error: {e}")

    # --- DASHBOARD ---
    if st.session_state.results_df is not None:
        df = st.session_state.results_df.copy()

        # Master space list for the "Free Space Finder"
        master_spaces = []
        if df_rules is not None:
            master_spaces = sorted(
                [s for s in df_rules["Space"].unique() if str(s).lower() != "nan"]
            )

        st.markdown("---")
        tab_teacher, tab_space, tab_analysis, tab_tools = st.tabs(
            ["👩‍🏫 Teacher View", "🏟️ Space Master", "📊 Analytics", "🛠️ Tools"]
        )

        # TAB 1: TEACHER VIEW
        with tab_teacher:
            c1, c2, c3 = st.columns([2, 2, 2])
            with c1:
                all_staff = sorted(df["Staff"].unique().tolist())
                sel_teacher = st.selectbox("Teacher:", all_staff)
            with c2:
                sel_week = st.radio(
                    "Week:", ["Both", "Week A", "Week B"], horizontal=True
                )
            with c3:
                view_type = st.radio("View:", ["🗺️ Map", "📄 List"], horizontal=True)

            d_t = df[df["Staff"] == sel_teacher].copy()
            if sel_week != "Both":
                d_t = d_t[d_t["Week"] == sel_week]

            st.markdown(f"### Schedule: **{sel_teacher}**")

            if view_type == "🗺️ Map":
                d_t["Info"] = d_t["Class"] + "\n(" + d_t["Space"] + ")"
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]

                def make_grid(data_subset):
                    if data_subset.empty:
                        return None
                    g = data_subset.pivot_table(
                        index="Period", columns="Day", values="Info", aggfunc="first"
                    )
                    return g.reindex(
                        columns=[d for d in days_order if d in g.columns]
                    ).sort_index()

                if sel_week == "Both":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.info("Week A")
                        grid_a = make_grid(d_t[d_t["Week"] == "Week A"])
                        if grid_a is not None:
                            st.dataframe(
                                grid_a.style.map(style_grid), use_container_width=True
                            )
                    with col_b:
                        st.info("Week B")
                        grid_b = make_grid(d_t[d_t["Week"] == "Week B"])
                        if grid_b is not None:
                            st.dataframe(
                                grid_b.style.map(style_grid), use_container_width=True
                            )
                else:
                    grid = make_grid(d_t)
                    if grid is not None:
                        st.dataframe(
                            grid.style.map(style_grid), use_container_width=True
                        )
            else:
                st.dataframe(d_t, use_container_width=True)

            # Download Button
            b = io.BytesIO()
            with pd.ExcelWriter(b, engine="xlsxwriter") as w:
                d_t.to_excel(w, index=False)
            st.download_button(
                f"📥 Download {sel_teacher}",
                b.getvalue(),
                f"{sel_teacher}_Schedule.xlsx",
            )

        # TAB 2: SPACE MASTER
        with tab_space:
            w_sel = st.selectbox("Week Scope", ["Week A", "Week B"])
            df_heat = df[df["Week"] == w_sel]
            if not df_heat.empty:
                mat = (
                    df_heat.pivot_table(
                        index="Space", columns="Period", values="Class", aggfunc="count"
                    )
                    .fillna(0)
                    .astype(int)
                )
                st.subheader(f"🔥 Class Count ({w_sel})")
                st.dataframe(mat, use_container_width=True)
            else:
                st.info("No data.")

        # TAB 3: ANALYTICS
        with tab_analysis:
            c_an1, c_an2 = st.columns(2)
            with c_an1:
                st.markdown("### Space Utilization")
                sc = df["Space"].value_counts().reset_index()
                sc.columns = ["Space", "Allocations"]
                st.dataframe(sc, use_container_width=True)
            with c_an2:
                st.markdown("### Unallocated Classes (TBC)")
                tbc_df = df[df["Space"] == "TBC"]
                if not tbc_df.empty:
                    st.error(f"{len(tbc_df)} Classes are TBC")
                    st.dataframe(
                        tbc_df[
                            ["Week", "Day", "Period", "Class", "Staff"]
                        ].drop_duplicates(),
                        use_container_width=True,
                    )
                else:
                    st.success("All classes allocated!")

        # TAB 4: TOOLS (Updated: Includes BOTH Tools now)
        with tab_tools:
            st.subheader("Department Tools")
            t1, t2 = st.tabs(["Free Space Finder", "Conflict Report"])

            # --- TOOL 1: FREE SPACE FINDER ---
            with t1:
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    f_day = st.selectbox(
                        "Day:", ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                    )
                with col_t2:
                    f_period = st.selectbox(
                        "Period:",
                        ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5"],
                    )

                if st.button("Check Availability"):
                    # Get spaces used in Week A and B
                    used_a = df[
                        (df["Week"] == "Week A")
                        & (df["Day"] == f_day)
                        & (df["Period"] == f_period)
                    ]["Space"].unique()
                    used_b = df[
                        (df["Week"] == "Week B")
                        & (df["Day"] == f_day)
                        & (df["Period"] == f_period)
                    ]["Space"].unique()

                    # Calculate differences
                    free_a = set(master_spaces) - set(used_a)
                    free_b = set(master_spaces) - set(used_b)
                    free_both = free_a.intersection(free_b)

                    c_res1, c_res2, c_res3 = st.columns(3)
                    with c_res1:
                        st.success(f"✅ Free Both Weeks ({len(free_both)})")
                        st.write(list(free_both) if free_both else "None")
                    with c_res2:
                        st.info(f"🔹 Free Week A Only ({len(free_a - free_both)})")
                        st.write(
                            list(free_a - free_both) if (free_a - free_both) else "None"
                        )
                    with c_res3:
                        st.warning(f"🔸 Free Week B Only ({len(free_b - free_both)})")
                        st.write(
                            list(free_b - free_both) if (free_b - free_both) else "None"
                        )

            # --- TOOL 2: CONFLICT REPORT ---
            with t2:
                st.info(
                    "Checks for double bookings (e.g., 7Hope and 7Peace in same space)."
                )
                # Identify duplicates based on Date, Period, and Space
                dupes = df[
                    df.duplicated(subset=["Date", "Period", "Space"], keep=False)
                ]
                # Exclude TBC from conflicts
                dupes = dupes[(dupes["Space"] != "TBC") & (dupes["Space"] != "nan")]

                if not dupes.empty:
                    st.error(f"⚠️ {len(dupes)} Conflicts Found!")
                    st.dataframe(
                        dupes[
                            ["Date", "Period", "Space", "Class", "Staff"]
                        ].sort_values(by=["Date", "Period"])
                    )
                else:
                    st.success("✅ No conflicts detected.")
