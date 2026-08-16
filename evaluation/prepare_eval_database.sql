-- Idempotent setup for the isolated InfoBank evaluation database.
--
-- Run with a local MariaDB administrator account before applying the schema.
-- This script does not touch the development database named infobank_db.

CREATE DATABASE IF NOT EXISTS infobank_eval
CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

GRANT ALL PRIVILEGES ON infobank_eval.* TO 'infobank'@'%';
FLUSH PRIVILEGES;
