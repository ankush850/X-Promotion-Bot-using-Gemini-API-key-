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
