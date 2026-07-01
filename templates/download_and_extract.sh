#!/bin/sh

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

# Downloads and extracts the packages listed in the DOWNLOAD_URLS_PRE_BUILD
# environment variable (one per line, optional wget options followed by the
# URL) into the current directory. Nested tar.gz files found inside the
# extracted archive are extracted as well.

echo "${DOWNLOAD_URLS_PRE_BUILD}" | while IFS= read -r line; do
  # Skip empty lines
  [ -z "$line" ] && continue

  # Parse line: extract wget options and URL
  # Assume the last token is the URL, everything before are wget options
  url=$(echo "$line" | awk '{print $NF}')
  wget_opts=$(echo "$line" | sed "s|${url}$||" | xargs)

  # Skip if a previous run (or a restored cache) already extracted this package
  filename=$(basename "$url")
  extract_dir="${filename%.tar.gz}"
  if [ -d "$extract_dir" ] && [ -n "$(ls -A "$extract_dir" 2>/dev/null)" ]; then
    echo "Already downloaded and extracted, skipping: $extract_dir"
    continue
  fi

  echo "Downloading: $url"
  # Download file
  max_attempts=10
  attempt=1
  while [ $attempt -le $max_attempts ]; do
    wget $wget_opts "$url" -O "$filename" > /dev/null 2>&1 && break || true
    sleep 10
    echo "Retrying... (attempt $attempt/$max_attempts)"
    attempt=$((attempt + 1))
  done
  if [ $attempt -gt $max_attempts ]; then
    echo "Error: Failed to download $url after $max_attempts attempts"
    exit 1
  fi
  echo "Downloaded to: $filename"

  # Extract main tar.gz file. Amarisoft packages wrap everything in a single
  # top-level directory (e.g. "2026-06-12/install.sh", "2026-06-12/trx_uhd-2026-06-12.tar.gz");
  # strip it so install.sh and the component tar.gz files land directly in extract_dir.
  mkdir -p "$extract_dir"
  tar -zxf "$filename" -C "$extract_dir" --strip-components=1

  # Extract only the trx_uhd driver tar.gz
  for nested_file in "$extract_dir"/trx_uhd*.tar.gz; do
    if [ -f "$nested_file" ]; then
      tar -zxf "$nested_file" -C "$extract_dir/"
    fi
  done
  echo "Extracted to: $extract_dir"

done
