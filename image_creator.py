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

config = configparser.ConfigParser()

if not os.path.exists('config.ini'):
    logging.error("config.ini file not found. Please make a copy of 'config_sample.ini', rename it to 'config.ini', and modify it accordingly.")
    exit()

config.read('config.ini')

HOST = config.get('DEFAULT', 'HOST')
PORT = config.getint('DEFAULT', 'PORT_IMAGE')
DOMAIN = config.get('DEFAULT', 'DOMAIN', fallback=None)
IMAGE_STORAGE_DIR = config.get('DEFAULT', 'IMAGE_STORAGE_DIR')
WEBPAGE_TIMEOUT_SECONDS = config.getint('DEFAULT', 'WEBPAGE_TIMEOUT_SECONDS')
WEBPAGE_LOAD_SECONDS = config.getint('DEFAULT', 'WEBPAGE_LOAD_SECONDS')
DUPLICATE_IMAGE_PRUNE_SECONDS = config.getint('DEFAULT', 'DUPLICATE_IMAGE_PRUNE_SECONDS')

app = Flask(__name__)

class ImageConverter:
    def __init__(self, storage_dir=IMAGE_STORAGE_DIR):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    @staticmethod
    def setup_undetected_chrome_driver():
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        chromedriver_autoinstaller.install()
        driver = uc.Chrome(options=options)
        return driver

    @staticmethod
    def await_webpage_load(driver, url):
        start_time = time.time()
        while time.time() - start_time < WEBPAGE_LOAD_SECONDS:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state in ['complete', 'interactive']:
                logging.info(f"Confirmed webpage is ready in {round(time.time() - start_time, 4)} seconds based on readyState.")
                return True
            time.sleep(0.1)
        logging.warning(f"Webpage '{url}' did not reach readyState within {WEBPAGE_LOAD_SECONDS} seconds.")

    def get_http_status_code(self, driver) -> int:
        current_url = driver.current_url
        status_code = driver.execute_script('return fetch(arguments[0], {method: "GET"}).then(response => response.status);', current_url)
        return status_code


    def convert_webpage_to_image(self, url) -> (str, int):
        try:
            driver = self.setup_undetected_chrome_driver()
            driver.set_page_load_timeout(WEBPAGE_TIMEOUT_SECONDS)
            driver.get(url)

            status_code = self.get_http_status_code(driver)

            logging.info(f"Accessed webpage '{url}' successfully, with HTTP status code {status_code}.")
            ImageConverter.await_webpage_load(driver, url)

            # Determine the height of the webpage
            total_height = driver.execute_script("return document.body.parentNode.scrollHeight")

            # Resize window to the full height of the webpage to capture all content
            driver.set_window_size(1920, total_height)  # Width is set to 1920, or any other width you prefer

            encoded_url = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')

            for file in os.listdir(self.storage_dir):
                if file.startswith(f"{encoded_url}_") and file.endswith(".png"):
                    if time.time() - os.path.getmtime(os.path.join(self.storage_dir, file)) > DUPLICATE_IMAGE_PRUNE_SECONDS:
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


@app.route('/convert', methods=['GET'])
def convert():
    url = request.args.get('url')
    if not url:
        return Response("Missing URL", status=400, mimetype='text/plain')

    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'http://' + url
    url = url.strip()

    logging.info(f"Received request to convert URL: {url}")

    converter = ImageConverter()
    safe_filename, status_code = converter.convert_webpage_to_image(url)
    if safe_filename:
        base_url = f"http://{DOMAIN}:2095" if DOMAIN else request.host_url.rstrip('/')
        image_url = f"{base_url}/images/{safe_filename}"
        response_contents = f"{image_url}*{status_code}*"
        return Response(response_contents, mimetype='text/plain')
    else:
        return Response("Failed to convert webpage to image.", status=500, mimetype='text/plain')

@app.route('/images/<path:filename>')
def serve_image(filename):
    actual_path = os.path.join(IMAGE_STORAGE_DIR, filename)
    logging.info(f"Attempting to serve image file: {actual_path}")
    if not os.path.exists(actual_path):
        logging.error(f"File not found: {actual_path}")
        return Response("File not found.", status=404, mimetype='text/plain')
    return send_from_directory(IMAGE_STORAGE_DIR, filename, as_attachment=False)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)
