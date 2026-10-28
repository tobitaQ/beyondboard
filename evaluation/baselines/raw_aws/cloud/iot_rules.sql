-- App 1: one rule with an S3 action (key: temp/${timestamp()}.json). Each message becomes one object.
SELECT * FROM 'esp32/temp'
-- App 2
SELECT * FROM 'esp32/config/get'
-- App 3
SELECT * FROM 'esp32/anomaly/request'
-- App 4
SELECT * FROM 'esp32/ask/request'
-- App 5
SELECT * FROM 'esp32/classify/request'
