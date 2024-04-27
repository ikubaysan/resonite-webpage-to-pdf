REST API and file server for converting webpages to PDFs or images, for consumption in Resonite.

This must be hosted on a machine exposed on the internet so other Resonite users can access the file server.

This documentation is written for Linux, but Windows should work as well.

# Running the server:

1. `cd` to the root of this repo
2. Create a venv: `python3 -m venv venv`
3. Activate venv: `source venv/bin/activate`
4. Install requirements: `pip3 install -r requirements.txt`
5. Make a copy of 'config_sample.ini' and rename it to 'config.ini'
6. Modify `config.ini` to your liking
7. Modify `main.py` `Options` section to your liking
8. Run: `python3 main.py`


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

# Optional: Running as a service
1. Open `resonite_webpage_to_pdf.service` in a text editor and modify these fields as needed:
    * ExecStart
    * WorkingDirectory
    * User
2. Copy `resonite_webpage_to_pdf.service` to `/etc/systemd/system/` with command: `sudo cp resonite_webpage_to_pdf.service /etc/systemd/system/`
3. Run `sudo systemctl daemon-reload` to reload the service files
4. Run `sudo systemctl start resonite_webpage_to_pdf` to start the service
5. (Optional) Run `sudo systemctl enable resonite_webpage_to_pdf` to enable the service on boot

To disable the service on boot:
`sudo systemctl disable resonite_webpage_to_pdf`

To stop the service:
`sudo systemctl stop resonite_webpage_to_pdf`

To check the status of the service:
`sudo systemctl status resonite_webpage_to_pdf`

To delete the service:
`sudo rm /etc/systemd/system/resonite_webpage_to_pdf.service`
`sudo systemctl daemon-reload`

# Notes
If you need to update chromium, and you installed it with snap:
`sudo snap refresh chromium`
