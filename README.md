# Vyos-Cloud
<a href="https://concourse.k8s.fabiv.pw/teams/main/pipelines/fborries.vyos-cloud/jobs/build-push-container/builds/latest"><img src="https://concourse.k8s.fabiv.pw/api/v1/teams/main/pipelines/fborries.vyos-cloud/badge" alt="Concourse Pipeline Status"></a>

## Description
Provide [Cloud-Init](https://cloudinit.readthedocs.io/en/latest/) [NoCloud](https://cloudinit.readthedocs.io/en/latest/reference/datasources/nocloud.html) user-data, meta-data, and vendor-data endpoints with configurable content in support of ephemeral [Vyos](https://vyos.io/) routing nodes.

## Dependencies
- Python3
- Flask
- Waitress
- jsonschema

## Usage
### Commandline
```bash
$ python3 ./app.py client [-h] [-a API] [-t {zip}] configFile templateFile`
```
or
```bash
$ docker run --rm PATH_TO_LOCAL_CONFIGS:/usr/src/app/configs $(docker build --quiet .) client [-h] [-a API] [-t {zip}] configFile templateFile
```

positional arguments:
  configFile            configuration file to read vars from
  templateFile          name of file to render from template dir

options:
  -h, --help            show this help message and exit
  -a API, --api API     version of template to use; defaults to v1
  -t {zip}, --archive {zip}
                        render all templates to an archive type specified here
                        and the archive name specified by filename


### Server 
```bash
$ docker run --rm -p 8080:8080 $(docker build --quiet .)
```

#### api v1

`http(s)://HOST/v1/VLAN/DOMAIN/FILEPATH` `http(s)://HOST/v1/VLAN/DOMAIN/FILENAME?archive=zip`

*   Serves the user-data and meta-data endpoints required by Cloud-Init.
*   Replace VLAN with the VLAN number.
*   Replace DOMAIN with the domain name.
*   Replace filepath/filename with the desired file path/name.
*   Use the archive query parameter to download all files in an archive. Only zip is supported at the moment.

Example: [/v1/100/example.com/user-data](/v1/100/example.com/user-data)

#### api v2-devel

`http(s)://HOST/v2-devel/CONF/FILEPATH` `http(s)://HOST/v2-devel/CONF/FILENAME?archive={zip}`

*   Serves the user-data and meta-data endpoints required by Cloud-Init.
*   Replace CONF with the configuration file name.
*   Replace filepath/filename with the desired file path/name.
*   Use the archive query parameter to download all files in an archive. Only zip is supported at the moment.

Example: [/v2-devel/example-v2/kea/kea-dhcp4.conf](/v2-devel/example-v2/kea/kea-dhcp4.json)