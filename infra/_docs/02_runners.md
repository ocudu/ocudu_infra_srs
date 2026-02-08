# Gitlab Runners Setup

## Set Up a Build Runner

Configure a GitLab runner for building OCUDU. Either:

- **Use GitLab Shared Runners** (recommended): Enable in project settings, no setup required
- **Self-hosted Runner**: Follow [GitLab Documentation](https://docs.gitlab.com/runner/install/) and use tags: `saas-linux-medium-amd64` or `saas-linux-medium-arm64`

## Set Up an E2E Runner

Deploy a GitLab runner with Kubernetes cluster access to execute Retina-based tests.

**Requirements:**

- **Tags**: Must include `retina`. Add testbed-specific tags: `zmq`, `rf`, `s72`, `viavi` (based on available resources)
- **Namespace**: Runner spawns test pods in the `retina` namespace, but the runner itself should run in a different namespace (`gitlab-runner` in the examples below.)

**Installation:**

- Create ServiceAccount, ClusterRole and ClusterRoleBinding:

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: example-retina-runner
  namespace: gitlab-runner
```

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: example-retina-runner
rules:
  - apiGroups: [""]
    resources: ["pods", "pods/attach", "pods/exec", "pods/log", "services", "endpoints", "secrets", "events", "configmaps", "namespaces", "nodes"]
    verbs: ["get", "list", "watch", "create", "delete", "patch", "update"]
  - apiGroups: ["apps"]
    resources: ["deployments", "replicasets", "daemonsets", "statefulsets"]
    verbs: ["get", "list", "watch", "create", "delete", "patch", "update"]
  - apiGroups: ["batch"]
    resources: ["jobs", "cronjobs"]
    verbs: ["get", "list", "watch", "create", "delete", "patch", "update"]
  - apiGroups: ["events.k8s.io"]
    resources: ["events"]
    verbs: ["get", "list", "watch"]
```

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: example-retina-runner
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: example-retina-runner
subjects:
  - kind: ServiceAccount
    name: example-retina-runner
    namespace: gitlab-runner
```

- Install the runner itself with helm. Here is an example of a minimal values.yaml file.

```yaml
gitlabUrl: https://gitlab.com/
runnerToken: "<your-runner-token>"
concurrent: 2
rbac:
  create: false  # Create it manually before
  serviceAccountName: example-retina-runner
runners:
  config: |
    [[runners]]
      [runners.kubernetes]
        namespace = "retina"
        privileged = true
    ... # Your configuration like default values, tolerations, etc.
  tags: "retina,zmq"  # Adjust based on testbed
```

```bash
helm repo add gitlab https://charts.gitlab.io
helm install <runner-name> gitlab/gitlab-runner --namespace gitlab-runner -f values.yaml
```
