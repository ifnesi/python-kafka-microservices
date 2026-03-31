-- Create PIZZA_STATUS table in Flink
-- This table consolidates status updates from all pizza processing stages
CREATE TABLE IF NOT EXISTS PIZZA_STATUS (
  `key` BYTES,
  `status` INT,
  `timestamp` BIGINT
)
DISTRIBUTED BY HASH(`key`) INTO 6 BUCKETS
WITH (
  'key.format'   = 'raw',
  'value.format' = 'avro-registry'
);
