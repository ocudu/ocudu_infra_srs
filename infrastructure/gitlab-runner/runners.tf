# SPDX-FileCopyrightText: Copyright (C) 2021-2026 Software Radio Systems Limited
# SPDX-License-Identifier: BSD-3-Clause-Open-MPI

locals {
  # Read cluster-level global config from the first runners_file.
  _yaml_cluster_config = yamldecode(file(var.runners_file[0])).global
  cluster_config = {
    image        = local._yaml_cluster_config.image
    gitlab_url   = local._yaml_cluster_config.gitlab_url
    cache        = local._yaml_cluster_config.cache
    host_aliases = try(local._yaml_cluster_config.host_aliases, null)
  }

  # Flatten runners from all files, filtering by cluster_type.
  # Runners without a cluster_types field are deployed to all clusters.
  _all_runners = flatten([
    for f in var.runners_file : [
      for node, runners in yamldecode(file(f)).runners : [
        for r in runners : merge(r, { node = node })
        if !contains(keys(r), "cluster_types") || contains(tolist(r.cluster_types), var.cluster_type)
      ]
    ]
  ])

  runners_map = { for r in local._all_runners : r.name => r }

  # Pre-process each runner into a sanitised object with all fields having defaults.
  # This allows the template to use plain ${runner.field} without try() or conditionals.
  processed_runners = {
    for name, r in local.runners_map : name => {
      concurrent                       = r.concurrent
      tags                             = tostring(r.tags)
      check_interval                   = try(r.check_interval, 1)
      unregister_runners               = try(r.unregister_runners, false)
      termination_grace_period_seconds = try(r.termination_grace_period_seconds, 3600)
      run_untagged                     = try(r.run_untagged, false)
      metrics_enabled                  = try(r.metrics_enabled, false)

      # Session server
      session_server_enabled                     = try(r.session_server_enabled, false)
      session_server_timeout                     = try(r.session_server_timeout, null)
      session_server_internal_port               = try(r.session_server_internal_port, null)
      session_server_external_port               = try(r.session_server_external_port, null)
      session_server_public_ip                   = try(r.session_server_public_ip, null)
      session_server_load_balancer_source_ranges = try(r.session_server_load_balancer_source_ranges, [])

      # Kubernetes executor
      poll_timeout  = try(r.poll_timeout, 1200)
      build_image   = try(r.build_image, "ubuntu")
      output_limit  = try(r.output_limit, 10485760)
      pull_policy   = try(r.pull_policy, null)
      helper_image  = try(r.helper_image, null)

      service_account                   = try(r.service_account, null)
      service_account_overwrite_allowed = try(r.service_account_overwrite_allowed, null)
      priority_class_name               = try(r.priority_class_name, null)
      clone_url                         = try(r.clone_url, null)

      # Resources — kept as strings for TOML output
      cpu_request    = try(r.cpu_request, null) != null ? tostring(r.cpu_request) : null
      cpu_limit      = try(r.cpu_limit, null) != null ? tostring(r.cpu_limit) : null
      memory_request = try(r.memory_request, null) != null ? tostring(r.memory_request) : null
      memory_limit   = try(r.memory_limit, null) != null ? tostring(r.memory_limit) : null

      cpu_request_overwrite_max_allowed    = tostring(try(r.cpu_request_overwrite_max_allowed, 20))
      cpu_limit_overwrite_max_allowed      = tostring(try(r.cpu_limit_overwrite_max_allowed, 20))
      memory_request_overwrite_max_allowed = tostring(try(r.memory_request_overwrite_max_allowed, "20Gi"))
      memory_limit_overwrite_max_allowed   = tostring(try(r.memory_limit_overwrite_max_allowed, "20Gi"))

      ephemeral_storage_request                       = try(r.ephemeral_storage_request, null) != null ? tostring(r.ephemeral_storage_request) : null
      ephemeral_storage_limit                         = try(r.ephemeral_storage_limit, null) != null ? tostring(r.ephemeral_storage_limit) : null
      ephemeral_storage_request_overwrite_max_allowed = tostring(try(r.ephemeral_storage_request_overwrite_max_allowed, "200Gi"))
      ephemeral_storage_limit_overwrite_max_allowed   = tostring(try(r.ephemeral_storage_limit_overwrite_max_allowed, "200Gi"))

      service_cpu_limit    = tostring(try(r.service_cpu_limit, "1"))
      service_memory_limit = tostring(try(r.service_memory_limit, "1Gi"))
      helper_cpu_limit     = tostring(try(r.helper_cpu_limit, "500m"))
      helper_memory_limit  = tostring(try(r.helper_memory_limit, "500Mi"))

      # Compute environment list: explicit list overrides cpu/memory-derived defaults
      environment = length(try(r.environment, [])) > 0 ? tolist(r.environment): [GIT_HTTP_POST_BUFFER=157286400]

      # Node selector (map) or default arch/os labels
      node_selector = try(r.node_selector, null)
      arch          = try(r.arch, "amd64")

      # Node tolerations dict (key=value_expression: effect)
      node_tolerations = try(r.node_tolerations, {})

      # Host aliases: per-runner overrides cluster-level var.host_aliases
      host_aliases = try(r.host_aliases, null)

      # Pod security context
      pod_security_context = try(r.pod_security_context, null) != null ? {
        run_as_non_root     = try(r.pod_security_context.run_as_non_root, null)
        run_as_user         = try(r.pod_security_context.run_as_user, null)
        run_as_group        = try(r.pod_security_context.run_as_group, null)
        fs_group            = try(r.pod_security_context.fs_group, null)
        supplemental_groups = tolist(try(r.pod_security_context.supplemental_groups, []))
      } : null

      # Volumes list
      volumes = [
        for v in try(r.volumes, []) : {
          type       = v.type
          name       = v.name
          mount_path = v.mount_path
          medium     = try(v.medium, null)
          host_path  = try(v.host_path, null)
          read_only  = try(v.read_only, true)
        }
      ]

      # RBAC
      rbac = {
        cluster_wide_access         = try(r.rbac.clusterWideAccess, false)
        rules                       = try(r.rbac.rules, [])
        service_account_annotations = try(r.rbac.serviceAccountAnnotations, null)
      }
    }
  }
}

# Pause each runner (drain jobs) before applying Helm chart changes.
# Triggered only when the runner's configuration changes.
# All runners are paused in parallel (Terraform's default concurrency).
resource "null_resource" "pre_apply_pause" {
  for_each = local.processed_runners

  triggers = {
    runner_hash = sha256(jsonencode(each.value))
  }

  provisioner "local-exec" {
    command = <<-EOT
      python3 "${path.module}/runner_pause_wait_unpause.py" \
        --runner-name "${each.key}" \
        --token "$RUNNER_TOKEN" \
        --pause_wait \
        --wait_minutes 5 \
        --runners-def '${jsonencode(var.runners_file)}'
    EOT
    environment = {
      RUNNER_TOKEN = var.gitlab_runner_token
    }
  }
}

resource "helm_release" "runners" {
  for_each   = local.processed_runners
  depends_on = [null_resource.pre_apply_pause]

  name             = each.key
  namespace        = "gitlab-runner"
  create_namespace = true
  repository       = "https://charts.gitlab.io"
  chart            = "gitlab-runner"
  version          = var.helm_version

  values = [templatefile("${path.module}/manifests/runner-values.yaml.tftpl", {
    runner         = each.value
    runner_token   = local.runners_map[each.key].token
    cluster_config = local.cluster_config
  })]

  lifecycle {
    ignore_changes = [description]
  }
}

# Unpause each runner after Helm chart changes have been applied.
# Triggered by the same hash as pre_apply_pause, and depends on all helm releases completing.
resource "null_resource" "post_apply_unpause" {
  for_each   = local.processed_runners
  depends_on = [helm_release.runners]

  triggers = {
    runner_hash = sha256(jsonencode(each.value))
  }

  provisioner "local-exec" {
    command = <<-EOT
      python3 "${path.module}/runner_pause_wait_unpause.py" \
        --runner-name "${each.key}" \
        --token "$RUNNER_TOKEN" \
        --unpause \
        --runners-def '${jsonencode(var.runners_file)}'
    EOT
    environment = {
      RUNNER_TOKEN = var.gitlab_runner_token
    }
  }
}
