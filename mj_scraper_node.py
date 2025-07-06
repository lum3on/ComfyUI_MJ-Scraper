import random
import string
import requests
import os
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import traceback
from urllib.parse import urlparse

MIN_FILE_SIZE_BYTES = 10 * 1024

class MJScraperNode:
    def __init__(self):
        pass

    @classmethod
    def INPUT_TYPES(s):
        return {
            "required": {
                "search_url": ("STRING", {"default": "https://midjourney.com/showcase/top/"}),
                "output_directory": ("STRING", {"default": "./Midjourney_Scraped_Images/"}),
                "num_images_to_scrape": ("INT", {"default": 10, "min": 0, "max": 1000, "step": 1}),
                "timeout": ("INT", {"default": 5, "min": 1, "max": 60, "step": 1}),
                "headless": ("BOOLEAN", {"default": True}),
                "cookies": ("STRING", {"default": ""}),
            }
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("image_paths",)
    FUNCTION = "scrape_images"
    CATEGORY = "Image Scrapers"

    def scrape_images(self, search_url, output_directory, num_images_to_scrape, timeout, headless, cookies):
        img_links = []
        driver = None
        print("Starting MJ Scraper Node...")
        try:
            options = uc.ChromeOptions()
            if headless:
                options.add_argument("--headless")
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")

            print("Initializing undetected_chromedriver...")
            driver = uc.Chrome(options=options)
            print("undetected_chromedriver initialized successfully.")

            driver.implicitly_wait(timeout)
            print(f"Navigating to: {search_url}")
            driver.get(search_url)
            print(f"Navigation complete. Current URL: {driver.current_url}")

            if cookies:
                print("Injecting provided cookies...")
                for cookie_pair in cookies.split(';'):
                    if '=' in cookie_pair:
                        name, value = cookie_pair.strip().split('=', 1)
                        try:
                            driver.add_cookie({'name': name, 'value': value, 'domain': '.midjourney.com'})
                            print(f"Added cookie: {name}")
                        except Exception as e:
                            print(f"Error adding cookie {name}: {e}")
                driver.get(search_url)
                print(f"Re-navigated after cookie injection. Current URL: {driver.current_url}")

            wait = WebDriverWait(driver, timeout)

            last_height = driver.execute_script("return document.body.scrollHeight")
            while True:
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                try:
                    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "img[src*='cdn.midjourney.com'], video[src*='cdn.midjourney.com']")))
                except:
                    pass

                time.sleep(3)
                new_height = driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            image_elements = driver.find_elements(By.CSS_SELECTOR, "img[src*='cdn.midjourney.com']")
            video_elements = driver.find_elements(By.CSS_SELECTOR, "video[src*='cdn.midjourney.com']")

            all_elements = image_elements + video_elements
            print(f"Found {len(all_elements)} potential links (images and videos).")

            for elem in all_elements:
                link = elem.get_attribute('src')
                if not link:
                    link = elem.get_attribute('href')

                if link:
                    print(f"Scraped link: {link}")
                    
                    if "/video/" in link and link.endswith(".webp"):
                        link = link.replace("_640_N.webp", ".mp4")
                        print(f"Transformed video link to: {link}")
                    elif ".webp" in link:
                        link = link.replace("0_0_32_N.webp", "0_0.png")
                        link = link.replace("0_1_32_N.webp", "0_0.png")
                        link = link.replace("0_2_32_N.webp", "0_0.png")
                        link = link.replace("0_3_32_N.webp", "0_0.png")
                        link = link.replace("grid_0_32_N.webp", "0_0.png")
                    
                    img_links.append(link)
                    if num_images_to_scrape > 0 and len(img_links) >= num_images_to_scrape:
                        print(f"Reached desired number of items ({num_images_to_scrape}). Stopping scraping.")
                        break
                else:
                    print("Warning: Found an element but could not extract 'src' or 'href' attribute. Skipping.")

            os.makedirs(output_directory, exist_ok=True)

            downloaded_image_paths = []
            print(f"Attempting to download {len(img_links)} items.")
            for i, item_link in enumerate(img_links):
                retries = 9
                for attempt in range(retries):
                    try:
                        print(f"Downloading item {i+1}/{len(img_links)}: {item_link} (Attempt {attempt + 1}/{retries})")
                        time.sleep(0.8)
                        download_headers = {
                            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                            'Accept': 'image/webp,image/apng,image/*,*/*;q=0.8,video/*',
                            'Accept-Language': 'en-US,en;q=0.9',
                            'Connection': 'keep-alive',
                            'Referer': search_url
                        }
                        item_data = requests.get(item_link, headers=download_headers, timeout=10).content
                        
                        parsed_url = urlparse(item_link)
                        path = parsed_url.path
                        ext = os.path.splitext(path)[1]
                        if not ext:
                            ext = ".png"
                        
                        item_name = ''.join(random.choices(string.ascii_letters + string.digits, k=8)) + ext
                        file_path = os.path.join(output_directory, item_name)
                        with open(file_path, 'wb') as handler:
                            handler.write(item_data)
                        
                        file_size = os.path.getsize(file_path)
                        if file_size < MIN_FILE_SIZE_BYTES:
                            print(f"Warning: Downloaded file {item_name} is only {file_size} bytes, which is less than {MIN_FILE_SIZE_BYTES} bytes. Considering it corrupted.")
                            os.remove(file_path)
                            raise requests.exceptions.RequestException("File too small, likely corrupted.")

                        downloaded_image_paths.append(file_path)
                        print(f"Downloaded: {item_name} ({file_size} bytes)")
                        break
                    except requests.exceptions.RequestException as e:
                        print(f"Error downloading {item_link}: {e}")
                        print(f"RequestException details: {e}")
                        if attempt < retries - 1:
                            print(f"Retrying download in 2 seconds...")
                            time.sleep(2)
                        else:
                            print(f"Failed to download {item_link} after {retries} attempts.")
                    except Exception as e:
                        print(f"Error saving item: {e}")
                        print(f"General Exception details: {e}")
                        break

            return (",".join(downloaded_image_paths),)

        except Exception as e:
            print(f"An unhandled error occurred during scraping: {e}")
            traceback.print_exc()
            return ("",)
        finally:
            if driver:
                driver.quit()


NODE_CLASS_MAPPINGS = {
    "MJScraper": MJScraperNode
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MJScraper": "Midjourney Scraper"
}