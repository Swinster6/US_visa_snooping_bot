"""
Single check script for cron job
Runs once per execution, then exits
"""
import os
from dotenv import load_dotenv
import logging

# Import the monitor class
from visa_monitor import VisaAppointmentMonitor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    # Load environment variables
    load_dotenv()

    # Get credentials from environment
    VISA_EMAIL = os.getenv("VISA_EMAIL")
    VISA_PASSWORD = os.getenv("VISA_PASSWORD")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

    # Create monitor
    monitor = VisaAppointmentMonitor(
        email=VISA_EMAIL,
        password=VISA_PASSWORD,
        notification_email=NOTIFICATION_EMAIL,
        smtp_email=SMTP_EMAIL,
        smtp_password=SMTP_APP_PASSWORD
    )

    # Run single check
    logging.info("Starting scheduled appointment check...")
    monitor.check_appointments()
    logging.info("Check complete. Exiting.")