# OCUDU Infra SRS

This repository contains all the software, configurations, and tools required to run the [SRS](https://srs.io/) suite of end-to-end tests for [OCUDU](https://gitlab.com/ocudu):

- E2E test code and configurations.
- E2E framework.
- Pipeline as Code (Gitlab CI/CD).
- Infrastructure as Code templates.
- Auxiliary scripts.

A third-party entity can replicate this repo's CI/CD flows to create their own testing infrastructure, reusing the software automation framework. To facilitate that task, Infrastructure as Code templates are available and generic labels and tags are used in the test orchestration.

This repository have dependencies on third-party hardware and software, such as O-RUs, SDRs, commercial off-the-shelf (COTS) UEs, 5GC, and UE emulators.

## More

Each folder contains a README.md and auxiliary markdown files to document each feature. Please read them to know more or navigate through the [documentation website](./docs/README.md) generated with all markdown files across the repo in [https://softwareradiosystems.gitlab.io/ocudu_infra_srs](https://softwareradiosystems.gitlab.io/ocudu_infra_srs).

- [GitLab Project Configuration](infra/gitlab/README.md)
- [Gitlab CI Components](templates/README.md)
- [OCUDU E2E Testing](e2e/README.md)
