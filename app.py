#!/usr/bin/env python3
from flask import Flask, request, render_template_string, render_template
import base64
import os
import mimetypes
import gzip
import secrets

app = Flask(__name__)
page_template = '''<!doctype html>
<html style=\"height: 100%;\">
    <head>
        <title>Cloud-Init</title>
        <meta http-equiv=\"refresh\" content=\"120\"/><meta http-equiv=\"cache-control\" content=\"no-cache\"/>
    </head>
    <body style=\"min-height: 90%; height: 98%;\">
        {{embed|safe}}
        {{errortext|safe}}
    </body>
</html>
'''
welcome_embed = '''<h1>NoCloud Cloud-Init</h1>
<h3>Usage</h3>
<p>
    <code>http(s)://host/v1/VLAN/DOMAIN/</code>
</p>
<ul>
    <li>Serves the user-data and meta-data endpoints required by Cloud-Init.</li>
</ul>'''

@app.route("/")
def welcome():
    return render_template_string(page_template, embed=welcome_embed)

@app.route("/favicon.ico")
def favicon_path():
    return app.response_class(
        response=base64.b64decode(gzip.decompress(base64.b64decode('H4sIAFDkMmUA/+1WQU+GMAz9QR56kcjFw4NNhMQAR88keDB+R5d8v562RGbmZ7LIJH5x79DspaOPdV03ABVg0VQvPLRoUbf1CDwIrcXgWcyTGPV/4HUbZfx18BYzSjGDWEMyJLePazwbo2/ky916l3mUvp+fEP5/rk1/Pdg/ynfn9XasnzsMcA7iK38M5of+tZST5F97Wq/x332Pu5ifwJ9w/xs9n6r3CUF+vvgPqT9db/t9/Out/6yf9f+V/u/dv9o/494fd4n1NV7U+yPjOBgiKsGGMLBxhu+uCbdys/czFc6c6GZCAZzQj+icebMN87NhPhebn0i4nx/wNR5Xlgv1cL8Ah4KBztQMAAA=')).decode('utf-8')),
        status=200,
        mimetype='image/vnd.microsoft.icon'
    )

@app.route("/robots.txt")
def robots_path():
    return "User-agent: *\nDisallow: /\n"

@app.errorhandler(404)
def errorhandler(e):
    return render_template_string(page_template, embed=welcome_embed, errortext=f"<p><b>Error 404<b></p>"), 404

@app.route("/v1/<string:VLAN>/<string:DOMAIN>/<string:FILE>")
def getMemberPath(VLAN, DOMAIN, FILE):
    return app.response_class(
        response=render_template('v1/' + FILE, VLAN=VLAN, DOMAIN=DOMAIN, PDNS_DB_PASSWORD=secrets.token_urlsafe(32), KEA_DB_PASSWORD=secrets.token_urlsafe(32), POSTGRES_PASSWORD=secrets.token_urlsafe(32), DDNS_KEY=base64.b64encode(secrets.token_bytes(32)).decode('utf-8')),
        status=200,
        mimetype='text/plain'
    )

if __name__ == "__main__":
    from waitress import serve
    import logging
    logger = logging.getLogger('waitress')
    logger.setLevel(logging.INFO) # TODO: add request logging
    serve(app, listen=os.environ.get('CLOUD_INIT_HOST', '*')+":"+os.environ.get('CLOUD_INIT_PORT', '8080'))

