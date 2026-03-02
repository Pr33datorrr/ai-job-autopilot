import os
import random
import smtplib
import time
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

FROM_ADDRESS = "hello@yashanalytics.pro"
SMTP_HOST = "mail.smtp2go.com"
SMTP_PORT = 2525
RESUME_FILENAME = "Yash_Gupta_Resume.pdf"


def send_cold_email(
    to_email: str,
    subject: str,
    body_text: str,
    pdf_attachment_path: str,
    test_mode: bool = False,
) -> bool:
    """
    Send a cold email with a PDF resume attachment via SMTP2GO.

    Parameters
    ----------
    to_email : str
        Recipient email address.
    subject : str
        Email subject line.
    body_text : str
        Plain-text body of the email.
    pdf_attachment_path : str
        Absolute or relative path to the PDF resume to attach.
    test_mode : bool
        If True, bypasses the human-jitter sleep for fast local testing.

    Returns
    -------
    bool
        True if the email was dispatched successfully, False otherwise.
    """

    # ------------------------------------------------------------------
    # 1.  Human jitter - avoid triggering batch-send spam filters
    # ------------------------------------------------------------------
    if not test_mode:
        delay = random.randint(120, 400)
        print(f"[email_dispatcher] Human jitter: sleeping {delay}s before sending...")
        time.sleep(delay)

    # ------------------------------------------------------------------
    # 2.  Load SMTP credentials
    # ------------------------------------------------------------------
    smtp_user = os.environ.get("SMTP2GO_USERNAME")
    smtp_pass = os.environ.get("SMTP2GO_PASSWORD")

    if not smtp_user or not smtp_pass:
        print("[email_dispatcher] ERROR: SMTP2GO_USERNAME or SMTP2GO_PASSWORD not set.")
        return False

    # ------------------------------------------------------------------
    # 3.  Build the email message
    # ------------------------------------------------------------------
    msg = MIMEMultipart()
    msg["From"] = FROM_ADDRESS
    msg["To"] = to_email
    msg["Subject"] = subject

    # Plain-text body
    msg.attach(MIMEText(body_text, "plain"))

    # ------------------------------------------------------------------
    # 4.  Attach the PDF resume
    # ------------------------------------------------------------------
    try:
        with open(pdf_attachment_path, "rb") as pdf_file:
            pdf_data = pdf_file.read()

        attachment = MIMEApplication(pdf_data, _subtype="pdf")
        attachment.add_header(
            "Content-Disposition",
            "attachment",
            filename=RESUME_FILENAME,
        )
        msg.attach(attachment)
    except FileNotFoundError:
        print(f"[email_dispatcher] ERROR: PDF not found at '{pdf_attachment_path}'.")
        return False
    except Exception as exc:
        print(f"[email_dispatcher] ERROR reading PDF attachment: {exc}")
        return False

    # ------------------------------------------------------------------
    # 5.  Send via SMTP2GO
    # ------------------------------------------------------------------
    try:
        print(f"[email_dispatcher] Connecting to {SMTP_HOST}:{SMTP_PORT}...")
        server = smtplib.SMTP(SMTP_HOST, SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.ehlo()

        server.login(smtp_user, smtp_pass)
        server.sendmail(FROM_ADDRESS, to_email, msg.as_string())
        server.quit()

        print(f"[email_dispatcher] Email sent successfully to {to_email}.")
        return True

    except smtplib.SMTPAuthenticationError as exc:
        print(f"[email_dispatcher] SMTP authentication failed: {exc}")
    except smtplib.SMTPException as exc:
        print(f"[email_dispatcher] SMTP error: {exc}")
    except Exception as exc:
        print(f"[email_dispatcher] Unexpected error: {exc}")

    return False


# ======================================================================
# CLI entry-point
# ======================================================================

if __name__ == "__main__":
    from dotenv import load_dotenv

    load_dotenv()

    TEST_PDF = os.path.join(
        os.path.dirname(__file__), "..", "output", "modified_template.pdf"
    )

    success = send_cold_email(
        to_email="iyashgupta@gmail.com",
        subject="[TEST] Data Engineer Intern Application - Yash Gupta",
        body_text=(
            "Hi there,\n\n"
            "This is a test email sent from the AI Job Autopilot pipeline.\n\n"
            "Please ignore - verifying SMTP delivery and PDF attachment.\n\n"
            "Best,\nYash Gupta"
        ),
        pdf_attachment_path=TEST_PDF,
        test_mode=True,
    )

    print(f"\nDispatch result: {'SUCCESS' if success else 'FAILED'}")
