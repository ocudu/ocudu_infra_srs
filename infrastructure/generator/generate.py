#
# Copyright 2021-2026 Software Radio Systems Limited
#
# By using this file, you agree to the terms and conditions set
# forth in the LICENSE file which can be found at the top level of
# the distribution.
#

import argparse
from pathlib import Path
from typing import Any, Dict

import jinja2
import yaml


def load_cluster_definition(
    base_path: Path,
    runners_path: Path = None,
    services_path: Path = None,
) -> Dict[str, Any]:
    """
    Load and merge cluster definition from multiple files.
    
    Args:
        base_path: Path to base cluster definition (e.g., lab_cluster.yaml)
        runners_path: Optional path to runners file (e.g., lab_cluster_runners.yaml)
        services_path: Optional path to services file (e.g., lab_cluster_services.yaml)
    
    Returns:
        Merged cluster definition dictionary
    """
    # Load base file
    with open(base_path, "r", encoding="utf-8") as f:
        cluster_def = yaml.safe_load(f)
    
    # Load runners file if provided and exists
    if runners_path and runners_path.exists():
        with open(runners_path, "r", encoding="utf-8") as f:
            runners_data = yaml.safe_load(f)
            # Merge runners into nodes by name
            runners_by_node = runners_data.get("runners", {})
            for node in cluster_def.get("nodes", []):
                node_name = node.get("name")
                if node_name in runners_by_node:
                    node["runner_list"] = runners_by_node[node_name]
    
    # Load services file if provided and exists
    if services_path and services_path.exists():
        with open(services_path, "r", encoding="utf-8") as f:
            services_data = yaml.safe_load(f)
            # Store global services config in cluster_def
            if "global" in services_data:
                if "global" not in cluster_def:
                    cluster_def["global"] = {}
                # Merge services global config into cluster_def global
                if "services" not in cluster_def["global"]:
                    cluster_def["global"]["services"] = {}
                cluster_def["global"]["services"].update(services_data["global"])
            # Merge services into nodes by name
            services_by_node = services_data.get("services", {})
            for node in cluster_def.get("nodes", []):
                node_name = node.get("name")
                if node_name in services_by_node:
                    node["services"] = services_by_node[node_name]
    
    return cluster_def


def get_template_loader(template_type: str = "gitlab-runner"):
    """
    Get Jinja2 template loader for templates.
    
    Args:
        template_type: Template type ("gitlab-runner", "k8s/linuxptp", or "k8s/tuned")
    
    Returns:
        Jinja2 FileSystemLoader
    """
    template_dir = Path(__file__).parent / "templates" / template_type
    return jinja2.FileSystemLoader(str(template_dir))


def get_runner_config(
    runner: Dict[str, Any],
    node: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract and prepare runner configuration from cluster definition.

    Copies all runner values and only overrides computed values.
    Defaults are handled in the Jinja template.

    Args:
        runner: Runner entry from runner_list (with gitlab_runner config merged via YAML anchor)
        node: Node entry containing the runner
        cluster_def: Full cluster definition
        cluster_type: Cluster type
        resource_name: Terraform resource name for this runner

    Returns:
        Dictionary with runner configuration for template rendering

    Raises:
        ValueError: If required fields are missing
    """
    # Validate mandatory fields (fields that didn't have defaults before)
    required_fields = [
        "token",
        "concurrent",
        "tags",
    ]

    missing_fields = []
    for field in required_fields:
        if field not in runner or runner[field] is None:
            missing_fields.append(f"runner.{field}")

    if missing_fields:
        runner_id = runner.get("id", "unknown")
        raise ValueError(
            f"Missing required fields for runner (id: {runner_id}): {', '.join(missing_fields)}"
        )

    # Get runner name from cluster definition, or use default: glr-{node_name}
    runner_name = runner.get("name")
    if not runner_name:
        runner_name = f"glr-{node.get('name', '')}"

    # Handle check_interval (defaults to 1 if not specified)
    check_interval = runner.get("check_interval", 1)

    # Copy all runner values and override only computed values
    # Defaults are handled in the Jinja template
    config = {
        **runner,  # Copy all runner values (including gitlab_runner config from anchor)
        "name": runner_name,
        "check_interval": check_interval,
    }

    # Convert CPU/memory values to strings if present (for template rendering)
    if "cpu_request" in config and config["cpu_request"] is not None:
        config["cpu_request"] = str(config["cpu_request"])
    if "cpu_limit" in config and config["cpu_limit"] is not None:
        config["cpu_limit"] = str(config["cpu_limit"])

    return config


def get_gitlab_runner_config_from_runner(runner: Dict[str, Any], cluster_def: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract GitLab runner configuration from a runner definition.

    With YAML anchors, gitlab_runner config is merged into each runner via <<: *gitlab_runner.
    This function extracts and validates the merged configuration.
    If fields are missing from the runner, they are merged from the global gitlab_runner config.

    Required fields must be present in the runner or in the global gitlab_runner config:
    - image (registry, image, tag)
    - gitlab_url
    - cache (type, path, s3 with server_address, access_key, secret_key, bucket_name, insecure)

    Args:
        runner: Runner definition (with gitlab_runner config merged via YAML anchor)
        cluster_def: Full cluster definition (for helm_version fallback and global config)

    Returns:
        Dictionary with GitLab runner configuration for template rendering

    Raises:
        ValueError: If required fields are missing
    """
    # Get global gitlab_runner config
    global_config = cluster_def.get("global", {})
    global_gitlab_runner = global_config.get("gitlab_runner", {})
    
    # Get helm version: from runner, gitlab_runner anchor, or global default
    global_helm_version = global_config.get("helm_version", "0.79.1")
    helm_version = runner.get("helm_version", global_gitlab_runner.get("helm_version", global_helm_version))

    # Merge global gitlab_runner config into runner (runner values take precedence)
    merged_runner = {**global_gitlab_runner, **runner}

    # Validate required fields (should be in runner or global gitlab_runner)
    required_fields = {
        "image": ["registry", "image", "tag"],
        "gitlab_url": None,
        "cache": ["type", "path"],
    }

    missing_fields = []
    for field, subfields in required_fields.items():
        if field not in merged_runner:
            missing_fields.append(f"runner.{field} (should be in runner or global gitlab_runner)")
        elif subfields:
            for subfield in subfields:
                if subfield not in merged_runner[field]:
                    missing_fields.append(f"runner.{field}.{subfield}")

    # Validate cache.s3 fields
    if "cache" in merged_runner:
        cache = merged_runner["cache"]
        if cache.get("type") == "s3":
            s3_required = ["server_address", "access_key", "secret_key", "bucket_name", "insecure"]
            if "s3" not in cache:
                missing_fields.append("runner.cache.s3")
            else:
                for s3_field in s3_required:
                    if s3_field not in cache["s3"]:
                        missing_fields.append(f"runner.cache.s3.{s3_field}")

    if missing_fields:
        raise ValueError(
            f"Missing required fields in runner definition: {', '.join(missing_fields)}\n"
            f"Make sure runner uses <<: *gitlab_runner to merge the anchor, or define in global gitlab_runner."
        )

    # Build config from merged runner (global config + runner overrides)
    config = {
        "image": merged_runner["image"].copy(),
        "gitlab_url": merged_runner["gitlab_url"],
        "cache": merged_runner["cache"].copy(),
        "helm_version": helm_version,
    }

    # Copy optional fields if present (from merged_runner to include global config)
    if "image_pull_secrets" in merged_runner:
        config["image_pull_secrets"] = merged_runner["image_pull_secrets"]
    if "rbac_service_account_annotations" in merged_runner:
        config["rbac_service_account_annotations"] = merged_runner["rbac_service_account_annotations"]
    if "host_aliases" in merged_runner:
        config["host_aliases"] = merged_runner["host_aliases"]

    return config


def get_manifest_filename(runner_name: str, cluster_type: str) -> str:
    """
    Generate manifest filename for a runner.

    Args:
        runner_name: Runner name (e.g., "glr-on-prem-sdr6-amd64")
        cluster_type: Cluster type (e.g., "prod-cluster", "staging-cluster", or any user-defined name)

    Returns:
        Manifest filename
    """
    if cluster_type == "local":
        return f"{runner_name}-helmchart.yaml"
    else:
        return f"{runner_name}.yaml"


def generate_gitlab_runners(
    cluster_def: Dict[str, Any],
    cluster_type: str,
    output_dir: Path,
    repo_root: Path = None,
):
    """
    Generate GitLab runner Terraform and manifest files from cluster definition.

    Generates runners that have both 'id' and 'name' defined in the cluster definition.
    Runners can be disabled by setting 'enabled: false'.

    Args:
        cluster_def: Cluster definition dictionary
        cluster_type: User-defined cluster type (e.g., 'prod-cluster', 'staging-cluster', 'my-cluster')
        output_dir: Directory to write generated Terraform files
    """
    env = jinja2.Environment(loader=get_template_loader(), trim_blocks=True, lstrip_blocks=True)

    # Collect all enabled runners from all nodes
    runners = []
    nodes = cluster_def.get("nodes", [])

    for node in nodes:
        node_name = node.get("name", "")
        runner_list = node.get("runner_list", [])

        for runner in runner_list:
            runner_id = runner.get("id")
            runner_name = runner.get("name")

            # Skip if missing required fields
            if not runner_id or not runner_name:
                continue

            # Skip if disabled
            if runner.get("enabled", True) is False:
                continue

            # Filter by cluster_type if specified in runner configuration
            # If 'cluster_types' field exists, only include runner if current cluster_type is in the list
            # If 'cluster_types' field is not specified, include runner for all cluster types
            runner_cluster_types = runner.get("cluster_types")
            if runner_cluster_types is not None:
                if not isinstance(runner_cluster_types, list):
                    raise ValueError(
                        f"Runner '{runner_name}' has invalid 'cluster_types' field: "
                        f"expected list, got {type(runner_cluster_types).__name__}"
                    )
                if cluster_type not in runner_cluster_types:
                    continue

            # Use name from cluster definition as resource name
            resource_name = runner_name
            manifest_filename = get_manifest_filename(runner_name, cluster_type)

            # Get GitLab runner config from runner (merged via YAML anchor)
            gitlab_runner_config = get_gitlab_runner_config_from_runner(runner, cluster_def)

            # Get runner configuration
            runner_config = get_runner_config(runner, node)

            runners.append(
                {
                    "resource_name": resource_name,
                    "manifest_filename": manifest_filename,
                    "node_name": node_name,
                    "runner_id": runner_id,
                    "disable_when": runner.get("disable_when", []),
                    "config": runner_config,
                    "gitlab_runner_config": gitlab_runner_config,
                }
            )

    if not runners:
        print("No enabled runners found in cluster definition")
        return

    # Generate main.tf
    main_template = env.get_template("terraform/main.tf.j2")
    main_content = main_template.render()
    (output_dir / "main.tf").write_text(main_content)

    # Generate individual runner Terraform files
    runner_template = env.get_template("terraform/runner.tf.j2")
    for runner in runners:
        helm_version = runner["gitlab_runner_config"]["helm_version"]
        runner_content = runner_template.render(runner=runner, helm_version=helm_version)
        runner_file = output_dir / f"{runner['resource_name']}.tf"
        runner_file.write_text(runner_content)

    # Generate manifest files
    # Output manifests to gitlab-runner/{cluster}/manifests/
    manifest_output_dir = output_dir.parent / "manifests"
    manifest_output_dir.mkdir(parents=True, exist_ok=True)

    manifest_template = env.get_template("manifests/runner-values.yaml.j2")
    for runner in runners:
        manifest_content = manifest_template.render(
            runner=runner["config"],
            cluster_config={"gitlab_runner": runner["gitlab_runner_config"]}
        )
        manifest_file = manifest_output_dir / runner["manifest_filename"]
        manifest_file.write_text(manifest_content)

    print(f"Generated {len(runners)} runner resources in {output_dir}")
    print(f"Generated {len(runners)} manifest files in {manifest_output_dir}")
    for runner in runners:
        print(f"  - {runner['resource_name']}.tf (node: {runner['node_name']}, id: {runner['runner_id']})")
        print(f"  - {runner['manifest_filename']} (manifest)")


def generate_k8s_helm_services(
    cluster_def: Dict[str, Any],
    service_name: str,
    output_dir: Path,
    repo_root: Path = None,
):
    """
    Generate Helm service Terraform and manifest files from cluster definition.
    
    Generates services (linuxptp or tuned) for nodes that have the service enabled.
    
    Args:
        cluster_def: Cluster definition dictionary
        service_name: 'linuxptp' or 'tuned'
        output_dir: Directory to write generated Terraform files (e.g., k8s/Helm/linuxptp/tf)
        repo_root: Root of the infrastructure repository (for reading profile/script files)
    """
    if service_name not in ["linuxptp", "tuned"]:
        raise ValueError(f"Invalid service_name: {service_name}. Must be 'linuxptp' or 'tuned'")
    
    # Add Jinja2 filter for indenting multi-line strings
    def indent_filter(text, spaces=2):
        if not text:
            return ""
        indent_str = " " * spaces
        return "\n".join(indent_str + line if line else "" for line in text.split("\n"))
    
    env = jinja2.Environment(
        loader=get_template_loader(f"k8s/{service_name}"),
        trim_blocks=True,
        lstrip_blocks=True
    )
    env.filters['indent'] = indent_filter
    
    # Get global config
    global_config = cluster_def.get("global", {})
    
    # Collect all enabled services from all nodes
    services = []
    nodes = cluster_def.get("nodes", [])
    
    for node in nodes:
        node_name = node.get("name", "")
        node_services = node.get("services", {})
        service_config = node_services.get(service_name, {})
        
        # Skip if service not enabled
        if not service_config.get("enabled", False):
            continue
        
        # Get service-specific config
        if service_name == "linuxptp":
            interface_name = service_config.get("interface_name")
            if not interface_name:
                raise ValueError(f"Node '{node_name}': linuxptp requires 'interface_name'")
            
            image_tag = service_config.get("image_tag") or global_config.get("linuxptp_image_tag", "v4.4_1.1.2")
            
            # Merge global config with node-specific config
            # Get global linuxptp config if it exists
            global_services = global_config.get("services", {})
            global_linuxptp_config = global_services.get("linuxptp", {}).get("config", {})
            
            # Get node-specific config (can be None or empty dict)
            node_config = service_config.get("config", {})
            
            # Deep merge: start with global config, then override with node-specific
            def deep_merge(base, override):
                """Deep merge two dictionaries, with override taking precedence."""
                result = base.copy()
                for key, value in override.items():
                    if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                        result[key] = deep_merge(result[key], value)
                    else:
                        result[key] = value
                return result
            
            config = deep_merge(global_linuxptp_config, node_config) if node_config else global_linuxptp_config
            
            services.append({
                "node_name": node_name,
                "interface_name": interface_name,
                "image_tag": image_tag,
                "config": config,
            })
        
        elif service_name == "tuned":
            # Get global tuned defaults
            global_tuned = global_config.get("tuned", {})
            global_tuned_image = global_tuned.get("image", {})
            global_tuned_reboot = global_tuned.get("reboot", {})
            
            # Get image configuration (global with node override)
            image_repository = service_config.get("image", {}).get("repository") or global_tuned_image.get("repository", "softwareradiosystems/tuned-agent")
            image_pull_policy = service_config.get("image", {}).get("pullPolicy") or global_tuned_image.get("pullPolicy", "IfNotPresent")
            
            # Get image tag (node-specific or global default)
            image_tag = service_config.get("image_tag")
            if not image_tag:
                # Use arch-specific default if node has arch field
                node_arch = None
                # Check if any runner on this node has arch field
                runner_list = node.get("runner_list", [])
                for runner in runner_list:
                    if "arch" in runner:
                        node_arch = runner.get("arch")
                        break
                
                if node_arch == "arm64":
                    image_tag = global_config.get("tuned_image_tag_arm64", "0.5.0-arm64")
                else:
                    image_tag = global_config.get("tuned_image_tag", "0.5.0")
            
            # Get profile content (required from service_config)
            profile_content = service_config.get("profileContent", "")
            if not profile_content:
                raise ValueError(f"Node '{node_name}': tuned requires 'profileContent' in cluster definition")
            
            # Get startup script content (required from service_config)
            startup_script_content = service_config.get("startupScriptContent", "")
            if not startup_script_content:
                raise ValueError(f"Node '{node_name}': tuned requires 'startupScriptContent' in cluster definition")
            
            # Get other values from global or service_config
            host_path_tuned = service_config.get("hostPathTuned") or global_tuned.get("hostPathTuned", "/usr/lib/tuned")
            security_context = service_config.get("securityContext") or global_tuned.get("securityContext", {"privileged": True})
            resources = service_config.get("resources") or global_tuned.get("resources", {})
            annotations = service_config.get("annotations") or global_tuned.get("annotations", {})
            restart_on_config_change = service_config.get("restartOnConfigChange")
            if restart_on_config_change is None:
                restart_on_config_change = global_tuned.get("restartOnConfigChange", True)
            node_selector = service_config.get("nodeSelector") or global_tuned.get("nodeSelector", {})
            
            # Get reboot config (merge global with node-specific)
            reboot = global_tuned_reboot.copy() if global_tuned_reboot else {}
            if "reboot" in service_config:
                reboot_config = service_config.get("reboot", {})
                if "cmd" in reboot_config:
                    reboot["cmd"] = reboot_config["cmd"]
                if "markerDir" in reboot_config:
                    reboot["markerDir"] = reboot_config["markerDir"]
                if "enabled" in reboot_config:
                    reboot["enabled"] = reboot_config["enabled"]
            
            # Set defaults if reboot is empty
            if not reboot:
                reboot = {
                    "enabled": True,
                    "cmd": "/sbin/shutdown -r +1 'tuned profile applied by helm'",
                    "markerDir": "/var/lib/tuned-helm"
                }
            
            # Generate profile name from node name
            profile_name = f"srsk8s-{node_name}"
            
            # Generate affinity and tolerations from node name
            affinity = {
                "nodeAffinity": {
                    "requiredDuringSchedulingIgnoredDuringExecution": {
                        "nodeSelectorTerms": [{
                            "matchExpressions": [{
                                "key": "kubernetes.io/hostname",
                                "operator": "In",
                                "values": [node_name]
                            }]
                        }]
                    }
                }
            }
            
            tolerations = [{
                "key": "machine",
                "operator": "Equal",
                "value": node_name,
                "effect": "NoSchedule"
            }]
            
            services.append({
                "node_name": node_name,
                "image_repository": image_repository,
                "image_tag": image_tag,
                "image_pull_policy": image_pull_policy,
                "profile_name": profile_name,
                "profile_content": profile_content,
                "startup_script_content": startup_script_content,
                "affinity": affinity,
                "tolerations": tolerations,
                "host_path_tuned": host_path_tuned,
                "node_selector": node_selector,
                "security_context": security_context,
                "resources": resources,
                "annotations": annotations,
                "restart_on_config_change": restart_on_config_change,
                "reboot": reboot,
            })
    
    if not services:
        print(f"No enabled {service_name} services found in cluster definition")
        return
    
    # Generate main.tf (if it doesn't exist, we'll preserve existing one)
    # For now, we'll skip generating main.tf as it's static
    
    # Create output directory for Terraform files
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate individual service Terraform files
    terraform_template = env.get_template("terraform/helm-release.tf.j2")
    for service in services:
        terraform_content = terraform_template.render(
            node_name=service["node_name"],
            service_name=service_name,
        )
        terraform_file = output_dir / f"{service['node_name']}.tf"
        terraform_file.write_text(terraform_content)
    
    # Generate manifest files
    manifest_output_dir = output_dir.parent / "manifests"
    manifest_output_dir.mkdir(parents=True, exist_ok=True)
    
    manifest_template = env.get_template("manifests/values.yaml.j2")
    for service in services:
        manifest_content = manifest_template.render(
            service_name=service_name,
            global_config=global_config,
            **service
        )
        manifest_file = manifest_output_dir / f"{service['node_name']}.yaml"
        manifest_file.write_text(manifest_content)
    
    print(f"Generated {len(services)} {service_name} resources in {output_dir}")
    print(f"Generated {len(services)} manifest files in {manifest_output_dir}")
    for service in services:
        print(f"  - {service['node_name']}.tf (node: {service['node_name']})")
        print(f"  - {service['node_name']}.yaml (manifest)")


def main():
    parser = argparse.ArgumentParser(description="Generate Terraform files from cluster definition")
    parser.add_argument("cluster_def", type=Path, help="Path to base cluster definition YAML file")
    parser.add_argument(
        "component",
        help="Component to generate: cluster type for runners (any name), or service name for k8s services (linuxptp, tuned)"
    )
    parser.add_argument("output_dir", type=Path, help="Output directory for generated Terraform files")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Root of the infrastructure repository")
    parser.add_argument("--runners-file", type=Path, help="Optional path to runners definition file")
    parser.add_argument("--services-file", type=Path, help="Optional path to services definition file")

    args = parser.parse_args()

    # Determine runners/services file paths if not provided
    base_dir = args.cluster_def.parent
    base_name = args.cluster_def.stem  # "lab_cluster" from "lab_cluster.yaml"
    
    runners_file = args.runners_file
    if not runners_file:
        runners_file = base_dir / f"{base_name}_runners.yaml"
    
    services_file = args.services_file
    if not services_file:
        services_file = base_dir / f"{base_name}_services.yaml"
    
    # Load cluster definition (supports multi-file)
    cluster_def = load_cluster_definition(
        args.cluster_def,
        runners_path=runners_file if runners_file.exists() else None,
        services_path=services_file if services_file.exists() else None,
    )
    
    # Generate based on component type
    if args.component in ["linuxptp", "tuned"]:
        # Generate k8s Helm services
        generate_k8s_helm_services(cluster_def, args.component, args.output_dir, args.repo_root)
    else:
        # Generate GitLab runners for any cluster type (user-defined)
        generate_gitlab_runners(cluster_def, args.component, args.output_dir, args.repo_root)


if __name__ == "__main__":
    main()
