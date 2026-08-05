-- Migration: 002_herblore_schema
-- Description: Create herblore schema and action_step table in the osrs database
-- Database: osrs

BEGIN;

CREATE SCHEMA IF NOT EXISTS herblore;

CREATE TABLE IF NOT EXISTS herblore.action_step (
    step_id                VARCHAR(64)  PRIMARY KEY,
    potion_family           TEXT[]       NOT NULL,
    step_label              VARCHAR(128) NOT NULL,
    input_1_item             VARCHAR(128) NOT NULL,
    input_1_qty              INTEGER      NOT NULL DEFAULT 1,
    input_2                  JSONB        NOT NULL DEFAULT '[]'::jsonb,
    output                   VARCHAR(128) NOT NULL,
    output_extra_dose        VARCHAR(128),
    output_doses             SMALLINT,
    xp                       NUMERIC(6,2) NOT NULL DEFAULT 0,
    level_req                SMALLINT     NOT NULL,
    zahur_clean              BOOLEAN      NOT NULL DEFAULT FALSE,
    zahur_unf                BOOLEAN      NOT NULL DEFAULT FALSE,
    wesley                   BOOLEAN      NOT NULL DEFAULT FALSE,
    dose_amulet              BOOLEAN      NOT NULL DEFAULT FALSE,
    goggles                   BOOLEAN      NOT NULL DEFAULT FALSE,
    created_datetime          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_datetime          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_herblore_action_step_family
    ON herblore.action_step USING GIN (potion_family);

COMMIT;
