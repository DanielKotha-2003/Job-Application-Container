import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import os
import base64

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
        # Try to get from Streamlit secrets first (for production/cloud deployment)
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
    except (FileNotFoundError, KeyError):
        # Fallback to environment variables for local development
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
# If you modify this list, update the CHECK constraint in supabase_setup.sql
STATUS_OPTIONS = ["Applied", "Accepted", "Withdrawn", "Rejected"]

# Helper Functions
def upload_resume_to_storage(uploaded_file, company_name):
    """Upload resume to Supabase Storage and return public URL"""
    try:
        # Generate unique filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name = uploaded_file.name
        file_path = f"{company_name.replace(' ', '_')}_{timestamp}_{file_name}"
        
        # Get file bytes
        file_bytes = uploaded_file.getvalue()
        
        # Upload to Supabase Storage
        response = supabase.storage.from_("resumes").upload(
            path=file_path,
            file=file_bytes,
            file_options={"content-type": "application/pdf"}
        )
        
        # Get public URL
        public_url = supabase.storage.from_("resumes").get_public_url(file_path)
        
        return public_url, file_path
    
    except Exception as e:
        st.error(f"Error uploading file: {str(e)}")
        return None, None

def insert_job_application(company, role, status, resume_url, resume_path):
    """Insert new job application into database"""
    try:
        # Validate status against allowed values
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
        
        response = supabase.table("job_applications").insert(data).execute()
        return True
    
    except Exception as e:
        error_msg = str(e).lower()
        if "constraint" in error_msg or "check" in error_msg:
            st.error(f"""
            ❌ **Database Constraint Error**
            
            The status '{status}' is not allowed by the database.
            
            **Allowed values:** {', '.join(STATUS_OPTIONS)}
            
            **Fix:** Make sure the status list in Python matches the database CHECK constraint in `supabase_setup.sql`
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
        # Validate status against allowed values
        if new_status not in STATUS_OPTIONS:
            st.error(f"Invalid status '{new_status}'. Must be one of: {', '.join(STATUS_OPTIONS)}")
            return False
        
        response = supabase.table("job_applications").update(
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
        # Extract file path from URL
        if resume_url:
            # URL format: https://[project].supabase.co/storage/v1/object/public/resumes/[file_path]
            file_path = resume_url.split("/resumes/")[-1] if "/resumes/" in resume_url else None
            
            # Delete file from storage
            if file_path:
                try:
                    supabase.storage.from_("resumes").remove([file_path])
                except Exception as storage_error:
                    st.warning(f"Could not delete resume file: {str(storage_error)}")
        
        # Delete from database
        response = supabase.table("job_applications").delete().eq("id", app_id).execute()
        return True
    
    except Exception as e:
        st.error(f"Error deleting application: {str(e)}")
        return False

# Sidebar - Add New Job Application
with st.sidebar:
    st.header("➕ Add New Application")
    
    with st.form("add_job_form", clear_on_submit=True):
        company = st.text_input("Company Name *", placeholder="e.g., Google")
        role = st.text_input("Role/Position *", placeholder="e.g., Software Engineer")
        status = st.selectbox(
            "Status",
            STATUS_OPTIONS
        )
        uploaded_file = st.file_uploader("Upload Resume (PDF)", type=["pdf"])
        
        submitted = st.form_submit_button("💾 Save Application", use_container_width=True)
        
        if submitted:
            if not company or not role:
                st.error("⚠️ Company name and role are required!")
            else:
                with st.spinner("Saving application..."):
                    resume_url = None
                    resume_path = None
                    
                    # Upload resume if provided
                    if uploaded_file:
                        resume_url, resume_path = upload_resume_to_storage(uploaded_file, company)
                        if not resume_url:
                            st.error("Failed to upload resume. Please try again.")
                            st.stop()
                    
                    # Insert into database
                    success = insert_job_application(company, role, status, resume_url, resume_path)
                    
                    if success:
                        st.success("✅ Application saved successfully!")
                        st.rerun()
                    else:
                        st.error("Failed to save application.")
    
    st.divider()
    st.caption("💡 Tip: Upload your resume as a PDF for each application")

# Main Dashboard
st.title("JOB APPLICATION CONTAINER")
st.markdown("Store all your applications in one place")

# Fetch all applications
applications = fetch_all_applications()

if not applications:
    st.info("📝 No applications yet. Add your first application using the sidebar!")
else:
# Search Filter
    search_query = st.text_input("🔍 Search Applications", placeholder="Search by Company or Role...").strip()

    if search_query:
        filtered_applications = [
            app for app in applications
            if search_query.lower() in app['company_name'].lower() or 
               search_query.lower() in app['role'].lower()
        ]
    else:
        filtered_applications = applications

    # Stats at the top
    col1, col2, col3, col4, col5 = st.columns(5)
    
    status_counts = {}
    for app in applications:
        status = app.get("status", "Unknown")
        status_counts[status] = status_counts.get(status, 0) + 1
    
    with col1:
        st.metric("Total Applications", len(applications))
    with col2:
        st.metric("Applied", status_counts.get("Applied", 0))
    with col3:
        st.metric("Accepted", status_counts.get("Accepted", 0))
    with col4:
        st.metric("Withdrawn", status_counts.get("Withdrawn", 0))
    with col5:
        st.metric("Rejected", status_counts.get("Rejected", 0))
    
    st.divider()
    
    if search_query:
        st.subheader(f"Search Results ({len(filtered_applications)})")
    else:
        st.subheader("All Applications")
    
    if not filtered_applications and search_query:
        st.info("No applications found matching your search.")
    
    for app in filtered_applications:
        with st.container():
            # Marker for CSS styling
            st.markdown('<div class="job-card-marker"></div>', unsafe_allow_html=True)
            
            col1, col2, col3, col4 = st.columns([3, 3, 2, 2])
            
            with col1:
                st.markdown(f"**🏢 {app['company_name']}**")
                st.caption(f"📅 {datetime.fromisoformat(app['applied_date']).strftime('%b %d, %Y')}")
            
            with col2:
                st.markdown(f"**👔 {app['role']}**")
                if app.get('resume_url'):
                    # Use target="_blank" to ensure it opens in new tab
                    st.markdown(f'<a href="{app["resume_url"]}" target="_blank" rel="noopener noreferrer">📄 View Resume</a>', unsafe_allow_html=True)
            
            with col3:
                # Status dropdown with unique key
                new_status = st.selectbox(
                    "Status",
                    STATUS_OPTIONS,
                    index=STATUS_OPTIONS.index(app['status']) if app['status'] in STATUS_OPTIONS else 0,
                    key=f"status_{app['id']}",
                    label_visibility="collapsed"
                )
                
                # Update status if changed
                if new_status != app['status']:
                    if update_application_status(app['id'], new_status):
                        st.success("Status updated!")
                        st.rerun()
            
            with col4:
                if st.button("🗑️ Delete", key=f"delete_{app['id']}", use_container_width=True):
                    if delete_application(app['id'], app.get('resume_url')):
                        st.success("Deleted!")
                        st.rerun()
        # st.divider() # Removed divider as cards have their own border now

# Footer
st.markdown("---")
st.caption("Developed by Daniel. K")
