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
import zipfile
import io
from typing import Callable
from sys import stderr

conf_dir=os.path.abspath("configs")
template_dir=os.path.abspath("templates")

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
        with open(os.path.join(conf_dir, name)) as file:
            env = json.load(file)
    else:
        with open(os.path.join(conf_dir, name if name[-5:] == ".yaml" else name + ".yaml")) as file:
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

def ret_zip(render:Callable[[os.PathLike],str], api:str) -> io.BytesIO:
    ret_buffer = io.BytesIO()
    with zipfile.ZipFile(ret_buffer, "w") as myzip:
        os.chdir(template_dir)
        for root, dirs, files in os.walk(api):
            for dir in dirs:
                myzip.mkdir(os.path.join(root, dir))
            for file in files:
                myzip.writestr(
                    os.path.join(root, file),
                    render(os.path.join(root, file)),
                )
    os.chdir("..")
    return ret_buffer

def ret_archive(render:Callable[[os.PathLike],str], api:str, type:str) -> io.BytesIO:
    if type == "zip":
        return ret_zip(render, api)
    else:
        print("Invalid archive type", file=stderr)
        return None

def client(args:argparse.Namespace) -> None:
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir),
        autoescape=jinja2.select_autoescape(),
    )
    env.filters["hostaddress"] = filter_hostaddress
    env.filters["netaddress"] = filter_netaddress
    env.globals, error = get_conf(args.input, args.api)
    if error != None:
        print(error,file=stderr)
        exit(1)
    if args.archive == "":
        print(env.get_template(os.path.join(args.api, args.filename)).render())
        exit(0)
    if val := ret_archive(lambda x: env.get_template(x).render(), args.api, args.archive):
        with open(args.filename, "wb") as f:
            f.write(val.getvalue())
    else:
        print("Error making archive", file=stderr)
        exit(1)

def server(env:argparse.Namespace) -> None:
    from flask import Flask, render_template_string, render_template, request
    from waitress import serve
    import logging

    app = Flask(__name__)
    app.logger
    app.add_template_filter(filter_hostaddress, "hostaddress")
    app.add_template_filter(filter_netaddress, "netaddress")
    app.template_folder = template_dir
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
    <h4>api v1</h4>
    <p>
        <code>http(s)://HOST/v1/VLAN/DOMAIN/FILEPATH</code>
        <code>http(s)://HOST/v1/VLAN/DOMAIN/FILENAME?archive=zip</code>
    </p>
    <ul>
        <li>Serves the user-data and meta-data endpoints required by Cloud-Init.</li>
        <li>Replace VLAN with the VLAN number.</li>
        <li>Replace DOMAIN with the domain name.</li>
        <li>Replace filepath/filename with the desired file path/name.</li>
        <li>Use the archive query parameter to download all files in an archive. Only zip is supported at the moment.</li>
    </ul>
    <h4>api v2-devel</h4>
    <p>
        <code>http(s)://HOST/v2-devel/CONF/FILEPATH</code>
        <code>http(s)://HOST/v2-devel/CONF/FILENAME?archive={zip}</code>
    </p>
    <ul>
        <li>Serves the user-data and meta-data endpoints required by Cloud-Init.</li>
        <li>Replace CONF with the configuration file name.</li>
        <li>Replace filepath/filename with the desired file path/name.</li>
        <li>Use the archive query parameter to download all files in an archive. Only zip is supported at the moment.</li>
    </ul>
    <p>Example 1: <a href="/v1/100/example.com/user-data">/v1/100/example.com/user-data</a></p>
    <p>Example 2: <a href="/v2-devel/example-v2/kea/kea-dhcp4.json">/v2-devel/example-v2/kea/kea-dhcp4.conf</a></p>
    """

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

    @app.route("/v1/<string:VLAN>/<string:DOMAIN>/<path:FILE>")
    def v1Path(VLAN, DOMAIN, FILE):
        if request.args.get("archive", default="") != "":
            return app.response_class(
                response=ret_archive(
                    lambda x: render_template(
                        x,
                        api="v1",
                        VLAN=VLAN,
                        DOMAIN=DOMAIN,
                        PDNS_DB_PASSWORD=gen_secret(),
                        KEA_DB_PASSWORD=gen_secret(),
                        POSTGRES_PASSWORD=gen_secret(),
                        DDNS_KEY=gen_secret("tsig"),
                    ),
                    "v1",
                    request.args.get("archive")
                ).getvalue(),
                status=200,
                mimetype="application/octet-stream"
            )
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

    @app.route("/v2-devel/<string:CONF>/<path:FILE>")
    def v2Path(CONF, FILE):
        api = "v2-devel"
        env, errors = get_conf(CONF, api)
        if errors != None:
            return app.response_class(
                response="Error 400\n\n" + errors,
                status=400,
                mimetype="text/plain",
            )
        if request.args.get("archive", default="") != "":
            return app.response_class(
                response=ret_archive(lambda x: render_template(x, **env), api, request.args.get("archive")).getvalue(),
                status=200,
                mimetype="application/octet-stream"
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
    parser_client.add_argument(
        "-t",
        "--archive",
        action="store",
        default="",
        help="render all templates to an archive type specified here and the archive name specified by filename",
        choices=["zip"],
    )

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
