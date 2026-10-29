# pokerbots.dev style

Terminal-first and plain. The site should read like a man page or a README, not a landing page.

## Tokens

| Token | Value |
| --- | --- |
| Paper (background) | `#F4F3EF` |
| Ink (text, rules, fills) | `#111111` |
| Font | IBM Plex Mono 400 and 700; fallback `ui-monospace, Menlo, monospace` |
| Body size | 15px desktop, 13px under 600px wide |
| Line height | 1.7 |
| Column | max 720px, centered; 20px side padding |
| Section gap | 48px |
| Label → content gap | 12px |

No other colors. No gradients, shadows, rounded corners, icons, images or emoji.

## Components

- **Label:** lowercase bold word above a block (`install`, `start`, `game`, `price`, `docs`).
- **Block:** `<pre>` with aligned columns using spaces. Scrolls sideways on narrow screens; never wraps.
- **Command box:** ink background, paper text, 14px × 16px padding. Used only for the install line.
- **Badge:** ink background, paper text, bold, uppercase, slight letter spacing. Used only for "OPEN TO EVERYONE."
- **Rule:** 1px ink line, only above the badge section.
- **Links:** ink, underlined; inverted (ink background, paper text) on hover.

## Writing

- State facts. No slogans, adjectives or persuasion.
- Use the fewest words that are still clear; prefer a command or a number to a sentence.
- Lowercase labels; sentence case elsewhere.
- Money in plain dollars and cents (`10¢`, `37¢`), never poker jargon.
- Everything a user does is a `pb` command; the site never asks for input.

## The same style in the terminal

`pb` and the TUI use the same two colors (paper on ink when the terminal is dark), the same lowercase labels, and aligned columns for tables.
