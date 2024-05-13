CREATE ROLE repl_user WITH REPLICATION LOGIN PASSWORD 'kali';
SELECT pg_create_physical_replication_slot('replication_slot');

-- Создаем таблицу для хранения email-адресов
CREATE TABLE email_addresses (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL
);

-- Создаем таблицу для хранения телефонных номеров
CREATE TABLE phone_numbers (
    id SERIAL PRIMARY KEY,
    phone_number VARCHAR(255) UNIQUE NOT NULL
);
