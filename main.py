from flask import Flask, request, jsonify
import time
import undetected_chromedriver as uc
import base64
import os
import logging
from urllib.parse import quote

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)

class PDFConverter:
    def __init__(self, storage_dir='pdf_storage'):
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
        driver = self.setup_undetected_chrome_driver()
        driver.get(url)
        time.sleep(3)

        result = driver.execute_cdp_cmd("Page.printToPDF", {"landscape": False, "printBackground": True})
        driver.quit()

        safe_filename = quote(url, safe='') + '.pdf'
        output_filename = os.path.join(self.storage_dir, safe_filename)

        with open(output_filename, "wb") as f:
            f.write(base64.b64decode(result['data']))

        # Log the creation of the PDF file
        logging.info(f"PDF file created: {os.path.abspath(output_filename)}")
        return output_filename

@app.route('/convert', methods=['GET'])
def convert():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    # Log receiving the request
    logging.info(f"Received request to convert URL: {url}")

    converter = PDFConverter()
    output_filename = converter.convert_webpage_to_pdf(url)

    return jsonify({"message": "Conversion successful", "pdf_url": output_filename}), 200

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5011)
