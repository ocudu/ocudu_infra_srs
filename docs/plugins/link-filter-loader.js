// SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
// SPDX-License-Identifier: BSD-3-Clause-Open-MPI

const path = require('path');

module.exports = function linkFilterLoader(source) {
    const filePath = this.resourcePath;
    const options = this.getOptions();
    const versionUrl = options?.versionUrl;
    const docsPath = options?.docsPath;

    // Filter out links to non-markdown files (keep only links to .md/.mdx files and directories)
    // This regex matches markdown links: [text](path)
    // Note: This preserves HTML anchor tags like <a id="..."></a> which are used for linking within documents
    const filteredSource = source.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, link) => {

        // Keep external links (http://, https://, mailto:, etc.)
        if (/^[a-z]+:/i.test(link)) {
            return match;
        }

        // Keep anchor links (#section)
        if (link.startsWith('#')) {
            return match;
        }

        // Keep image links (png, jpg, jpeg, gif, svg, etc.)
        if (/\.(png|jpe?g|gif|svg|webp|bmp|ico)$/i.test(link)) {
            return match;
        }

        // Keep links to markdown files (including with anchors like file.md#section)
        if (/\.mdx?(#|$)/i.test(link)) {
            return match;
        }

        // Keep links to directories (no extension or ends with /)
        if (!path.extname(link) || link.endsWith('/')) {
            return match;
        }

        if (versionUrl && docsPath) {
            // Resolve the absolute path of the linked file
            const currentDir = path.dirname(filePath);
            const absoluteTargetPath = path.resolve(currentDir, link);

            // Get relative path from docs root
            const relativePath = path.relative(docsPath, absoluteTargetPath);

            // Create GitLab blob URL (assuming main branch)
            const gitlabLink = `${versionUrl}/${relativePath}`;

            console.log(`[link-filter-loader] Converting link: ${link} -> ${gitlabLink} in ${filePath}`);
            return `[${text}](${gitlabLink})`;
        }

        // Remove link to non-markdown file, keep only the text
        console.log(`[link-filter-loader] Filtering out link: ${link} in ${filePath}`);
        return text;

    });

    return filteredSource;
};
