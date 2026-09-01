import { defineCollection, z } from 'astro:content';

const postsCollection = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    subtitle: z.string().optional().default(''),
    date: z.coerce.date(),
    category: z.enum(['SKATE', 'BMX', 'SURF', 'CLIMB', 'SNOW', 'EVENT', 'SPOT', 'ATHLETE', 'SAFETY', 'TRICKS']).default('SKATE'),
    topic_type: z.enum(['EVENT', 'SPOT', 'ATHLETE', 'SAFETY', 'RECORD', 'TIPS', 'GEAR', 'GENERAL']).default('GENERAL'),
    cover_image: z.string(),
    cover_image_source: z.string().optional().default('Official / Pexels'),
    author: z.string().default('Una (@Una_next)'),
    lang: z.string().optional().default('zh-hk'),
    city_tag: z.string().optional().default('GLOBAL'),
    featured: z.boolean().optional().default(false),
    
    // Official Video & Social Embeds
    youtube_video_id: z.string().optional(),
    youtube_video_title: z.string().optional(),
    instagram_embed_url: z.string().optional(),
    
    // Pillar 1: Expert / Athlete Spotlight
    expert_info: z.object({
      name: z.string(),
      country: z.string().optional(),
      stance_or_style: z.string().optional(),
      signature_tricks: z.array(z.string()).optional(),
      key_achievements: z.array(z.string()).optional(),
      instagram_handle: z.string().optional(),
      setup_breakdown: z.string().optional()
    }).optional(),

    // Pillar 2: Spots & Venues
    spot_info: z.object({
      name: z.string(),
      location: z.string(),
      difficulty: z.enum(['All Levels', 'Beginner', 'Intermediate', 'Advanced', 'Pro']).default('All Levels'),
      features: z.array(z.string()).optional(),
      fee: z.string().optional(),
      best_season_or_hours: z.string().optional(),
      google_map_query: z.string().optional()
    }).optional(),

    // Pillar 3 & 4: Upcoming Events (3-12 mos) & Results
    event_info: z.object({
      event_name: z.string(),
      dates: z.string(),
      event_status: z.enum(['UPCOMING', 'LIVE', 'COMPLETED']).default('UPCOMING'),
      location: z.string(),
      tier: z.string().optional(), // e.g. "World Championship / X Games Tier"
      official_site_url: z.string().optional(),
      livestream_url: z.string().optional(),
      podium_results: z.array(z.object({
        place: z.string(),
        athlete: z.string(),
        score_or_time: z.string().optional()
      })).optional()
    }).optional(),

    // Pillar 5: Safety Gear & Tricks
    safety_gear_info: z.object({
      gear_type: z.string(), // Helmet, Knee Pads, etc.
      certification: z.string().optional(), // ASTM F1492 / CPSC / CE EN1078
      key_protection_points: z.array(z.string()).optional(),
      pros: z.array(z.string()).optional(),
      cons: z.array(z.string()).optional()
    }).optional(),

    trick_info: z.object({
      trick_name: z.string(),
      difficulty_rating: z.number().min(1).max(5).default(3), // 1 to 5 stars
      prerequisites: z.array(z.string()).optional(),
      key_mechanics: z.array(z.string()).optional(),
      common_mistakes: z.array(z.string()).optional()
    }).optional(),

    // Amazon Affiliate & Monetization
    gear_keyword: z.string().optional(),
    affiliate_products: z.array(z.object({
      title: z.string(),
      subtitle: z.string().optional(),
      search_term: z.string(),
      amazon_url: z.string(),
      recommended_for: z.string().optional(),
      badge_text: z.string().optional().default('Editor Pick')
    })).optional().default([])
  })
});

export const collections = {
  posts: postsCollection
};
