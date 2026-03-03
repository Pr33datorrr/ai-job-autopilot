import os
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from src.db_manager import SheetManager
from src.cloud_storage import download_pdf_from_drive
from src.email_dispatcher import send_cold_email

# -- Page Config --
st.set_page_config(
    page_title="AI Job Autopilot - Mission Control",
    page_icon="🎯",
    layout="wide",
)

# -- Header --
st.markdown(
    """
    <style>
    .main-header {
        background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
        padding: 2rem 2.5rem;
        border-radius: 16px;
        margin-bottom: 2rem;
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2.2rem;
        margin: 0;
    }
    .main-header p {
        color: #a0a0cc;
        font-size: 1rem;
        margin: 0.3rem 0 0 0;
    }
    </style>
    <div class="main-header">
        <h1>🎯 AI Job Autopilot - Mission Control</h1>
        <p>Review AI-generated applications before dispatch. Approve, edit, or reject.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# -- Data Fetching --
@st.cache_resource(ttl=30)
def get_sheet_manager():
    return SheetManager()


def fetch_pending_jobs(sheet: SheetManager) -> list[dict]:
    """Fetch all rows with Status == 'Pending Review', with strict 9-column padding."""
    raw = sheet.sheet.get_all_values()
    if len(raw) < 2:
        return []

    rows = []
    for row in raw[1:]:
        # Pad row to 9 columns to prevent gspread truncation issues
        row += [''] * (9 - len(row))

        # Strict unpacking
        hash_id, company, title, status, match_score, pain_point, email, pdf, link = row[:9]

        if status != "Pending Review":
            continue

        # Safe int parse for match_score
        score_val = int(match_score) if str(match_score).isdigit() else 0

        rows.append({
            "Job_Hash_ID": hash_id,
            "Company": company,
            "Job_Title": title,
            "Status": status,
            "Match_Score": score_val,
            "Pain_Point": pain_point,
            "Email_Draft_Body": email,
            "PDF_Cloud_Link": pdf,
            "Job_Link": link,
        })
    return rows


sheet_manager = get_sheet_manager()
pending_jobs = fetch_pending_jobs(sheet_manager)

# -- Empty State --
if not pending_jobs:
    st.balloons()
    st.success("🎉 **All caught up!** No pending applications.")
    st.stop()

# -- Metrics Bar --
col_m1, col_m2, col_m3 = st.columns(3)
col_m1.metric("Pending Review", len(pending_jobs))
avg_score = sum(j["Match_Score"] for j in pending_jobs) / len(pending_jobs)
col_m2.metric("Avg Match Score", f"{avg_score:.0f}")
col_m3.metric("Top Match", max(j["Match_Score"] for j in pending_jobs))

st.divider()

# -- Job Cards --
for idx, job in enumerate(pending_jobs):
    job_hash = job["Job_Hash_ID"]
    company = job["Company"]
    title = job["Job_Title"]
    score_int = job["Match_Score"]
    pain_point = job["Pain_Point"]
    email_draft = job["Email_Draft_Body"]
    pdf_link = job["PDF_Cloud_Link"]
    job_link = job["Job_Link"]

    # -- Rich Header --
    label = f"\U0001f3e2 {company}  |  \U0001f4bc {title}  |  \U0001f3af Match: {score_int}%"

    with st.expander(label, expanded=(idx == 0)):

        # Top Metrics Bar (3 columns)
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
                st.link_button(
                    "\U0001f4c4 View Generated PDF",
                    pdf_link,
                    use_container_width=True,
                )
            else:
                st.caption("No PDF link available.")

        st.divider()

        # Two-Column Workspace
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
                key=f"email_{job_hash}",
                placeholder="recruiter@company.com",
            )

            edited_email = st.text_area(
                "Email Draft (edit before sending)",
                value=email_draft,
                height=350,
                key=f"draft_{job_hash}",
            )

        # Action Footer
        st.divider()

        _, btn_left, btn_right, _ = st.columns([1, 2, 2, 1])

        with btn_left:
            approve = st.button(
                "\u2705 Approve & Dispatch",
                key=f"approve_{job_hash}",
                type="primary",
                use_container_width=True,
            )

        with btn_right:
            reject = st.button(
                "\u274c Reject",
                key=f"reject_{job_hash}",
                use_container_width=True,
            )

        # -- Button Logic --
        if reject:
            sheet_manager.update_status(job_hash, "Rejected - UI")
            st.toast(f"Rejected: {company} \u2014 {title}", icon="\u274c")
            st.rerun()

        if approve:
            if not recruiter_email or "@" not in recruiter_email:
                st.error("\u26a0\ufe0f Please enter a valid recruiter email address before approving.")
                st.stop()

            # Download PDF
            with st.spinner("Downloading PDF from Drive..."):
                local_pdf = os.path.join("output", f"dispatch_{company.replace(' ', '_')}.pdf")
                try:
                    download_pdf_from_drive(pdf_link, local_pdf)
                except Exception as e:
                    st.error(f"Drive download failed: {e}")
                    st.stop()

            # Dispatch Email
            with st.spinner("Dispatching email..."):
                subject = f"Application: {title} \u2014 Yash Gupta"
                success = send_cold_email(
                    to_email=recruiter_email,
                    subject=subject,
                    body_text=edited_email,
                    pdf_attachment_path=local_pdf,
                    test_mode=True,
                )

            if success:
                sheet_manager.update_status(job_hash, "Applied")
                st.toast(f"Dispatched to {recruiter_email}!", icon="\u2705")
                st.rerun()
            else:
                st.error("Email dispatch failed. Check SMTP credentials.")
