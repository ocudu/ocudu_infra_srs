# OCUDU Infra SRS Documentation

This directory contains the documentation infrastructure for the OCUDU Infra SRS project: a markdown-based documentation site (Docusaurus).

## Docker Services

```bash
docker compose -f docs/docker-compose.yml up
```

**Access:** [http://localhost:3000/ocudu_infra_srs](http://localhost:3000/ocudu_infra_srs)

## Docusaurus

### Automatically rendering of .md files in the repository

1. It collects all markdown files anywhere in the repository (except excluded paths)
2. A custom Docusaurus plugin [frontmatter-loader](./docusaurus/plugins/frontmatter-loader.js) automatically adds the required Docusaurus header (frontmatter).
3. Files appear in the sidebar and are searchable
4. README.md files become index pages for their directory

### More Features

- **Search**: Local search powered by `@easyops-cn/docusaurus-search-local`.
