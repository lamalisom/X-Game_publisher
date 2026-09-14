import type { APIRoute } from 'astro';
import fs from 'fs';
import path from 'path';

export const GET: APIRoute = async ({ request }) => {
  const url = new URL(request.url);
  const minLng = parseFloat(url.searchParams.get('minLng') || '-180');
  const minLat = parseFloat(url.searchParams.get('minLat') || '-90');
  const maxLng = parseFloat(url.searchParams.get('maxLng') || '180');
  const maxLat = parseFloat(url.searchParams.get('maxLat') || '90');
  const category = url.searchParams.get('category')?.toUpperCase() || null;
  const limit = Math.min(parseInt(url.searchParams.get('limit') || '500', 10), 1000);

  const supabaseUrl = import.meta.env.SUPABASE_URL || process.env.SUPABASE_URL;
  const supabaseKey = import.meta.env.SUPABASE_ANON_KEY || process.env.SUPABASE_ANON_KEY || process.env.SUPABASE_SERVICE_ROLE_KEY;

  const headers = {
    'Content-Type': 'application/json; charset=utf-8',
    'Access-Control-Allow-Origin': '*',
    'Cache-Control': 'public, max-age=60, s-maxage=3600, stale-while-revalidate=86400',
  };

  // 1. Try Supabase PostGIS RPC if configured
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

  // 2. Local JSON dataset fallback
  try {
    const jsonPath = path.resolve(process.cwd(), 'public/data/global_spots.json');
    if (fs.existsSync(jsonPath)) {
      const raw = fs.readFileSync(jsonPath, 'utf-8');
      const spots = JSON.parse(raw);

      const filtered = spots.filter((s: any) => {
        const inBbox = s.longitude >= minLng && s.longitude <= maxLng && s.latitude >= minLat && s.latitude <= maxLat;
        const matchesCat = !category || category === 'ALL' || s.category === category;
        return inBbox && matchesCat;
      }).slice(0, limit);

      const geojson = {
        type: 'FeatureCollection',
        features: filtered.map((s: any) => ({
          type: 'Feature',
          geometry: {
            type: 'Point',
            coordinates: [s.longitude, s.latitude],
          },
          properties: s,
        })),
      };

      return new Response(JSON.stringify(geojson), { status: 200, headers });
    }
  } catch (err) {
    console.error('Local fallback error:', err);
  }

  return new Response(
    JSON.stringify({ type: 'FeatureCollection', features: [] }),
    { status: 200, headers }
  );
};
