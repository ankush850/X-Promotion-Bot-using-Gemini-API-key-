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
from selenium.common.exceptions import NoSuchElementException
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
            raise ValueError("GEMINI_API_KEY not found")
        genai.configure(api_key=gemini_api_key)
        model_names = ['models/gemini-1.5-flash','models/gemini-2.0-flash','gemini-1.5-flash','models/gemini-1.5-pro','gemini-1.5-pro']
        self.model = None
        self.ai_available = False
        for model_name in model_names:
            try:
                test_model = genai.GenerativeModel(model_name)
                test_model.generate_content("Test")
                self.model = test_model
                self.ai_available = True
                break
            except Exception as e:
                error_str = str(e).lower()
                if any(err in error_str for err in ["404","not found","429","quota"]):
                    continue
        if not self.model:
            self.ai_available = False
        self.setup_driver()

    def setup_driver(self):
        os.makedirs(self.chrome_profile, exist_ok=True)
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument(f'--user-data-dir={self.chrome_profile}')
        chrome_options.add_experimental_option('excludeSwitches',['enable-automation'])
        chrome_options.add_experimental_option('useAutomationExtension',False)
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver,20)
        self.driver.get("https://twitter.com")

    def save_cookies(self):
        with open(self.cookies_file,'w') as f:
            json.dump(self.driver.get_cookies(),f)

    def load_cookies(self):
        try:
            with open(self.cookies_file,'r') as f:
                cookies=json.load(f)
                for cookie in cookies:
                    self.driver.add_cookie(cookie)
            return True
        except FileNotFoundError:
            return False

    def login(self):
        try:
            self.driver.get('https://x.com/i/flow/login')
            time.sleep(5)
            if not self.load_cookies():
                username_input=self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'input[autocomplete="username"]')))
                username_input.clear()
                for char in self.username:
                    username_input.send_keys(char)
                    time.sleep(0.1)
                time.sleep(1)
                username_input.send_keys(Keys.RETURN)
                time.sleep(2)
                password_input=self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,'input[name="password"]')))
                password_input.clear()
                for char in self.password:
                    password_input.send_keys(char)
                    time.sleep(0.1)
                time.sleep(1)
                password_input.send_keys(Keys.RETURN)
                time.sleep(10)
                self.save_cookies()
            self.driver.get('https://x.com/home')
            time.sleep(5)
            return "home" in self.driver.current_url.lower()
        except Exception:
            return False

    def get_feed_tweets(self):
        try:
            return self.wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR,'article[data-testid="tweet"]')))
        except Exception:
            return []

    def get_tweet_text(self,tweet_element):
        try:
            return tweet_element.find_element(By.CSS_SELECTOR,'[data-testid="tweetText"]').text
        except Exception:
            return None

    def get_tweet_id(self,tweet_element):
        try:
            time_element=tweet_element.find_element(By.CSS_SELECTOR,'time')
            tweet_link=time_element.find_element(By.XPATH,'..').get_attribute('href')
            try:
                author_element=tweet_element.find_element(By.CSS_SELECTOR,'[data-testid="User-Name"]')
                author_name=author_element.text.split('\n')[0]
                return f"{author_name}_{tweet_link}"
            except:
                return tweet_link
        except Exception:
            return None

    def is_own_tweet(self,tweet_element):
        try:
            username_element=tweet_element.find_element(By.CSS_SELECTOR,'[data-testid="User-Name"]')
            username_text=username_element.text.lower()
            return os.getenv('TWITTER_USERNAME','').lower() in username_text
        except Exception:
            return True

    def is_reply_tweet(self,tweet_element):
        try:
            if tweet_element.find_elements(By.CSS_SELECTOR,'[data-testid="socialContext"]'):
                return True
            if tweet_element.find_elements(By.XPATH,'.//*[contains(text(), "Replying to")]'):
                return True
            return False
        except Exception:
            return True

    def should_promote_on_tweet(self,tweet_text):
        if not tweet_text:
            return False
        if not self.ai_available or not self.model:
            return self._keyword_based_filtering(tweet_text)
        try:
            prompt=f"Analyze: {tweet_text}. Respond YES or NO."
            response=self.model.generate_content(prompt)
            ai_decision=response.text.strip().upper()
            return self._validate_ai_decision_with_keywords(ai_decision,tweet_text)
        except Exception:
            return self._keyword_based_filtering(tweet_text)

    def _keyword_based_filtering(self,tweet_text):
        text=tweet_text.lower()
        tech=['website','web','site','app','software','saas','platform','ux','ui','conversion','analytics','support','chatbot','engagement','visitors','e-commerce','startup','tech','developer','code']
        nontech=['agriculture','farm','recipe','food','sports','politics','health','travel','hotel']
        return any(k in text for k in tech) and not any(k in text for k in nontech)

    def _validate_ai_decision_with_keywords(self,ai_decision,tweet_text):
        text=tweet_text.lower()
        tech=['website','web','site','app','software','saas','platform','ux','ui','conversion','analytics','support','chatbot','engagement','visitors','e-commerce','startup','tech','developer','code']
        nontech=['agriculture','farm','recipe','food','sports','politics','health','travel','hotel']
        return ai_decision=="YES" and any(k in text for k in tech) and not any(k in text for k in nontech)

    def generate_salesly_promotion(self,tweet_text):
        if not self.ai_available or not self.model:
            return self._generate_fallback_response(tweet_text)
        try:
            prompt=f"Write a helpful response under 250 chars with salesly.live. Tweet: {tweet_text}"
            response=self.model.generate_content(prompt)
            return self.clean_text(response.text.strip())
        except Exception:
            return self._generate_fallback_response(tweet_text)

    def _generate_fallback_response(self,tweet_text):
        text=tweet_text.lower()
        if any(w in text for w in ['website','site','web']):
            return f"Visitors matter! Try {SALESLY_CONFIG['website_url']}"
        elif any(w in text for w in ['support','help','customer']):
            return f"Catch visitor questions early with {SALESLY_CONFIG['website_url']}"
        elif any(w in text for w in ['startup','business','growth']):
            return f"Insights are key! {SALESLY_CONFIG['website_url']}"
        else:
            return f"Check {SALESLY_CONFIG['website_url']} for engagement insights."

    def clean_text(self,text):
        return ' '.join(text.replace('*','').replace('_','').split())[:270]

def main():
    bot=TwitterBot()
    if bot.login():
        print("Bot ready.")

if __name__=="__main__":
    main()
