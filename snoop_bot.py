"""
US Visa Appointment Availability Monitor
Checks for available appointment dates in Calgary and sends email notifications
"""

import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
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
        self.driver = None

    def setup_driver(self):
        """Setup Chrome driver with options"""
        options = webdriver.ChromeOptions()
        options.add_argument('--headless=new')  # Use new headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=options)

        # Additional stealth settings
        self.driver.execute_cdp_cmd('Network.setUserAgentOverride', {
            "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        self.driver.implicitly_wait(10)

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
            self.driver.get("https://ais.usvisa-info.com/en-ca/niv/users/sign_in")

            # Wait for and fill email
            email_field = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "user_email"))
            )
            email_field.clear()
            email_field.send_keys(self.email)

            # Fill password
            password_field = self.driver.find_element(By.ID, "user_password")
            password_field.clear()
            password_field.send_keys(self.password)

            # Accept terms if checkbox exists (use JavaScript to avoid click interception)
            try:
                terms_checkbox = self.driver.find_element(By.ID, "policy_confirmed")
                if not terms_checkbox.is_selected():
                    self.driver.execute_script("arguments[0].click();", terms_checkbox)
            except NoSuchElementException:
                pass

            # Click sign in
            sign_in_button = self.driver.find_element(By.NAME, "commit")
            sign_in_button.click()

            logging.info("Login submitted")
            time.sleep(3)

            return True
        except Exception as e:
            logging.error(f"Login failed: {str(e)}")
            return False

    def navigate_to_reschedule(self):
        """Navigate to the reschedule appointment page"""
        try:
            logging.info("Looking for Continue button...")
            continue_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable((By.LINK_TEXT, "Continue"))
            )
            continue_button.click()

            # Expand the "Reschedule Appointment" accordion
            logging.info("Expanding 'Reschedule Appointment' accordion...")
            reschedule_toggle = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH, "//li[a[h5[contains(., 'Reschedule Appointment')]]]//a[@class='accordion-title']")
                )
            )
            reschedule_toggle.click()

            # Now find the green link inside that same accordion item
            logging.info("Clicking green 'Reschedule Appointment' button...")
            reschedule_button = WebDriverWait(self.driver, 20).until(
                EC.element_to_be_clickable(
                    (By.XPATH,
                     "//li[a[h5[contains(., 'Reschedule Appointment')]]]//a[contains(@class,'button') and contains(text(),'Reschedule Appointment')]")
                )
            )

            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'});", reschedule_button)
            try:
                reschedule_button.click()
            except:
                self.driver.execute_script("arguments[0].click();", reschedule_button)

            return True

        except Exception as e:
            logging.error(f"Navigation to reschedule failed: {str(e)}")
            return False

    def check_reschedule_availability(self):
        """Check if appointments are available by checking if Reschedule button is enabled"""
        try:
            # Select Calgary from dropdown
            logging.info("Selecting Calgary location...")
            location_dropdown = WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.ID, "appointments_consulate_appointment_facility_id"))
            )
            select = Select(location_dropdown)
            select.select_by_visible_text("Calgary")
            time.sleep(4)  # Give it time to load availability info

            # Check for the error message
            logging.info("Checking for system busy message...")
            try:
                error_message = self.driver.find_element(
                    By.XPATH,
                    "//*[contains(text(), 'System is busy. Please try again later.')]"
                )
                if error_message.is_displayed():
                    logging.info("System is busy - no appointments available")
                    return False
            except NoSuchElementException:
                logging.info("No 'system busy' message found - good sign!")

            # Check if the Reschedule button is enabled
            logging.info("Checking if Reschedule button is enabled...")
            reschedule_submit_button = self.driver.find_element(By.ID, "appointments_submit")

            is_disabled = reschedule_submit_button.get_attribute("disabled")

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
        try:
            self.setup_driver()

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
            if self.driver:
                self.driver.quit()

    def run_monitor(self, check_interval=30):
        """
        Run the monitor continuously

        Args:
            check_interval: Time between checks in seconds (default: 3600 = 1 hour)
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
    # Configuration
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

    # Run every hour (3600 seconds)
    monitor.run_monitor(check_interval=30)