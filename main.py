import time
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import base64


def setup_undetected_chrome_driver():
    options = uc.ChromeOptions()
    options.add_argument('--headless')
    # Add any other options you need
    driver = uc.Chrome(options=options)
    return driver


def convert_webpage_to_pdf(url, output_filename):
    driver = setup_undetected_chrome_driver()
    driver.get(url)

    # Use explicit waits or time.sleep as necessary
    # Example of an explicit wait:
    # WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

    # Execute Chrome's print to PDF command
    result = driver.execute_cdp_cmd("Page.printToPDF", {"landscape": False, "printBackground": True})

    # Decode the base64-encoded result and save to file
    with open(output_filename, "wb") as f:
        f.write(base64.b64decode(result['data']))

    driver.quit()


# Example usage
url = "http://yahoo.com"
output_filename = "output.pdf"
convert_webpage_to_pdf(url, output_filename)
