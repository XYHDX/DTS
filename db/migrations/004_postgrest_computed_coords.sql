-- Migration 004: PostgREST computed columns for lat/lon
--
-- The schema stores coordinates as PostGIS geometry(Point,4326) in a
-- "location" column.  PostgREST does not automatically decompose geometry
-- into latitude/longitude.  These computed-column functions make
-- "latitude" and "longitude" available as virtual selectable columns
-- in the REST API for every table that has a location geometry.

-- vehicle_positions_latest
CREATE OR REPLACE FUNCTION vehicle_positions_latest_latitude(vehicle_positions_latest)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_Y($1.location)::float8
$$;

CREATE OR REPLACE FUNCTION vehicle_positions_latest_longitude(vehicle_positions_latest)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_X($1.location)::float8
$$;

-- vehicle_positions (historical)
CREATE OR REPLACE FUNCTION vehicle_positions_latitude(vehicle_positions)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_Y($1.location)::float8
$$;

CREATE OR REPLACE FUNCTION vehicle_positions_longitude(vehicle_positions)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_X($1.location)::float8
$$;

-- stops
CREATE OR REPLACE FUNCTION stops_latitude(stops)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_Y($1.location)::float8
$$;

CREATE OR REPLACE FUNCTION stops_longitude(stops)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_X($1.location)::float8
$$;

-- geofences (centroid for polygon geometries)
CREATE OR REPLACE FUNCTION geofences_latitude(geofences)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_Y(ST_Centroid($1.geometry))::float8
$$;

CREATE OR REPLACE FUNCTION geofences_longitude(geofences)
  RETURNS float8 LANGUAGE sql STABLE AS $$
  SELECT ST_X(ST_Centroid($1.geometry))::float8
$$;
