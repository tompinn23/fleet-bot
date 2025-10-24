-- initial schema
-- depends:

-- migrate: apply
CREATE TABLE link_codes(
    code TEXT PRIMARY KEY,
    expires TIMESTAMPTZ,
    redeemed BOOL,
    uid BIGINT,
    guild_id BIGINT
);

ALTER TABLE link_codes ENABLE ROW LEVEL SECURITY;
CREATE POLICY guild_rls_link
ON link_codes
FOR SELECT
USING (
    current_setting('app.guild_id', true) IS NOT NULL AND
    guild_id = current_setting('app.guild_id', true)::bigint
);

CREATE TABLE tokens(
    token TEXT,
    expires TIMESTAMPTZ,
    refresh TEXT,
    refresh_expires TIMESTAMPTZ,
    uid BIGINT
);

CREATE TABLE carriers(
    callsign TEXT NOT NULL,
    uid BIGINT NOT NULL,
    name TEXT,
    location TEXT,
    fuel INT,
    crew_cargo INT,
    cargo INT,
    balance BIGINT,
    created TIMESTAMPTZ DEFAULT now() NOT NULL,
    last_updated TIMESTAMPTZ DEFAULT TO_TIMESTAMP(0) NOT NULL,
    guild_id BIGINT NOT NULL,
    PRIMARY KEY (callsign, guild_id)
);

CREATE INDEX idx_callsign_carriers ON carriers(callsign);

ALTER TABLE carriers ENABLE ROW LEVEL SECURITY;
CREATE POLICY guild_rls_carriers ON carriers
FOR SELECT USING (
    current_setting('app.guild_id', true) IS NOT NULL AND
    guild_id = current_setting('app.guild_id', true)::bigint
);

CREATE TABLE jump_log(
    id SERIAL PRIMARY KEY,
    callsign TEXT NOT NULL,
    start TEXT NOT NULL,
    destination TEXT NOT NULL,
    destination_body TEXT,
    departure TIMESTAMPTZ NOT NULL,
    fuel INT,
    status TEXT NOT NULL CHECK (status IN ('requested', 'cancelled', 'completed'))
    UNIQUE (callsign, departure)
);

CREATE OR REPLACE FUNCTION check_jump_log_callsign()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM carriers WHERE callsign = NEW.callsign
    ) THEN
        RAISE EXCEPTION 'callsign % does not exist in carriers', NEW.callsign;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER jump_log_callsign_check
BEFORE INSERT OR UPDATE ON jump_log
FOR EACH ROW
EXECUTE FUNCTION check_jump_log_callsign();

CREATE TABLE users(
    id SERIAL PRIMARY KEY,
    uid BIGINT NOT NULL UNIQUE,
    username TEXT,
    discriminator TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE refresh_tokens(
    token TEXT PRIMARY KEY,
    revoked BOOL,
    reason TEXT
);

CREATE TABLE device_sessions(
    device_code TEXT PRIMARY KEY,
    expires_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    user_id INT REFERENCES users(id) ON DELETE SET NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'linked', 'completed', 'denied'))
);    


-- migrate: rollback
DROP TABLE refresh_tokens;
DROP TABLE device_sessions;
DROP TABLE users;

DROP TABLE jump_log;
DROP TABLE carriers;
DROP TABLE tokens;
DROP TABLE link_codes;

DROP FUNCTION auto_updatetz;
