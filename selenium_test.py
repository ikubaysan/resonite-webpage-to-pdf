import undetected_chromedriver as uc
from undetected_chromedriver import Chrome, ChromeOptions

# Initialize ChromeOptions
options = ChromeOptions()

# Implicit wait
options.add_argument("--wait-for-browser")

# Initialize undetected Chrome driver
driver = uc.Chrome(options=options)

# URL launch
driver.get("https://www.github.com/1arsitdenmauyarst")

# Get current URL
current_url = driver.current_url

# Find the status code using JavaScript in the browser
response_code = driver.execute_script('return fetch(arguments[0], {method: "HEAD"}).then(response => response.status);', current_url)

# Print response code
print("Http response code:", response_code)

# Quit the driver
driver.quit()
