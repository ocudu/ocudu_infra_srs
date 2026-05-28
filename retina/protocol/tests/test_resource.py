# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

"""
Unit tests for resource module functionality.
"""

import tempfile
import unittest
from pathlib import Path

import yaml

from retina.protocol.resource import (
    Core,
    License,
    Ru,
    Ue,
    API,
    dump_resource_list_to_file,
    load_resources_from_file,
)


class TestResourceFileFunctions(unittest.TestCase):
    """Test cases for resource file operations."""

    def test_dump_resource_list_to_file(self):
        """Test dumping resource list to YAML file."""
        core = Core(address="10.45.0.1", port=38412, mask=24)
        api = API(address="localhost", port=8080)
        resources = [core, api]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            temp_path = temp_file.name

            dump_resource_list_to_file(resources, temp_path)

            # Verify file was created
            self.assertTrue(Path(temp_path).exists())

            # Load and verify content
            with open(temp_path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)

            # Should be a generator that was dumped, so we need to convert to list
            self.assertIsInstance(content, list)
            self.assertEqual(len(content), 2)

    def test_dump_resource_creates_directories(self):
        """Test that dump_resource_list_to_file creates parent directories."""
        core = Core(address="192.168.1.1", port=38412, mask=24)

        with tempfile.TemporaryDirectory() as temp_dir:
            nested_path = Path(temp_dir) / "nested" / "folder" / "resources.yml"

            dump_resource_list_to_file([core], str(nested_path))

            self.assertTrue(nested_path.exists())

    def test_load_resources_from_file_success(self):
        """Test loading resources from a valid YAML file."""
        # Create test YAML content
        test_resources = [
            {"address": "192.168.1.1", "port": 38412, "mask": 24, "type": "Core"},
            {"address": "localhost", "port": 8080, "type": "API"},
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            yaml.dump(test_resources, temp_file)
            temp_path = temp_file.name

            result = load_resources_from_file(temp_path)

            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], Core)
            self.assertIsInstance(result[1], API)
            self.assertEqual(result[0].address, "192.168.1.1")
            self.assertEqual(result[1].port, 8080)

    def test_load_resources_from_nonexistent_file(self):
        """Test loading resources from non-existent file raises FileNotFoundError."""
        with self.assertRaises(FileNotFoundError) as context:
            load_resources_from_file("/nonexistent/path/file.yml")

    def test_load_resources_from_directory(self):
        """Test loading resources when path points to directory raises FileNotFoundError."""
        with tempfile.TemporaryDirectory() as temp_dir:
            with self.assertRaises(FileNotFoundError) as context:
                load_resources_from_file(temp_dir)

    def test_load_resources_invalid_yaml_structure(self):
        """Test loading resources from YAML with invalid structure."""
        # Create YAML that's not a list
        invalid_content = {"address": "192.168.1.1", "type": "License"}

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            yaml.dump(invalid_content, temp_file)
            temp_path = temp_file.name

            with self.assertRaises(ValueError) as context:
                load_resources_from_file(temp_path)

    def test_load_resources_with_path_object(self):
        """Test loading resources using Path object instead of string."""
        test_resources = [{"address": "192.168.1.1", "type": "License", "args": ""}]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            yaml.dump(test_resources, temp_file)
            temp_path = Path(temp_file.name)

            result = load_resources_from_file(temp_path)

            self.assertEqual(len(result), 1)
            self.assertIsInstance(result[0], License)

    def test_dump_load_consistency(self):
        """Test that dump and load operations are consistent"""
        # Create some resources
        core = Core(address="192.168.1.1", port=38412, mask=24)
        api = API(address="localhost", port=8080)
        ue = Ue(
            model="Test Phone", serial_id="12345", imsi="001010123456789", k="key", amf="amf", opc="opc", adb_key="adb"
        )

        original_resources = [core, api, ue]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            temp_path = temp_file.name

            # Dump resources to file
            dump_resource_list_to_file(original_resources, temp_path)

            # Load resources from file
            loaded_resources = load_resources_from_file(temp_path)

            # Verify they match
            self.assertEqual(len(loaded_resources), 3)

            # Check each resource type and content
            core_loaded = next(r for r in loaded_resources if isinstance(r, Core))
            api_loaded = next(r for r in loaded_resources if isinstance(r, API))
            ue_loaded = next(r for r in loaded_resources if isinstance(r, Ue))

            self.assertEqual(core_loaded, core)
            self.assertEqual(api_loaded, api)
            self.assertEqual(ue_loaded, ue)

    def test_dump_load_consistency_with_nested_structures(self):
        """Test dumping and loading Ru resource."""
        ru = Ru(
            model="fake-ru",
            network_interface=["0000:51:01.0"],
            ru_mac_address=["B8:CE:F6:38:25:4B"],
            du_mac_address=["00:33:22:33:00:11"],
            vlan_tag_up=["1"],
            vlan_tag_cp=["1"],
            prach_port_id="[8, 9]",
            dl_port_id="[0, 1, 2, 3]",
            ul_port_id="[0, 1]",
        )

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml") as temp_file:
            temp_path = temp_file.name

            # Dump resources to file
            dump_resource_list_to_file([ru], temp_path)

            # Load resources from file
            loaded_resources = load_resources_from_file(temp_path)

            # Verify they match
            self.assertEqual(len(loaded_resources), 1)
            self.assertIsInstance(loaded_resources[0], Ru)
            self.assertEqual(loaded_resources[0], ru)


if __name__ == "__main__":
    unittest.main()
