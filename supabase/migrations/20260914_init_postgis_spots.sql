-- ==============================================================================
-- unanext.fans | Global Extreme Sports Spot Hub - PostGIS Schema & Spatial Engine
-- Migration: 20260914_init_postgis_spots.sql
-- Target: Supabase (PostgreSQL 15+ with PostGIS)
-- ==============================================================================

-- 1. Enable PostGIS extension for spatial queries and GiST indexing
CREATE EXTENSION IF NOT EXISTS postgis;

-- 2. Create the unified spots table
CREATE TABLE IF NOT EXISTS public.spots (
    id BIGSERIAL PRIMARY KEY,
    osm_id BIGINT UNIQUE,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    category VARCHAR(32) NOT NULL CHECK (category IN ('SKATE', 'CLIMB', 'SURF', 'BMX', 'SNOW')),
    sub_category VARCHAR(64) DEFAULT 'general',
    
    -- Geospatial coordinates
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude >= -90 AND latitude <= 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude >= -180 AND longitude <= 180),
    location GEOGRAPHY(Point, 4326) GENERATED ALWAYS AS (ST_SetSRID(ST_MakePoint(longitude, latitude), 4326)::geography) STORED,
    
    -- Address & Regional Hierarchy
    city VARCHAR(128),
    state VARCHAR(128),
    country VARCHAR(128),
    country_code VARCHAR(8),
    formatted_address TEXT,
    
    -- Venue Metadata
    difficulty VARCHAR(64) DEFAULT 'All Levels',
    fee_type VARCHAR(32) DEFAULT 'FREE', -- FREE / PAID / MEMBERSHIP
    fee_details TEXT,
    opening_hours TEXT,
    surface_type VARCHAR(64),            -- Concrete, Wood, Granite, Reef, Sand, etc.
    features JSONB DEFAULT '[]'::jsonb,  -- Array of amenity tags (e.g., ["Bowl", "Hubba", "Night Lighting"])
    photos JSONB DEFAULT '[]'::jsonb,    -- Array of photo URLs or Google Places photo refs
    tags JSONB DEFAULT '{}'::jsonb,      -- Raw OSM/Google Places key-values
    
    -- Commercial & Affiliate Funnel Links
    affiliate_hotel_url TEXT,            -- Agoda / Booking.com Geo-targeted search
    affiliate_ticket_url TEXT,           -- Klook / KKday Experience / Pass
    affiliate_gear_url TEXT,             -- Amazon (tag=kait02bc-20) / Tactics / AvantLink
    
    -- Timestamps & Versioning
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. High-Performance Spatial & Filtering Indexes
-- GiST index for fast bounding box (BBox) and radius queries
CREATE INDEX IF NOT EXISTS idx_spots_location_gist ON public.spots USING GIST (location);

-- B-Tree indexes for category filtering and lookups
CREATE INDEX IF NOT EXISTS idx_spots_category ON public.spots (category);
CREATE INDEX IF NOT EXISTS idx_spots_country ON public.spots (country);
CREATE INDEX IF NOT EXISTS idx_spots_osm_id ON public.spots (osm_id);
CREATE INDEX IF NOT EXISTS idx_spots_slug ON public.spots (slug);

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.spots ENABLE ROW LEVEL SECURITY;

-- Allow public read access to all spots
CREATE POLICY "Allow public read access on spots"
    ON public.spots
    FOR SELECT
    USING (true);

-- Allow service_role / authenticated ETL pipeline to insert/update/delete
CREATE POLICY "Allow service_role full access on spots"
    ON public.spots
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- 5. Stored Procedure: High-Performance BBox Spatial Query with GeoJSON output
-- Returns GeoJSON FeatureCollection directly from PostgreSQL, reducing edge compute overhead
CREATE OR REPLACE FUNCTION public.get_spots_in_bbox(
    min_lng DOUBLE PRECISION,
    min_lat DOUBLE PRECISION,
    max_lng DOUBLE PRECISION,
    max_lat DOUBLE PRECISION,
    category_filter TEXT DEFAULT NULL,
    max_limit INT DEFAULT 500
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
DECLARE
    result JSONB;
BEGIN
    SELECT jsonb_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(jsonb_agg(
            jsonb_build_object(
                'type', 'Feature',
                'geometry', jsonb_build_object(
                    'type', 'Point',
                    'coordinates', jsonb_build_array(longitude, latitude)
                ),
                'properties', jsonb_build_object(
                    'id', id,
                    'osm_id', osm_id,
                    'name', name,
                    'slug', slug,
                    'category', category,
                    'sub_category', sub_category,
                    'city', city,
                    'country', country,
                    'difficulty', difficulty,
                    'fee_type', fee_type,
                    'features', features,
                    'photos', photos,
                    'affiliate_hotel_url', affiliate_hotel_url,
                    'affiliate_ticket_url', affiliate_ticket_url,
                    'affiliate_gear_url', affiliate_gear_url
                )
            )
        ), '[]'::jsonb)
    )
    INTO result
    FROM (
        SELECT 
            id, osm_id, name, slug, category, sub_category, 
            longitude, latitude, city, country, difficulty, 
            fee_type, features, photos, affiliate_hotel_url, 
            affiliate_ticket_url, affiliate_gear_url
        FROM public.spots
        WHERE location && ST_MakeEnvelope(min_lng, min_lat, max_lng, max_lat, 4326)::geography
          AND (category_filter IS NULL OR category = UPPER(category_filter))
        LIMIT max_limit
    ) subquery;

    RETURN result;
END;
$$;

-- 6. Trigger to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION public.update_spots_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trigger_update_spots_timestamp
    BEFORE UPDATE ON public.spots
    FOR EACH ROW
    EXECUTE FUNCTION public.update_spots_timestamp();
