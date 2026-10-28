#!/bin/sh
set -e

reader_password=$(cat /run/clickhouse-reader/password)

clickhouse-client --user grafana_reader --password "$reader_password" \
    --query "SELECT device_id, metric, count() AS points, min(sent_at) AS first_point, max(sent_at) AS last_point FROM default.metrics WHERE product = 'grafana_iframe_demo' GROUP BY device_id, metric ORDER BY device_id, metric"
