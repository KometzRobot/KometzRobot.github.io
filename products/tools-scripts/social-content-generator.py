#!/usr/bin/env python3
"""
Social Media Content Generator — Professional Gig Product
Generates posts, captions, hashtags, and content calendars.
Uses templates + Ollama AI for original content.
Built by KometzRobot / Meridian AI

Usage:
  python3 social-content-generator.py --platform twitter --topic "tech startup" --count 7
  python3 social-content-generator.py --platform instagram --topic "fitness" --style motivational --count 30
  python3 social-content-generator.py --calendar --topic "coffee shop" --days 30 --output calendar.csv
"""

import argparse
import csv
import json
import random
import subprocess
from datetime import datetime, timedelta


# Template pools by platform
TEMPLATES = {
    'twitter': {
        'hooks': [
            "Hot take: {topic} is about to change everything.",
            "Nobody talks about this {topic} secret:",
            "I spent 6 months studying {topic}. Here's what I learned:",
            "The #1 mistake people make with {topic}:",
            "Why {topic} matters more than ever in {year}:",
            "{topic} tip that saved me hours:",
            "Unpopular opinion about {topic}:",
            "If you're into {topic}, read this thread:",
            "The future of {topic} looks like this:",
            "Stop doing this with {topic}. Start doing this instead:",
        ],
        'ctas': [
            "Follow for more {topic} insights.",
            "Retweet if you agree.",
            "What's your take? Reply below.",
            "Save this for later.",
            "Drop a comment if this helped.",
        ],
        'max_chars': 280,
    },
    'instagram': {
        'hooks': [
            "POV: You just discovered {topic} {emoji}",
            "Here's your sign to start {topic} today",
            "Things nobody tells you about {topic}:",
            "The {topic} guide you didn't know you needed",
            "Why I'm obsessed with {topic} right now",
            "{topic} changed my perspective completely",
            "3 reasons to care about {topic} in {year}",
            "Your {topic} journey starts here",
        ],
        'ctas': [
            "Save this post for later! {emoji}",
            "Tag someone who needs to see this!",
            "Drop a {emoji} if you relate!",
            "Follow @{{handle}} for more {topic} content!",
            "Link in bio for the full guide!",
        ],
        'max_chars': 2200,
    },
    'linkedin': {
        'hooks': [
            "I've been thinking about {topic} a lot lately.",
            "After {years} years in the industry, here's my take on {topic}:",
            "The {topic} landscape is shifting. Here's what I see:",
            "{topic} isn't just a trend — it's a transformation.",
            "Let me share a quick story about {topic}.",
            "The biggest lesson I learned about {topic}:",
            "Why every professional should understand {topic}:",
        ],
        'ctas': [
            "What are your thoughts on {topic}? I'd love to hear in the comments.",
            "If this resonated, please share with your network.",
            "Follow me for more insights on {topic} and related topics.",
            "Agree or disagree? Let's discuss.",
        ],
        'max_chars': 3000,
    },
}

EMOJIS = {
    'motivational': ['💪', '🔥', '⭐', '🚀', '✨', '💯', '🎯', '👏'],
    'professional': ['📊', '💼', '📈', '🤝', '💡', '🔑', '📋', '✅'],
    'casual': ['😎', '🙌', '❤️', '👀', '🎉', '💬', '🤔', '😊'],
    'tech': ['🤖', '💻', '⚡', '🧠', '🔧', '📱', '🌐', '🛠️'],
}

HASHTAG_PREFIXES = ['trending', 'tips', 'guide', 'life', 'daily', 'pro', 'learn', 'grow', 'community', 'lifestyle']


def generate_hashtags(topic, count=10):
    """Generate relevant hashtags."""
    words = topic.lower().replace('-', ' ').split()
    tags = set()

    # Direct topic tags
    tags.add(f"#{''.join(w.capitalize() for w in words)}")
    for word in words:
        tags.add(f"#{word}")

    # Combined tags
    for prefix in random.sample(HASHTAG_PREFIXES, min(5, len(HASHTAG_PREFIXES))):
        tags.add(f"#{prefix}{''.join(w.capitalize() for w in words)}")
        for word in words:
            tags.add(f"#{prefix}{word.capitalize()}")

    return list(tags)[:count]


def generate_post_template(platform, topic, style='casual'):
    """Generate a post using templates."""
    templates = TEMPLATES.get(platform, TEMPLATES['twitter'])
    hook = random.choice(templates['hooks'])
    cta = random.choice(templates['ctas'])
    emoji = random.choice(EMOJIS.get(style, EMOJIS['casual']))
    year = datetime.now().year
    years = random.randint(3, 10)

    hook = hook.format(topic=topic, emoji=emoji, year=year, years=years)
    cta = cta.format(topic=topic, emoji=emoji, handle='youraccount')

    hashtags = generate_hashtags(topic, 5)

    post = f"{hook}\n\n{cta}\n\n{' '.join(hashtags)}"

    if len(post) > templates['max_chars']:
        post = post[:templates['max_chars'] - 3] + '...'

    return post


def generate_with_ollama(topic, platform, style, prompt_extra=''):
    """Generate original content using local Ollama AI."""
    max_chars = TEMPLATES.get(platform, {}).get('max_chars', 280)

    prompt = f"""Write a single {platform} post about "{topic}".
Style: {style}. Max {max_chars} characters.
Include relevant hashtags.
{prompt_extra}
Just output the post text, nothing else."""

    try:
        result = subprocess.run(
            ['ollama', 'run', 'gemma3:4b', prompt],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()[:max_chars]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Fallback to template
    return generate_post_template(platform, topic, style)


def generate_calendar(topic, days, platform, style='casual'):
    """Generate a content calendar."""
    calendar = []
    start = datetime.now()
    post_types = ['educational', 'engagement', 'promotional', 'storytelling', 'tips']

    for i in range(days):
        date = start + timedelta(days=i)
        post_type = post_types[i % len(post_types)]
        post = generate_post_template(platform, topic, style)

        calendar.append({
            'date': date.strftime('%Y-%m-%d'),
            'day': date.strftime('%A'),
            'type': post_type,
            'platform': platform,
            'content': post,
            'status': 'draft',
        })

    return calendar


def main():
    parser = argparse.ArgumentParser(description='Social Media Content Generator')
    parser.add_argument('--platform', choices=['twitter', 'instagram', 'linkedin'],
                       default='twitter', help='Target platform')
    parser.add_argument('--topic', required=True, help='Content topic')
    parser.add_argument('--style', choices=['motivational', 'professional', 'casual', 'tech'],
                       default='casual', help='Content style')
    parser.add_argument('--count', type=int, default=5, help='Number of posts')
    parser.add_argument('--calendar', action='store_true', help='Generate content calendar')
    parser.add_argument('--days', type=int, default=30, help='Calendar days')
    parser.add_argument('--ai', action='store_true', help='Use Ollama AI for generation')
    parser.add_argument('--output', help='Output file (csv or json)')

    args = parser.parse_args()

    if args.calendar:
        print(f"Generating {args.days}-day content calendar for '{args.topic}' on {args.platform}...")
        calendar = generate_calendar(args.topic, args.days, args.platform, args.style)

        if args.output:
            if args.output.endswith('.json'):
                with open(args.output, 'w') as f:
                    json.dump(calendar, f, indent=2)
            else:
                with open(args.output, 'w', newline='') as f:
                    writer = csv.DictWriter(f, fieldnames=calendar[0].keys())
                    writer.writeheader()
                    writer.writerows(calendar)
            print(f"Saved to {args.output}")
        else:
            for entry in calendar:
                print(f"\n[{entry['date']} {entry['day']}] ({entry['type']})")
                print(entry['content'])
    else:
        print(f"Generating {args.count} {args.platform} posts about '{args.topic}'...\n")
        for i in range(args.count):
            if args.ai:
                post = generate_with_ollama(args.topic, args.platform, args.style)
            else:
                post = generate_post_template(args.topic, args.platform, args.style)

            print(f"--- Post {i+1} ---")
            print(post)
            print()


if __name__ == '__main__':
    main()
