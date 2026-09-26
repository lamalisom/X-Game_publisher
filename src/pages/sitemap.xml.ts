import { getCollection } from 'astro:content';

export async function GET() {
  const posts = await getCollection('posts');
  const siteUrl = 'https://unanext.fans';

  const staticPages = [
    '',
    '/spots/map',
    '/spots/map/en',
    '/today',
    '/skate',
    '/bmx',
    '/surf',
    '/climb',
    '/snow',
    '/events',
    '/spots',
    '/athletes',
    '/tricks',
    '/safety',
  ];

  let xml = `<?xml version="1.0" encoding="UTF-8"?>\n`;
  xml += `<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n`;

  // 1. 靜態主要頁面
  for (const page of staticPages) {
    xml += `  <url>\n`;
    xml += `    <loc>${siteUrl}${page}</loc>\n`;
    xml += `    <changefreq>daily</changefreq>\n`;
    xml += `    <priority>${page === '' || page === '/spots/map' ? '1.0' : '0.8'}</priority>\n`;
    xml += `  </url>\n`;
  }

  // 2. 所有深度專題文章
  for (const post of posts) {
    const pubDate = post.data.pub_date ? new Date(post.data.pub_date).toISOString().split('T')[0] : '2026-09-27';
    xml += `  <url>\n`;
    xml += `    <loc>${siteUrl}/posts/${post.slug}/</loc>\n`;
    xml += `    <lastmod>${pubDate}</lastmod>\n`;
    xml += `    <changefreq>weekly</changefreq>\n`;
    xml += `    <priority>0.7</priority>\n`;
    xml += `  </url>\n`;
  }

  xml += `</urlset>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/xml; charset=utf-8',
    },
  });
}
