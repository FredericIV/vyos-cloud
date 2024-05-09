# Vyos-Cloud
## Description
Provide [Cloud-Init](https://cloudinit.readthedocs.io/en/latest/) [NoCloud](https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html) user-data, meta-data, and vendor-data endpoints with configurable content in support of ephemeral [Vyos](https://vyos.io/) routing nodes.

## Dependencies
- Python3
- Flask
- Waitress

## Usage
### Commandline
To execute, run:
```bash
$ python3 ./app.py server
```

To view, access the following in your browser, where VLAN and DOMAIN are as required and FILE is one of the files in the template directory:
```
http://localhost:8080/v1/VLAN/DOMAIN/FILE
```
### Docker
```bash
$ docker run --rm -p 8080:8080 $(docker build --quiet .)
```
