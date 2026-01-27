---
sidebar_position: 1
---

# OCUDU Infra SRS

This repository contains all the software required to run the [SRS](https://srs.io/) suite of end-to-end tests for [OCUDU](https://gitlab.com/ocudu):

- E2E test code and configurations.
- E2E framework.
- Pipeline as Code (Gitlab CI/CD).
- Infrastructure as Code templates.
- Auxiliary scripts.

A third-party entity can replicate this repo's CI/CD to create their own e2e suite of tests, reusing the test automation framework. To facilitate that task, Infrastructure as Code templates and examples are available.

This repository has dependencies on third-party hardware and software, such as O-RUs, SDRs, commercial off-the-shelf (COTS) UEs, 5GC, and UE emulators.

## Index

- [Gitlab CI Components](templates/README.md)
- [OCUDU E2E Testing](e2e/README.md)
- [Retina Framework for E2E Testing](retina/README.md)
- [About the documentation](/docs/README.md) in [https://ocudu.gitlab.io/ocudu_infra_srs](https://ocudu.gitlab.io/ocudu_infra_srs).
