-- Toronto 311 service requests, 2024-2025.
-- One row per request. Source: City of Toronto Open Data, "311 Service Requests - Customer Initiated".

DROP VIEW IF EXISTS v_requests;
DROP TABLE IF EXISTS service_requests;
DROP TABLE IF EXISTS request_types;
DROP TABLE IF EXISTS wards;

CREATE TABLE wards (
    ward_id    integer PRIMARY KEY,          -- official ward number, 1 to 25
    ward_name  text NOT NULL UNIQUE          -- e.g. 'Toronto-Danforth'
);

CREATE TABLE request_types (
    request_type text PRIMARY KEY,           -- raw type name as written by 311
    topic        text NOT NULL               -- one of 15 plain-language groups (see topics.py)
);

CREATE TABLE service_requests (
    request_id            bigserial PRIMARY KEY,
    created_at            timestamp NOT NULL,    -- when the request was opened
    status                text NOT NULL,         -- Completed, Cancelled, In Progress, New, Closed, Unknown
    postal_fsa            char(3),               -- first 3 characters of the postal code, e.g. 'M4C'; NULL when logged at an intersection
    intersection_street_1 text,
    intersection_street_2 text,
    ward_id               integer REFERENCES wards(ward_id),   -- NULL when the ward is unknown
    request_type          text NOT NULL REFERENCES request_types(request_type),
    division              text NOT NULL,         -- city division that owns the request
    section               text NOT NULL          -- section inside that division
);

CREATE INDEX ON service_requests (created_at);
CREATE INDEX ON service_requests (ward_id);
CREATE INDEX ON service_requests (request_type);

-- Convenience view the agent is encouraged to use: everything joined, plus the topic.
CREATE VIEW v_requests AS
SELECT r.request_id, r.created_at, r.status, r.postal_fsa,
       r.intersection_street_1, r.intersection_street_2,
       r.ward_id, w.ward_name, r.request_type, t.topic, r.division, r.section
FROM service_requests r
JOIN request_types t USING (request_type)
LEFT JOIN wards w USING (ward_id);

-- Read-only login for the agent. Even if the model writes DELETE, the database refuses.
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'agent_ro') THEN
    CREATE ROLE agent_ro LOGIN PASSWORD 'agent_ro';
  END IF;
END $$;
GRANT USAGE ON SCHEMA public TO agent_ro;
GRANT SELECT ON wards, request_types, service_requests, v_requests TO agent_ro;
ALTER ROLE agent_ro SET statement_timeout = '15s';
ALTER ROLE agent_ro SET default_transaction_read_only = on;
