# Documentation

The documentation for the OCUDU Infra SRS project is built with Docusaurus. It collects all markdown files across the repo and render them into a website.

## Generate the documentation locally using Docker

```bash
docker compose -f docs/docker-compose.yml up
```

**Access:** [http://localhost:3000](http://localhost:3000)

## Docusaurus Details

### Automatically rendering of .md files in the repository

1. It collects all markdown files anywhere in the repository (except excluded paths)
2. A custom Docusaurus plugin [frontmatter-loader](./plugins/frontmatter-loader.js) automatically adds the required Docusaurus header (frontmatter).
3. Files appear in the sidebar and are searchable
4. README.md files become index pages for their directory

### More Features

- **Search**: Local search powered by `@easyops-cn/docusaurus-search-local`.
