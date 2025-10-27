-- Initial database bootstrap script for SOCIALIZER
-- Run manually or through docker-entrypoint init scripts

DO
$$
BEGIN
    IF NOT EXISTS (
        SELECT FROM pg_roles WHERE rolname = 'ltsr_user'
    ) THEN
        EXECUTE 'CREATE ROLE ltsr_user WITH LOGIN PASSWORD ''ltsr_password''';
    END IF;
END
$$;

SELECT 'CREATE DATABASE ltsr_db OWNER ltsr_user TEMPLATE template0 ENCODING ''UTF8'''
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'ltsr_db'
)\gexec

SELECT 'CREATE DATABASE ltsr_test OWNER ltsr_user TEMPLATE template0 ENCODING ''UTF8'''
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'ltsr_test'
)\gexec

SELECT 'GRANT ALL PRIVILEGES ON DATABASE ltsr_db TO ltsr_user'
WHERE EXISTS (
    SELECT FROM pg_database WHERE datname = 'ltsr_db'
)\gexec

SELECT 'GRANT ALL PRIVILEGES ON DATABASE ltsr_test TO ltsr_user'
WHERE EXISTS (
    SELECT FROM pg_database WHERE datname = 'ltsr_test'
)\gexec

ALTER SYSTEM SET max_connections = 200;
ALTER SYSTEM SET shared_buffers = '256MB';

SELECT pg_reload_conf();
