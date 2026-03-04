#!/usr/bin/env python3

# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""Add copyright headers to generated protobuf files."""

from datetime import datetime
from pathlib import Path


def add_header(file_path: Path) -> None:
    """Add copyright header to a file if it doesn't already have one."""
    year = datetime.now().year
    header = f"""# SPDX-FileCopyrightText: Copyright (C) 2021-{year} Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
    
    content = file_path.read_text()
    
    # Skip if header already exists
    if "Copyright 2021-" in content:
        return
    
    # Add header
    file_path.write_text(header + content)
    print(f"Added header to {file_path}")


def main() -> None:
    """Find and process all generated protobuf files."""
    protocol_dir = Path(__file__).parent.parent / "src" / "retina" / "protocol"
    
    # Find all _pb2*.py files
    for pattern in ["*_pb2.py", "*_pb2_grpc.py", "*_pb2.pyi"]:
        for file_path in protocol_dir.glob(pattern):
            add_header(file_path)


if __name__ == "__main__":
    main()
