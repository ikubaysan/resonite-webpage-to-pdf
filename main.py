import pdfkit
import requests


def url_to_pdf(url, output_filename):
    try:
        # Fetch the content of the URL
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError if the HTTP request returned an unsuccessful status code

        # Use pdfkit to convert HTML to PDF
        pdfkit.from_string(response.text, output_filename)

        print(f"PDF successfully created: {output_filename}")
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


# Example usage
url = "http://google.com"
output_filename = "output.pdf"
url_to_pdf(url, output_filename)
