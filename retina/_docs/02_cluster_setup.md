# Cluster Setup

## Configure the cluster to use Retina

- Create a `retina` namespace.
- Add `retina.srs.io/member=true` label to all nodes you want to be used by retina:

```bash
kubectl label nodes <node_name> retina.srs.io/member=true
```

- If the retina container registry is not public, you need to create a secret with the credentials:

```bash
kubectl -n retina create secret docker-registry registry-credentials \
  --docker-server='registry.gitlab.com' \
  --docker-username='username' \
  --docker-password='password'
```

For GitLab Container Registry, you can create a `Deploy Token` with `read_registry` scope.

## Cluster definition

TBD

## Generate a .kube/config file or support in-cluster mode

TBD
