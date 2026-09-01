import rss from '@astrojs/rss';
import { getCollection } from 'astro:content';
import type { APIContext } from 'astro';

export async function GET(context: APIContext) {
  const posts = await getCollection('posts');
  const sortedPosts = posts.sort((a, b) => b.data.date.getTime() - a.data.date.getTime());

  return rss({
    title: 'xGame Radar Magazine | 全球極限運動前線',
    description: '每日自動更新滑板、BMX、衝浪、攀岩與雪上運動的最新賽事情報、焦點選手專題、場地深度評測與安全裝備指南。',
    site: context.site || 'https://xgame-radar.pages.dev',
    items: sortedPosts.map((post) => ({
      title: post.data.title,
      pubDate: post.data.date,
      description: post.data.subtitle || post.data.title,
      link: `/posts/${post.slug}/`,
      categories: [post.data.category, post.data.topic_type],
      author: post.data.author,
    })),
    customData: `<language>zh-hk</language>`,
  });
}
