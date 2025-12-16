const { themes } = require('prism-react-renderer');

const gitlab_namespace = 'softwareradiosystems';
const gitlab_project = 'ocudu_infra_srs';
const url = `https://${gitlab_namespace}.gitlab.io/`;
const baseUrl = process.env.BASE_URL || '/';
const version = process.env.CI_COMMIT_SHORT_SHA || 'local';
const gitlab_repo_url = `https://gitlab.com/${gitlab_namespace}/${gitlab_project}`;

const versionLink = version !== 'local'
  ? `<a href="${gitlab_repo_url}/-/tree/${version}" target="_blank" rel="noopener noreferrer">Version: ${version}</a>`
  : `Version: ${version}`;

/** @type {import('@docusaurus/types').DocusaurusConfig} */
module.exports = {
  title: 'OCUDU Infra SRS',
  tagline: 'SRS end-to-end tests and infrastructure for OCUDU',
  url: url,
  baseUrl: baseUrl,
  onBrokenLinks: 'throw',
  onBrokenAnchors: 'throw',
  favicon: 'https://srs.io/wp-content/uploads/ocudu_color.png',
  organizationName: gitlab_namespace,
  projectName: gitlab_project,
  customFields: {
    version: version,
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
          href: gitlab_repo_url,
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
              href: gitlab_repo_url,
            },
          ],
        },
      ],
      copyright: `Copyright © ${new Date().getFullYear()} Software Radio Systems. | ${versionLink}`,
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
            '**/docs/**',
            '**/.tox/**',
            '**/__pycache__/**',
            '**/.pytest_cache/**',
          ],
          sidebarPath: require.resolve('./sidebars.js'),
          editUrl: undefined,
        },
        blog: false,
        theme: {
          customCss: require.resolve('./src/css/custom.css'),
        },
      }
    ],
  ],
  plugins: [
    './plugins/inject-frontmatter-plugin.js',

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
