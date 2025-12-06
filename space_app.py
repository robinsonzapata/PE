import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import io
import xlsxwriter


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
        return clean_columns(df)
    except Exception as e:
        st.error(f"❌ Read Error: {e}")
        return None


def style_grid(val):
    if isinstance(val, str) and val != "":
        return "background-color: #e0f2fe; color: #0369a1; border: 1px solid #bae6fd;"
    return "color: #e5e7eb;"


# ==========================================
# 2. LOGIC ENGINE
# ==========================================
def check_space(class_code, date_obj, df_rules):
    rules = df_rules.to_dict("records")
    class_code = str(class_code).strip()
    match = re.search(r"(\d+)\s*([A-Za-z]+)", class_code)

    if not match:
        return "TBC"

    year, cls_str = match.groups()
    cls = cls_str.upper()[0]
    day_name = date_obj.strftime("%A")

    for rule in rules:
        try:
            r_start = pd.to_datetime(rule["Start"], dayfirst=True).date()
            r_end = pd.to_datetime(rule["End"], dayfirst=True).date()
            if (
                str(rule["Year"]) == year
                and str(rule["Class"]) == cls
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
st.set_page_config(page_title="PE Space Master Pro", layout="wide", page_icon="🏆")
st.title("🏆 PE Space Master Pro")

if "results_df" not in st.session_state:
    st.session_state.results_df = None
df_timetable, df_rules = None, None

# --- SIDEBAR ---
with st.sidebar:
    st.header("1. Upload Files")
    header_idx = st.number_input("Header Row:", min_value=1, value=1)
    file_tt = st.file_uploader("Timetable", type=["csv", "xlsx"])
    file_rules = st.file_uploader("Rules", type=["csv", "xlsx"])
    if file_tt and file_rules:
        df_timetable = read_file(file_tt, header_idx)
        df_rules = read_file(file_rules, header_idx)
        if df_timetable is not None:
            st.success("Files Loaded")

    st.header("2. Settings")
    start_date = st.date_input("Start", datetime(2025, 9, 5))
    end_date = st.date_input("End", datetime(2025, 12, 19))
    start_week = st.radio("Start Week", ["Week A", "Week B"])

# --- MAIN APP ---
if df_timetable is not None and df_rules is not None:
    # --- VALIDATION ---
    tt_missing = [c for c in ["Week", "Day", "Staff"] if c not in df_timetable.columns]
    if tt_missing:
        st.error(f"❌ Timetable Error: Missing columns {tt_missing}")
        st.stop()

    rules_missing = [
        c
        for c in ["Start", "End", "Year", "Class", "Space", "Day"]
        if c not in df_rules.columns
    ]
    if rules_missing:
        st.error(f"❌ Rules Error: Missing columns {rules_missing}")
        st.stop()

    if st.button("🚀 Run Allocation Engine", type="primary"):
        results = []
        try:
            current_date, week_toggle = start_date, 0 if start_week == "Week A" else 1
            days_count = (end_date - start_date).days + 1
            bar = st.progress(0)

            for i in range(days_count):
                curr = start_date + timedelta(days=i)
                bar.progress((i + 1) / days_count)
                if curr.weekday() < 5:
                    if curr.weekday() == 0 and curr != start_date:
                        week_toggle = 1 - week_toggle
                    wk_label, day_label = (
                        ("Week A" if week_toggle == 0 else "Week B"),
                        curr.strftime("%A"),
                    )

                    daily = df_timetable[
                        (df_timetable["Week"].str.upper() == wk_label.upper())
                        & (df_timetable["Day"].str.upper() == day_label.upper())
                    ]

                    for _, row in daily.iterrows():
                        for p in range(1, 6):
                            col = f"Period {p}"
                            if col in row and pd.notna(row[col]):
                                cls = str(row[col]).strip()
                                if len(cls) > 1:
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
            bar.empty()
            st.session_state.results_df = pd.DataFrame(results) if results else None
        except Exception as e:
            st.error(f"Run Error: {e}")

    # --- RESULTS DASHBOARD ---
    if st.session_state.results_df is not None:
        df = st.session_state.results_df.copy()
        master_spaces = sorted(
            [
                s
                for s in df_rules["Space"].astype(str).unique()
                if s != "nan" and s.strip() != ""
            ]
        )

        st.markdown("---")

        tab_teacher, tab_space, tab_analysis, tab_tools = st.tabs(
            ["👩‍🏫 Teacher View", "🏟️ Space Master", "📊 Analytics", "🛠️ Tools"]
        )

        # ================= TAB 1: TEACHER VIEW =================
        with tab_teacher:
            c1, c2, c3 = st.columns([2, 2, 2])
            with c1:
                all_staff = sorted(df["Staff"].astype(str).unique().tolist())
                sel_teacher = st.selectbox("1. Select Teacher:", all_staff)
            with c2:
                sel_week = st.radio(
                    "2. Select Week:", ["Both", "Week A", "Week B"], horizontal=True
                )
            with c3:
                view_type = st.radio(
                    "3. Show As:",
                    ["🗺️ Map (Grid)", "📄 All Data (List)"],
                    horizontal=True,
                )

            d_t = df[df["Staff"] == sel_teacher].copy()
            if sel_week != "Both":
                d_t = d_t[d_t["Week"] == sel_week]
            st.markdown(f"### 📅 Schedule: **{sel_teacher}**")

            if view_type == "🗺️ Map (Grid)":
                d_t["Info"] = d_t["Class"] + "\n(" + d_t["Space"] + ")"
                days_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
                if sel_week == "Both":
                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.info("Week A")
                        da = d_t[d_t["Week"] == "Week A"]
                        if not da.empty:
                            grid = da.pivot_table(
                                index="Period",
                                columns="Day",
                                values="Info",
                                aggfunc="first",
                            )
                            grid = grid.reindex(
                                columns=[d for d in days_order if d in grid.columns]
                            ).sort_index()
                            st.dataframe(
                                grid.style.map(style_grid), use_container_width=True
                            )
                        else:
                            st.write("No classes.")
                    with col_b:
                        st.info("Week B")
                        db = d_t[d_t["Week"] == "Week B"]
                        if not db.empty:
                            grid = db.pivot_table(
                                index="Period",
                                columns="Day",
                                values="Info",
                                aggfunc="first",
                            )
                            grid = grid.reindex(
                                columns=[d for d in days_order if d in grid.columns]
                            ).sort_index()
                            st.dataframe(
                                grid.style.map(style_grid), use_container_width=True
                            )
                        else:
                            st.write("No classes.")
                else:
                    if not d_t.empty:
                        grid = d_t.pivot_table(
                            index="Period",
                            columns="Day",
                            values="Info",
                            aggfunc="first",
                        )
                        grid = grid.reindex(
                            columns=[d for d in days_order if d in grid.columns]
                        ).sort_index()
                        st.dataframe(
                            grid.style.map(style_grid), use_container_width=True
                        )
                    else:
                        st.warning("No classes.")
            else:
                st.dataframe(d_t, use_container_width=True)

            b = io.BytesIO()
            with pd.ExcelWriter(b, engine="xlsxwriter") as w:
                d_t.to_excel(w, index=False)
            st.download_button(
                f"📥 Download {sel_teacher}",
                b.getvalue(),
                f"{sel_teacher}_Schedule.xlsx",
            )

        # ================= TAB 2: SPACE MASTER =================
        with tab_space:
            w_sel = st.selectbox("Select Week", ["Week A", "Week B"])
            df_heat = df[df["Week"] == w_sel]
            if not df_heat.empty:
                mat = (
                    df_heat.pivot_table(
                        index="Space", columns="Period", values="Class", aggfunc="count"
                    )
                    .fillna(0)
                    .astype(int)
                )
                desired = ["Period 1", "Period 2", "Period 3", "Period 4", "Period 5"]
                mat = mat[[c for c in desired if c in mat.columns]]
                st.dataframe(mat, use_container_width=True)
            else:
                st.info("No data")

        # ================= TAB 3: ANALYTICS =================
        with tab_analysis:
            col_an_1, col_an_2 = st.columns(2)
            with col_an_1:
                st.markdown("### 🏟️ Space Utilization %")
                space_counts = df["Space"].value_counts().reset_index()
                space_counts.columns = ["Space", "Total Allocations"]
                total_curriculum_slots = space_counts["Total Allocations"].sum()
                space_counts["% Share"] = (
                    space_counts["Total Allocations"] / total_curriculum_slots
                )
                st.dataframe(
                    space_counts.style.format({"% Share": "{:.1%}"}).bar(
                        subset=["% Share"], color="#3b82f6"
                    ),
                    use_container_width=True,
                    hide_index=True,
                )

            with col_an_2:
                st.markdown("### 👥 Teacher Workload")
                staff_counts = df["Staff"].value_counts().reset_index()
                staff_counts.columns = ["Teacher", "Classes"]
                st.dataframe(
                    staff_counts.style.bar(subset=["Classes"], color="#10b981"),
                    use_container_width=True,
                    hide_index=True,
                )

        # ================= TAB 4: TOOLS (IMPROVED) =================
        with tab_tools:
            st.subheader("🛠️ Department Tools")

            t1, t2 = st.tabs(["🕵️ Free Space Finder", "🚩 Conflict Report"])

            # TOOL A: FREE SPACE FINDER (DUAL MODE)
            with t1:
                finder_mode = st.radio(
                    "Search Mode:",
                    [
                        "🔄 Recurring (Week A/B Check)",
                        "📅 Specific Date (Calendar Check)",
                    ],
                    horizontal=True,
                )

                if finder_mode == "🔄 Recurring (Week A/B Check)":
                    c_day, c_per = st.columns(2)
                    with c_day:
                        f_day = st.selectbox(
                            "Select Day:",
                            ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
                        )
                    with c_per:
                        f_period = st.selectbox(
                            "Select Period:",
                            [
                                "Period 1",
                                "Period 2",
                                "Period 3",
                                "Period 4",
                                "Period 5",
                            ],
                        )

                    if st.button("🔍 Check Availability"):
                        # Get Used Spaces for Week A
                        used_a = (
                            df[
                                (df["Week"] == "Week A")
                                & (df["Day"] == f_day)
                                & (df["Period"] == f_period)
                            ]["Space"]
                            .unique()
                            .tolist()
                        )
                        # Get Used Spaces for Week B
                        used_b = (
                            df[
                                (df["Week"] == "Week B")
                                & (df["Day"] == f_day)
                                & (df["Period"] == f_period)
                            ]["Space"]
                            .unique()
                            .tolist()
                        )

                        # Calculate Free
                        free_a = set(master_spaces) - set(used_a)
                        free_b = set(master_spaces) - set(used_b)
                        free_both = free_a.intersection(
                            free_b
                        )  # Available in both weeks

                        # Display Results
                        c_res1, c_res2, c_res3 = st.columns(3)

                        with c_res1:
                            st.success(f"✅ Free Both Weeks ({len(free_both)})")
                            st.write(
                                "\n".join([f"- {s}" for s in sorted(list(free_both))])
                            )

                        with c_res2:
                            st.info(f"🔹 Free Week A Only")
                            only_a = free_a - free_both
                            if only_a:
                                st.write(
                                    "\n".join([f"- {s}" for s in sorted(list(only_a))])
                                )
                            else:
                                st.caption("None (All taken or free in both)")

                        with c_res3:
                            st.warning(f"🔸 Free Week B Only")
                            only_b = free_b - free_both
                            if only_b:
                                st.write(
                                    "\n".join([f"- {s}" for s in sorted(list(only_b))])
                                )
                            else:
                                st.caption("None (All taken or free in both)")

                else:  # CALENDAR MODE
                    c_date, c_per = st.columns(2)
                    with c_date:
                        f_date_input = st.date_input("Select Date:", start_date)
                    with c_per:
                        f_period = st.selectbox(
                            "Period:",
                            [
                                "Period 1",
                                "Period 2",
                                "Period 3",
                                "Period 4",
                                "Period 5",
                            ],
                            key="cal_per",
                        )

                    if st.button("Check Specific Date"):
                        # We just query the results_df directly because it already contains specific dates!
                        f_date_str = f_date_input.strftime("%Y-%m-%d")

                        # Find what week type this date actually is from our generated data
                        day_data = df[df["Date"] == f_date_str]

                        if day_data.empty:
                            st.error(
                                "No classes found on this date (Is it a weekend or holiday?)"
                            )
                        else:
                            actual_week_type = day_data.iloc[0]["Week"]
                            st.info(
                                f"Checking **{f_date_str}** ({actual_week_type})..."
                            )

                            # Find used spaces
                            used_spaces = (
                                day_data[day_data["Period"] == f_period]["Space"]
                                .unique()
                                .tolist()
                            )
                            free_spaces = sorted(
                                list(set(master_spaces) - set(used_spaces))
                            )

                            if free_spaces:
                                st.success(f"✅ {len(free_spaces)} Spaces Available:")
                                st.dataframe(
                                    pd.DataFrame(free_spaces, columns=["Free Spaces"]),
                                    use_container_width=True,
                                )
                            else:
                                st.error("❌ Fully Booked!")

            # TOOL B: CONFLICT REPORT
            with t2:
                st.info("List of all double bookings (2+ classes in one space).")
                duplicates = df[
                    df.duplicated(subset=["Week", "Day", "Period", "Space"], keep=False)
                ]
                duplicates = duplicates[duplicates["Space"] != "TBC"]
                if not duplicates.empty:
                    st.error(f"Found {len(duplicates)} Conflicts!")
                    duplicates = duplicates.sort_values(
                        by=["Week", "Day", "Period", "Space"]
                    )
                    st.dataframe(
                        duplicates[
                            ["Week", "Day", "Period", "Space", "Class", "Staff"]
                        ],
                        use_container_width=True,
                    )
                    b2 = io.BytesIO()
                    with pd.ExcelWriter(b2, engine="xlsxwriter") as w:
                        duplicates.to_excel(w, index=False)
                    st.download_button(
                        "📥 Download Conflict Report", b2.getvalue(), "Conflicts.xlsx"
                    )
                else:
                    st.success("✅ No conflicts detected!")

else:
    st.info("👈 Please upload your files to begin.")
