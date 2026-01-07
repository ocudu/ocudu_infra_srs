#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

"""
Unit tests for ResourceManager class.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch


from retina.agent.app.resource_manager import AvailableResources, ResourceManager
from retina.protocol.resource import API, Core, Ue


class TestAvailableResources(unittest.TestCase):
    """Test cases for AvailableResources dataclass."""

    def test_available_resources_initialization(self):
        """Test that AvailableResources initializes with None values."""
        resources = AvailableResources()

        self.assertIsNone(resources.remote)
        self.assertIsNone(resources.core)
        self.assertIsNone(resources.api)
        self.assertIsNone(resources.license)
        self.assertIsNone(resources.ue)
        self.assertIsNone(resources.sdr)
        self.assertIsNone(resources.ru)

    def test_available_resources_with_values(self):
        """Test AvailableResources with actual resource objects."""
        core = Core(address="192.168.1.1", port=8080, mask=24)
        api = API(address="localhost", port=8080)

        resources = AvailableResources(core=core, api=api)

        self.assertEqual(resources.core, core)
        self.assertEqual(resources.api, api)
        self.assertIsNone(resources.remote)  # Other fields should remain None


class TestResourceManager(unittest.TestCase):
    """Test cases for ResourceManager class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Reset the class variable before each test
        ResourceManager._available_resources = None

    def tearDown(self):
        """Clean up after each test method."""
        # Reset the class variable after each test
        ResourceManager._available_resources = None

    def test_get_resources_before_loading(self):
        """Test that get_resources raises ValueError when resources aren't loaded."""
        with self.assertRaises(ValueError) as context:
            ResourceManager.get_resources()

    def test_load_resources_nonexistent_folder(self):
        """Test loading resources from non-existent folder raises FileNotFoundError."""
        nonexistent_path = Path("/nonexistent/folder")

        with self.assertRaises(FileNotFoundError) as context:
            ResourceManager.load_resources(nonexistent_path)

    def test_load_resources_file_instead_of_folder(self):
        """Test loading resources when path points to a file instead of folder."""
        with tempfile.NamedTemporaryFile() as temp_file:
            temp_path = Path(temp_file.name)

            with self.assertRaises(FileNotFoundError) as context:
                ResourceManager.load_resources(temp_path)

    def test_load_resources_empty_folder(self):
        """Test loading resources from empty folder."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            ResourceManager.load_resources(temp_path)

        # Should create AvailableResources with None values
        resources = ResourceManager.get_resources()
        self.assertIsInstance(resources, AvailableResources)
        self.assertIsNone(resources.core)
        self.assertIsNone(resources.remote)
        self.assertIsNone(resources.core)
        self.assertIsNone(resources.api)
        self.assertIsNone(resources.license)
        self.assertIsNone(resources.ue)
        self.assertIsNone(resources.sdr)
        self.assertIsNone(resources.ru)

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_with_core_resource(self, mock_load):
        """Test loading resources with a core resource."""
        # Mock the load_resources_from_file to return a core object
        core_resource = Core(address="192.168.1.100", port=8080, mask=24)
        mock_load.return_value = [core_resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a dummy .yml file
            yml_file = temp_path / "core.yml"
            yml_file.write_text("dummy content")

            ResourceManager.load_resources(temp_path)

        resources = ResourceManager.get_resources()
        self.assertEqual(resources.core, core_resource)
        self.assertIsNone(resources.remote)  # Other resources should be None

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_with_multiple_resources(self, mock_load):
        """Test loading multiple different resource types."""
        core_resource = Core(address="192.168.1.100", port=8080, mask=24)
        api_resource = API(address="localhost", port=8080)
        android_resource = Ue(
            model="Samsung",
            serial_id="123456",
            imsi="123456789012345",
            k="key",
            amf="amf",
            opc="opc",
            adb_key="adb_key",
        )

        mock_load.return_value = [core_resource, api_resource, android_resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a dummy .yml file
            yml_file = temp_path / "resources.yml"
            yml_file.write_text("dummy content")

            ResourceManager.load_resources(temp_path)

        resources = ResourceManager.get_resources()
        self.assertEqual(resources.core, core_resource)
        self.assertEqual(resources.api, api_resource)
        self.assertEqual(resources.ue, android_resource)
        self.assertIsNone(resources.remote)  # Unloaded resources should be None

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_with_multiple_yml_files(self, mock_load):
        """Test loading resources from multiple .yml files."""
        core_resource = Core(address="192.168.1.100", port=8080, mask=24)
        api_resource = API(address="localhost", port=8080)

        # Configure mock to return different resources for different calls
        mock_load.side_effect = [[core_resource], [api_resource]]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple dummy .yml files
            (temp_path / "core.yml").write_text("core config")
            (temp_path / "api.yml").write_text("api config")

            ResourceManager.load_resources(temp_path)

        resources = ResourceManager.get_resources()
        self.assertEqual(resources.core, core_resource)
        self.assertEqual(resources.api, api_resource)

        # Should have been called twice (once for each .yml file)
        self.assertEqual(mock_load.call_count, 2)

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_unknown_resource_type(self, mock_load):
        """Test loading an unknown resource type raises ValueError."""
        # Create a mock object that doesn't match any expected resource type
        unknown_resource = Mock()
        unknown_resource.__class__.__name__ = "UnknownResource"

        mock_load.return_value = [unknown_resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create a dummy .yml file
            yml_file = temp_path / "unknown.yml"
            yml_file.write_text("dummy content")

            with self.assertRaises(ValueError) as context:
                ResourceManager.load_resources(temp_path)

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_overwrites_previous_resources(self, mock_load):
        """Test that loading resources overwrites previously loaded resources."""
        # First load
        core_resource1 = Core(address="192.168.1.100", port=8080, mask=24)
        mock_load.return_value = [core_resource1]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            yml_file = temp_path / "core.yml"
            yml_file.write_text("dummy content")

            ResourceManager.load_resources(temp_path)
            resources1 = ResourceManager.get_resources()
            self.assertEqual(resources1.core, core_resource1)

            # Second load with different resource
            core_resource2 = Core(address="192.168.1.200", port=8080, mask=24)
            mock_load.return_value = [core_resource2]

            ResourceManager.load_resources(temp_path)
            resources2 = ResourceManager.get_resources()
            self.assertEqual(resources2.core, core_resource2)
            self.assertNotEqual(resources2.core, core_resource1)

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_string_path(self, mock_load):
        """Test loading resources with string path instead of Path object."""
        core_resource = Core(address="192.168.1.100", port=8080, mask=24)
        mock_load.return_value = [core_resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            yml_file = Path(temp_dir) / "core.yml"
            yml_file.write_text("dummy content")

            # Pass string path instead of Path object
            ResourceManager.load_resources(temp_dir)

        resources = ResourceManager.get_resources()
        self.assertEqual(resources.core, core_resource)

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_load_resources_ignores_non_yml_files(self, mock_load):
        """Test that non-.yml files are ignored."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create files with different extensions
            (temp_path / "config.txt").write_text("text file")
            (temp_path / "data.json").write_text("json file")
            (temp_path / "readme.md").write_text("markdown file")

            ResourceManager.load_resources(temp_path)

        # Should not have called load_resources_from_file since no .yml files
        mock_load.assert_not_called()

    @patch("retina.agent.app.resource_manager.load_resources_from_file")
    def test_resource_manager_is_singleton_like(self, mock_load):
        """Test that ResourceManager behaves like a singleton for resources."""
        core_resource = Core(address="192.168.1.100", port=8080, mask=24)

        mock_load.return_value = [core_resource]

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            yml_file = temp_path / "core.yml"
            yml_file.write_text("dummy content")

            ResourceManager.load_resources(temp_path)

        # Multiple calls to get_resources should return the same object
        resources1 = ResourceManager.get_resources()
        resources2 = ResourceManager.get_resources()

        self.assertIs(resources1, resources2)
        self.assertEqual(resources1.core, resources2.core)


if __name__ == "__main__":
    unittest.main()
