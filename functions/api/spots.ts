/**
 * Cloudflare Pages Functions: /api/spots
 * High-Performance Geospatial Bounding Box (BBox) Edge API for unanext.fans
 */

interface Env {
  SUPABASE_URL?: string;
  SUPABASE_ANON_KEY?: string;
  SUPABASE_SERVICE_ROLE_KEY?: string;
}

export const onRequestGet: PagesFunction<Env> = async (context) => {
  const url = new URL(context.request.url);
  const minLng = parseFloat(url.searchParams.get('minLng') || '-180');
  const minLat = parseFloat(url.searchParams.get('minLat') || '-90');
  const maxLng = parseFloat(url.searchParams.get('maxLng') || '180');
  const maxLat = parseFloat(url.searchParams.get('maxLat') || '90');
  const category = url.searchParams.get('category')?.toUpperCase() || null;
  const zoom = parseInt(url.searchParams.get('zoom') || '10', 10);
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '500', 10), 1000);

  const supabaseUrl = context.env.SUPABASE_URL;
  const supabaseKey = context.env.SUPABASE_ANON_KEY || context.env.SUPABASE_SERVICE_ROLE_KEY;

  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    // Cache at Cloudflare Edge CDN for 1 hour, browser for 60s, background revalidation for 24h
    'Cache-Control': 'public, max-age=60, s-maxage=3600, stale-while-revalidate=86400',
    'CDN-Cache-Control': 'max-age=3600',
  };

  if (context.request.method === 'OPTIONS') {
    return new Response(null, { headers });
  }

  // 1. If Supabase is configured, execute PostGIS RPC
  if (supabaseUrl && supabaseKey) {
    try {
      const rpcEndpoint = `${supabaseUrl.replace(/\/$/, '')}/rest/v1/rpc/get_spots_in_bbox`;
      const response = await fetch(rpcEndpoint, {
        method: 'POST',
        headers: {
          apikey: supabaseKey,
          Authorization: `Bearer ${supabaseKey}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          min_lng: minLng,
          min_lat: minLat,
          max_lng: maxLng,
          max_lat: maxLat,
          category_filter: category === 'ALL' ? null : category,
          max_limit: limit,
        }),
      });

      if (response.ok) {
        const geojson = await response.json();
        return new Response(JSON.stringify(geojson), { status: 200, headers });
      }
    } catch (err) {
      console.error('Supabase query error:', err);
    }
  }

  // 2. Fallback Response (Standard GeoJSON FeatureCollection format)
  const emptyFallback = {
    type: 'FeatureCollection',
    features: [],
    metadata: {
      bbox: [minLng, minLat, maxLng, maxLat],
      zoom,
      category,
      source: 'edge_fallback',
    },
  };

  return new Response(JSON.stringify(emptyFallback), { status: 200, headers });
};
