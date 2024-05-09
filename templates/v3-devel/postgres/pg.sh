#!/bin/sh
psql -U postgres -W $PGPOOL_POSTGRES_PASSWORD < db-creqate.sql
psql -U postgres -W $PGPOOL_POSTGRES_PASSWORD kea < kea-schema.sql
psql -U postgres -W $PGPOOL_POSTGRES_PASSWORD pdns < pdns-schema.sql
psql -U postgres -W $PGPOOL_POSTGRES_PASSWORD pdns < pdns-init.sql