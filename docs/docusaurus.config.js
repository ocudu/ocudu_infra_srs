// SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
// SPDX-License-Identifier: BSD-3-Clause-Open-MPI

const { themes } = require('prism-react-renderer');

const gitlabNamespace = 'ocudu';
const gitlabProject = 'ocudu_infra_srs';
const url = `https://${gitlabNamespace}.gitlab.io/`;
const baseUrl = process.env.BASE_URL || '/';
const version = process.env.CI_COMMIT_SHORT_SHA || 'main';
const gitlabRepoUrl = `https://gitlab.com/${gitlabNamespace}/${gitlabProject}`;
const versionUrl = `${gitlabRepoUrl}/-/tree/${version}`;

/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: 'OCUDU Infra SRS',
  tagline: 'SRS end-to-end tests and infrastructure for OCUDU',
  url: url,
  baseUrl: baseUrl,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  favicon: 'https://srs.io/wp-content/uploads/ocudu_color.png',
  organizationName: gitlabNamespace,
  projectName: gitlabProject,
  customFields: {
    versionUrl: versionUrl,
  },
  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  themes: ['@docusaurus/theme-mermaid'],
  themeConfig: {
    prism: {
      theme: themes.github,
      darkTheme: themes.dracula,
      defaultLanguage: 'bash',
      additionalLanguages: ['bash', 'shell-session', 'python', 'json', 'yaml'],
    },
    mermaid: {
      theme: {light: 'neutral', dark: 'dark'},
    },    
    navbar: {
      title: '',
      logo: {
        alt: 'OCUDU Logo',
        src: 'https://srs.io/wp-content/uploads/ocudu_color.png',
      },
      items: [
        {
          to: '/',
          position: 'left',
          label: 'Technical Documentation',
        },
        {
          href: 'https://ocudu.org',
          label: 'OCUDU Website',
          position: 'right',
        },
        {
          href: 'https://srs.io',
          label: 'SRS Website',
          position: 'right',
        },
        {
          href: gitlabRepoUrl,
          label: 'Gitlab',
          position: 'right',
        },
      ],
    },
    announcementBar: {
      id: 'wip',
      content:
        'This documentation is a work in progress!',
      backgroundColor: '#ddc36fff',
      textColor: '#091E42',
      isCloseable: false,
    },
    footer: {
      style: 'dark',
      links: [
        {
          title: 'More',
          items: [
            {
              label: 'OCUDU Website',
              href: 'https://ocudu.org',
            },
            {
              label: 'SRS Website',
              href: 'https://srs.io',
            },
            {
              label: 'Gitlab',
              href: gitlabRepoUrl,
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Software Radio Systems. | <a href="${versionUrl}" target="_blank" rel="noopener noreferrer">Version: ${version}</a>`,
    },
  },
  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },
  presets: [
    [
      '@docusaurus/preset-classic',
      {
        docs: {
          path: '../',
          routeBasePath: '/',
          include: ['**/*.md', '**/*.mdx'],
          exclude: [
            '**/node_modules/**',
            '**/.git/**',
            '**/.tox/**',
            '**/__pycache__/**',
            '**/.pytest_cache/**',
          ],
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: undefined,
          async sidebarItemsGenerator({ defaultSidebarItemsGenerator, ...args }) {
            const sidebarItems = await defaultSidebarItemsGenerator(args);

            // Flatten categories that don't have a README or index page
            function flattenCategories(items) {
              return items.flatMap(item => {
                if (item.type === 'category') {
                  // Check if category has a link (means it has README or _category_.yml with link)
                  if (!item.link && item.items) {
                    // No link means no README - flatten this category
                    console.log(`[sidebar] Flattening category without README: ${item.label}`);
                    return flattenCategories(item.items);
                  }
                  // Category has a link, keep it but process its children
                  if (item.items) {
                    item.items = flattenCategories(item.items);
                  }
                }
                return [item];
              });
            }

            // Sort items to put README files first
            function sortReadmeFirst(items) {
              return items.map(item => {
                // Recursively process category items
                if (item.type === 'category' && item.items) {
                  item.items = sortReadmeFirst(item.items);
                }
                return item;
              }).sort((a, b) => {
                // README files always come first
                const aIsReadme = a.id?.endsWith('/README') || a.id === 'README';
                const bIsReadme = b.id?.endsWith('/README') || b.id === 'README';

                if (aIsReadme && !bIsReadme) return -1;
                if (!aIsReadme && bIsReadme) return 1;

                // Otherwise maintain original order (use position if exists)
                return 0;
              });
            }

            const flattened = flattenCategories(sidebarItems);
            return sortReadmeFirst(flattened);
          },
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }
    ],
  ],
  plugins: [
    './plugins/link-filter-plugin.js',
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      {
        hashed: true,
        indexDocs: true,
        indexPages: true,
        indexBlog: false,
        docsRouteBasePath: '/',
      },
    ],
  ]
};
