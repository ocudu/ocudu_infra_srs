# OCUDU E2E Testing

This folder contains e2e tests sources, configurations and testbeds, alongside the Gitlab CI code to replicate SRS scheduled pipelines.

To run them, you need to install and configure [Retina framework](../retina/README.md)

## Gitlab Pipelines

### Manual Pipeline

We have a pipeline designed for triggered executions from the GitLab API or web interface. This pipeline orchestrates two main jobs:

1. **Build Job**: Compiles ocudu according to specified parameters
2. **E2E Job**: Runs selected end-to-end tests

When the E2E testbed is configured for Amarisoft and ZMQ, the pipeline will automatically attempt to build the ZMQ driver alongside the normal build process. This requires:

- The `AMARISOFT_PACKAGE_REGISTRY` variable to be available in the GitLab repository
- Proper access credentials to the registry as commented in the build [component documentation](../templates/README.md#download-urls-configuration).

Please refer to the [build and e2e component documentation](../templates/README.md) for more info.

## Pipeline Trigger Script

The `run_e2e_pipeline.py` script allows you to create a [GitLab pipeline with custom configurations](#manual-pipeline), helping the user to fill all the inputs that Gitlab CI expects.

### Installation

```bash
# Install dependencies
pip install pyyaml python_gitlab
```

### Usage

The script provides flexible ways to specify pipeline inputs:

**Default behavior (Interactive Mode):**

- The script will prompt you for **every input field**. Press Enter to accept the default value shown in brackets
- If you provide a value via **command-line argument**, the script will show it and ask for confirmation

**Using `--yes` flag:**

- Skips all interactive prompts and confirmations
- Uses command-line values if provided, otherwise uses defaults

**Using `--replicate JOB_ID_OR_NAME`:**

- Fetches all input values from an existing GitLab job
- Pre-populates all fields with values from that job
- You can still override any value via:
  - Interactive input (without `--yes`)
  - Command-line arguments (takes priority)

**Priority order (highest to lowest):**

1. Command-line arguments
2. Interactive user input (if not using `--yes`)
3. Replicated job values (if using `--replicate`)
4. Default values from `.gitlab-ci.yml`

**Dryrun mode:**

You can add the `--dyrun` flag to preview the input values without creating any pipeline.

**Examples:**

```bash
python3 run_e2e_pipeline.py --token YOUR_GITLAB_TOKEN

📝 Fill the inputs. Press enter to keep the value between brackets. You can skip this confirmation adding --yes flag to the call.
 - ocudu_ref ["main"]: 
 - os=ubuntu-24.04
...
⏩ Creating pipeline with inputs:
  - ocudu_ref=main
...
✅ Pipeline created: https://...
```

```bash
python3 run_e2e_pipeline.py --token YOUR_GITLAB_TOKEN --ocudu-ref main --testbed none --yes

⏩ Creating pipeline with inputs:
  - ocudu_ref=main
...
✅ Pipeline created: https://...
```

```bash
python3 run_e2e_pipeline.py --token YOUR_GITLAB_TOKEN --replicate "smoke zmq" --compiler gcc --yes

⏳ Looking for the job...
🟢 Job "smoke zmq" found (id: 12093074966)
🟢 Job "release with deb info" found (id: 12093074943)
⏩ Creating pipeline with inputs:
  - ocudu_ref=main
  - compiler=gcc
...
✅ Pipeline created: https://...
```
