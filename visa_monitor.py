"""
US Visa Appointment Availability Monitor
Checks for available appointment dates in Calgary and sends email notifications
Updated for Render deployment with Playwright
"""

import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import logging
from dotenv import load_dotenv
import os

# Configure logging with UTF-8 encoding
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('visa_monitor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)


class VisaAppointmentMonitor:
    def __init__(self, email, password, notification_email, smtp_email, smtp_password):
        """
        Initialize the monitor

        Args:
            email: Your visa account email
            password: Your visa account password
            notification_email: Email to receive notifications
            smtp_email: Gmail address to send from
            smtp_password: Gmail app password (not regular password)
        """
        self.email = email
        self.password = password
        self.notification_email = notification_email
        self.smtp_email = smtp_email
        self.smtp_password = smtp_password
        self.browser = None
        self.page = None

    def send_notification(self, subject, message):
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_email
            msg['To'] = self.notification_email
            msg['Subject'] = subject

            body = MIMEText(message, 'plain')
            msg.attach(body)

            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self.smtp_email, self.smtp_password)
                server.send_message(msg)

            logging.info(f"Notification sent: {subject}")
        except Exception as e:
            logging.error(f"Failed to send notification: {str(e)}")

    def login(self):
        """Login to the visa appointment system"""
        try:
            logging.info("Navigating to login page...")
            self.page.goto("https://ais.usvisa-info.com/en-ca/niv/users/sign_in", wait_until="networkidle")

            # Wait for and fill email
            self.page.wait_for_selector("#user_email", timeout=20000)
            self.page.fill("#user_email", self.email)

            # Fill password
            self.page.fill("#user_password", self.password)

            # Accept terms checkbox - click the label
            try:
                logging.info("Looking for policy checkbox...")
                # Wait for the checkbox to be available
                self.page.wait_for_selector("#policy_confirmed", timeout=5000)

                # Check if it's not already checked
                if not self.page.is_checked("#policy_confirmed"):
                    logging.info("Checking policy checkbox by clicking label...")
                    # Click the label instead of the checkbox directly
                    self.page.click("label[for='policy_confirmed']")
                    self.page.wait_for_timeout(500)  # Brief wait for the check to register
                    logging.info("Policy checkbox checked successfully")
                else:
                    logging.info("Policy checkbox already checked")

            except PlaywrightTimeout:
                logging.warning("Policy checkbox not found - it may not be required")
            except Exception as e:
                logging.warning(f"Could not check policy checkbox: {str(e)}")

            # Click sign in
            logging.info("Clicking sign in button...")
            self.page.click("input[name='commit']")
            logging.info("Login submitted")

            # Wait for navigation to complete
            self.page.wait_for_timeout(3000)

            # Verify login was successful
            try:
                # Check if we're on the continue page or still on login
                current_url = self.page.url
                logging.info(f"Current URL after login: {current_url}")

                if "sign_in" in current_url:
                    logging.error("Still on login page - login may have failed")
                    return False
            except:
                pass

            return True

        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            return False
    def navigate_to_reschedule(self):
        """Navigate to the reschedule appointment page"""
        try:
            logging.info("Looking for Continue button...")
            self.page.wait_for_selector("a:text('Continue')", timeout=20000)
            self.page.click("a:text('Continue')")

            # Expand the "Reschedule Appointment" accordion
            logging.info("Expanding 'Reschedule Appointment' accordion...")
            accordion_xpath = "//li[a[h5[contains(., 'Reschedule Appointment')]]]//a[@class='accordion-title']"
            self.page.wait_for_selector(f"xpath={accordion_xpath}", timeout=20000)
            self.page.click(f"xpath={accordion_xpath}")

            # Click the reschedule button
            logging.info("Clicking green 'Reschedule Appointment' button...")
            button_xpath = "//li[a[h5[contains(., 'Reschedule Appointment')]]]//a[contains(@class,'button') and contains(text(),'Reschedule Appointment')]"
            self.page.wait_for_selector(f"xpath={button_xpath}", timeout=20000)

            # Scroll into view and click
            self.page.evaluate(
                f"document.evaluate(\"{button_xpath}\", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue.scrollIntoView({{block:'center'}})")
            self.page.click(f"xpath={button_xpath}")

            return True

        except Exception as e:
            logging.error(f"Navigation to reschedule failed: {str(e)}")
            return False

    def check_reschedule_availability(self):
        """Check if appointments are available by checking if Reschedule button is enabled"""
        try:
            # Select Calgary from dropdown
            logging.info("Selecting Calgary location...")
            self.page.wait_for_selector("#appointments_consulate_appointment_facility_id", timeout=20000)
            self.page.select_option("#appointments_consulate_appointment_facility_id", label="Calgary")
            self.page.wait_for_timeout(4000)  # Give it time to load availability info

            # Check for the error message
            logging.info("Checking for system busy message...")
            try:
                error_element = self.page.locator("//*[contains(text(), 'System is busy. Please try again later.')]")
                if error_element.is_visible():
                    logging.info("System is busy - no appointments available")
                    return False
            except:
                logging.info("No 'system busy' message found - good sign!")

            # Check if the Reschedule button is enabled
            logging.info("Checking if Reschedule button is enabled...")
            reschedule_button = self.page.locator("#appointments_submit")

            is_disabled = reschedule_button.get_attribute("disabled")

            if is_disabled:
                logging.info("Reschedule button is disabled - no appointments available")
                return False
            else:
                logging.info("🎉 Reschedule button is ENABLED - appointments are available!")
                return True

        except Exception as e:
            logging.error(f"Availability check failed: {str(e)}")
            return False

    def check_appointments(self):
        """Main method to check for appointments"""
        playwright = None
        try:
            playwright = sync_playwright().start()
            self.browser = playwright.chromium.launch(
                headless=False,
                args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
            )

            context = self.browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            self.page = context.new_page()

            if not self.login():
                return False

            if not self.navigate_to_reschedule():
                return False

            is_available = self.check_reschedule_availability()

            if is_available == False:
                message = f"🎉 APPOINTMENT AVAILABLE!\n\n"
                message += f"The Reschedule button is now ENABLED in Calgary!\n"
                message += f"This means appointment slots have opened up.\n\n"
                message += f"Log in immediately to book your appointment:\n"
                message += f"https://ais.usvisa-info.com/en-ca/niv/users/sign_in"

                self.send_notification(
                    "🚨 US Visa Appointment Available in Calgary!",
                    message
                )
                return True
            else:
                logging.info("No available appointments - system is busy or button disabled")
                return False

        except Exception as e:
            logging.error(f"Check failed: {str(e)}")
            return False
        finally:
            if self.browser:
                self.browser.close()
            if playwright:
                playwright.stop()

    def run_monitor(self, check_interval=1800):
        """
        Run the monitor continuously

        Args:
            check_interval: Time between checks in seconds (default: 1800 = 30 minutes)
        """
        logging.info("Starting visa appointment monitor...")
        self.send_notification(
            "Visa Monitor Started",
            "The appointment monitoring bot has started. You'll receive notifications when appointments become available."
        )

        while True:
            try:
                logging.info("Starting appointment check...")
                self.check_appointments()
                logging.info(f"Check complete. Waiting {check_interval} seconds until next check...")
                time.sleep(check_interval)
            except KeyboardInterrupt:
                logging.info("Monitor stopped by user")
                break
            except Exception as e:
                logging.error(f"Error in monitor loop: {str(e)}")
                time.sleep(check_interval)


# Usage example
if __name__ == "__main__":
    # Load environment variables from .env
    load_dotenv()

    VISA_EMAIL = os.getenv("VISA_EMAIL")
    VISA_PASSWORD = os.getenv("VISA_PASSWORD")
    NOTIFICATION_EMAIL = os.getenv("NOTIFICATION_EMAIL")
    SMTP_EMAIL = os.getenv("SMTP_EMAIL")
    SMTP_APP_PASSWORD = os.getenv("SMTP_APP_PASSWORD")

    # Create and run monitor
    monitor = VisaAppointmentMonitor(
        email=VISA_EMAIL,
        password=VISA_PASSWORD,
        notification_email=NOTIFICATION_EMAIL,
        smtp_email=SMTP_EMAIL,
        smtp_password=SMTP_APP_PASSWORD
    )

    # Run every 30 minutes (1800 seconds) - adjust as needed
    monitor.run_monitor(check_interval=1800)
