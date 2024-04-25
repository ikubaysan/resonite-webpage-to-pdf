from flask import Flask, request, send_from_directory, Response
import time
import base64
import hashlib
import os
import logging
import undetected_chromedriver as uc
import chromedriver_autoinstaller
import configparser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WebDriverManager:
    def __init__(self, webpage_timeout_seconds: int):
        self.driver = None
        self.setup_undetected_chrome_driver(webpage_timeout_seconds)

    def setup_undetected_chrome_driver(self, webpage_timeout_seconds: int):
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        chromedriver_autoinstaller.install()
        self.driver = uc.Chrome(options=options)
        self.driver.set_page_load_timeout(webpage_timeout_seconds)

    # def click_at_pixel(self, x, y) -> bool:
    #     self.driver.execute_script("window.scrollTo(0, 0)")
    #     element = self.driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", x, y)
    #     if element and (element.tag_name == 'a' or element.get_attribute('onclick')):
    #         print("Element is clickable.")
    #         # Use ActionChains to move to element and click (if required)
    #         actions = ActionChains(self.driver)
    #         actions.move_to_element(element).click().perform()
    #         return True
    #     elif element:
    #         print("Element is not clickable.")
    #         return False
    #     else:
    #         print("No element found at these coordinates.")
    #         return False

    def click_at_pixel(self, x, y) -> bool:
        # Scroll the window to the y-coordinate minus half the window height to ensure the element is in the view
        logging.info(f"Clicking at x={x}, y={y}")
        self.driver.execute_script("window.scrollTo(0, arguments[0] - window.innerHeight / 2);", y)
        time.sleep(0.1)  # Allow time for dynamic content

        # Retrieve the element at the given x, y coordinates
        element = self.driver.execute_script("return document.elementFromPoint(arguments[0], arguments[1]);", x, y)
        if element:
            # Check if the element itself or any of its parents are clickable
            clickable_element = self.get_clickable_element(element)
            if clickable_element:
                # Check if the element is likely to cause a URL change
                if clickable_element.tag_name.lower() == 'a' and clickable_element.get_attribute('href'):
                    logging.info("Element will change the URL. Adjusting window size.")
                    self.driver.set_window_size(1920, 1080)
                # Execute a click directly via JavaScript
                self.driver.execute_script("arguments[0].click();", clickable_element)
                return True
            else:
                print("Element or its parents are not clickable.")
                return False
        else:
            print("No element found at these coordinates.")
            return False

    def get_clickable_element(self, element):
        # Traverse up the DOM to find a clickable element
        while element:
            # Ensure the element is not None and has the properties we need to check
            try:
                tag_name = element.tag_name.lower() if element.tag_name else ''
                onclick = element.get_attribute('onclick')
                role = element.get_attribute('role')
                href = element.get_attribute('href')
            except Exception as e:
                # Handle exceptions, which can happen if the element is stale or the WebDriver loses reference to it
                print(f"Error accessing element properties: {e}")
                return None

            if tag_name in ['a', 'button'] or onclick or (href and tag_name == 'a'):
                return element
            if role == 'button':
                return element

            # Move to the next parent element safely
            try:
                element = self.driver.execute_script("return arguments[0].parentNode;", element)
            except Exception as e:
                print(f"Error moving to parent element: {e}")
                return None

        return None


class ImageConverter:
    def __init__(self, storage_dir: str, webpage_load_seconds: int, duplicate_image_prune_seconds: int):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

        self.webpage_load_seconds = webpage_load_seconds
        self.duplicate_image_prune_seconds = duplicate_image_prune_seconds

    def await_webpage_load(self, driver) -> bool:
        start_time = time.time()
        while time.time() - start_time < self.webpage_load_seconds:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state in ['complete', 'interactive']:
                logging.info(f"Confirmed webpage is ready in {round(time.time() - start_time, 4)} seconds based on readyState.")
                return True
            time.sleep(0.1)
        return False

    def get_http_status_code(self, driver) -> int:
        current_url = driver.current_url
        status_code = driver.execute_script('return fetch(arguments[0], {method: "GET"}).then(response => response.status);', current_url)
        return status_code

    def prune_old_images(self, encoded_url: str):
        for file in os.listdir(self.storage_dir):
            if file.startswith(f"{encoded_url}_") and file.endswith(".png"):
                if time.time() - os.path.getmtime(os.path.join(self.storage_dir, file)) > self.duplicate_image_prune_seconds:
                    logging.info(f"Pruning old image file: {file}")
                    os.remove(os.path.join(self.storage_dir, file))


    def convert_webpage_to_image(self, driver, url: str = None) -> (str, int):
        try:
            if url:
                # Reset window size to a default value before resizing according to content
                driver.set_window_size(1920, 1080)  # Default window size
                logging.info("Window size reset to default 1920x1080 because a URL was provided.")
                driver.get(url)
            else:
                logging.info("No URL provided. Using the current URL in the WebDriver.")
                url = driver.current_url

            status_code = self.get_http_status_code(driver)

            logging.info(f"Accessed webpage '{url}' successfully, with HTTP status code {status_code}.")
            await_webpage_load_result = self.await_webpage_load(driver)
            if not await_webpage_load_result:
                logging.warning(f"Webpage '{url}' did not reach readyState within {self.webpage_load_seconds} seconds.")

            # Determine the height of the webpage
            #total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
            total_height = driver.execute_script("return document.documentElement.scrollHeight")

            # Resize window to the full height of the webpage to capture all content
            driver.set_window_size(1920, total_height)  # Width is set to 1920, or any other width you prefer
            logging.info(f"Resized window to 1920x{total_height}")
            driver.execute_script("window.scrollTo(0, 0)")

            encoded_url = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
            # Use a hash of the URL to keep the filename short and manageable
            encoded_url = hashlib.md5(encoded_url.encode('utf-8')).hexdigest()

            self.prune_old_images(encoded_url)

            safe_filename = f"{encoded_url}_{int(time.time())}.png"
            output_filename = os.path.join(self.storage_dir, safe_filename)

            driver.save_screenshot(output_filename)

            logging.info(f"Image file created: {os.path.abspath(output_filename)}")

            # clickable_elements = driver.find_elements(By.TAG_NAME, "a")
            # for element in clickable_elements:
            #     if not element.get_attribute('onclick'):
            #         if element.size['width'] > 0 and element.size['height'] > 0 and element.location['x'] > 0 and element.location['y'] > 0:
            #             print(f"Tag: {element.tag_name}, x={element.location['x']}, y={element.location['y']}, "
            #                   f"width={element.size['width']}, height={element.size['height']}, "
            #                   f"href={element.get_attribute('href')}")

            return safe_filename, status_code
        except Exception as e:
            logging.error(f"Error converting URL to image: {e}")
            return None, None



class FlaskWebApp:
    def __init__(self, config_path: str = 'config.ini'):

        if not os.path.exists('config.ini'):
            logging.error("config.ini file not found. Please make a copy of 'config_sample.ini', rename it to 'config.ini', and modify it accordingly.")
            exit()

        self.app = Flask(__name__)
        config = configparser.ConfigParser()
        config.read(config_path)

        self.HOST = config.get('DEFAULT', 'HOST')
        self.PORT = config.getint('DEFAULT', 'PORT_IMAGE')
        self.DOMAIN = config.get('DEFAULT', 'DOMAIN', fallback=None)
        self.IMAGE_STORAGE_DIR = config.get('DEFAULT', 'IMAGE_STORAGE_DIR')
        self.WEBPAGE_TIMEOUT_SECONDS = config.getint('DEFAULT', 'WEBPAGE_TIMEOUT_SECONDS')
        self.WEBPAGE_LOAD_SECONDS = config.getint('DEFAULT', 'WEBPAGE_LOAD_SECONDS')
        self.DUPLICATE_IMAGE_PRUNE_SECONDS = config.getint('DEFAULT', 'DUPLICATE_IMAGE_PRUNE_SECONDS')

        self.image_converter = ImageConverter(storage_dir=self.IMAGE_STORAGE_DIR,
                                                webpage_load_seconds=self.WEBPAGE_LOAD_SECONDS,
                                                duplicate_image_prune_seconds=self.DUPLICATE_IMAGE_PRUNE_SECONDS)

        self.setup_routes()
        self.web_driver_manager = WebDriverManager(webpage_timeout_seconds=self.WEBPAGE_TIMEOUT_SECONDS)
        return

    def setup_routes(self):
        self.app.add_url_rule('/convert', 'convert', self.convert, methods=['GET'])
        self.app.add_url_rule('/images/<path:filename>', 'serve_image', self.serve_image, methods=['GET'])
        self.app.add_url_rule('/click', 'click', self.click, methods=['GET'])

    def run(self):
        self.app.run(host=self.HOST, port=self.PORT)

    def click(self):
        # Clicks at the provided x, y coordinates on the currently loaded webpage, if any
        x = request.args.get('x')
        y = request.args.get('y')
        if not x or not y:
            return Response("Missing x or y coordinates", status=400)

        x = int(x)
        y = int(y)

        click_executed = self.web_driver_manager.click_at_pixel(x, y)
        if click_executed:
            # We need to create a new image after the click, and return the URL
            safe_filename, status_code = self.image_converter.convert_webpage_to_image(self.web_driver_manager.driver, url=None)
            if safe_filename:
                base_url = f"http://{self.DOMAIN}:{self.PORT}" if self.DOMAIN else request.host_url.rstrip('/')
                image_url = f"{base_url}/images/{safe_filename}"
                response_contents = f"{image_url}*{status_code}*"
                return Response(response_contents, mimetype='text/plain')
            else:
                return Response("Click executed, but failed to convert webpage to image.", status=500, mimetype='text/plain')
        else:
            return Response("Click not executed.", status=400)

    def convert(self):
        url = request.args.get('url')
        if not url:
            return Response("Missing URL", status=400)

        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'http://' + url
        url = url.strip()

        logging.info(f"Received request to convert URL: {url}")

        driver = self.web_driver_manager.driver

        safe_filename, status_code = self.image_converter.convert_webpage_to_image(driver, url)

        if safe_filename:
            base_url = f"http://{self.DOMAIN}:{self.PORT}" if self.DOMAIN else request.host_url.rstrip('/')
            image_url = f"{base_url}/images/{safe_filename}"
            response_contents = f"{image_url}*{status_code}*"
            return Response(response_contents, mimetype='text/plain')
        else:
            return Response("Failed to convert webpage to image.", status=500, mimetype='text/plain')

    def serve_image(self, filename):
        actual_path = os.path.join(self.IMAGE_STORAGE_DIR, filename)
        logging.info(f"Attempting to serve image file: {actual_path}")
        if not os.path.exists(actual_path):
            logging.error(f"File not found: {actual_path}")
            return Response("File not found.", status=404)
        return send_from_directory(self.IMAGE_STORAGE_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    app = FlaskWebApp()
    app.run()
