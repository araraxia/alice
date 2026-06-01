-- Migration: 001_blog_schema
-- Description: Create blog schema and post table in the accounts database
-- Database: accounts

BEGIN;

CREATE SCHEMA IF NOT EXISTS blog;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type
        WHERE typname = 'blog_post_status'
        AND typnamespace = (SELECT oid FROM pg_namespace WHERE nspname = 'blog')
    ) THEN
        CREATE TYPE blog.blog_post_status AS ENUM ('draft', 'published', 'deleted');
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS blog.post (
    id                    UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    author_uuid           UUID         NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title                 VARCHAR(255) NOT NULL,
    body                  TEXT         NOT NULL DEFAULT '',
    status                blog.blog_post_status NOT NULL DEFAULT 'draft',
    post_datetime         TIMESTAMPTZ,
    last_updated_datetime TIMESTAMPTZ,
    created_datetime      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_blog_post_status
    ON blog.post (status);

CREATE INDEX IF NOT EXISTS idx_blog_post_author
    ON blog.post (author_uuid);

CREATE INDEX IF NOT EXISTS idx_blog_post_datetime
    ON blog.post (post_datetime DESC NULLS LAST)
    WHERE status = 'published';

COMMIT;
