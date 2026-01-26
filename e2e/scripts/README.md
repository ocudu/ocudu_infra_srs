# Scripts

In this folder there are some scripts to help the user to trigger customized Build + E2E Pipelines.

- [run_e2e_pipeline](#pipeline-trigger-script)
- [run_viavi_pipeline](#viavi-pipeline-trigger-script)

## Pipeline Trigger Script

The `run_e2e_pipeline.py` script allows you to create a [GitLab pipeline with custom configurations](../README.md#manual-pipeline), helping the user to fill all the inputs that Gitlab CI expects.

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

**Running on a non-default infrastructure git repository/branch:**

You can set the environment variables `OCUDU_INFRA_PATH` and `OCUDU_INFRA_REF` to specify a different repository and branch other than the defaults (`ocudu/ocudu_infra_srs` and `main`).

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

## Viavi Pipeline Trigger Script

The `run_viavi_pipeline.py` script allows you to trigger Viavi test pipelines in GitLab CI with custom configurations.

### Installation

```bash
# Install dependencies
pip install pyyaml python_gitlab
```

### Usage

The script provides two ways to run Viavi tests:

**A) Use predefined tests from test_declaration.yml:**

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_GITLAB_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --ocudu-ref dev \
  --build-mode rtsan
```

**B) Use custom test from Viavi campaign:**

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_GITLAB_TOKEN \
  --test "32UE ideal UDP attach-detach with traffic conservative" \
  --campaign "C:\ci\CI 4x4 ORAN-FH-complete.xml" \
  --ocudu-ref dev \
  --build-mode standard
```

**C) Running on a non-default infrastructure git repository/branch:**

You can set the environment variables `OCUDU_INFRA_PATH` and `OCUDU_INFRA_REF` to specify a different repository and branch other than the defaults (`ocudu/ocudu_infra_srs` and `main`).

### Arguments

**Required:**

- `--token`: GitLab private access token

**Common options:**

- `--ocudu-path`: OCUDU repository path (default: `ocudu/ocudu`)
- `--ocudu-ref`: Branch or tag to test (default: `dev`)
- `--build-mode`: Build configuration - `standard` or `rtsan` (default: `rtsan`)
  - standard: Release build
  - rtsan: Same as standard but with RealTime Sanitizer enabled
- `--timeout`: Test timeout in seconds (optional, uses Viavi default if not specified)

**For predefined tests:**

- `--testid`: Test ID from `test_declaration.yml` (e.g., `"1UE ideal UDP bidirectional"`)

**For custom tests:**

- `--test`: Test name in the Viavi campaign
- `--campaign`: Campaign file path (default: uses default CI campaign)

**Advanced:**

- `--gnb-cli`: Custom arguments for the gNB binary (e.g., `"log --all_level=info"`)
  - ⚠️ This overrides any configuration in `test_declaration.yml`

### Examples

```bash
# Run predefined test with rtsan
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --build-mode rtsan
```

```bash
# Run custom test with standard build
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --test "My Custom Test" \
  --build-mode standard
```

```bash
# Run with custom gNB logging
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --gnb-cli "log --all_level=debug"
```
