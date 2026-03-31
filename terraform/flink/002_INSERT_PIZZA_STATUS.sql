-- Insert data into PIZZA_STATUS table in Flink
-- This statement populates the PIZZA_STATUS table with data from all pizza processing stages
EXECUTE STATEMENT SET
BEGIN
   INSERT INTO `PIZZA_STATUS` (`key`, `status`, `timestamp`) SELECT `key`, `status`, `timestamp` FROM `pizza-ordered`;
   INSERT INTO `PIZZA_STATUS` (`key`, `status`, `timestamp`) SELECT `key`, `status`, `timestamp` FROM `pizza-pending`;
   INSERT INTO `PIZZA_STATUS` (`key`, `status`, `timestamp`) SELECT `key`, `status`, `timestamp` FROM `pizza-assembled`;
   INSERT INTO `PIZZA_STATUS` (`key`, `status`, `timestamp`) SELECT `key`, `status`, `timestamp` FROM `pizza-baked`;
   INSERT INTO `PIZZA_STATUS` (`key`, `status`, `timestamp`) SELECT `key`, `status`, `timestamp` FROM `pizza-delivered`;
END;
