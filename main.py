from flask import Flask, request, send_from_directory, Response
import time
import base64
import hashlib
import os
import logging
import undetected_chromedriver as uc
import chromedriver_autoinstaller
import configparser
from selenium.webdriver.common.by import By
import validators
from abc import ABC, abstractmethod
from typing import List, Tuple, Union
from LinkIdentification.DocumentCollection import DocumentCollection
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

config_path = "config.ini"
config = configparser.ConfigParser()
config.read(config_path)

HOST = config.get('DEFAULT', 'HOST')
PORT = config.getint('DEFAULT', 'PORT')
DOMAIN = config.get('DEFAULT', 'DOMAIN', fallback=None)
IMAGE_STORAGE_DIR = config.get('DEFAULT', 'IMAGE_STORAGE_DIR')
PDF_STORAGE_DIR = config.get('DEFAULT', 'PDF_STORAGE_DIR')
WEBPAGE_TIMEOUT_SECONDS = config.getint('DEFAULT', 'WEBPAGE_TIMEOUT_SECONDS')
WEBPAGE_LOAD_SECONDS = config.getint('DEFAULT', 'WEBPAGE_LOAD_SECONDS')
DUPLICATE_IMAGE_PRUNE_SECONDS = config.getint('DEFAULT', 'DUPLICATE_IMAGE_PRUNE_SECONDS')
DUPLICATE_PDF_PRUNE_SECONDS = config.getint('DEFAULT', 'DUPLICATE_PDF_PRUNE_SECONDS')
IMAGE_DEFAULT_WINDOW_WIDTH = config.getint('DEFAULT', 'IMAGE_DEFAULT_WINDOW_WIDTH')
IMAGE_DEFAULT_WINDOW_HEIGHT = config.getint('DEFAULT', 'IMAGE_DEFAULT_WINDOW_HEIGHT')
HEADLESS_WEBDRIVER = config.getboolean('DEFAULT', 'HEADLESS_WEBDRIVER')


class WebDriverManager:
    def __init__(self, webpage_timeout_seconds: int):
        self.driver = None
        self.setup_undetected_chrome_driver(webpage_timeout_seconds)

    def setup_undetected_chrome_driver(self, webpage_timeout_seconds: int):
        chromedriver_autoinstaller.install()

        set_device_metrics_override = dict({
            "width": 360,
            "height": 800,
            "deviceScaleFactor": 50,
            "mobile": True
        })

        options = uc.ChromeOptions()

        options.add_experimental_option("prefs", {
            "profile.default_content_setting_values.geolocation": 2,  # 1: allow, 2: block
        })

        if HEADLESS_WEBDRIVER:
            logging.info("Running WebDriver in headless mode. Note: some websites may detect this and block access.")
            options.add_argument('--headless')
        else:
            logging.info("Running WebDriver in non-headless mode.")

        self.driver = uc.Chrome(options=options)
        self.driver.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', set_device_metrics_override)
        self.driver.set_page_load_timeout(webpage_timeout_seconds)

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
                    self.driver.set_window_size(IMAGE_DEFAULT_WINDOW_WIDTH, IMAGE_DEFAULT_WINDOW_HEIGHT)
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



class Converter(ABC):

    @abstractmethod
    def convert_webpage(self, driver, url: str = None) -> (str, int):
        pass

    def prune_old_assets(self, storage_dir: str, encoded_url: str, extension: str, prune_seconds: int):
        for file in os.listdir(storage_dir):
            if file.startswith(f"{encoded_url}_") and file.endswith(extension):
                if time.time() - os.path.getmtime(os.path.join(storage_dir, file)) > prune_seconds:
                    logging.info(f"Pruning old file: {file}")
                    os.remove(os.path.join(storage_dir, file))

    @staticmethod
    def await_webpage_load(driver, webpage_load_seconds) -> bool:
        start_time = time.time()
        while time.time() - start_time < webpage_load_seconds:
            ready_state = driver.execute_script("return document.readyState")
            if ready_state == "complete":
                logging.info(f"Confirmed webpage is ready in {round(time.time() - start_time, 4)} seconds based on readyState.")
                return True
            time.sleep(0.1)
        return False


    @staticmethod
    def get_http_status_code(driver) -> int:
        current_url = driver.current_url
        status_code = driver.execute_script('return fetch(arguments[0], {method: "GET"}).then(response => response.status);', current_url)
        return status_code

    @staticmethod
    def query_to_google_search_url(query: str) -> str:
        base_url = "https://www.google.com/search?q="
        encoded_query = "+".join(query.split())
        return base_url + encoded_query


class Link:
    def __init__(self, uri: str, bounds: Tuple[float, float, float, float], page_width: float, page_height: float):
        self.uri = uri
        self.bounds = bounds  # (x0, y0, x1, y1)
        self.bounds_width = bounds[2] - bounds[0]
        self.bounds_height = bounds[3] - bounds[1]
        # Normalize bounds
        self.normalized_bounds = (
            bounds[0] / page_width,
            bounds[1] / page_height,
            bounds[2] / page_width,
            bounds[3] / page_height
        )

    def __repr__(self):
        return f"Link(uri={self.uri}, bounds={self.bounds}, normalized_bounds={self.normalized_bounds}, bounds_width={self.bounds_width}, bounds_height={self.bounds_height})"

class Page:
    def __init__(self, number: int, size: Tuple[float, float]):
        self.number = number
        self.size = size  # (width, height)
        self.links: List[Link] = []

    def add_link(self, link: Link):
        self.links.append(link)

    def __repr__(self):
        return f"Page(number={self.number}, size={self.size}, links={self.links})"

class PDFConverter(Converter):

    def __init__(self, storage_dir: str, webpage_load_seconds: int, duplicate_pdf_prune_seconds: int):
        self.storage_dir = storage_dir
        self.webpage_load_seconds = webpage_load_seconds
        self.duplicate_pdf_prune_seconds = duplicate_pdf_prune_seconds
        self.document_collection = DocumentCollection()

        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    def convert_webpage(self, driver, url: str = None) -> (str, int):
        try:
            if not url:
                logging.info("No URL provided. Using the current URL in the WebDriver.")
                url = driver.current_url

            driver.get(url)

            status_code = self.get_http_status_code(driver)

            logging.info(f"Accessed webpage '{url}' successfully, with HTTP status code {status_code}. "
                         f"Waiting {WEBPAGE_LOAD_SECONDS} seconds for it to "
                         f"load before creating PDF...")

            await_webpage_load_result = PDFConverter.await_webpage_load(driver, self.webpage_load_seconds)
            if not await_webpage_load_result:
                logging.warning(f"Webpage '{url}' did not reach readyState within {self.webpage_load_seconds} seconds.")

            # Check if the URL changed
            if driver.current_url != url:
                logging.info(f"URL changed to {driver.current_url}. Reassigning URL.")
                # Sleep for 1 second because there may be multiple redirects
                time.sleep(1)
                url = driver.current_url
                logging.info(f"New URL: {url}")
                # We now must await webpage load again
                await_webpage_load_result = PDFConverter.await_webpage_load(driver, self.webpage_load_seconds)
                if not await_webpage_load_result:
                    logging.warning(f"Webpage '{url}' accessed after redirect did not reach readyState within {self.webpage_load_seconds} seconds.")

            result = driver.execute_cdp_cmd("Page.printToPDF", {
                "landscape": False,
                "printBackground": True,
                "marginTop": 0,
                "marginBottom": 0,
                "marginLeft": 0,
                "marginRight": 0,
                "preferCSSPageSize": True
            })

            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()

            for file in os.listdir(self.storage_dir):
                if file.startswith(f"{hashed_url}_") and file.endswith(".pdf"):
                    if time.time() - os.path.getmtime(os.path.join(self.storage_dir, file)) > DUPLICATE_PDF_PRUNE_SECONDS:
                        logging.info(f"Pruning old PDF file: {file}")
                        os.remove(os.path.join(self.storage_dir, file))

            safe_filename = f"{hashed_url}_{int(time.time())}.pdf"
            output_file_path = os.path.join(self.storage_dir, safe_filename)

            with open(output_file_path, "wb") as f:
                f.write(base64.b64decode(result['data']))

            logging.info(f"PDF file created: {os.path.abspath(output_file_path)}")

            self.document_collection.add_document(local_file_path=output_file_path)

            return safe_filename, status_code
        except Exception as e:
            logging.error(f"Error converting URL to PDF: {e}")
            return None, None

    def click(self, normalized_x: float, normalized_y: float, page_index: int, pdf_filename: str) -> Union[str, None]:
        """
        :param normalized_x:
        :param normalized_y:
        :param page_index:
        :param pdf_filename:
        :return: URL which can be accessed by clicking at the given coordinates, or None if no URL is found
        """

        document = self.document_collection.get_document_by_filename(filename=pdf_filename)
        if not document:
            try:
                self.document_collection.add_document(local_file_path=os.path.join(self.storage_dir, pdf_filename))
                document = self.document_collection.get_document_by_filename(filename=pdf_filename)
            except FileNotFoundError:
                logging.error(f"PDF file not found: {pdf_filename}")
                return None

        url = document.get_url_at_position(normalized_x, normalized_y, normalized_coordinates=True, page_index=page_index)
        if url:
            logging.info(f"Found a URL at position ({normalized_x}, {normalized_y}) on page {page_index} for PDF {pdf_filename}: {url}")
            return url
        else:
            logging.info(f"No URL found at position ({normalized_x}, {normalized_y}) on page {page_index} for PDF {pdf_filename}")
            return None

class ImageConverter(Converter):
    def __init__(self, storage_dir: str, webpage_load_seconds: int, duplicate_image_prune_seconds: int):
        self.storage_dir = storage_dir
        self.webpage_load_seconds = webpage_load_seconds
        self.duplicate_image_prune_seconds = duplicate_image_prune_seconds

        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)


    def print_clickable_elements(self, driver):
        clickable_elements = driver.find_elements(By.TAG_NAME, "a")
        for element in clickable_elements:
            if not element.get_attribute('onclick'):
                if element.size['width'] > 0 and element.size['height'] > 0 and element.location['x'] > 0 and element.location['y'] > 0:
                    print(f"Tag: {element.tag_name}, x={element.location['x']}, y={element.location['y']}, "
                          f"width={element.size['width']}, height={element.size['height']}, "
                          f"href={element.get_attribute('href')}")

    def convert_webpage(self, driver, url: str = None) -> (str, int):
        try:
            if url:
                # Reset window size to a default value before resizing according to content
                driver.set_window_size(IMAGE_DEFAULT_WINDOW_WIDTH, IMAGE_DEFAULT_WINDOW_HEIGHT)  # Default window size
                logging.info(f"Window size reset to default {IMAGE_DEFAULT_WINDOW_WIDTH}x{IMAGE_DEFAULT_WINDOW_HEIGHT} because a URL was provided.")
                driver.get(url)
            else:
                logging.info("No URL provided. Using the current URL in the WebDriver.")
                url = driver.current_url

            status_code = self.get_http_status_code(driver)

            logging.info(f"Accessed webpage '{url}' successfully, with HTTP status code {status_code}.")
            await_webpage_load_result = self.await_webpage_load(driver, self.webpage_load_seconds)

            if not await_webpage_load_result:
                logging.warning(f"Webpage '{url}' did not reach readyState within {self.webpage_load_seconds} seconds.")

            # Determine the height of the webpage
            #total_height = driver.execute_script("return document.body.parentNode.scrollHeight")
            total_height = driver.execute_script("return document.documentElement.scrollHeight")

            # Resize window to the full height of the webpage to capture all content
            driver.set_window_size(IMAGE_DEFAULT_WINDOW_WIDTH, total_height)
            logging.info(f"Resized window to {IMAGE_DEFAULT_WINDOW_WIDTH}x{total_height}")
            driver.execute_script("window.scrollTo(0, 0)")

            # Use a hash of the URL to keep the filename short and manageable
            hashed_url = hashlib.md5(url.encode('utf-8')).hexdigest()

            self.prune_old_assets(storage_dir=self.storage_dir,
                                  encoded_url=hashed_url,
                                  extension='.png',
                                  prune_seconds=self.duplicate_image_prune_seconds)

            safe_filename = f"{hashed_url}_{int(time.time())}.png"
            output_filename = os.path.join(self.storage_dir, safe_filename)

            driver.save_screenshot(output_filename)

            logging.info(f"Image file created: {os.path.abspath(output_filename)}")

            #self.print_clickable_elements(driver)

            return safe_filename, status_code
        except Exception as e:
            logging.error(f"Error converting URL to image: {e}")
            return None, None


def is_valid_url(url):
    """
    Validates whether a given string is a valid URL. Adds 'http://' if no protocol is specified.

    Args:
    url (str): The URL string to validate.

    Returns:
    bool: True if the string is a valid URL, False otherwise.
    """
    # Check if the URL has a protocol, if not prepend 'http://'
    if not url.startswith(('http://', 'https://')):
        url = 'http://' + url

    result = validators.url(url)
    return True if result else False

class FlaskWebApp:
    def __init__(self, config_path: str = 'config.ini'):

        if not os.path.exists(config_path):
            logging.error(f"{config_path} file not found. "
                          f"Please make a copy of 'config_sample.ini', "
                          f"rename it to '{config_path}', and modify it accordingly.")
            exit()

        self.app = Flask(__name__)
        self.limiter = Limiter(
            key_func=get_remote_address,
            app=self.app,
            default_limits=["7200 per hour", "120 per minute"]
        )

        self.image_converter = ImageConverter(storage_dir=IMAGE_STORAGE_DIR,
                                                webpage_load_seconds=WEBPAGE_LOAD_SECONDS,
                                                duplicate_image_prune_seconds=DUPLICATE_IMAGE_PRUNE_SECONDS)
        self.pdf_converter = PDFConverter(storage_dir=PDF_STORAGE_DIR,
                                            webpage_load_seconds=WEBPAGE_LOAD_SECONDS,
                                            duplicate_pdf_prune_seconds=DUPLICATE_PDF_PRUNE_SECONDS)

        self.setup_routes()
        self.image_web_driver_manager = WebDriverManager(webpage_timeout_seconds=WEBPAGE_TIMEOUT_SECONDS)
        self.pdf_web_driver_manager = WebDriverManager(webpage_timeout_seconds=WEBPAGE_TIMEOUT_SECONDS)
        return

    def setup_routes(self):
        self.app.add_url_rule('/convert-to-image', 'convert_to_image', self.convert_to_image, methods=['GET'])
        self.app.add_url_rule('/convert-to-pdf', 'convert_to_pdf', self.convert_to_pdf, methods=['GET'])
        self.app.add_url_rule('/images/<path:filename>', 'serve_image', self.serve_image, methods=['GET'])
        self.app.add_url_rule('/pdfs/<path:filename>', 'serve_pdf', self.serve_pdf, methods=['GET'])
        self.app.add_url_rule('/click-image', 'click_image', self.click_image, methods=['GET'])
        self.app.add_url_rule('/click-pdf', 'click_pdf', self.click_pdf, methods=['GET'])

    def run(self):
        self.app.run(host=HOST, port=PORT)

    def click_pdf(self):
        # Clicks at the provided x, y coordinates on the currently loaded PDF, if any
        x = request.args.get('x')
        y = request.args.get('y')
        pdf_filename = request.args.get('pdf_filename')

        if "/" in pdf_filename:
            # Remove everything before and including the last slash
            original_pdf_filename = pdf_filename
            pdf_filename = pdf_filename.split("/")[-1]
            logging.info(f"Extracted PDF filename from {original_pdf_filename}: {pdf_filename}")

        page_index = request.args.get('page_index')
        if not x or not y or not pdf_filename or not page_index:
            return Response("Missing x, y, pdf_filename, or page_index", status=400)

        x = float(x)
        y = float(y)

        if x > 1 or y > 1 or x < 0 or y < 0:
            return Response("x and y coordinates must be normalized between 0 and 1, where origin is at the top left.", status=400)

        page_index = int(page_index)

        #url_accessed, safe_filename, status_code = self.pdf_converter.click(driver, x, y, page_index, pdf_filename)

        url_at_position = self.pdf_converter.click(x, y, page_index, pdf_filename)

        if url_at_position:
            return Response(url_at_position, mimetype='text/plain', status=200)
        else:
            return Response("", mimetype='text/plain', status=500)


    def click_image(self):
        # Clicks at the provided x, y coordinates on the currently loaded webpage, if any
        x = request.args.get('x')
        y = request.args.get('y')
        if not x or not y:
            return Response("Missing x or y coordinates", status=400)

        x = int(x)
        y = int(y)

        click_executed = self.image_web_driver_manager.click_at_pixel(x, y)
        if click_executed:
            # We need to create a new image after the click, and return the URL
            safe_filename, status_code = self.image_converter.convert_webpage(self.image_web_driver_manager.driver, url=None)
            if safe_filename:
                base_url = f"http://{DOMAIN}:{PORT}" if DOMAIN else request.host_url.rstrip('/')
                image_url = f"{base_url}/images/{safe_filename}"
                response_contents = f"{image_url}*{status_code}*"
                return Response(response_contents, mimetype='text/plain')
            else:
                return Response("Click executed, but failed to convert webpage to image.", status=500, mimetype='text/plain')
        else:
            return Response("Click not executed.", status=400)


    def sanitize_url(self, url: str):
        url = url.strip()

        # Replace | with & in the URL.
        # The client should replace & with | when sending the URL.
        # This is because a requested URL may contain '&',
        # and this can cause it to be unintentionally picked up as a query parameter.
        url = url.replace('|', '&')

        if is_valid_url(url):
            logging.info(f"Confirmed URL is valid: {url}")
        else:
            logging.info(f"Invalid URL: {url}. Attempting to convert to Google search URL.")
            url = Converter.query_to_google_search_url(url)

        if not (url.startswith('http://') or url.startswith('https://')):
            url = 'http://' + url

        return url


    def convert_to_pdf(self):
        url = request.args.get('url')
        if not url:
            return Response("Missing URL", status=400)

        logging.info(f"Received request to convert URL to PDF: {url}")
        url = self.sanitize_url(url)
        logging.info(f"Sanitized URL: {url}")


        driver = self.pdf_web_driver_manager.driver

        safe_filename, status_code = self.pdf_converter.convert_webpage(driver, url)

        if safe_filename:
            base_url = f"http://{DOMAIN}:{PORT}" if DOMAIN else request.host_url.rstrip('/')
            pdf_url = f"{base_url}/pdfs/{safe_filename}"
            response_contents = f"{pdf_url}*{status_code}*"
            return Response(response_contents, mimetype='text/plain')
        else:
            return Response("Failed to convert webpage to PDF.", status=500, mimetype='text/plain')


    def convert_to_image(self):
        url = request.args.get('url')
        if not url:
            return Response("Missing URL", status=400)

        url = self.sanitize_url(url)

        logging.info(f"Received request to convert URL to image: {url}")

        driver = self.image_web_driver_manager.driver

        safe_filename, status_code = self.image_converter.convert_webpage(driver, url)

        if safe_filename:
            base_url = f"http://{DOMAIN}:{PORT}" if DOMAIN else request.host_url.rstrip('/')
            image_url = f"{base_url}/images/{safe_filename}"
            response_contents = f"{image_url}*{status_code}*"
            return Response(response_contents, mimetype='text/plain')
        else:
            return Response("Failed to convert webpage to image.", status=500, mimetype='text/plain')

    def serve_image(self, filename):
        actual_path = os.path.join(IMAGE_STORAGE_DIR, filename)
        logging.info(f"Attempting to serve image file: {actual_path}")
        if not os.path.exists(actual_path):
            logging.error(f"File not found: {actual_path}")
            return Response("File not found.", status=404)
        return send_from_directory(IMAGE_STORAGE_DIR, filename, as_attachment=False)

    def serve_pdf(self, filename):
        actual_path = os.path.join(PDF_STORAGE_DIR, filename)
        logging.info(f"Attempting to serve PDF file: {actual_path}")
        if not os.path.exists(actual_path):
            logging.error(f"File not found: {actual_path}")
            return Response("File not found.", status=404)
        return send_from_directory(PDF_STORAGE_DIR, filename, as_attachment=False)


if __name__ == "__main__":
    app = FlaskWebApp()
    app.run()
