#!/usr/bin/env python3
import argparse
import base64
import ipaddress
import jinja2
import os
import secrets
import yaml
import json
import jsonschema
import copy


def filter_hostaddress(value, purpose=None):
    address = ipaddress.ip_interface(value)
    match purpose:
        case "reverse":
            return address.ip.reverse_pointer
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
    local_store = copy.deepcopy(store)
    match api:
        case "v1":
            for password in [
                "POSTGRES_PASSWORD",
                "KEA_DB_PASSWORD",
                "PDNS_DB_PASSWORD",
            ]:
                if local_store.get(password) is None:
                    local_store[password] = gen_secret()
            if local_store.get("DDNS_KEY") is None:
                local_store["DDNS_KEY"] = gen_secret("tsig")

        case "v2-devel" | "v2":
            if local_store.get("databases") is None:
                local_store["databases"] = dict()
            for password in [
                "dhcp_db_password",
                "dns_db_password",
                "admin_db_password",
            ]:
                if local_store["databases"].get(password) is None:
                    local_store["databases"][password] = gen_secret()
            if local_store["dns"].get("tsig_key") is None:
                local_store["dns"]["tsig_key"] = gen_secret("tsig")
    return local_store


def interface_flatten(conf: dict) -> dict:
    retval = copy.deepcopy(conf)
    retval["flat_int"] = []
    for interface in conf["interfaces"]:
        int_dict = copy.deepcopy(interface)
        int_dict["_intID"] = "eth" + str(int_dict["id"])
        retval["flat_int"].append(int_dict)
        if interface.get("subinterfaces") is not None:
            for subinterface in interface["subinterfaces"]:
                subint_dict = copy.deepcopy(subinterface)
                subint_dict["_intID"] = (
                    "eth" + str(interface["id"]) + "." + str(subinterface["id"])
                )
                retval["flat_int"].append(copy.deepcopy(subint_dict))
    return retval


def load_conf(name: str) -> dict:
    if name[-5:] == ".json":
        with open(name) as file:
            env = json.load(file)
    else:
        with open(name if name[-5:] == ".yaml" else name + ".yaml") as file:
            env = yaml.safe_load(file)
    return env


# Validate config, returning str only f/ errors.
def validate_conf(conf: dict, api: str) -> str | None:
    if api in ["v3-devel"]:
        raise NotImplementedError("v3-devel is not implemented")
    elif api not in ["v1", "v2-devel", "v3-devel"]:
        raise ValueError("Invalid api")
    with open("vyos-cloud." + api + ".schema.json") as file:
        contents = json.load(file)
        # Use $schema as validator, otherwise 2020-12. Validate config, return the errors.
        errors = jsonschema.validators.validator_for(contents)(
            schema=contents
        ).iter_errors(instance=conf)
        del contents
    errortext = ""
    for error in errors:
        path = ""
        for i in error.schema_path:
            if i not in ["properties", "items", "type"]:
                path += i + " > "
        errortext += error.message + "\tPath: " + path + "\n"
    return errortext if errortext != "" else None


def get_conf(name: str, api: str) -> tuple[str, str]:
    # Load
    try:
        env = load_conf(name)
    except FileNotFoundError as e:
        return (None, "Config not found!")
    except Exception as e:
        return (None, "Error getting config!\n\n" + str(e))
    # Validate
    try:
        errors = validate_conf(env, api)
    except NotImplementedError:
        errors = None
    except Exception as e:
        errors = "Error validating config!\n\n" + str(e)
    if errors != None:
        return (None, errors)
    # Hydrate
    match api:
        case "v1":
            env = update_secret(api, env)
            env["api"] = api
            assert validate_conf(env, api) == None
        case "v2-devel" | "v2":
            env = update_secret(api, env)
            env["api"] = api
            env.setdefault("hostname", "rtr" + str(env["router_id"]))
            assert validate_conf(env, api) == None
            env = interface_flatten(env)
        case "*" | _:
            return (None, "Invalid api")
    return (env, None)


def client(args):
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader("templates"),
        autoescape=jinja2.select_autoescape(),
    )
    env.filters["hostaddress"] = filter_hostaddress
    env.filters["netaddress"] = filter_netaddress
    env.globals, error = get_conf(args.input, args.api)
    if error != None:
        print(error)
        exit(1)
    print(env.get_template(os.path.join(args.api, args.filename)).render())
    exit(0)


def server(args):
    from flask import Flask, render_template_string, render_template
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
        api = "v2-devel"
        env, errors = get_conf(CONF, api)
        if errors != None:
            return app.response_class(
                response="Error 400\n\n" + errors,
                status=400,
                mimetype="text/plain",
            )
        try:
            return app.response_class(
                response=render_template(os.path.join(api, FILE), **env),
                status=200,
                mimetype="text/plain",
            )
        except jinja2.TemplateNotFound as e:
            return app.response_class(
                response="Error 404\n\nTemplate not found!\nTemplate:" + str(e),
                status=404,
                mimetype="text/plain",
            )
        except Exception as e:
            return app.response_class(
                response="Error!\n\n" + str(e),
                status=400,
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
        "input",
        metavar="configFile",
        action="store",
        help="configuration file to read vars from",
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
