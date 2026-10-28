INSERT INTO default.metrics
SELECT
    metric,
    device_id AS serial_number,
    'Demo sensor' AS model,
    'grafana_iframe_demo' AS product,
    toString(metric_value) AS value_str,
    metric_value AS value_num,
    now() - toIntervalMinute((47 - tick) * 30) AS sent_at,
    device_id
FROM
(
    SELECT
        tick,
        device_id,
        metric,
        round(
            if(
                metric = 'temperature',
                18 + indexOf(['0030014467', '10', '1140000464', '1050'], device_id) * 2
                    + sin(tick / 5),
                45 + indexOf(['0030014467', '10', '1140000464', '1050'], device_id) * 3
                    + cos(tick / 6)
            ),
            2
        ) AS metric_value
    FROM (SELECT number AS tick FROM numbers(48)) AS time_points
    CROSS JOIN
    (
        SELECT arrayJoin(['0030014467', '10', '1140000464', '1050']) AS device_id
    ) AS devices
    CROSS JOIN
    (
        SELECT arrayJoin(['temperature', 'humidity']) AS metric
    ) AS metrics
) AS samples
WHERE (SELECT count() FROM default.metrics WHERE product = 'grafana_iframe_demo') = 0;
