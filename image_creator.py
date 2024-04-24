from flask import Flask, request, send_from_directory, Response
import time
import base64
import os
import logging
import undetected_chromedriver as uc
import chromedriver_autoinstaller
import configparser

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class WebDriverManager:
    def __init__(self):
        self.driver = None
        self.current_url = None
        self.setup_undetected_chrome_driver()

    def setup_undetected_chrome_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        chromedriver_autoinstaller.install()
        self.driver = uc.Chrome(options=options)

class ImageConverter:
    def __init__(self, storage_dir: str, webpage_load_seconds: int, webpage_timeout_seconds: int, duplicate_image_prune_seconds: int):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

        self.webpage_load_seconds = webpage_load_seconds
        self.webpage_timeout_seconds = webpage_timeout_seconds
        self.duplicate_image_prune_seconds = duplicate_image_prune_seconds

    def await_webpage_load(self, driver, url):
        start_time = time.time()
        while time.time() - start_time < self.webpage_load_seconds:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state in ['complete', 'interactive']:
                logging.info(f"Confirmed webpage is ready in {round(time.time() - start_time, 4)} seconds based on readyState.")
                return True
            time.sleep(0.1)
        logging.warning(f"Webpage '{url}' did not reach readyState within {self.webpage_load_seconds} seconds.")

    def get_http_status_code(self, driver) -> int:
        current_url = driver.current_url
        status_code = driver.execute_script('return fetch(arguments[0], {method: "GET"}).then(response => response.status);', current_url)
        return status_code

    def convert_webpage_to_image(self, driver, url) -> (str, int):
        try:
            driver.set_page_load_timeout(self.webpage_timeout_seconds)
            driver.get(url)

            status_code = self.get_http_status_code(driver)

            logging.info(f"Accessed webpage '{url}' successfully, with HTTP status code {status_code}.")
            self.await_webpage_load(driver, url)

            # Determine the height of the webpage
            total_height = driver.execute_script("return document.body.parentNode.scrollHeight")

            # Resize window to the full height of the webpage to capture all content
            driver.set_window_size(1920, total_height)  # Width is set to 1920, or any other width you prefer

            encoded_url = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')

            for file in os.listdir(self.storage_dir):
                if file.startswith(f"{encoded_url}_") and file.endswith(".png"):
                    if time.time() - os.path.getmtime(os.path.join(self.storage_dir, file)) > self.duplicate_image_prune_seconds:
                        logging.info(f"Pruning old image file: {file}")
                        os.remove(os.path.join(self.storage_dir, file))

            safe_filename = f"{encoded_url}_{int(time.time())}.png"
            output_filename = os.path.join(self.storage_dir, safe_filename)

            driver.save_screenshot(output_filename)

            logging.info(f"Image file created: {os.path.abspath(output_filename)}")
            driver.quit()

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
                                                webpage_timeout_seconds=self.WEBPAGE_TIMEOUT_SECONDS,
                                                duplicate_image_prune_seconds=self.DUPLICATE_IMAGE_PRUNE_SECONDS)

        self.setup_routes()
        return

    def setup_routes(self):
        self.app.add_url_rule('/convert', 'convert', self.convert, methods=['GET'])
        self.app.add_url_rule('/images/<path:filename>', 'serve_image', self.serve_image, methods=['GET'])

    def run(self):
        self.app.run(host=self.HOST, port=self.PORT)

    def convert(self):
        url = request.args.get('url')
        if not url:
            return Response("Missing URL", status=400)

        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'http://' + url
        url = url.strip()

        logging.info(f"Received request to convert URL: {url}")

        driver = WebDriverManager().driver
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
