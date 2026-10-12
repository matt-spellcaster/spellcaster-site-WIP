# Design

Approved by Matthew at the M2 design gate on 2026-09-23 (Inter, cool dark, cards), then
revised on 2026-09-24 to the "Editorial, with sky" direction from the session 4 design canvas:
a serif reading page on a warm black, with a thin-line planetary horizon under the pitch. The
mockup pages from the M2 gate were removed afterwards; `git log -- src/pages/mockup` has them.
On 2026-09-27 Matthew replaced Newsreader: Inter became the primary face and IBM Plex Mono the
secondary.

## Decisions

| Decision | Choice |
|---|---|
| Theme | Dark only, on a warm black |
| Primary face (`font-primary`) | **Inter** (variable, Latin subset), self-hosted through Astro's Fonts API from `@fontsource-variable/inter`. Headings, body text, the project names, the name in the header, and the demo's Slack and Jira mockups. `h1` and `h2` are tracked `-0.02em`. |
| Secondary face (`font-secondary`, also `font-mono`) | **IBM Plex Mono** (Latin subset, weights 400 and 500 only: it has no variable cut), from `@fontsource/ibm-plex-mono`. The nav and menu, labels, small links, buttons, captions, facts' labels, tables, code, the footer. Buttons are 13px, a step under the text around them, so the case study's two fit on one row on a phone. Never bolder than 500, so no synthetic bold. |
| Accent | **Blue `#8ab4f8`**: links in running text, the ledger's GitHub links, primary buttons |
| Layout | One reading column, `--container-page` (52rem, 48rem of text). The home page reads top to bottom: pitch, the featured project as an article, the other projects as a ledger, About, Contact. |
| Header glass | Tint **0.80** of the canvas, `saturate(160%) blur(16px)` |
| Menu glass | Tint **0.92**, same filter (see below) |
| Sky | The wash, the stars and the horizon, at `--sky-intensity` 0.6 |

## Tokens

Defined once in `src/styles/global.css` (`@theme`), and checked by `tests/unit/contrast.test.ts`.

| Token | Value | Use |
|---|---|---|
| `canvas` | `#111010` | Page background; text on accent buttons |
| `surface` | `#181616` | The screenshot frame, code blocks; the opaque glass fallback |
| `surface-2` | `#221f1f` | Hover states, inline code |
| `planet` | `#0b0c10` | The horizon's disc, fading out under the featured project's header, so the contrast test treats it as a surface. |
| `line` | `#2b2828` | Borders and dividers |
| `ink` | `#ecebe6` | Headings, names, links. Body text is `ink` at 85%, the ledger's one-liners at 70%. |
| `muted` | `#b0ada5` | Labels, captions, the nav, the footer |
| `accent` | `#8ab4f8` | Links and primary buttons |
| `keep` / `revoke` / `decide` | `#5cc98a` / `#f07178` / `#e6b450` | The demo's decision colours (M6); code highlighting |

Every text colour meets WCAG AA (4.5:1) on every surface, on the header glass with a white
image directly behind it (the worst case: blur leaves a white area white), and over the sky's
wash and the horizon's glow at their strongest. `muted` is as dark as the glass check allows. The contrast test fails
on any colour in `@theme` it doesn't know, so a new one has to be added there.

The sky's own blues (`#4f7fd9` haze, `#6f9fe6` limb light, `#dbe7ff` the line) are gradient
stops in `Sky.astro` and `Horizon.astro`, and the stars are `#ffffff`, `#dbe7ff` and `#c9d8ff`
fills: never text and never a surface. The wash and the glow are behind text, and the test
composites both over the canvas.

## Type

- The pitch is a 34px statement (28px on phones), the featured title 40px (32px on phones), the
  project names 20px, body text 19px to 20px (the featured paragraph 18px on phones, the ledger's
  one-liners 17px), the About and Contact headings 22px; all Inter at weight 400 or 500,
  never bolder, including `strong` in the case study.
- Section labels ("Featured", "More projects", "Case study") are the `eyebrow` utility: IBM Plex
  Mono 12px, tracked, uppercase, `muted`.
- Text links (`TextLink.astro`) are underlined, in `ink` with the underline at 40%, and turn
  `accent` on hover; the Contact email is one. Links in running text are `accent` and
  underlined. Buttons (`LinkButton.astro`) stay for the case study and the 404 page.
- A ledger row is one link: hovering anywhere on it turns the project name `accent`. The
  one-liner sits above the link so it can be selected.

## Sky

`Sky.astro` (in the layout) draws a cool radial wash from the top edge and 88 seeded stars over
the hero. `Horizon.astro` (in the hero, under the links) draws the limb of a warm-black planet:
a wide haze, a tighter limb light, the disc, and a 1.5px line, fading out through the featured
project's header. Both are `aria-hidden`, take no space in the flow, and scale with
`--sky-intensity`.

- **Gradients only.** No `filter: blur()` and no SVG `feGaussianBlur`: a 64px CSS blur behind
  the screenshot crashed WebKit's renderer in the phone tests, so the glow is radial gradients
  with their stops at the limb.
- The drawings are a fixed 2560px wide and centred, so the curve and the glow are the same size
  on every screen; narrower screens see the middle. The horizon's box is absolutely positioned
  with `top: auto`, so it follows the hero's real height on every screen but spans the viewport.
  Its fade mask is bounded to the drawing (`maskUnits="userSpaceOnUse"`), so WebKit never sizes
  the mask from the planet's full circle.
- The screenshot frame is opaque `surface` with an inner edge light and a soft shadow. It is not
  glass (see below), and nothing bright is ever behind it.

## Glass

Frosted glass is used on the header and the mobile menu only, never on content. This follows
Apple's "content first" guidance, and it's where a translucent layer earns its keep: the page
scrolls under it.

- `src/styles/glass.css` writes the filter out literally, `-webkit-` first. Safari before 18
  needs the prefix and ignores custom properties inside it.
- Astro builds with target `esnext`, so the CSS minifier would drop the prefix. `astro.config.ts`
  sets `build.cssTarget` to the supported browsers, and a dist test checks the prefix survives.
- Every fallback is opaque (`surface`): no `backdrop-filter` support, `prefers-reduced-transparency`,
  `prefers-contrast: more` and forced colors (system colours). An E2E test checks the last two.
- Nothing above the header may set `transform`, `filter`, `contain`, `perspective` or
  `will-change`: each one breaks `position: fixed` or the backdrop. An E2E test checks.
- **The menu sheet uses a heavier tint (0.92).** It's a popover, so it lives in the top layer,
  and WebKit draws no blur there. At 0.80 the page's heading showed through the menu links.
  To recheck on real devices in M4c: if iOS Safari does blur the sheet, 0.92 still looks right.

## Mobile menu

A Popover API sheet (`src/components/MobileMenu.astro`). Opening, closing, Esc, outside clicks
and returning focus to the Menu button all work without JavaScript. The sheet repeats the header
row (name on the left, Close where Menu was), so opening it reads as the header growing
downwards. A small script closes the sheet after an in-page link, since an in-page link doesn't
change the document.
