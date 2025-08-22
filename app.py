import requests
from bs4 import BeautifulSoup
import json
import time
from datetime import datetime, timedelta
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import pandas as pd

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class RatingAgencyAlertSystem:
    def __init__(self):
        self.setup_selenium()
        self.alerts = []
        
    def setup_selenium(self):
        """Setup Selenium WebDriver with Chrome options"""
        chrome_options = Options()
        chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--window-size=1920,1080')
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
        except Exception as e:
            logger.error(f"Failed to setup Selenium: {e}")
            self.driver = None

    def get_current_date_str(self):
        """Get current date in various formats"""
        today = datetime.now()
        return {
            'dd-mm-yyyy': today.strftime('%d-%m-%Y'),
            'yyyy-mm-dd': today.strftime('%Y-%m-%d'),
            'dd/mm/yyyy': today.strftime('%d/%m/%Y'),
            'mm/dd/yyyy': today.strftime('%m/%d/%Y'),
            'dd-mmm-yyyy': today.strftime('%d-%b-%Y'),
            'dd mmm yyyy': today.strftime('%d %b %Y'),
        }

    def scrape_icra_ratings(self):
        """Scrape ICRA ratings with date-wise updates and pagination"""
        logger.info("Scraping ICRA ratings...")
        try:
            if not self.driver:
                return []
            
            # Navigate to ICRA ratings page
            self.driver.get("https://www.icra.in/Rating/RatingList.aspx")
            
            # Wait for page to load
            time.sleep(3)
            
            # Set current date filter if available
            try:
                date_input = self.driver.find_element(By.ID, "txtFromDate")
                date_input.clear()
                date_input.send_keys(self.get_current_date_str()['dd/mm/yyyy'])
                
                to_date_input = self.driver.find_element(By.ID, "txtToDate")
                to_date_input.clear()
                to_date_input.send_keys(self.get_current_date_str()['dd/mm/yyyy'])
                
                # Click search/filter button
                search_btn = self.driver.find_element(By.ID, "btnSearch")
                search_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                logger.info("Date filter not found, proceeding with default view")
            
            alerts = []
            page_num = 1
            
            while True:
                logger.info(f"Processing ICRA page {page_num}")
                
                # Extract ratings from current page
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Look for rating table/list
                rating_rows = soup.find_all('tr', class_='gridrow') or soup.find_all('div', class_='rating-item')
                
                for row in rating_rows:
                    try:
                        # Extract rating information
                        company_name = self.extract_text_from_element(row, ['company', 'entity', 'name'])
                        rating_date = self.extract_text_from_element(row, ['date', 'rated-on'])
                        rating_action = self.extract_text_from_element(row, ['action', 'rating', 'grade'])
                        
                        if company_name and self.is_today_date(rating_date):
                            alerts.append({
                                'agency': 'ICRA',
                                'company': company_name,
                                'date': rating_date,
                                'action': rating_action,
                                'timestamp': datetime.now().isoformat()
                            })
                    except Exception as e:
                        logger.warning(f"Error extracting ICRA rating: {e}")
                
                # Check for next page
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Next')] | //input[@value='Next']")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        break
                except NoSuchElementException:
                    break
            
            logger.info(f"Found {len(alerts)} ICRA alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping ICRA: {e}")
            return []

    def scrape_careedge_ratings(self):
        """Scrape CareEdge ratings with scrolling through recent ratings"""
        logger.info("Scraping CareEdge ratings...")
        try:
            if not self.driver:
                return []
            
            self.driver.get("https://www.careratings.com/")
            time.sleep(3)
            
            alerts = []
            
            # Look for "Recent Ratings" section
            try:
                recent_ratings_section = self.wait.until(
                    EC.presence_of_element_located((By.CLASS_NAME, "recent-ratings"))
                )
                
                # Scroll through the recent ratings
                last_height = self.driver.execute_script("return document.querySelector('.recent-ratings').scrollHeight")
                
                while True:
                    # Scroll down in the recent ratings section
                    self.driver.execute_script("document.querySelector('.recent-ratings').scrollTo(0, document.querySelector('.recent-ratings').scrollHeight);")
                    time.sleep(2)
                    
                    # Calculate new scroll height and compare with last scroll height
                    new_height = self.driver.execute_script("return document.querySelector('.recent-ratings').scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height
                
                # Extract all ratings after scrolling
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                rating_items = soup.find_all('div', class_=['rating-item', 'rating-card', 'recent-rating-item'])
                
                for item in rating_items:
                    try:
                        company_name = self.extract_text_from_element(item, ['company', 'entity', 'name'])
                        rating_date = self.extract_text_from_element(item, ['date', 'rated-on', 'timestamp'])
                        rating_action = self.extract_text_from_element(item, ['action', 'rating', 'grade'])
                        
                        if company_name and self.is_today_date(rating_date):
                            alerts.append({
                                'agency': 'CareEdge',
                                'company': company_name,
                                'date': rating_date,
                                'action': rating_action,
                                'timestamp': datetime.now().isoformat()
                            })
                    except Exception as e:
                        logger.warning(f"Error extracting CareEdge rating: {e}")
                        
            except TimeoutException:
                logger.warning("Recent ratings section not found on CareEdge")
            
            logger.info(f"Found {len(alerts)} CareEdge alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping CareEdge: {e}")
            return []

    def scrape_acuite_ratings(self):
        """Scrape Acuite ratings with pagination"""
        logger.info("Scraping Acuite ratings...")
        try:
            if not self.driver:
                return []
            
            self.driver.get("https://connect.acuite.in/liveratings")
            time.sleep(3)
            
            alerts = []
            page_num = 1
            
            while True:
                logger.info(f"Processing Acuite page {page_num}")
                
                # Extract ratings from current page
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Look for rating table rows
                rating_rows = soup.find_all('tr')
                
                for row in rating_rows[1:]:  # Skip header row
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 3:
                            rating_date = cells[0].get_text(strip=True) if cells else ""
                            company_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                            rating_action = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                            
                            if company_name and self.is_today_date(rating_date):
                                alerts.append({
                                    'agency': 'Acuite',
                                    'company': company_name,
                                    'date': rating_date,
                                    'action': rating_action,
                                    'timestamp': datetime.now().isoformat()
                                })
                    except Exception as e:
                        logger.warning(f"Error extracting Acuite rating: {e}")
                
                # Check for next page
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Next')] | //button[contains(text(), 'Next')]")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        break
                except NoSuchElementException:
                    break
            
            logger.info(f"Found {len(alerts)} Acuite alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping Acuite: {e}")
            return []

    def scrape_crisil_ratings(self):
        """Scrape CRISIL ratings with load more functionality"""
        logger.info("Scraping CRISIL ratings...")
        try:
            if not self.driver:
                return []
            
            self.driver.get("https://www.crisil.com/en/home/our-businesses/ratings/ratings-actions.html")
            time.sleep(3)
            
            alerts = []
            
            # Keep clicking "Load More" until no more content
            while True:
                try:
                    load_more_button = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Load More')] | //a[contains(text(), 'Load More')]")
                    if load_more_button.is_displayed() and load_more_button.is_enabled():
                        load_more_button.click()
                        time.sleep(3)
                    else:
                        break
                except NoSuchElementException:
                    break
            
            # Extract all ratings after loading all content
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            rating_items = soup.find_all('div', class_=['rating-item', 'rating-card', 'announcement-item'])
            
            for item in rating_items:
                try:
                    company_name = self.extract_text_from_element(item, ['company', 'entity', 'name', 'title'])
                    rating_date = self.extract_text_from_element(item, ['date', 'rated-on', 'timestamp'])
                    rating_action = self.extract_text_from_element(item, ['action', 'rating', 'grade', 'description'])
                    
                    if company_name and self.is_today_date(rating_date):
                        alerts.append({
                            'agency': 'CRISIL',
                            'company': company_name,
                            'date': rating_date,
                            'action': rating_action,
                            'timestamp': datetime.now().isoformat()
                        })
                except Exception as e:
                    logger.warning(f"Error extracting CRISIL rating: {e}")
            
            logger.info(f"Found {len(alerts)} CRISIL alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping CRISIL: {e}")
            return []

    def scrape_bse_announcements(self):
        """Scrape BSE announcements for current date (Equity and Debt segments)"""
        logger.info("Scraping BSE announcements...")
        try:
            if not self.driver:
                return []
            
            alerts = []
            current_date = self.get_current_date_str()['dd/mm/yyyy']
            
            # BSE Corporate Announcements URL
            self.driver.get("https://www.bseindia.com/corporates/ann.html")
            time.sleep(3)
            
            # Set current date
            try:
                from_date = self.driver.find_element(By.ID, "txtFromDt")
                from_date.clear()
                from_date.send_keys(current_date)
                
                to_date = self.driver.find_element(By.ID, "txtToDt")
                to_date.clear()
                to_date.send_keys(current_date)
            except NoSuchElementException:
                logger.warning("Date fields not found on BSE")
            
            # Check both Equity and Debt segments
            segments = ['Equity', 'Debt']
            
            for segment in segments:
                try:
                    logger.info(f"Processing BSE {segment} segment")
                    
                    # Select segment if dropdown exists
                    try:
                        segment_dropdown = self.driver.find_element(By.ID, "ddlSegment")
                        for option in segment_dropdown.find_elements(By.TAG_NAME, "option"):
                            if segment.lower() in option.text.lower():
                                option.click()
                                break
                    except NoSuchElementException:
                        pass
                    
                    # Click submit/search button
                    try:
                        submit_btn = self.driver.find_element(By.ID, "btnSubmit")
                        submit_btn.click()
                        time.sleep(3)
                    except NoSuchElementException:
                        pass
                    
                    # Extract announcements
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    announcement_rows = soup.find_all('tr')[1:]  # Skip header
                    
                    for row in announcement_rows:
                        try:
                            cells = row.find_all('td')
                            if len(cells) >= 3:
                                company_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                                subject = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                                
                                if company_name:
                                    alerts.append({
                                        'agency': f'BSE ({segment})',
                                        'company': company_name,
                                        'date': current_date,
                                        'action': subject,
                                        'timestamp': datetime.now().isoformat()
                                    })
                        except Exception as e:
                            logger.warning(f"Error extracting BSE announcement: {e}")
                            
                except Exception as e:
                    logger.warning(f"Error processing BSE {segment}: {e}")
            
            logger.info(f"Found {len(alerts)} BSE alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping BSE: {e}")
            return []

    def scrape_nse_announcements(self):
        """Scrape NSE announcements for Equity and Debt"""
        logger.info("Scraping NSE announcements...")
        try:
            if not self.driver:
                return []
            
            alerts = []
            
            # NSE Announcements URL
            self.driver.get("https://www.nseindia.com/companies-listing/corporate-filings-announcements")
            time.sleep(5)
            
            segments = ['Equity', 'Debt']
            
            for segment in segments:
                try:
                    logger.info(f"Processing NSE {segment} segment")
                    
                    # Click on segment tab
                    try:
                        segment_tab = self.driver.find_element(By.XPATH, f"//a[contains(text(), '{segment}')]")
                        segment_tab.click()
                        time.sleep(3)
                    except NoSuchElementException:
                        logger.warning(f"NSE {segment} tab not found")
                        continue
                    
                    # Extract announcements
                    soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                    
                    # Look for announcement table or list
                    announcement_rows = soup.find_all('tr') or soup.find_all('div', class_='announcement-item')
                    
                    for row in announcement_rows:
                        try:
                            if row.name == 'tr':
                                cells = row.find_all('td')
                                if len(cells) >= 3:
                                    company_name = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                                    subject = cells[2].get_text(strip=True) if len(cells) > 2 else ""
                                    date_text = cells[0].get_text(strip=True) if cells else ""
                            else:
                                company_name = self.extract_text_from_element(row, ['company', 'symbol'])
                                subject = self.extract_text_from_element(row, ['subject', 'title'])
                                date_text = self.extract_text_from_element(row, ['date', 'time'])
                            
                            if company_name and self.is_today_date(date_text):
                                alerts.append({
                                    'agency': f'NSE ({segment})',
                                    'company': company_name,
                                    'date': date_text,
                                    'action': subject,
                                    'timestamp': datetime.now().isoformat()
                                })
                        except Exception as e:
                            logger.warning(f"Error extracting NSE announcement: {e}")
                            
                except Exception as e:
                    logger.warning(f"Error processing NSE {segment}: {e}")
            
            logger.info(f"Found {len(alerts)} NSE alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping NSE: {e}")
            return []

    def scrape_sebi_announcements(self):
        """Scrape SEBI announcements with pagination and current date selection"""
        logger.info("Scraping SEBI announcements...")
        try:
            if not self.driver:
                return []
            
            self.driver.get("https://www.sebi.gov.in/sebiweb/home/HomeAction.do?doListing=yes&sid=1&ssid=1&smid=1")
            time.sleep(3)
            
            alerts = []
            current_date = self.get_current_date_str()
            
            # Set current date filter if available
            try:
                date_input = self.driver.find_element(By.NAME, "fromDate")
                date_input.clear()
                date_input.send_keys(current_date['dd-mm-yyyy'])
                
                to_date_input = self.driver.find_element(By.NAME, "toDate")
                to_date_input.clear()
                to_date_input.send_keys(current_date['dd-mm-yyyy'])
                
                # Click search button
                search_btn = self.driver.find_element(By.XPATH, "//input[@type='submit']")
                search_btn.click()
                time.sleep(3)
            except NoSuchElementException:
                logger.warning("SEBI date filter not found")
            
            page_num = 1
            while True:
                logger.info(f"Processing SEBI page {page_num}")
                
                # Extract announcements from current page
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                announcement_rows = soup.find_all('tr')[1:]  # Skip header
                
                for row in announcement_rows:
                    try:
                        cells = row.find_all('td')
                        if len(cells) >= 2:
                            date_text = cells[0].get_text(strip=True) if cells else ""
                            announcement_text = cells[1].get_text(strip=True) if len(cells) > 1 else ""
                            
                            if announcement_text and self.is_today_date(date_text):
                                alerts.append({
                                    'agency': 'SEBI',
                                    'company': 'SEBI Announcement',
                                    'date': date_text,
                                    'action': announcement_text,
                                    'timestamp': datetime.now().isoformat()
                                })
                    except Exception as e:
                        logger.warning(f"Error extracting SEBI announcement: {e}")
                
                # Check for next page
                try:
                    next_button = self.driver.find_element(By.XPATH, "//a[contains(text(), 'Next')] | //input[@value='Next']")
                    if next_button.is_enabled():
                        next_button.click()
                        time.sleep(3)
                        page_num += 1
                    else:
                        break
                except NoSuchElementException:
                    break
            
            logger.info(f"Found {len(alerts)} SEBI alerts")
            return alerts
            
        except Exception as e:
            logger.error(f"Error scraping SEBI: {e}")
            return []

    def extract_text_from_element(self, element, selectors):
        """Extract text from element using multiple selector strategies"""
        for selector in selectors:
            try:
                # Try class name
                found = element.find(class_=lambda x: x and selector in x.lower())
                if found:
                    return found.get_text(strip=True)
                
                # Try by text content
                found = element.find(string=lambda text: text and selector in text.lower())
                if found:
                    return found.strip()
                
                # Try by tag with text
                for tag in ['span', 'div', 'td', 'p', 'a']:
                    found = element.find(tag, string=lambda text: text and selector in text.lower())
                    if found:
                        return found.get_text(strip=True)
                        
            except Exception:
                continue
        return ""

    def is_today_date(self, date_text):
        """Check if the given date text represents today's date"""
        if not date_text:
            return False
            
        today = datetime.now()
        today_formats = [
            today.strftime('%d-%m-%Y'),
            today.strftime('%Y-%m-%d'),
            today.strftime('%d/%m/%Y'),
            today.strftime('%m/%d/%Y'),
            today.strftime('%d-%b-%Y'),
            today.strftime('%d %b %Y'),
            today.strftime('%d %B %Y'),
        ]
        
        # Clean the date text
        cleaned_date = date_text.strip().replace(',', '')
        
        return any(fmt in cleaned_date for fmt in today_formats)

    def run_all_scrapers(self):
        """Run all rating agency scrapers"""
        logger.info("Starting rating agency alerts collection...")
        
        all_alerts = []
        
        # Define scrapers
        scrapers = [
            ('ICRA', self.scrape_icra_ratings),
            ('CareEdge', self.scrape_careedge_ratings),
            ('Acuite', self.scrape_acuite_ratings),
            ('CRISIL', self.scrape_crisil_ratings),
            ('BSE', self.scrape_bse_announcements),
            ('NSE', self.scrape_nse_announcements),
            ('SEBI', self.scrape_sebi_announcements),
        ]
        
        for agency_name, scraper_func in scrapers:
            try:
                logger.info(f"Running {agency_name} scraper...")
                agency_alerts = scraper_func()
                all_alerts.extend(agency_alerts)
                logger.info(f"Completed {agency_name}: {len(agency_alerts)} alerts")
                
                # Small delay between agencies
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error running {agency_name} scraper: {e}")
        
        # Save alerts to file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"rating_alerts_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(all_alerts, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Total alerts found: {len(all_alerts)}")
        logger.info(f"Alerts saved to: {filename}")
        
        return all_alerts

    def generate_alert_report(self, alerts):
        """Generate a formatted report of all alerts"""
        if not alerts:
            return "No alerts found for today."
        
        report = []
        report.append("=" * 60)
        report.append(f"RATING AGENCY ALERTS - {datetime.now().strftime('%d %B %Y')}")
        report.append("=" * 60)
        report.append("")
        
        # Group alerts by agency
        by_agency = {}
        for alert in alerts:
            agency = alert['agency']
            if agency not in by_agency:
                by_agency[agency] = []
            by_agency[agency].append(alert)
        
        for agency, agency_alerts in by_agency.items():
            report.append(f"{agency} ({len(agency_alerts)} alerts):")
            report.append("-" * 30)
            
            for alert in agency_alerts:
                report.append(f"Company: {alert['company']}")
                report.append(f"Date: {alert['date']}")
                report.append(f"Action: {alert['action']}")
                report.append("")
            
            report.append("")
        
        return "\n".join(report)

    def cleanup(self):
        """Cleanup resources"""
        if self.driver:
            self.driver.quit()

def main():
    """Main function to run the alert system"""
    alert_system = RatingAgencyAlertSystem()
    
    try:
        # Run all scrapers
        alerts = alert_system.run_all_scrapers()
        
        # Generate and print report
        report = alert_system.generate_alert_report(alerts)
        print(report)
        
        # Save report to file
        report_filename = f"rating_alerts_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(report_filename, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"Report saved to: {report_filename}")
        
    except Exception as e:
        logger.error(f"Error in main execution: {e}")
    
    finally:
        alert_system.cleanup()

if __name__ == "__main__":
    main()
