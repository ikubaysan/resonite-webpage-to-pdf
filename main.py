from flask import Flask, request, jsonify, send_from_directory
import time
import undetected_chromedriver as uc
import base64
import os
import logging
from urllib.parse import quote

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
pdf_storage_dir = 'pdf_storage'  # Define the storage directory globally


class PDFConverter:
    def __init__(self, storage_dir=pdf_storage_dir):
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

        # Encode URL to a filesystem-safe Base64 string
        encoded_url = base64.urlsafe_b64encode(url.encode('utf-8')).decode('utf-8')
        safe_filename = f"{encoded_url}.pdf"
        output_filename = os.path.join(self.storage_dir, safe_filename)

        with open(output_filename, "wb") as f:
            f.write(base64.b64decode(result['data']))

        # Log the creation of the PDF file
        logging.info(f"PDF file created: {os.path.abspath(output_filename)}")
        return safe_filename  # Return the safe filename for URL generation


@app.route('/convert', methods=['GET'])
def convert():
    url = request.args.get('url')
    if not url:
        return jsonify({"error": "Missing URL"}), 400

    # Log receiving the request
    logging.info(f"Received request to convert URL: {url}")

    converter = PDFConverter()
    safe_filename = converter.convert_webpage_to_pdf(url)
    # Corrected to use /pdfs/ to match the route
    pdf_url = request.host_url.rstrip('/') + '/pdfs/' + safe_filename

    return jsonify({"message": "Conversion successful", "pdf_url": pdf_url}), 200


@app.route('/pdfs/<path:filename>')
def serve_pdf(filename):
    actual_path = os.path.join(pdf_storage_dir, filename)
    logging.info(f"Attempting to serve PDF file: {actual_path}")
    if not os.path.exists(actual_path):
        logging.error(f"File not found: {actual_path}")
        return "File not found.", 404
    return send_from_directory(pdf_storage_dir, filename, as_attachment=True)


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5011)
