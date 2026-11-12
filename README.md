# UTOPI project page

Source of the project page for *UTOPI: Efficient Egocentric Long-Video Understanding in AR via
User-Guided Token Pre-Compression* (NeurIPS 2026).

Next.js 15 static export + Tailwind CSS. Pushing to `main` builds the site with GitHub Actions and
publishes it to GitHub Pages; `basePath` is derived from the repository name, so the same code serves
`<owner>.github.io/<repo>/` for any repository.

```bash
npm install
npm run dev     # http://localhost:3000
npm run build   # static export to out/
```

All text, links, numbers and figure paths live in `src/lib/content.ts`. Figures are in
`public/paper-assets/`. Demo videos, when added, should be uploaded as GitHub Release assets and
referenced from `demoClips` in `content.ts` so they do not enter the git history.

One-time repository setup: Settings > Pages > Build and deployment > Source: GitHub Actions.
