// SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
// SPDX-License-Identifier: BSD-3-Clause-Open-MPI

const path = require('path');

module.exports = function linkFilterPlugin(context, options) {
    return {
        name: 'link-filter-plugin',

        getPathsToWatch() {
            // Watch for markdown files
            return [path.resolve(context.siteDir, '../**/*.{md,mdx}')];
        },

        async loadContent() {
            return {};
        },

        configureWebpack(config) {
            const loaderPath = path.resolve(__dirname, 'link-filter-loader.js');
            const versionUrl = context.siteConfig.customFields?.versionUrl || null;

            return {
                module: {
                    rules: [
                        {
                            test: /\.mdx?$/,
                            include: path.resolve(__dirname, '../..'),
                            exclude: [
                                /node_modules/,
                                path.resolve(__dirname, '..'),
                            ],
                            enforce: 'pre',
                            use: [{
                                loader: loaderPath,
                                options: {
                                    versionUrl: versionUrl,
                                    docsPath: path.resolve(context.siteDir, '../'),
                                }
                            }],
                        },
                    ],
                },
            };
        },
    };
};
