# Zeel's Daily — Private Kindle Newspaper for Zeel Patel

A daily Kindle newspaper for Zeel Patel, Shirin's wife. Same architectural
pattern as Shirin's Brief, but the topic universe is design + AI:

- What is happening in the design-AI world
- What designers are doing differently with new AI tools
- Product design, UX/UI design, generative UI design
- New AI tools for designers and new design-relevant topics
- How designers stay current

The brief is delivered as a Kindle-safe EPUB. She has no interactive access
to Hermy; the system is fully automated and operated by Shirin from the VPS.

## Status

**Planning mode.** A sample edition has been built and validated locally;
no email has been sent to Zeel's Kindle. Awaiting Shirin's confirmation
before any test send and any daily cron.

## Requirements

- Python 3.11
- [EbookLib](https://github.com/aerkalov/ebooklib)
- [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) (used by the
  shared `brief_html.py` for HTML sanitization)
- [Pillow](https://pillow.readthedocs.io/) (cover rendering)
- AgentMail credentials in `/root/.hermes/.env` (`AGENTMAIL_API_KEY`,
  `AGENTMAIL_INBOX_ID`, `KINDLE_SEND_TO_EMAIL`)

## Layout

| File | Purpose |
|---|---|
| `src/zeels_daily_schema.py` | JSON issue schema with required desks and source-ledger. |
| `src/zeels_daily_html.py`   | Renders sanitized, semantic HTML chapters from an issue. |
| `src/zeels_daily_markup.py` | Inline emphasis + safe-link helpers. |
| `src/zeels_daily_epub_builder.py` | Builds a valid EPUB3 (metadata, nav, spine, CSS, cover) from an issue. |
| `src/zeels_daily_cover_tool.py` | Composes a Kindle-safe JPEG cover: monochrome MMX art + beautiful abstract design elements. |
| `src/zeels_daily_deliver.py` | CLI: build and/or send a daily edition. |
| `src/cover_image.py`        | Shared JPEG cover validator. |
| `src/agentmail_client.py`   | Shared stdlib AgentMail HTTPS client. |
| `src/hermes_env.py`         | Shared env loader. |

## Commands

```bash
# Build the EPUB only — no network, no send
python3 src/zeels_daily_deliver.py 2026-07-23 --build-only

# Build and explicitly send via AgentMail
python3 src/zeels_daily_deliver.py 2026-07-23 --send
```

Sending is never implicit. `--build-only` never touches the network.

## Cover Contract

- A genuinely new MMX/MiniMax image is generated every edition from the day's
  lead story
- `src/zeels_daily_cover_tool.py` overlays beautiful abstract design
  elements (concentric arcs, grids, isometric blocks, dotted grids, type
  columns) selected deterministically from a daily seed
- The final cover is a grayscale baseline JPEG around 600×800 and no
  larger than 250 KB
- PNG covers are prohibited (the same Amazon download issue we diagnosed
  for Shirin's Brief)

## Safety Guardrails

The DST-safe delivery slot refuses to send when:

- `/var/www/briefs/ZEEL_KINDLE_EMAIL` is missing or empty
- The current Toronto local hour is not 19 (7:00 PM)
- Today's edition files (`.zeels-daily.json`, `.zeels-daily.cover.jpg`) are
  missing
- A delivery marker already exists for today (idempotent)

## Deployment / Cron (Planned)

Once Shirin says "lock it":

- Production job: pin MiniMax M3, schedule at 9:00 UTC during EDT (sufficient
  buffer to research, draft, render art, build, and validate before the
  evening slot)
- Delivery job: `0 23,0 * * *` (only the 7:00 PM Toronto hour runs the
  send; the other slot is silenced by the local-time guard)
- Production scripts deploy to `/root/.hermes/scripts/zeel/`
- Per-edition Kindle address lives at `/var/www/briefs/ZEEL_KINDLE_EMAIL`
  (mode 600), no secrets in code

## Relationship to Shirin's Brief

Same proven pipeline, completely separate artifacts. The two editions
never collide, never share idempotency keys, never share delivery markers.

## Testing

Tests live in `tests/` and run through the public interfaces. Cover
validation, schema enforcement, escaping, link preservation, marker
idempotency and EPUB zip + official `epubcheck` (when installed) are all
covered.
