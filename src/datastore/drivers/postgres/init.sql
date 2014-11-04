-- Add extensions on the template database
CREATE EXTENSION "hstore";
CREATE EXTENSION "ltree";
CREATE EXTENSION "uuid-ossp";

-- Create database and user
CREATE DATABASE freenas;
CREATE USER freenas;
GRANT ALL ON DATABASE freenas TO freenas;

-- Create initial metadata collection
\c freenas freenas
CREATE TABLE __collections (
  id character varying,
  data json
);