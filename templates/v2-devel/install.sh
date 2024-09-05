{% import api ~ '/macros.j2' as macros -%}
#!/bin/bash -x
if [ "$EUID" -ne 0 ]
  then echo "Please run as root"
  exit
fi

mkdir -p /opt/vyatta/etc/config/{scripts,containers/{{'{{'}}postgres,kea-dhcp4,kea-dhcp-ddns,kea-ctrl-agent}/config,pdns-auth,pdns-recursor{{'}}'}}
chown -R root:vyattacfg /opt/vyatta/etc/config
chmod -R 0775 /opt/vyatta/etc/config/scripts

cat << EOF > /opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script
#!/bin/vbash
source /opt/vyatta/etc/functions/script-template
{%- for image in [
  'docker.io/postgres:'~(databases.version if databases is defined and databases.version is defined else macros.POSTGRES_VER)~'-alpine',
  'docker.io/jonasal/kea-dhcp4-ha:2-alpine',
  'docker.io/jonasal/kea-dhcp-ddns:2-alpine',
  'docker.io/jonasal/kea-ctrl-agent:2-alpine',
  'docker.io/powerdns/pdns-auth-'~macros.PDNS_AUTH_VER~':latest',
  'docker.io/powerdns/pdns-recursor-'~macros.PDNS_RECURSOR_VER~':latest'] %}
run add container image '{{image}}'
{%- endfor %}{% for container in ["postgres","pdns-auth","pdns-recursor","kea-dhcp4", "kea-dhcp-ddns", "kea-ctrl-agent"] %}
run restart container {{container}}
{%- endfor %}
EOF
chown root:vyattacfg /opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script
chmod 0755 /opt/vyatta/etc/config/scripts/vyos-postconfig-bootup.script


cat << EOF > /opt/vyatta/etc/config/containers/pdns-auth/pdns.conf
{% call macros.edit("") %}
{% include api ~ '/pdns-auth-conf' %}
{% endcall -%}
EOF
chown root:root /opt/vyatta/etc/config/containers/pdns-auth/pdns.conf
chmod 0664 /opt/vyatta/etc/config/containers/pdns-auth/pdns.conf


cat << EOF > /opt/vyatta/etc/config/containers/pdns-recursor/recursor.yml
{% call macros.edit("") %}
{% include api ~ '/pdns-recursor-conf' %}
{% endcall -%}
EOF
chown root:root /opt/vyatta/etc/config/containers/pdns-recursor/recursor.yml
chmod 0664 /opt/vyatta/etc/config/containers/pdns-recursor/recursor.yml


{% for file in ["kea-dhcp4", "kea-dhcp-ddns", "kea-ctrl-agent"] %}
cat << EOF > /opt/vyatta/etc/config/containers/{{file}}/config/{{file}}.json
{% call macros.edit("") %}
{% include api ~ '/kea/' ~ file ~ '.json' %}
{% endcall -%}
EOF
chown root:root /opt/vyatta/etc/config/containers/{{file}}/config/{{file}}.json
chmod 0664 /opt/vyatta/etc/config/containers/{{file}}/config/{{file}}.json
{% endfor %}

{% for file in ["db-create.psql", "kea-schema.psql", "pdns-init.psql", "pdns-schema.psql"] %}
cat << EOF > /opt/vyatta/etc/config/containers/postgres/config/{{file}}
{% call macros.edit("") %}
{% include api ~ '/postgres/' ~ file %}
{% endcall -%}
EOF
chown root:root /opt/vyatta/etc/config/containers/postgres/config/{{file}}
chmod 0664 /opt/vyatta/etc/config/containers/postgres/config/{{file}}
{% endfor %}

cat << EOF > /opt/vyatta/etc/config/containers/postgres/config/pg.sh
{% call macros.edit("") %}
{% include api ~ '/postgres/pg.sh' %}
{% endcall -%}
EOF
chown root:root /opt/vyatta/etc/config/containers/postgres/config/pg.sh
chmod 0775 /opt/vyatta/etc/config/containers/postgres/config/pg.sh

/bin/vbash << EOF
source /opt/vyatta/etc/functions/script-template
{% call macros.edit("") %}
{% include api ~ '/vyos-conf' %}
{% endcall -%}
exit
EOF