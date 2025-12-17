#!/usr/bin/env python3
#
# Copyright 2021-2025 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""Add copyright headers to generated protobuf files."""

from datetime import datetime
from pathlib import Path


def add_header(file_path: Path) -> None:
    """Add copyright header to a file if it doesn't already have one."""
    year = datetime.now().year
    header = f"""#
# Copyright 2021-{year} Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

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
