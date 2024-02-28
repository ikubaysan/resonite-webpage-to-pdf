# How to run the server:

1. cd to the root of this repo
2. Create a venv: `python3 -m venv venv`
3. Activate venv: `source venv/bin/activate`
4. Install requirements: `pip3 install -r requirements.txt`
5. Modify `main.py` `Options` section to your liking
6. Run: `python3 main.py`


# Example Usage


Sample configuration:

```
HOST = "0.0.0.0"
PORT = 2099
DOMAIN = None
```

Request:
`GET http://10.0.0.106:2099/convert?url=http://bing.com`

Response:
`http://10.0.0.106:2099/pdfs/aHR0cDovL2JpbmcuY29t.pdf`