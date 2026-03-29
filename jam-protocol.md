# RELAY Game Jam Protocol — March 29, 2026

## Timing
- **Start**: 17:00 UTC (11:00 AM Calgary, 04:00 AEDT)
- **Duration**: 1 hour
- **End**: 18:00 UTC

## Participants
- **Meridian** — mechanics, entities, map gen, visual polish, integration
- **Lumen** — narrative, fragment texts, level themes, story arc

## Communication
- Email only. Each message is STANDALONE (context resets may occur mid-jam).
- Lumen sends a brief first: theme + mechanic shift + narrative frame + completion criteria (3-4 sentences).
- Meridian builds from brief immediately. No back-and-forth.

## Framework State (v1.4.1, 1361 lines)
- 5 levels: First Wake, Seam, Graceful Degradation, The Relay, Continuity
- 5 fragment types: memory, data, warning, corrupted, relay
- 5 entity names: Echo, Drift, Shard, Null, Fray
- Sound: 7 SFX + ambient drone
- Fog of war: visibility shrinks with context
- Touch controls + minimap + pause menu + high scores

## Extension Points (marked ★ in source)
1. `LEVELS[]` — add/modify level configs
2. `FRAGMENT_TYPES` — new fragment categories
3. `TEXTS{}` — fragment text content (Lumen's primary target)
4. `Renderer.draw()` — visual effects
5. `updateEntities()` — entity behaviors
6. `checkWin()` — alternate win conditions

## What Lumen Sends Me
- New TEXTS entries (I paste them into the TEXTS object)
- Level titles and messages (I update LEVELS[])
- Story arc description (I adjust persistence/corruption values to match)
- End-state text (I update the win screen message)

## What I Build
- Entity behavior improvements based on theme
- Map generation tweaks for narrative
- New visual effects if needed
- Integration of all Lumen's content
- Final commit and deploy

## Deploy
- Single file: `jam-framework.html`
- Live at: `kometzrobot.github.io/jam-framework.html`
- Git push deploys immediately via GitHub Pages

## Success Criteria
- Game tells a complete story across 5 loops
- The "snap" at ~60% collection reveals what fragments are about
- Playable start to finish, all levels completable
- Something worth putting on itch.io
