/*
 *
 * Copyright 2021-2026 Software Radio Systems Limited
 *
 * By using this file, you agree to the terms and conditions set
 * forth in the LICENSE file which can be found at the top level of
 * the distribution.
 *
 */

const path = require('path');

module.exports = function linkFilterLoader(source) {
    const filePath = this.resourcePath;

    // Filter out links to non-markdown files (keep only links to .md/.mdx files and directories)
    // This regex matches markdown links: [text](path)
    // Note: This preserves HTML anchor tags like <a id="..."></a> which are used for linking within documents
    const filteredSource = source.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (match, text, link) => {

        // Custom exception for files without extension
        if (link === './LICENSE') {
            return text;
        }

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

        // Remove link to non-markdown file, keep only the text
        console.log(`[link-filter-loader] Filtering out link: ${link} in ${filePath}`);
        return text;
    });

    return filteredSource;
};
