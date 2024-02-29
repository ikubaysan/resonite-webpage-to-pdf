from flask import Flask, request, send_from_directory, Response
import time
import undetected_chromedriver as uc
import base64
import os
import logging

"""
Options
"""
HOST = "0.0.0.0"
PORT = 2095

# Set this to None if you don't want to use a custom domain for the URLs returned by the API
DOMAIN = "dingo.pinkplayhouse.xyz"

PDF_STORAGE_DIR = 'pdf_storage'
# driver.get() webpage access timeout
WEBPAGE_TIMEOUT_SECONDS = 5
# After the webpage has been accessed, duration to wait for webpage to load before taking a screenshot
WEBPAGE_LOAD_SECONDS = 5
"""
End of Options
"""


# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

class PDFConverter:
    def __init__(self, storage_dir=PDF_STORAGE_DIR):
        self.storage_dir = storage_dir
        if not os.path.exists(storage_dir):
            os.makedirs(storage_dir)

    @staticmethod
    def setup_undetected_chrome_driver():
        options = uc.ChromeOptions()
        options.add_argument('--headless')
        driver = uc.Chrome(options=options)
        return driver

    def convert_webpage_to_pdf(self, url):
        try:
            driver = self.setup_undetected_chrome_driver()
            driver.set_page_load_timeout(WEBPAGE_TIMEOUT_SECONDS)
            driver.get(url)
            logging.info(f"Accessed webpage '{url}' successfully. "
                         f"Waiting {WEBPAGE_LOAD_SECONDS} seconds for it to "
                         f"load before creating PDF...")
            time.sleep(WEBPAGE_LOAD_SECONDS)

            result = driver.execute_cdp_cmd("Page.printToPDF", {"landscape": False, "printBackground": True})
            driver.quit()

            # Encode URL to a filesystem-safe Base64 string
            encoded_url = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
            safe_filename = f"{encoded_url}.pdf"
            output_filename = os.path.join(self.storage_dir, safe_filename)

            with open(output_filename, "wb") as f:
                f.write(base64.b64decode(result['data']))

            # Log the creation of the PDF file
            logging.info(f"PDF file created: {os.path.abspath(output_filename)}")
            return safe_filename  # Return the safe filename for URL generation
        except Exception as e:
            logging.error(f"Error converting URL to PDF: {e}")
            return None

@app.route('/convert', methods=['GET'])
def convert():
    url = request.args.get('url')
    if not url:
        return Response("Missing URL", status=400, mimetype='text/plain')

    # Check if the URL has a scheme, if not, prepend 'http://'
    if not (url.startswith('http://') or url.startswith('https://')):
        url = 'http://' + url

    logging.info(f"Received request to convert URL: {url}")

    converter = PDFConverter()
    safe_filename = converter.convert_webpage_to_pdf(url)
    if safe_filename:
        # Determine base URL based on whether DOMAIN is set
        base_url = f"http://{DOMAIN}:2095" if DOMAIN else request.host_url.rstrip('/')
        pdf_url = f"{base_url}/pdfs/{safe_filename}"
        return Response(pdf_url, mimetype='text/plain')
    else:
        return Response("Failed to convert webpage to PDF.", status=500, mimetype='text/plain')

@app.route('/pdfs/<path:filename>')
def serve_pdf(filename):
    actual_path = os.path.join(PDF_STORAGE_DIR, filename)
    logging.info(f"Attempting to serve PDF file: {actual_path}")
    if not os.path.exists(actual_path):
        logging.error(f"File not found: {actual_path}")
        return Response("File not found.", status=404, mimetype='text/plain')
    return send_from_directory(PDF_STORAGE_DIR, filename, as_attachment=False)

if __name__ == "__main__":
    app.run(host=HOST, port=PORT)
