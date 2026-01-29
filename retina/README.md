# Retina

## Summary

Retina is a testing framework for RAN that orchestrates your infrastructure and executes tests on it.

Retina uses Kubernetes as its orchestration platform. Kubernetes is a popular open-source container orchestration system that is used to automate the deployment, scaling, and management of containerized applications. By using Kubernetes, Retina can easily manage and scale the test infrastructure needed to run various network setups.

To handle complex distributed infrastructures, Retina deploys agents in each node the test is going to use, configured to handle some specific software. The main node, where the test will be launched, will create a client for each one of those agents and connect to them through TCP/IP.

Retina architecture has been designed with the following ideas in mind:

- Testing Infrastructure should be:
  - Scalable
  - Replicable
  - Transparent for the user
  - Able to handle tests running in:
    - Developer PC
    - On-prem Laboratory
    - Cloud provider
- Do one thing and do it well
  - Split orchestration, test and infrastructure management
  - Reuse existing tools for each phase

Retina uses [pytest](https://docs.pytest.org/) as test framework. Tests are written in python using pytest fixtures and syntax.

## Index

- [Overview](_docs/01_overview.md)
- [Cluster Setup](_docs/02_cluster_setup.md)
- [Install Retina on your PC](_docs/03_installation.mdx)
- [Use the booking system](_docs/04_reserve_resources.md)
- [Run a Retina Test in the Cluster](_docs/05_run_cluster_test.md)
- [Run a Retina Test in local](_scripts/README.md)
