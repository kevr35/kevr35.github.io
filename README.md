# Personal Website

This repository contains the [Hugo](https://gohugo.io/) source for [kevin-reiss.com](https://kevin-reiss.com/), a personal academic, writing, publication, and climbing website. It is built with the [PaperMod](https://github.com/adityatelange/hugo-PaperMod) theme and deployed automatically to **GitHub Pages** by a **GitHub Actions** workflow.

This README covers everything needed to run the site locally, edit content, understand the deployment pipeline in detail, and reuse this repository as a template for a similar site.

## Table of Contents

- [How the Site Works](#how-the-site-works)
- [Repository Layout](#repository-layout)
- [Local Development](#local-development)
- [Adding Content](#adding-content)
- [Publishing](#publishing)
- [How Deployment Works (GitHub Actions)](#how-deployment-works-github-actions)
- [Building a Similar Site From Scratch](#building-a-similar-site-from-scratch)
- [Documentation](#documentation)
- [Security](#security)

## How the Site Works

Hugo is a static site generator: Markdown files in [content/](content/) are combined with templates in [layouts/](layouts/) and the [themes/PaperMod](themes/PaperMod/) submodule to produce plain HTML/CSS/JS in `public/`. There is no server-side application code and no database — the deployed site is just static files served by GitHub Pages.

- **Content** lives as Markdown with YAML front matter under [content/](content/) (posts, publications, climbing routes).
- **Presentation** comes from the PaperMod theme, overridden/extended by project-specific templates in [layouts/](layouts/) and styles in [assets/css/extended/](assets/css/extended/).
- **Small interactive tools** (the publication and climbing entry editors) are plain client-side JavaScript pages under `/admin/`, built from [assets/js/publication-editor.js](assets/js/publication-editor.js) and [assets/js/climbing-editor.js](assets/js/climbing-editor.js), rendered by [layouts/publication-editor/single.html](layouts/publication-editor/single.html) and [layouts/climbing-editor/single.html](layouts/climbing-editor/single.html).
- **Build & deploy** happens entirely in [.github/workflows/hugo.yml](.github/workflows/hugo.yml): every push to `master` triggers a GitHub Actions run that installs Hugo, builds the site, and publishes it to GitHub Pages. There is no separate "hugo server" running in production — GitHub Pages just serves the static files that Hugo generated during the Actions run.

## Repository Layout

| Path | Purpose |
|---|---|
| [hugo.toml](hugo.toml) | Site configuration: base URL, theme, menus, math/markup support, social icons. |
| [content/](content/) | Markdown source for posts, publications, climbing routes, and admin editor pages. |
| [archetypes/](archetypes/) | Front-matter templates used by `hugo new`. |
| [layouts/](layouts/) | Project-specific Hugo templates that extend/override the theme (climbing list/single pages, publication list page, admin editors, partials). |
| [assets/](assets/) | CSS and JavaScript processed through Hugo Pipes (bundling/fingerprinting), including the editor JS. |
| [static/](static/) | Files copied verbatim into the deployed site (favicons, resume PDF, route images, notebooks, previews). |
| [data/climbing/locations.yaml](data/climbing/locations.yaml) | Shared crag/region coordinates referenced by climbing route front matter. |
| [themes/PaperMod/](themes/PaperMod/) | Git submodule for the PaperMod theme; not edited directly for site changes. |
| [tools/climbing_editor.py](tools/climbing_editor.py) | Local Python helper server that writes new climbing entries (and resized photos) directly into the repo. |
| [.github/workflows/hugo.yml](.github/workflows/hugo.yml) | GitHub Actions workflow that builds the site with Hugo and deploys it to GitHub Pages. |
| `public/` | Generated output of `hugo`/`hugo server`. Git-ignored; never commit it. |

## Local Development

Requirements:

- [Hugo Extended](https://gohugo.io/installation/) (the workflow currently pins `0.146.0`; use a matching or newer extended version locally).
- Git, with submodule support.
- Optional: [Dart Sass](https://sass-lang.com/dart-sass/) if you add SCSS that needs external compilation (PaperMod itself does not require it).
- Optional: Python 3 with [Pillow](https://pypi.org/project/Pillow/) for the local climbing editor (`pip install Pillow`).

Clone and run:

```powershell
git clone https://github.com/kevr35/kevr35.github.io.git
cd kevr35.github.io
git submodule update --init --recursive
hugo server -D
```

Open `http://localhost:1313/` while the server is running. The `-D` flag includes draft content and Hugo live-reloads on file changes; stop the server with `Ctrl+C`.

Before committing changes, run a production-equivalent build to catch template/asset errors:

```powershell
hugo --minify
```

The generated `public/` directory is git-ignored and should never be committed — GitHub Actions regenerates it on every deploy.

## Adding Content

Create content with the appropriate archetype:

```powershell
hugo new posts/my-post.md
hugo new publications/my-paper.md --kind publication
hugo new climbing/my-route.md --kind climbing-route
```

Edit the generated Markdown file, review it locally, and set `draft: false` when it is ready to publish.

### Local editing mode

For the fastest workflow, run one script that serves all three moderator tools with direct-save into the repository (no manual download/move step):

```powershell
python tools/site_editor.py
```

This rebuilds the site once, then serves `http://127.0.0.1:8000/admin/climbing/`, `/admin/publications/`, and `/admin/notebooks/`. Each page detects it is running locally and swaps its "Download Markdown" button for a "Save directly to content/..." button that writes the file and reruns `hugo --minify`. The same pages are also hosted at `kevin-reiss.com` for editing from any browser, where they fall back to downloading a file to move into the repository by hand.

### Publications

The browser-based publication editor is available at [`/admin/publications/`](https://kevin-reiss.com/admin/publications/). Enter a DOI or paper URL to fetch metadata, or paste BibTeX/load a `.bib` file directly. Review the imported fields and choose whether to include an image. When enabled, the image options are a publisher favicon derived from the publisher URL or a local preview image path; uncheck the image checkbox to omit the image. Move the Markdown file into `content/publications/` and any local image into `static/previews/`, review them, and commit them manually. The editor cleans the stored BibTeX down to conventional citation fields.

DOI lookup uses Crossref, then follows the DOI redirect when possible so publisher-specific icons can be used. The editor also searches arXiv by title and fills the arXiv field when it finds a close match. URL lookup attempts to read page metadata and embedded BibTeX, but publisher pages and external APIs may block browser requests with CORS; in that case, paste the BibTeX manually.

The editor does not authenticate, write to GitHub, or publish changes. It contains no repository credentials and must not be given a GitHub token.

### Climbing

Climbing entries follow the Mountain Project hierarchy: `region` (for example, Red River Gorge), `location` (the crag, such as Muir Valley), and `area` (the wall or sector, such as Solarium). Shared crag coordinates live once in `data/climbing/locations.yaml`; route files store the hierarchy names. The map shows a region only when it contains multiple crags; a region with one crag shows that crag directly.

Climbing pages send a `noimageindex` directive, and future route photos should be stored under `/route-images/`, which is disallowed in `robots.txt`. These are crawler instructions, not access control: public images can still be viewed, copied, or indexed by systems that ignore them.

The hosted climbing editor is available at [`/admin/climbing/`](https://kevin-reiss.com/admin/climbing/) and downloads Markdown. It also accepts multiple route photos; local mode resizes them to web-sized JPEGs under `static/route-images/<route>/` and writes `thumbnail`/`photos` metadata. For the faster local workflow, run:

```powershell
python tools/site_editor.py
```

Open `http://127.0.0.1:8000/admin/climbing/`. Paste a Mountain Project route URL or search Mountain Project in a new tab, review and correct every field, optionally add a YouTube URL, and click **Save directly to content/climbing/**. The local tool writes the Markdown file into the repository and rebuilds Hugo. Mountain Project may block browser scraping, so every field remains editable.

### Notebooks

Notebooks are not hosted on this site; each one must first be published to the Wolfram Cloud (`CloudDeploy` in Mathematica, with public sharing enabled) so it has a shareable "Embed Code" URL. The browser-based notebook editor is available at [`/admin/notebooks/`](https://kevin-reiss.com/admin/notebooks/): paste that embed URL, it derives a default title and filename from the link, edit the description/tags/date, and either click **Save directly to content/notebooks/** (local editing mode) or download a Hugo Markdown file to move there by hand. The editor does not authenticate or publish anything itself.

## Publishing

The production branch is `master`. GitHub Pages is *not* built from a branch directly — a GitHub Actions workflow builds the site and deploys the generated artifact, so `master` only needs to hold the Hugo *source*, never a built `public/` directory:

```powershell
git status
git add <changed-files>
git commit -m "Describe the change"
git push origin master
```

Pushing to `master` triggers the `Deploy Hugo site to Pages` workflow described in detail below. Check the repository's **Actions** tab if the deployment does not appear online after a few minutes.

## How Deployment Works (GitHub Actions)

The full workflow lives in [.github/workflows/hugo.yml](.github/workflows/hugo.yml). This section explains each part so it can be reused or adapted for another Hugo project.

### Triggers

```yaml
on:
  push:
    branches: ["master"]
  workflow_dispatch:
```

The workflow runs automatically on every push to `master`, and can also be triggered manually from the **Actions** tab (`workflow_dispatch`) — useful for re-deploying without a code change (for example, after changing a GitHub Pages setting).

### Permissions and concurrency

```yaml
permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: "pages"
  cancel-in-progress: false
```

- `permissions` grants the workflow's automatically-provisioned `GITHUB_TOKEN` just enough scope to read the repo, write to GitHub Pages, and mint an OIDC token (`id-token: write`) for the Pages deployment action — no personal access token or secret is needed.
- `concurrency` serializes deployments under a single `pages` group so two pushes in quick succession don't race each other, while `cancel-in-progress: false` lets an in-flight deployment finish rather than being killed by a newer push (the newer one queues instead).

### Build job

Runs on `ubuntu-latest` and performs these steps in order:

1. **Install Hugo CLI** — downloads the exact **Hugo Extended** `.deb` package pinned by the `HUGO_VERSION` env var (`0.146.0`) directly from Hugo's GitHub releases and installs it with `dpkg`. Pinning the version keeps local builds and CI builds reproducible; the "Extended" edition is required because it bundles the SCSS/Sass compiler that PaperMod (and many themes) depend on.
2. **Install Dart Sass** — installs the `dart-sass` snap as a companion Sass compiler for any styles that need it beyond Hugo's built-in support.
3. **Checkout** (`actions/checkout@v4`) — clones the repository with `submodules: recursive`, so the `themes/PaperMod` submodule content is checked out too (without this the theme directory would be empty and the build would fail), and `fetch-depth: 1` for a shallow, faster clone. Because `enableGitInfo = true` is set in [hugo.toml](hugo.toml), Hugo reads Git history to populate "last modified" dates; a shallow clone still provides the latest commit's data for that.
4. **Setup Pages** (`actions/configure-pages@v5`) — queries the GitHub Pages API for this repository and returns outputs (notably `steps.pages.outputs.base_url`) describing the canonical URL the site will be served from, so the build doesn't have to hard-code it.
5. **Install Node.js dependencies** — conditionally runs `npm ci` only if a `package-lock.json`/`npm-shrinkwrap.json` is present. This repo currently has neither, so the step is a no-op; it exists so the workflow keeps working unmodified if PostCSS/Node-based tooling is added later.
6. **Build with Hugo** — runs `hugo --minify --baseURL "<pages-base-url>/"`, with `HUGO_ENVIRONMENT=production` (lets templates branch on environment, e.g. to disable draft content or enable analytics) and `HUGO_CACHEDIR` pointed at the runner's temp directory (speeds up repeated builds via Hugo's resource cache). The `--baseURL` override ensures generated absolute URLs match wherever Pages is actually serving from, even if that differs slightly from the `baseURL` in `hugo.toml`.
7. **Upload artifact** (`actions/upload-pages-artifact@v3`) — packages the `./public` directory (Hugo's output) as a Pages deployment artifact, which is the hand-off point between the build job and the deploy job.

### Deploy job

```yaml
deploy:
  environment:
    name: github-pages
    url: ${{ steps.deployment.outputs.page_url }}
  needs: build
  steps:
    - uses: actions/deploy-pages@v4
```

This job `needs: build`, so it only runs after a successful build, and it targets the special `github-pages` GitHub environment (which is what shows the live deployment URL and history on the repo's **Environments** page). `actions/deploy-pages@v4` takes the artifact uploaded by the build job and publishes it to GitHub Pages using the OIDC token granted by `id-token: write` — no manual token or `gh-pages` branch push is involved.

### End-to-end flow

```mermaid
flowchart LR
    A[git push origin master] --> B[hugo.yml triggers]
    B --> C[build job: install Hugo + Dart Sass]
    C --> D[checkout repo + submodules]
    D --> E[hugo --minify --baseURL ...]
    E --> F[upload public/ as Pages artifact]
    F --> G[deploy job: actions/deploy-pages]
    G --> H[Live at kevin-reiss.com]
```

## Building a Similar Site From Scratch

To reuse this repository as a template for another Hugo + PaperMod + GitHub Pages site:

1. **Create a new repository** on GitHub (it does not need to be named `<user>.github.io`; that naming is only required for a user/organization root site).
2. **Scaffold Hugo locally**:
   ```powershell
   hugo new site my-site
   cd my-site
   git init
   ```
3. **Add PaperMod as a submodule** (or another theme of your choice):
   ```powershell
   git submodule add https://github.com/adityatelange/hugo-PaperMod.git themes/PaperMod
   ```
4. **Configure `hugo.toml`**: set `baseURL` to your future Pages URL, `theme = 'PaperMod'`, menus, and any params you need (see this repo's [hugo.toml](hugo.toml) for a working example, including math support via `markup.goldmark.extensions.passthrough`).
5. **Copy the workflow file**: add [.github/workflows/hugo.yml](.github/workflows/hugo.yml) to your repository unchanged, updating `HUGO_VERSION` if you want a different pinned Hugo release.
6. **Enable GitHub Pages via Actions**: in the repository's **Settings → Pages**, set **Source** to **GitHub Actions** (not "Deploy from a branch"). No `gh-pages` branch or Pages-specific secrets are required — the workflow's `GITHUB_TOKEN` permissions handle it.
7. **Push to `master`** (or update the workflow's `branches:` filter to match your default branch, e.g. `main`). The first push triggers the workflow, which builds and publishes the site; watch progress under the **Actions** tab, and find the live URL under **Settings → Pages** or the `github-pages` environment.
8. **Add content types as needed**: create `archetypes/*.md` templates and matching `layouts/` templates the same way this repo does for `publications` and `climbing` (see [archetypes/publication.md](archetypes/publication.md), [archetypes/climbing-route.md](archetypes/climbing-route.md), and their corresponding `layouts/publications/` and `layouts/climbing/` templates) if you want custom content types beyond ordinary posts.
9. **Optional admin tools**: the `/admin/publications/`, `/admin/climbing/`, and `/admin/notebooks/` pages in this repo are static pages with client-side JavaScript ([assets/js/publication-editor.js](assets/js/publication-editor.js), [assets/js/climbing-editor.js](assets/js/climbing-editor.js), [assets/js/notebook-editor.js](assets/js/notebook-editor.js)) rendered through dedicated layout types ([layouts/publication-editor/single.html](layouts/publication-editor/single.html), [layouts/climbing-editor/single.html](layouts/climbing-editor/single.html), [layouts/notebook-editor/single.html](layouts/notebook-editor/single.html)). Hosted, they run entirely in the visitor's browser, hold no credentials, and only download files for the site owner to manually commit. Run locally via [tools/site_editor.py](tools/site_editor.py) — a small `http.server` subclass — the same pages instead save Markdown directly into `content/` and rerun `hugo --minify`, detected client-side via `window.location.hostname` — a pattern worth copying for any "generate front matter for me" tool on a statically hosted site.

## Documentation

See [website-runbook.md](website-runbook.md) for detailed workflows, front-matter references, troubleshooting, submodule guidance, Wolfram notebook notes, and public-information safety rules.

## Security

Never commit passwords, API tokens, private keys, cookies, unpublished manuscripts, or other private data. Hugo content and static files are published as part of the website. The GitHub Actions workflow uses only the automatically-provisioned `GITHUB_TOKEN`; no repository secrets are required for deployment.