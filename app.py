import streamlit as st
from supabase import create_client, Client
from datetime import datetime, date
from urllib.parse import unquote
import os
import base64
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

# Page Configuration
st.set_page_config(
    page_title="Job Application Tracker",
    page_icon="🚀",
    layout="wide"
)

# Custom CSS for better styling
st.markdown("""
    <style>
    /* Main text color and shadow for better contrast */
    h1, h2, h3, h4, h5, h6, .stMarkdown, .stMetricLabel, .stMetricValue, p {
        color: white !important;
        text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
    }
    
    /* Dark Glassmorphism for Job Cards using :has() selector */
    div[data-testid="stVerticalBlock"]:has(div.job-card-marker) {
        background-color: rgba(15, 23, 42, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 20px;
        margin-bottom: 20px;
        width: 100%; /* Full width to prevent alignment issues */
        backdrop-filter: blur(10px);
    }
    
    /* Dashboard metric cards */
    div[data-testid="stVerticalBlock"]:has(div.metric-card-marker) {
        background: rgba(15, 23, 42, 0.85);
        border: 1px solid rgba(255, 255, 255, 0.12);
        border-radius: 12px;
        padding: 20px;
        backdrop-filter: blur(10px);
        text-align: center;
    }

    .metric-value {
        font-size: 2.4rem;
        font-weight: 700;
        color: #60a5fa !important;
        text-shadow: none !important;
        line-height: 1.1;
    }

    .metric-label {
        font-size: 0.85rem;
        color: rgba(255,255,255,0.6) !important;
        text-shadow: none !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-top: 4px;
    }

    .metric-accent-green  { color: #34d399 !important; }
    .metric-accent-purple { color: #a78bfa !important; }
    .metric-accent-yellow { color: #fbbf24 !important; }

    .job-header {
        font-size: 1.2rem;
        font-weight: bold;
        color: #ffffff;
        margin-bottom: 0.5rem;
    }
    
    .job-role {
        font-size: 1rem;
        color: #dddddd;
        margin-bottom: 0.5rem;
    }
    
    /* Styles for buttons to popup on dark background */
    .stButton>button {
        width: 100%;
        background-color: rgba(255, 255, 255, 0.1);
        color: white;
        border: 1px solid rgba(255, 255, 255, 0.2);
    }
    .stButton>button:hover {
        background-color: rgba(255, 255, 255, 0.2);
        border-color: white;
        color: white;
    }
    
    /* Tab styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background: rgba(15, 23, 42, 0.6);
        border-radius: 10px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: rgba(255,255,255,0.7);
        font-weight: 500;
    }
    .stTabs [aria-selected="true"] {
        background: rgba(96, 165, 250, 0.2) !important;
        color: #60a5fa !important;
    }

    /* Background Video Container */
    #myVideo {
        position: fixed;
        right: 0;
        bottom: 0;
        min-width: 100%; 
        min-height: 100%;
        z-index: -2;
    }
    
    /* Dark Overlay for Video */
    #videoOverlay {
        position: fixed;
        right: 0;
        bottom: 0;
        min-width: 100%; 
        min-height: 100%;
        background: rgba(0, 0, 0, 0.5);
        z-index: -1;
    }
    
    .stApp {
        background: rgba(0,0,0,0);
    }
    </style>
""", unsafe_allow_html=True)

@st.cache_data
def get_base64_video(video_path):
    with open(video_path, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

def set_background_video():
    video_path = "background.mp4"
    if os.path.exists(video_path):
        video_base64 = get_base64_video(video_path)
        video_html = f"""
        <video autoplay muted loop id="myVideo">
            <source src="data:video/mp4;base64,{video_base64}" type="video/mp4">
        </video>
        <div id="videoOverlay"></div>
        """
        st.markdown(video_html, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Background video not found. Please ensure 'background.mp4' is in the project directory.")

set_background_video()

# Initialize Supabase Client
@st.cache_resource
def init_supabase():
    """Initialize Supabase client with credentials from environment or secrets"""
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except (FileNotFoundError, KeyError):
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
    
    if not url or not key:
        st.error("""
        ⚠️ **Supabase credentials not found!**
        
        Please set up your credentials using one of these methods:
        
        **Option 1: Local Development (secrets.toml)**
        1. Create a file: `.streamlit/secrets.toml`
        2. Add your credentials:
        ```
        SUPABASE_URL = "https://your-project.supabase.co"
        SUPABASE_KEY = "your-anon-key-here"
        ```
        
        **Option 2: Environment Variables**
        ```bash
        export SUPABASE_URL="https://your-project.supabase.co"
        export SUPABASE_KEY="your-anon-key-here"
        ```
        """)
        st.stop()
    
    try:
        return create_client(url, key)
    except Exception as e:
        st.error(f"❌ Failed to connect to Supabase: {str(e)}")
        st.info("Please check that your SUPABASE_URL and SUPABASE_KEY are correct.")
        st.stop()

supabase: Client = init_supabase()

# Status options - MUST match the database constraint exactly (case-sensitive)
STATUS_OPTIONS = ["Applied", "Accepted", "Withdrawn", "Rejected"]

# Status color map for charts
STATUS_COLORS = {
    "Applied":   "#60a5fa",
    "Accepted":  "#34d399",
    "Withdrawn": "#fbbf24",
    "Rejected":  "#f87171",
}

# ── Helper Functions ──────────────────────────────────────────────────────────

def upload_resume_to_storage(uploaded_file, company_name):
    """Upload resume to Supabase Storage and return public URL"""
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = uploaded_file.name
        file_path = f"{company_name.replace(' ', '_')}_{timestamp}_{file_name}"
        file_bytes = uploaded_file.getvalue()
        response = supabase.storage.from_("resumes").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
        public_url = supabase.storage.from_("resumes").get_public_url(file_path)
        return public_url, file_path
    except Exception as e:
        st.error(f"Error uploading file: {str(e)}")
        return None, None

def insert_job_application(company, role, status, resume_url, resume_path):
    """Insert new job application into database"""
    try:
        if status not in STATUS_OPTIONS:
            st.error(f"Invalid status '{status}'. Must be one of: {', '.join(STATUS_OPTIONS)}")
            return False
        data = {
            "company_name": company,
            "role": role,
            "status": status,
            "resume_url": resume_url,
            "applied_date": datetime.now().isoformat()
        }
        supabase.table("job_applications").insert(data).execute()
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "constraint" in error_msg or "check" in error_msg:
            st.error(f"""
            ❌ **Database Constraint Error**
            
            The status '{status}' is not allowed by the database.
            
            **Allowed values:** {', '.join(STATUS_OPTIONS)}
            """)
        else:
            st.error(f"Error saving application: {str(e)}")
        return False

def fetch_all_applications():
    """Fetch all job applications from database"""
    try:
        response = supabase.table("job_applications").select("*").order("applied_date", desc=True).execute()
        return response.data
    except Exception as e:
        st.error(f"Error fetching applications: {str(e)}")
        return []

def update_application_status(app_id, new_status):
    """Update job application status"""
    try:
        if new_status not in STATUS_OPTIONS:
            st.error(f"Invalid status '{new_status}'. Must be one of: {', '.join(STATUS_OPTIONS)}")
            return False
        supabase.table("job_applications").update(
            {"status": new_status}
        ).eq("id", app_id).execute()
        return True
    except Exception as e:
        error_msg = str(e).lower()
        if "constraint" in error_msg or "check" in error_msg:
            st.error(f"""
            ❌ **Database Constraint Error**
            
            The status '{new_status}' is not allowed by the database.
            Please check that STATUS_OPTIONS in the code matches the SQL constraint.
            """)
        else:
            st.error(f"Error updating status: {str(e)}")
        return False

def delete_application(app_id, resume_url):
    """Delete application and associated resume file"""
    try:
        if resume_url:
            file_path = unquote(resume_url.split("/resumes/")[-1]) if "/resumes/" in resume_url else None
            if file_path:
                try:
                    supabase.storage.from_("resumes").remove([file_path])
                except Exception as storage_error:
                    st.warning(f"Could not delete resume file: {str(storage_error)}")
        supabase.table("job_applications").delete().eq("id", app_id).execute()
        return True
    except Exception as e:
        st.error(f"Error deleting application: {str(e)}")
        return False

# ── Dashboard Helpers ─────────────────────────────────────────────────────────

PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="white", family="sans-serif"),
    margin=dict(l=20, r=20, t=40, b=20),
)

def build_dashboard(df: pd.DataFrame):
    """Render all dashboard rows."""

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown("### 🎛️ Filters")
    fcol1, fcol2, fcol3 = st.columns([2, 2, 1])
    min_date = df["applied_date"].min().date() if not df.empty else date(2024, 1, 1)
    max_date = df["applied_date"].max().date() if not df.empty else date.today()

    with fcol1:
        start_date = st.date_input("From", value=min_date, key="dash_start")
    with fcol2:
        end_date = st.date_input("To", value=max_date, key="dash_end")
    with fcol3:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()

    # Apply date filter
    mask = (df["applied_date"].dt.date >= start_date) & (df["applied_date"].dt.date <= end_date)
    df = df[mask].copy()

    if df.empty:
        st.info("📭 No applications in the selected date range. Adjust the filter or add more applications!")
        return

    st.divider()

    # ── Row 1 – Key Metric Cards ──────────────────────────────────────────────
    total = len(df)
    applied_count  = len(df[df["status"] == "Applied"])
    accepted_count = len(df[df["status"] == "Accepted"])
    acceptance_rate = (accepted_count / total * 100) if total else 0

    mc1, mc2, mc3, mc4 = st.columns(4)

    def metric_card(col, label, value, accent_class=""):
        with col:
            with st.container():
                st.markdown('<div class="metric-card-marker"></div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="metric-value {accent_class}">{value}</div>'
                    f'<div class="metric-label">{label}</div>',
                    unsafe_allow_html=True
                )

    metric_card(mc1, "Total Applications", total)
    metric_card(mc2, "Applied",  applied_count,  "metric-accent-yellow")
    metric_card(mc3, "Accepted", accepted_count, "metric-accent-green")
    metric_card(mc4, "Acceptance Rate", f"{acceptance_rate:.1f}%", "metric-accent-purple")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Row 2 – Acceptance Rate Over Time  +  Status Pie ─────────────────────
    rc2l, rc2r = st.columns(2)

    with rc2l:
        st.markdown("#### 📈 Acceptance Rate Over Time")
        monthly = df.copy()
        monthly["month"] = monthly["applied_date"].dt.to_period("M")
        grp = monthly.groupby("month").apply(
            lambda g: pd.Series({
                "total": len(g),
                "accepted": (g["status"] == "Accepted").sum()
            })
        ).reset_index()
        grp["rate"] = grp["accepted"] / grp["total"] * 100
        grp["month_str"] = grp["month"].dt.strftime("%b %Y")

        if len(grp) >= 1:
            fig_line = go.Figure()
            fig_line.add_trace(go.Scatter(
                x=grp["month_str"],
                y=grp["rate"],
                mode="lines+markers",
                line=dict(color="#60a5fa", width=2.5),
                marker=dict(size=8, color="#60a5fa", line=dict(color="white", width=1.5)),
                fill="tozeroy",
                fillcolor="rgba(96,165,250,0.15)",
                name="Acceptance Rate",
                hovertemplate="%{x}<br>Rate: %{y:.1f}%<extra></extra>"
            ))
            fig_line.update_layout(
                **PLOTLY_LAYOUT,
                xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
                yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)",
                           ticksuffix="%", range=[0, 105]),
                height=320,
            )
            st.plotly_chart(fig_line, use_container_width=True)
        else:
            st.info("Add applications across multiple months to see the trend.")

    with rc2r:
        st.markdown("#### 🍩 Status Distribution")
        status_counts = df["status"].value_counts().reset_index()
        status_counts.columns = ["status", "count"]
        colors = [STATUS_COLORS.get(s, "#94a3b8") for s in status_counts["status"]]

        fig_pie = go.Figure(go.Pie(
            labels=status_counts["status"],
            values=status_counts["count"],
            hole=0.4,
            marker=dict(colors=colors, line=dict(color="rgba(0,0,0,0.3)", width=2)),
            textinfo="percent+label",
            hovertemplate="%{label}: %{value} applications<extra></extra>",
        ))
        fig_pie.update_layout(
            **PLOTLY_LAYOUT,
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5),
            height=320,
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    # ── Row 3 – Acceptance Rate by Role ──────────────────────────────────────
    st.markdown("#### 💼 Acceptance Rate by Role")
    role_grp = df.groupby("role").apply(
        lambda g: pd.Series({
            "total": len(g),
            "accepted": (g["status"] == "Accepted").sum()
        })
    ).reset_index()
    role_grp["rate"] = role_grp["accepted"] / role_grp["total"] * 100
    role_grp["label"] = role_grp.apply(
        lambda r: f"{int(r['accepted'])} accepted / {int(r['total'])} total", axis=1
    )
    role_grp = role_grp.sort_values("rate", ascending=True)

    bar_colors = [
        "#34d399" if r > 50 else "#fbbf24" if r >= 25 else "#f87171"
        for r in role_grp["rate"]
    ]

    fig_role = go.Figure(go.Bar(
        x=role_grp["rate"],
        y=role_grp["role"],
        orientation="h",
        marker_color=bar_colors,
        text=role_grp["label"],
        textposition="outside",
        hovertemplate="%{y}<br>Rate: %{x:.1f}%<extra></extra>",
    ))
    fig_role.update_layout(
        **PLOTLY_LAYOUT,
        xaxis=dict(ticksuffix="%", range=[0, 115],
                   showgrid=True, gridcolor="rgba(255,255,255,0.08)"),
        yaxis=dict(showgrid=False),
        height=max(280, 50 * len(role_grp)),
        bargap=0.3,
    )
    st.plotly_chart(fig_role, use_container_width=True)

    # ── Row 4 – Top Companies  +  Recent Applications ────────────────────────
    rb5l, rb5r = st.columns(2)

    with rb5l:
        st.markdown("#### 🏢 Top Companies")
        top_co = (
            df["company_name"].value_counts()
            .head(10)
            .reset_index()
        )
        top_co.columns = ["company", "count"]
        top_co = top_co.sort_values("count", ascending=True)

        fig_co = go.Figure(go.Bar(
            x=top_co["count"],
            y=top_co["company"],
            orientation="h",
            marker_color="#60a5fa",
            hovertemplate="%{y}: %{x} applications<extra></extra>",
        ))
        fig_co.update_layout(
            **PLOTLY_LAYOUT,
            xaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.08)", dtick=1),
            yaxis=dict(showgrid=False),
            height=max(280, 42 * len(top_co)),
            bargap=0.3,
        )
        st.plotly_chart(fig_co, use_container_width=True)

    with rb5r:
        st.markdown("#### 🕐 Recent Applications")
        recent = df.sort_values("applied_date", ascending=False).head(5).copy()
        recent["Date"] = recent["applied_date"].dt.strftime("%b %d, %Y")

        status_badge = {
            "Applied":   "🔵",
            "Accepted":  "🟢",
            "Withdrawn": "🟡",
            "Rejected":  "🔴",
        }
        recent["Status"] = recent["status"].apply(lambda s: f"{status_badge.get(s, '⚪')} {s}")

        display = recent[["company_name", "role", "Status", "Date"]].copy()
        display.columns = ["Company", "Role", "Status", "Date"]
        display = display.reset_index(drop=True)

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
            height=min(210, 42 * (len(display) + 1)),
        )


# ── Sidebar – Add New Application ─────────────────────────────────────────────
with st.sidebar:
    st.header("➕ Add New Application")
    
    with st.form("add_job_form", clear_on_submit=True):
        company  = st.text_input("Company Name *", placeholder="e.g., Google")
        role     = st.text_input("Role/Position *", placeholder="e.g., Software Engineer")
        status   = st.selectbox("Status", STATUS_OPTIONS)
        uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
        
        submitted = st.form_submit_button("💾 Save Application", use_container_width=True)
        
        if submitted:
            if not company or not role:
                st.error("⚠️ Company name and role are required!")
            else:
                with st.spinner("Saving application..."):
                    resume_url = None
                    resume_path = None
                    if uploaded_file:
                        resume_url, resume_path = upload_resume_to_storage(uploaded_file, company)
                        if not resume_url:
                            st.error("Failed to upload resume. Please try again.")
                            st.stop()
                    success = insert_job_application(company, role, status, resume_url, resume_path)
                    if success:
                        st.success("✅ Application saved successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save application.")
    
    st.divider()
    st.caption("💡 Tip: Upload your resume as a PDF for each application")


# ── Main Content ──────────────────────────────────────────────────────────────
st.title("JOB APPLICATION CONTAINER")
st.markdown("Store all your applications in one place")

# Fetch data once — shared between both tabs
applications = fetch_all_applications()

tab1, tab2 = st.tabs(["📋 Application Tracker", "📊 Dashboard & Analytics"])

# ── Tab 1: Application Tracker ────────────────────────────────────────────────
with tab1:
    if not applications:
        st.info("📝 No applications yet. Add your first application using the sidebar!")
    else:
        search_query = st.text_input(
            "🔍 Search Applications",
            placeholder="Search by Company or Role..."
        ).strip()

        if search_query:
            filtered_applications = [
                app for app in applications
                if search_query.lower() in app["company_name"].lower()
                or search_query.lower() in app["role"].lower()
            ]
        else:
            filtered_applications = applications

        # Stats row
        col1, col2, col3, col4, col5 = st.columns(5)
        status_counts = {}
        for app in applications:
            s = app.get("status", "Unknown")
            status_counts[s] = status_counts.get(s, 0) + 1

        with col1: st.metric("Total Applications", len(applications))
        with col2: st.metric("Applied",    status_counts.get("Applied",    0))
        with col3: st.metric("Accepted",   status_counts.get("Accepted",   0))
        with col4: st.metric("Withdrawn",  status_counts.get("Withdrawn",  0))
        with col5: st.metric("Rejected",   status_counts.get("Rejected",   0))

        st.divider()

        if search_query:
            st.subheader(f"Search Results ({len(filtered_applications)})")
        else:
            st.subheader("All Applications")

        if not filtered_applications and search_query:
            st.info("No applications found matching your search.")

        for app in filtered_applications:
            with st.container():
                st.markdown('<div class="job-card-marker"></div>', unsafe_allow_html=True)
                c1, c2, c3, c4 = st.columns([3, 3, 2, 2])

                with c1:
                    st.markdown(f"**🏢 {app['company_name']}**")
                    st.caption(f"📅 {datetime.fromisoformat(app['applied_date']).strftime('%b %d, %Y')}")

                with c2:
                    st.markdown(f"**👔 {app['role']}**")
                    if app.get("resume_url"):
                        st.markdown(
                            f'<a href="{app["resume_url"]}" target="_blank" rel="noopener noreferrer">📄 View Resume</a>',
                            unsafe_allow_html=True
                        )

                with c3:
                    new_status = st.selectbox(
                        "Status",
                        STATUS_OPTIONS,
                        index=STATUS_OPTIONS.index(app["status"]) if app["status"] in STATUS_OPTIONS else 0,
                        key=f"status_{app['id']}",
                        label_visibility="collapsed"
                    )
                    if new_status != app["status"]:
                        if update_application_status(app["id"], new_status):
                            st.success("Status updated!")
                            st.rerun()

                with c4:
                    if st.button("🗑️ Delete", key=f"delete_{app['id']}", use_container_width=True):
                        if delete_application(app["id"], app.get("resume_url")):
                            st.success("Deleted!")
                            st.rerun()

# ── Tab 2: Dashboard & Analytics ─────────────────────────────────────────────
with tab2:
    if not applications:
        st.info("📭 No data yet. Add applications to see analytics!")
    else:
        # Build a DataFrame
        df = pd.DataFrame(applications)
        df["applied_date"] = pd.to_datetime(df["applied_date"])
        with st.spinner("Building dashboard…"):
            build_dashboard(df)


# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("---")
st.caption("Developed by Daniel. K")
