import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.db_manager import SheetManager
from src.cloud_storage import download_pdf_from_drive
from src.email_dispatcher import send_cold_email

st.set_page_config(
    page_title="AI Job Autopilot - Mission Control",
    page_icon="\U0001f3af",
    layout="wide",
)


def bootstrap_cloud_env():
    """Write credential files and inject env vars from Streamlit Secrets."""
    os.makedirs("req_files", exist_ok=True)
    if "GCP_SERVICE_ACCOUNT_JSON" in st.secrets:
        sa_path = os.path.join("req_files", "gcp_service_account.json")
        with open(sa_path, "w") as f:
            f.write(st.secrets["GCP_SERVICE_ACCOUNT_JSON"])
        os.environ.setdefault("GOOGLE_SHEETS_CREDENTIALS", sa_path)
    if "GCP_OAUTH_TOKEN_JSON" in st.secrets:
        with open(os.path.join("req_files", "token.json"), "w") as f:
            f.write(st.secrets["GCP_OAUTH_TOKEN_JSON"])
    for env_var in ["GOOGLE_SHEETS_ID", "DRIVE_ROOT_FOLDER_ID", "SAFE_MODE_EMAIL"]:
        if env_var in st.secrets:
            os.environ.setdefault(env_var, st.secrets[env_var])


bootstrap_cloud_env()


st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
    }
    .main-header h1 { color: #ffffff; font-size: 2.2rem; margin: 0; }
    .main-header p { color: #a0a0cc; font-size: 1rem; margin: 0.3rem 0 0 0; }
    </style>
    <div class="main-header">
        <h1>\U0001f3af AI Job Autopilot \u2014 Mission Control</h1>
        <p>Review AI-generated applications before dispatch. Approve, edit, or reject.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

NUM_COLS = 11
COL_NAMES = [
    "Job_Hash_ID", "Company", "Job_Title", "Status",
    "Match_Score", "Evaluation_Reason", "Pain_Point",
    "Email_Draft_Body", "PDF_Cloud_Link", "Job_Link",
    "Applied_To_Email",
]

@st.cache_resource(ttl=30)
def get_sheet_manager():
    return SheetManager()

def _parse_rows(raw):
    parsed = []
    for row in raw[1:]:
        row += [''] * (NUM_COLS - len(row))
        parsed.append(dict(zip(COL_NAMES, row[:NUM_COLS])))
    return parsed

def fetch_by_status(sheet, statuses):
    raw = sheet.sheet.get_all_values()
    if len(raw) < 2:
        return []
    rows = _parse_rows(raw)
    filtered = [r for r in rows if r["Status"] in statuses]
    for r in filtered:
        ms = r["Match_Score"]
        r["Match_Score"] = int(ms) if str(ms).isdigit() else 0
    return filtered

sheet_manager = get_sheet_manager()

tab1, tab2, tab3 = st.tabs([
    "\U0001f4cb Pending Review",
    "\u2705 Dispatch History",
    "\U0001f5d1\ufe0f Evaluation Logs",
])

# TAB 1 - Pending Review
with tab1:
    pending_jobs = fetch_by_status(sheet_manager, ["Pending Review"])
    if not pending_jobs:
        st.success("\U0001f389 **All caught up!** No pending applications.")
    else:
        col_m1, col_m2, col_m3 = st.columns(3)
        col_m1.metric("Pending Review", len(pending_jobs))
        avg_score = sum(j["Match_Score"] for j in pending_jobs) / len(pending_jobs)
        col_m2.metric("Avg Match Score", f"{avg_score:.0f}")
        col_m3.metric("Top Match", max(j["Match_Score"] for j in pending_jobs))
        st.divider()

        for idx, job in enumerate(pending_jobs):
            job_hash = job["Job_Hash_ID"]
            company = job["Company"]
            title = job["Job_Title"]
            score_int = job["Match_Score"]
            eval_reason = job["Evaluation_Reason"]
            pain_point = job["Pain_Point"]
            email_draft = job["Email_Draft_Body"]
            pdf_link = job["PDF_Cloud_Link"]
            job_link = job["Job_Link"]

            label = f"\U0001f3e2 {company}  |  \U0001f4bc {title}  |  \U0001f3af Match: {score_int}%"
            with st.expander(label, expanded=(idx == 0)):
                met_col1, met_col2, met_col3 = st.columns(3)
                with met_col1:
                    st.metric("Match Score", f"{score_int}%")
                    st.progress(min(score_int, 100) / 100.0)
                with met_col2:
                    if pain_point:
                        st.info(f"**Extracted Pain Point**\n\n{pain_point}")
                    else:
                        st.info("No pain point extracted.")
                with met_col3:
                    if pdf_link:
                        st.link_button("\U0001f4c4 View Generated PDF", pdf_link, use_container_width=True)
                    else:
                        st.caption("No PDF link available.")

                if eval_reason:
                    st.caption(f"**12B Evaluation:** {eval_reason}")
                st.divider()

                col_left, col_right = st.columns([1, 1.5])
                with col_left:
                    st.subheader("Context")
                    if job_link:
                        st.markdown(f"[\U0001f517 Link to Original Job Posting]({job_link})")
                    else:
                        st.caption("No job link available.")
                    st.markdown(f"**Company:** {company}")
                    st.markdown(f"**Role:** {title}")
                    st.markdown(f"**Match Score:** {score_int}%")
                    if pain_point:
                        st.markdown("---")
                        st.markdown(f"**Pain Point:** {pain_point}")
                with col_right:
                    st.subheader("Dispatch")
                    recruiter_email = st.text_input(
                        "Target Recruiter Email (Required to Send)",
                        key=f"email_{job_hash}", placeholder="recruiter@company.com",
                    )
                    edited_email = st.text_area(
                        "Email Draft (edit before sending)",
                        value=email_draft, height=350, key=f"draft_{job_hash}",
                    )

                st.divider()
                _, btn_left, btn_right, _ = st.columns([1, 2, 2, 1])
                with btn_left:
                    approve = st.button("\u2705 Approve & Dispatch", key=f"approve_{job_hash}", type="primary", use_container_width=True)
                with btn_right:
                    reject = st.button("\u274c Reject", key=f"reject_{job_hash}", use_container_width=True)

                if reject:
                    sheet_manager.update_status(job_hash, "Rejected - UI")
                    st.toast(f"Rejected: {company} \u2014 {title}", icon="\u274c")
                    st.rerun()
                if approve:
                    if not recruiter_email or "@" not in recruiter_email:
                        st.error("\u26a0\ufe0f Please enter a valid recruiter email address before approving.")
                        st.stop()
                    with st.spinner("Downloading PDF from Drive..."):
                        local_pdf = os.path.join("output", f"dispatch_{company.replace(' ', '_')}.pdf")
                        try:
                            download_pdf_from_drive(pdf_link, local_pdf)
                        except Exception as e:
                            st.error(f"Drive download failed: {e}")
                            st.stop()
                    with st.spinner("Dispatching email..."):
                        subject = f"Application: {title} \u2014 Yash Gupta"
                        success = send_cold_email(
                            to_email=recruiter_email, subject=subject,
                            body_text=edited_email, pdf_attachment_path=local_pdf, test_mode=True,
                        )
                    if success:
                        sheet_manager.update_status(job_hash, "Applied", applied_to_email=recruiter_email)
                        st.toast(f"Dispatched to {recruiter_email}!", icon="\u2705")
                        st.rerun()
                    else:
                        st.error("Email dispatch failed. Check SMTP credentials.")

# TAB 2 - Dispatch History
with tab2:
    applied_jobs = fetch_by_status(sheet_manager, ["Applied"])
    if not applied_jobs:
        st.info("No dispatched applications yet.")
    else:
        st.metric("Total Dispatched", len(applied_jobs))
        st.divider()
        for job in applied_jobs:
            company = job["Company"]
            title = job["Job_Title"]
            score = job["Match_Score"]
            sent_to = job["Applied_To_Email"]
            pdf_link = job["PDF_Cloud_Link"]
            with st.expander(f"\u2705 {company} \u2014 {title} (Score: {score}%)"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**Company:** {company}")
                    st.markdown(f"**Role:** {title}")
                    st.markdown(f"**Match Score:** {score}%")
                    st.markdown(f"**Sent To:** `{sent_to}`" if sent_to else "**Sent To:** N/A")
                with c2:
                    if pdf_link:
                        st.link_button("\U0001f4c4 View Submitted PDF", pdf_link, use_container_width=True)
                    else:
                        st.caption("No PDF link.")

# TAB 3 - Evaluation Logs
with tab3:
    eval_jobs = fetch_by_status(sheet_manager, ["Rejected - Red Flag", "Low Match", "Rejected - UI"])
    if not eval_jobs:
        st.info("No rejected or low-match jobs to display.")
    else:
        red_flags = [j for j in eval_jobs if j["Status"] == "Rejected - Red Flag"]
        low_matches = [j for j in eval_jobs if j["Status"] == "Low Match"]
        ui_rejects = [j for j in eval_jobs if j["Status"] == "Rejected - UI"]
        c1, c2, c3 = st.columns(3)
        c1.metric("\U0001f6a9 Red Flags", len(red_flags))
        c2.metric("\U0001f4c9 Low Match", len(low_matches))
        c3.metric("\U0001f5d1\ufe0f UI Rejected", len(ui_rejects))
        st.divider()
        for job in eval_jobs:
            company = job["Company"]
            title = job["Job_Title"]
            score = job["Match_Score"]
            status = job["Status"]
            eval_reason = job["Evaluation_Reason"]
            pain_point = job["Pain_Point"]
            icon = "\U0001f6a9" if "Red Flag" in status else ("\U0001f4c9" if status == "Low Match" else "\U0001f5d1\ufe0f")
            with st.expander(f"{icon} {company} \u2014 {title} | {status} | Score: {score}%"):
                st.markdown(f"**Status:** {status}")
                st.markdown(f"**Match Score:** {score}%")
                if eval_reason:
                    st.warning(f"**12B Evaluation Reason:**\n\n{eval_reason}")
                else:
                    st.caption("No evaluation reason recorded.")
                if pain_point:
                    st.info(f"**Pain Point:** {pain_point}")
