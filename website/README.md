# FlashPilot website

The public landing page for FlashPilot. Static site, no runtime, no server.

- **Stack:** Vite 6 + React 19 + TypeScript
- **Output:** `dist/` — plain HTML, CSS, JS and images
- **Deploy:** GitHub Pages, via `.github/workflows/pages.yml`

## Commands

```bash
npm install       # once
npm run dev       # local dev server on http://localhost:5173
npm run build     # type check + production build into dist/
npm run preview   # serve the built site on http://localhost:4173
npm run typecheck # type check only
```

Node 18.19 or newer is enough — the dependency tree is pinned to versions that
support it.

## How it is wired

| Path | What it holds |
|---|---|
| `src/App.tsx` | Section order |
| `src/components/` | One component per section |
| `src/data/protocols.ts` | The handshake panel — packet codes from the Rust core |
| `src/data/site.ts` | Every number and table on the page |
| `src/styles/tokens.css` | Colours, type, spacing and radii, copied from `python/gui/theme.py` |
| `src/styles/global.css` | Base layer and component styles |
| `public/img/` | Screenshots copied from `docs/` |

## Rules for editing

- **Keep the numbers honest.** Flow counts, job counts and catalogue sizes come
  from `src/flows.rs` and `python/gui/supported_devices.json`. If the source
  changes, update `src/data/site.ts` in the same commit.
- **Keep the protocol codes honest.** The handshake panel quotes real packet
  codes out of `src/sam_download.rs`, `src/mtk.rs`, `src/qualcomm/` and
  `src/spd.rs`. Never invent a command that the bridge does not send.
- **Keep the palette honest.** The site uses the app's live theme tokens. A new
  colour needs a token in `python/gui/theme.py` first.
- **Do not claim a version.** The application version is not settled yet, so the
  site carries no version number.

## Publishing

The workflow publishes on every push to `dev` that touches `website/`. For it
to run, Pages must be set to **GitHub Actions** as the source in the repository
settings. `vite.config.ts` uses `base: './'`, so the same build works under a
project path, a custom domain, or a plain file server.
