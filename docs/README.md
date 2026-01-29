# Documentation

The documentation for the OCUDU Infra SRS project is built with [Docusaurus](https://docusaurus.io/). It automatically collects all markdown files across the repository and renders them into a searchable, navigable website.

## Generate Documentation Locally

```bash
docker compose -f docs/docker-compose.yml up
```

**Access:** [http://localhost:3000](http://localhost:3000)

## Docusaurus Details

### Automatic Markdown Rendering

The documentation system automatically processes all `.md` files in the repository:

1. Gathers all markdown files from anywhere in the repository (excluding specified paths)
2. A custom Docusaurus plugin ([link-filter-loader](./plugins/link-filter-loader.js)) automatically converts links to valid references in the webpage.
3. Files automatically appear in the sidebar navigation
4. `README.md` files become index pages for their respective directories

### Additional Features

- **Local Search**: Powered by `@easyops-cn/docusaurus-search-local` for fast, client-side search
