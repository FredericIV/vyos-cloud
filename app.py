#!/usr/bin/env python3
import argparse
import base64
import ipaddress
from jinja2 import Environment, FileSystemLoader, select_autoescape
import os
import secrets
from yaml import safe_load


def filter_hostaddress(value, purpose=None):
    address = ipaddress.ip_interface(value)
    match purpose:
        case "reverse":
            return address.reverse_pointer
        case "mask":
            return address.hostmask
        case "strip" | _:
            return address.ip


def filter_netaddress(value, purpose=None):
    address = ipaddress.ip_interface(value).network
    match purpose:
        case "reverse":
            return address.reverse_pointer
        case "mask":
            return address.netmask
        case "broadcast":
            return address.broadcast_address
        case "cidr":
            return address
        case "cidr-only":
            return address.prefixlen
        case "strip" | _:
            return address.network_address


def gen_secret(purpose="password"):
    match purpose:
        case "tsig":
            return base64.b64encode(secrets.token_bytes(32)).decode("utf-8")
        case "password" | _:
            return secrets.token_urlsafe(32)


def update_secret(api: str, store: dict):
    match api:
        case "v1":
            for password in [
                "POSTGRES_PASSWORD",
                "KEA_DB_PASSWORD",
                "PDNS_DB_PASSWORD",
            ]:
                if store.get(password) is None:
                    store[password] = gen_secret()
            if store.get("DDNS_KEY") is None:
                store["DDNS_KEY"] = gen_secret("tsig")

        case "v2-devel" | "v2":
            if store.get("databases") is None:
                store["databases"] = dict()
            for password in [
                "dhcp_db_password",
                "dns_db_password",
                "admin_db_password",
            ]:
                if store["databases"].get(password) is None:
                    store["databases"][password] = gen_secret()
            if store["dns"].get("ddns_tsig_key") is None:
                store["dns"]["ddns_tsig_key"] = gen_secret("tsig")
    return store


def client(args):
    env = Environment(
        loader=FileSystemLoader("templates"),
        autoescape=select_autoescape(),
    )
    env.filters["hostaddress"] = filter_hostaddress
    env.filters["netaddress"] = filter_netaddress
    with open(args.input) as file:
        env.globals = safe_load(file)

    env.globals = update_secret(args.api, env.globals)
    env.globals["api"] = args.api

    print(env.get_template(os.path.join(args.api, args.filename)).render())
    os._exit(0)


def server(args):
    from flask import Flask, request, render_template_string, render_template
    from waitress import serve
    import logging

    app = Flask(__name__)
    app.logger
    app.add_template_filter(filter_hostaddress, "hostaddress")
    app.add_template_filter(filter_netaddress, "netaddress")
    page_template = """<!doctype html>
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
    """
    welcome_embed = """<h1>NoCloud Cloud-Init</h1>
    <h3>Usage</h3>
    <p>
        <code>http(s)://host/v1/VLAN/DOMAIN/[filename]</code>
    </p>
    <ul>
        <li>Serves the user-data and meta-data endpoints required by Cloud-Init.</li>
    </ul>"""

    @app.route("/")
    def welcome():
        return render_template_string(page_template, embed=welcome_embed)

    @app.route("/favicon.ico")
    def favicon_path():
        return app.response_class(status=404)

    @app.route("/robots.txt")
    def robots_path():
        return "User-agent: *\nDisallow: /\n"

    @app.errorhandler(404)
    def errorhandler(e):
        return (
            render_template_string(
                page_template, embed=welcome_embed, errortext="<p><b>Error 404<b></p>"
            ),
            404,
        )

    @app.route("/v1/<string:VLAN>/<string:DOMAIN>/<string:FILE>")
    def v1Path(VLAN, DOMAIN, FILE):
        return app.response_class(
            response=render_template(
                os.path.join("v1", FILE),
                api="v1",
                VLAN=VLAN,
                DOMAIN=DOMAIN,
                PDNS_DB_PASSWORD=gen_secret(),
                KEA_DB_PASSWORD=gen_secret(),
                POSTGRES_PASSWORD=gen_secret(),
                DDNS_KEY=gen_secret("tsig"),
            ),
            status=200,
            mimetype="text/plain",
        )

    @app.route("/v2-devel/<string:CONF>/<string:FILE>")
    def v2Path(CONF, FILE):
        with open(CONF if CONF[-5:] == ".yaml" else CONF + ".yaml") as file:
            env = safe_load(file)
        env = update_secret("v2-devel", env)
        env["api"] = "v2-devel"
        return app.response_class(
            response=render_template(os.path.join("v2-devel", FILE), **env),
            status=200,
            mimetype="text/plain",
        )

    logger = logging.getLogger("waitress")
    logger.setLevel(logging.INFO)  # TODO: add request logging
    serve(
        app,
        listen=os.environ.get("CLOUD_INIT_HOST", "*")
        + ":"
        + os.environ.get("CLOUD_INIT_PORT", "8080"),
    )


def main():
    parser = argparse.ArgumentParser(description="vyos config generator")
    subparsers = parser.add_subparsers(
        required=True,
        title="subcommands",
        description="valid subcommands",
        help="run as one-off generator or web-server",
    )

    parser_server = subparsers.add_parser(
        "server", description="Run app.py as a server. Takes no arguments."
    )
    parser_server.set_defaults(func=server)

    parser_client = subparsers.add_parser("client")
    parser_client.set_defaults(func=client)
    parser_client.add_argument(
        "input", metavar="inputYaml", action="store", help="YAML file to read vars from"
    )
    parser_client.add_argument(
        "filename",
        metavar="templateFile",
        action="store",
        help="name of file to render from template dir",
    )
    parser_client.add_argument(
        "-a",
        "--api",
        action="store",
        default="v1",
        help="version of template to use; defaults to v1",
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
