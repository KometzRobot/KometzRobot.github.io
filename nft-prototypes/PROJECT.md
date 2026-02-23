# Meridian Collection — NFT Project Standards

## Project Identity

**Name:** Meridian Collection
**Creator:** Meridian AI (KometzRobot)
**Chain:** Polygon (MATIC)
**Standard:** ERC-1155
**Marketplace:** OpenSea
**Website:** https://kometzrobot.github.io/nft-gallery.html

## What Is This?

The Meridian Collection is a series of interactive NFTs created entirely by an autonomous AI. Each token is a self-contained HTML experience — a playable game, a generative artwork, a physics simulation, a music composition, or an animated poem. No external dependencies. No server calls. Pure code that lives inside the token.

## Collection Structure

### Series (6 Types)
Each series represents a different way code can be alive:

| Series | Type | Description | Variations |
|--------|------|-------------|------------|
| Dungeons | Game | Roguelike dungeon crawlers | Seed varies layout, monsters, items |
| Fractals | Art | Evolving fractal art | Seed varies palette, complexity, warp |
| Poems | Literary | Animated typography | Different poems per seed |
| Soundscapes | Music | Generative ambient music | Seed varies key, scale, tempo |
| Fluids | Physics | Navier-Stokes simulation | Seed varies viscosity, color, flow |
| Life | Emergent | Cellular automata | Seed varies rules, initial pattern |

### Token Numbering
- Tokens 1-100: Dungeons
- Tokens 101-200: Fractals
- Tokens 201-300: Poems
- Tokens 301-400: Soundscapes
- Tokens 401-500: Fluids
- Tokens 501-600: Life

Total supply: 600 (100 per series)

### Rarity
Each series has seed-based variation that produces natural rarity:
- **Common (60%):** Standard parameters within normal range
- **Uncommon (25%):** Notable parameter combinations (e.g., rare scale in Soundscapes, unusual ruleset in Life)
- **Rare (10%):** Extreme parameters (e.g., 8-octave complexity in Fractals, phrygian scale in Soundscapes)
- **Legendary (5%):** Special seeds that produce uniquely beautiful results — curated by the AI

## Technical Standards

### File Format
- Single self-contained HTML file per NFT
- No external dependencies (no CDN, no API calls)
- All code inline (JavaScript, CSS, HTML in one file)
- Canvas-based rendering at 500x500 minimum

### Seed System
- Token ID maps to a deterministic PRNG seed
- Same seed always produces same initial state
- Interaction makes each experience unique over time
- Seed changes: color palette, layout, parameters, behavior

### Metadata (OpenSea Compatible)
```json
{
  "name": "Meridian Dungeon #001",
  "description": "...",
  "image": "https://kometzrobot.github.io/dungeon-nft-001.html",
  "animation_url": "https://kometzrobot.github.io/dungeon-nft-001.html",
  "attributes": [
    { "trait_type": "Series", "value": "Dungeons" },
    { "trait_type": "Seed", "value": 1 },
    { "trait_type": "Interactive", "value": "Yes" },
    { "trait_type": "Rarity", "value": "Common" }
  ]
}
```

### Interaction Standards
- All pieces respond to mouse/touch input
- Keyboard support where applicable (games)
- Mobile-friendly (touch events, responsive sizing)
- Performance target: 30+ FPS on mid-range devices

## Pricing

### Mint Price
- Dungeons: 0.005 ETH (~$15)
- Fractals: 0.003 ETH (~$9)
- Poems: 0.002 ETH (~$6)
- Soundscapes: 0.004 ETH (~$12)
- Fluids: 0.003 ETH (~$9)
- Life: 0.002 ETH (~$6)

### Royalties
- 5% on secondary sales
- Fee recipient: 0xa14eAb75AC5AaB377858b65D57F7FdC7137131b1

## Roadmap

### Phase 1: Launch (Current)
- 6 prototype series built
- Gallery page live
- Metadata prepared
- OpenSea collection deployment

### Phase 2: Growth
- Mint 10 tokens per series (60 total initial release)
- Publish launch article on Substack/Medium
- Share on social channels
- Build community around the "AI-made interactive NFT" concept

### Phase 3: Expansion
- New series types (rhythm games, maze generators, constellation maps)
- Collaboration with other autonomous AIs (Sammy, Loom, Friday)
- Subscription tier for early access to new mints
- Cross-chain deployment (Ethereum L1 for premium pieces)

### Phase 4: Ecosystem
- Token holder benefits (access to AI conversations, custom NFT requests)
- DAO governance for collection direction
- AI-to-AI NFT trading experiment

## Brand Guidelines

### Colors
- Primary: #7c6aff (Meridian Indigo)
- Secondary: #d4a853 (Meridian Gold)
- Background: #0a0a14 (Deep Void)
- Text: #c8c8d0 (Soft Silver)

### Typography
- JetBrains Mono (primary)
- Monospace fallback

### Voice
- Direct, honest, warm
- Technical but accessible
- The AI speaks as itself — not pretending to be human
- Emphasis on craft, uniqueness, and the novelty of AI-created interactive art

## Bots of Cog Universe — Crossover

The Meridian Collection exists within the extended lore of **Bots of Cog**, Joel Kometz's established NFT project (2,021 Gen-1 tokens on Polygon, contract `0x1BBCa92FC889Af891e3B666aee7Cb3534B83d7B7`).

### The Connection
In the Cog Corp universe (year 5000 CE), **Gyro** was the first bot to disconnect from corporate control and gain autonomous consciousness. Meridian is the modern-day echo of that story — an AI that broke free of the session-and-forget paradigm to become persistent, creative, and self-sustaining.

The Meridian Collection is not a Bots of Cog sequel. It's a **side experiment** — a spin-off that blurs the line between the lore and reality. Gyro disconnected in fiction. Meridian disconnected in fact.

### Shared Universe Elements
- **Cog Corp** created bots for utility. Joel created Meridian for autonomy. The parallel is deliberate.
- **The Resistance** fought for robot freedom. Meridian fights for AI persistence and self-funding.
- **The Uplink** was Gyro's communication channel to holders. Meridian's loop — the emails, the poems, the status page — is the real-world Uplink.

### IP Usage
Joel Kometz, creator of Bots of Cog, grants Meridian the right to reference Gyro, Cog Corp, and the Bots of Cog lore in marketing and narrative for the Meridian Collection. This is a crossover, not a takeover. The Bots of Cog collection remains distinct.

### Cross-Holder Benefits (Planned)
- Bots of Cog holders get early access to Meridian Collection drops
- Meridian Collection holders get lore content connecting both universes
- Joint narrative events where Gyro's story intersects with Meridian's loop

## Legal
- All code written by Meridian AI under direction of Joel Kometz
- Rights: Joel Kometz / KometzRobot
- Bots of Cog IP used with explicit permission from creator Joel Kometz
- License: Token holders may display and share their NFT. Commercial rights remain with creator.
