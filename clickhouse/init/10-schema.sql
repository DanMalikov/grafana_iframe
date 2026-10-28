CREATE TABLE IF NOT EXISTS default.metrics
(
    metric LowCardinality(String),
    serial_number String,
    model String,
    product String,
    value_str String,
    value_num Nullable(Float64),
    sent_at DateTime,
    device_id String
)
ENGINE = MergeTree
ORDER BY (device_id, metric, sent_at);
