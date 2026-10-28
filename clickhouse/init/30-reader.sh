#!/bin/sh
set -e

reader_hash=$(sha256sum /run/clickhouse-reader/password | cut -d ' ' -f1)
admin_password=$(cat /run/clickhouse-admin/password)

clickhouse-client --user demo_admin --password "$admin_password" --multiquery <<SQL
CREATE USER IF NOT EXISTS grafana_reader
    IDENTIFIED WITH sha256_hash BY '$reader_hash';
ALTER USER grafana_reader
    IDENTIFIED WITH sha256_hash BY '$reader_hash';
GRANT SELECT ON default.metrics TO grafana_reader;
GRANT SHOW TABLES ON default.metrics TO grafana_reader;
GRANT SHOW DATABASES ON default.* TO grafana_reader;
SQL
