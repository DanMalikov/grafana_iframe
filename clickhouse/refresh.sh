#!/bin/sh
set -e

admin_password=$(cat /run/clickhouse-admin/password)

clickhouse-client --user demo_admin --password "$admin_password" \
    --query "ALTER TABLE default.metrics DELETE WHERE product = 'grafana_iframe_demo' SETTINGS mutations_sync = 1"
clickhouse-client --user demo_admin --password "$admin_password" \
    < /docker-entrypoint-initdb.d/20-seed.sql
