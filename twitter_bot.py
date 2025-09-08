import os
import json
import time
import random
from dotenv import load_dotenv
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from datetime import datetime, timedelta
import google.generativeai as genai

load_dotenv()

SALESLY_CONFIG = {
    'website_url': 'salesly.live',
    'max_promotions_per_hour': 6,
    'min_delay_between_promotions': 15,
    'max_delay_between_promotions': 30
}

class TwitterBot:
    def __init__(self):
        self.username = os.getenv('TWITTER_USERNAME')
        self.password = os.getenv('TWITTER_PASSWORD')
        self.cookies_file = os.getenv('COOKIES_FILE')
        self.chrome_profile = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'chrome_profile')
        
        gemini_api_key = os.getenv('GEMINI_API_KEY')
        if not gemini_api_key:
            raise ValueError("GEMINI_API_KEY not found in environment variables")
        genai.configure(api_key=gemini_api_key)
        
        model_names = [
            'models/gemini-1.5-flash',
            'models/gemini-2.0-flash',
            'gemini-1.5-flash',
            'models/gemini-1.5-pro',
            'gemini-1.5-pro'
        ]
        self.model = None
        self.ai_available = False
        
        for model_name in model_names:
            try:
                test_model = genai.GenerativeModel(model_name)
                test_response = test_model.generate_content("Test")
                self.model = test_model
                self.ai_available = True
                print(f"✓ AI model initialized: {model_name}")
                break
            except Exception as e:
                error_str = str(e).lower()
                if "404" in error_str or "not found" in error_str:
                    continue
                elif "429" in error_str or "quota" in error_str:
                    continue
                else:
                    continue
        
        if not self.model:
            self.ai_available = False
            print("⚠ AI unavailable - using keyword-based filtering")
        
        self.setup_driver()

    def setup_driver(self):
        """Initialize the Chrome WebDriver with appropriate options"""
        try:
            os.makedirs(self.chrome_profile, exist_ok=True)
            
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument(f'--user-data-dir={self.chrome_profile}')
            chrome_options.add_experimental_option('excludeSwitches', ['enable-automation'])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            self.driver = webdriver.Chrome(options=chrome_options)
            self.wait = WebDriverWait(self.driver, 20)
            
            self.driver.get("https://twitter.com")
            print("Browser initialized and Twitter opened")
                
        except Exception as e:
            print(f"X Browser setup failed: {str(e)}")
            if hasattr(self, 'driver'):
                self.driver.quit()
            raise e

    def save_cookies(self):
        """Save cookies to file"""
        with open(self.cookies_file, 'w') as f:
            json.dump(self.driver.get_cookies(), f)

    def load_cookies(self):
        """Load cookies from file if exists"""
        try:
            with open(self.cookies_file, 'r') as f:
                cookies = json.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            return True
        except FileNotFoundError:
            return False

    def login(self):
        """Login to Twitter using credentials"""
        try:
            print("Starting login process...")
            self.driver.get('https://x.com/i/flow/login')
            time.sleep(5)
            
            if not self.load_cookies():
                print("Entering credentials...")
                username_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[autocomplete="username"]'))
                )
                username_input.clear()
                for char in self.username:
                    username_input.send_keys(char)
                    time.sleep(0.1)
                time.sleep(1)
                username_input.send_keys(Keys.RETURN)
                time.sleep(2)
                
                password_input = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, 'input[name="password"]'))
                )
                password_input.clear()
                for char in self.password:
                    password_input.send_keys(char)
                    time.sleep(0.1)
                time.sleep(1)
                password_input.send_keys(Keys.RETURN)
                
                time.sleep(10)
                self.save_cookies()
                print("Login successful - cookies saved")
            else:
                print("Using saved cookies")
            
            self.driver.get('https://x.com/home')
            time.sleep(5)
            
            if "home" in self.driver.current_url.lower():
                print("Successfully navigated to home feed")
                return True
            else:
                print("Login verification failed")
                return False
            
        except Exception as e:
            print(f"Login failed: {str(e)}")
            return False

    def get_feed_tweets(self):
        """Get tweets from the home feed"""
        try:
            tweets = self.wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, 'article[data-testid="tweet"]'))
            )
            return tweets
        except Exception:
            return []

    def get_tweet_text(self, tweet_element):
        """Extract text content from a tweet"""
        try:
            text_element = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="tweetText"]')
            return text_element.text
        except NoSuchElementException:
            return None
        except Exception as e:
            return None

    def get_tweet_id(self, tweet_element):
        """Extract unique identifier for a tweet"""
        try:
            time_element = tweet_element.find_element(By.CSS_SELECTOR, 'time')
            tweet_link = time_element.find_element(By.XPATH, '..').get_attribute('href')
            
            try:
                author_element = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
                author_name = author_element.text.split('\n')[0]
                return f"{author_name}_{tweet_link}"
            except:
                return tweet_link
        except NoSuchElementException:
            return None

    def get_tweet_timestamp(self, tweet_element):
        """Extract timestamp from a tweet"""
        try:
            time_element = tweet_element.find_element(By.CSS_SELECTOR, 'time')
            timestamp = time_element.get_attribute('datetime')
            return datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%S.%fZ")
        except (NoSuchElementException, ValueError):
            return None

    def is_within_24_hours(self, tweet_element):
        """Check if tweet is within the last 24 hours"""
        tweet_time = self.get_tweet_timestamp(tweet_element)
        if tweet_time:
            current_time = datetime.utcnow()
            time_difference = current_time - tweet_time
            return time_difference <= timedelta(hours=24)
        return False

    def is_own_tweet(self, tweet_element):
        """Check if the tweet is from our own account"""
        try:
            username_element = tweet_element.find_element(By.CSS_SELECTOR, '[data-testid="User-Name"]')
            username_text = username_element.text.lower()
            our_username = os.getenv('TWITTER_USERNAME', '').lower()
            
            return our_username in username_text
        except Exception:
            return True

    def is_reply_tweet(self, tweet_element):
        """Check if the tweet is a reply"""
        try:
            reply_indicators = tweet_element.find_elements(By.CSS_SELECTOR, '[data-testid="socialContext"]')
            if reply_indicators:
                return True

            replying_to = tweet_element.find_elements(By.XPATH, './/*[contains(text(), "Replying to")]')
            if replying_to:
                return True

            return False
        except Exception:
            return True

    def should_promote_on_tweet(self, tweet_text):
        """Determine if this tweet is suitable for Salesly promotion using AI analysis"""
        if not tweet_text:
            return False
        
        if not self.ai_available or not self.model:
            print("Using keyword-based filtering")
            return self._keyword_based_filtering(tweet_text)
            
        try:
            analysis_prompt = f"""
            Analyze this tweet and determine if it's suitable for promoting Salesly (a website visitor engagement tool).
            
            Salesly helps websites provide instant answers to visitors and gives insights into visitor behavior.
            
            Only return "YES" if the tweet is about:
            1. Website development, design, or optimization
            2. Customer support challenges on websites
            3. SaaS/software businesses looking to improve user experience
            4. E-commerce sites wanting to reduce cart abandonment
            5. Entrepreneurs/startups building web platforms
            6. Web analytics, visitor behavior, or conversion optimization
            7. Freelancers/agencies building websites for clients
            8. Technical discussions about improving website engagement
            
            Return "NO" if the tweet is about:
            - Agriculture, farming, food, recipes
            - Sports, entertainment, personal life
            - Politics, news, social issues
            - Physical products (not digital/web-related)
            - Health, fitness, medical topics
            - Travel, lifestyle, fashion
            - Cryptocurrency, NFTs, financial trading
            - Generic motivational content without tech context
            - Spam or promotional content
            
            Tweet: "{tweet_text}"
            
            Response (YES or NO only):"""
            
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = self.model.generate_content(analysis_prompt)
                    ai_decision = response.text.strip().upper()
                    break
                except Exception as api_error:
                    error_str = str(api_error).lower()
                    if "404" in error_str or "not found" in error_str:
                        self.ai_available = False
                        return self._keyword_based_filtering(tweet_text)
                    elif "429" in error_str or "quota" in error_str:
                        wait_time = (attempt + 1) * 10
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            return self._keyword_based_filtering(tweet_text)
                    elif "503" in error_str or "overloaded" in error_str:
                        wait_time = (attempt + 1) * 5
                        time.sleep(wait_time)
                        if attempt == max_retries - 1:
                            return self._keyword_based_filtering(tweet_text)
                    else:
                        if attempt == max_retries - 1:
                            return self._keyword_based_filtering(tweet_text)
                        time.sleep(2)
            
            return self._validate_ai_decision_with_keywords(ai_decision, tweet_text)
            
        except Exception:
            return self._keyword_based_filtering(tweet_text)
