# Kevin Reiss Website

This repository contains the Hugo source for [kevin-reiss.com](https://kevin-reiss.com/), a personal academic, writing, publication, and climbing website.

## Local Development

Requirements: Hugo Extended and Git.

```powershell
git clone https://github.com/kevr35/kevr35.github.io.git
cd kevr35.github.io
git submodule update --init --recursive
hugo server -D
```

Open `http://localhost:1313/` while the server is running. Draft content is included during local development.

Before committing changes, run:

```powershell
hugo --minify
```

The generated `public/` directory is ignored and should not be committed.

## Adding Content

Create content with the appropriate archetype:

```powershell
hugo new posts/my-post.md
hugo new publications/my-paper.md --kind publication
hugo new climbing/my-route.md --kind climbing-route
```

Edit the generated Markdown file, review it locally, and set `draft: false` when it is ready to publish.

### Publications

The browser-based publication editor is available at [`/admin/publications/`](https://kevin-reiss.com/admin/publications/). Enter a DOI or paper URL to fetch metadata, or paste BibTeX/load a `.bib` file directly. Review the imported fields and choose whether to include an image. When enabled, the image options are a publisher favicon derived from the publisher URL or a local preview image path; uncheck the image checkbox to omit the image. Move the Markdown file into `content/publications/` and any local image into `static/previews/`, review them, and commit them manually. The editor cleans the stored BibTeX down to conventional citation fields.

DOI lookup uses Crossref, then follows the DOI redirect when possible so publisher-specific icons can be used. The editor also searches arXiv by title and fills the arXiv field when it finds a close match. URL lookup attempts to read page metadata and embedded BibTeX, but publisher pages and external APIs may block browser requests with CORS; in that case, paste the BibTeX manually.

The editor does not authenticate, write to GitHub, or publish changes. It contains no repository credentials and must not be given a GitHub token.

### Climbing

Climbing entries support bouldering and sport routes, indoor or outdoor settings, grades, dates, locations, Mountain Project links, YouTube embeds, and personal notes. Use the generated route archetype and fill in its front matter.

The local climbing editor is available at [`/admin/climbing/`](https://kevin-reiss.com/admin/climbing/). Paste a Mountain Project route URL or search Mountain Project in a new tab, import what the page exposes, correct the grade or any other field, optionally add a YouTube URL, and download the Markdown file into `content/climbing/`. Mountain Project may block browser scraping, so every field remains editable.

## Publishing

The production branch is `master`:

```powershell
git status
git add <changed-files>
git commit -m "Describe the change"
git push origin master
```

GitHub Actions builds and deploys the site to GitHub Pages after a successful push. Check the repository's **Actions** tab if the deployment does not appear online.

## Documentation

See [website-runbook.md](website-runbook.md) for detailed workflows, troubleshooting, submodule guidance, Wolfram notebook notes, and public-information safety rules.

## Security

Never commit passwords, API tokens, private keys, cookies, unpublished manuscripts, or other private data. Hugo content and static files are published as part of the website.