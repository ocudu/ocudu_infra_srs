# Scripts

This directory contains utility scripts to help trigger customized Build + E2E pipelines in GitLab.

## Available Scripts

- [Pipeline Trigger Script](#pipeline-trigger-script) - `run_e2e_pipeline.py`: Trigger custom E2E test pipelines
- [Viavi Pipeline Trigger Script](#viavi-pipeline-trigger-script) - `run_viavi_pipeline.py`: Trigger Viavi-specific test pipelines

## Pipeline Trigger Script

The `run_e2e_pipeline.py` script allows you to create [GitLab pipelines with custom configurations](../README.md#manual-pipeline), helping you specify all the inputs that GitLab CI expects.

### Installation

```bash
# Install required dependencies
pip install pyyaml python-gitlab
```

### Usage

The script provides flexible ways to specify pipeline inputs:

#### Default Behavior (Interactive Mode)

- The script will prompt you for **every input field**
- Press Enter to accept the default value shown in brackets
- If you provide a value via **command-line argument**, the script will show it and ask for confirmation

#### Using `--yes` Flag

- Skips all interactive prompts and confirmations
- Uses command-line values if provided, otherwise uses defaults

#### Using `--replicate JOB_ID_OR_NAME`

- Fetches all input values from an existing GitLab job
- Pre-populates all fields with values from that job
- You can still override any value via:
  - Interactive input (without `--yes`)
  - Command-line arguments (takes priority)

#### Priority Order (Highest to Lowest)

1. Command-line arguments
2. Interactive user input (if not using `--yes`)
3. Replicated job values (if using `--replicate`)
4. Default values from `.gitlab-ci.yml`

#### Dry Run Mode

Add the `--dryrun` flag to preview the input values without creating any pipeline.

#### Custom Infrastructure Repository/Branch

Set environment variables to use a different infrastructure repository or branch:

- `OCUDU_INFRA_PATH`: Repository path (default: `ocudu/ocudu_infra_srs`)
- `OCUDU_INFRA_REF`: Branch name (default: `main`)

#### Examples

**Interactive mode:**

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

**Non-interactive mode with explicit parameters:**

```bash
python3 run_e2e_pipeline.py --token YOUR_GITLAB_TOKEN --ocudu-ref main --testbed none --yes

⏩ Creating pipeline with inputs:
  - ocudu_ref=main
...
✅ Pipeline created: https://...
```

**Replicate existing job with override:**

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

#### Option A: Use Predefined Tests

Run tests from `test_declaration.yml`:

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_GITLAB_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --ocudu-ref dev \
  --build-mode rtsan
```

#### Option B: Use Custom Test from Viavi Campaign

Run a custom test from a Viavi campaign file:

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_GITLAB_TOKEN \
  --test "32UE ideal UDP attach-detach with traffic conservative" \
  --campaign "C:\ci\CI 4x4 ORAN-FH-complete.xml" \
  --ocudu-ref dev \
  --build-mode standard
```

#### Option C: Custom Infrastructure Repository/Branch

Set environment variables to use a different infrastructure repository or branch:

- `OCUDU_INFRA_PATH`: Repository path (default: `ocudu/ocudu_infra_srs`)
- `OCUDU_INFRA_REF`: Branch name (default: `main`)

### Arguments

#### Required

| Argument | Description |
|----------|-------------|
| `--token` | GitLab private access token |

#### Common Options

| Argument | Description | Default |
|----------|-------------|----------|
| `--ocudu-path` | OCUDU repository path | `ocudu/ocudu` |
| `--ocudu-ref` | Branch or tag to test | `dev` |
| `--build-mode` | Build configuration: `standard` or `rtsan` | `rtsan` |
| `--timeout` | Test timeout in seconds (optional) | Viavi default |

**Build modes:**

- `standard`: Release build
- `rtsan`: Release build with RealTime Sanitizer enabled

#### For Predefined Tests

| Argument | Description |
|----------|-------------|
| `--testid` | Test ID from `test_declaration.yml` (e.g., `"1UE ideal UDP bidirectional"`) |

#### For Custom Tests

| Argument | Description | Default |
|----------|-------------|----------|
| `--test` | Test name in the Viavi campaign | - |
| `--campaign` | Campaign file path | Default CI campaign |

#### Advanced Options

| Argument | Description |
|----------|-------------|
| `--gnb-cli` | Custom arguments for the gNB binary (e.g., `"log --all_level=info"`) |

⚠️ **Note**: Using `--gnb-cli` overrides any configuration in `test_declaration.yml`.

### Examples

**Run predefined test with rtsan:**

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --build-mode rtsan
```

**Run custom test with standard build:**

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --test "My Custom Test" \
  --build-mode standard
```

**Run with custom gNB logging:**

```bash
python3 run_viavi_pipeline.py \
  --token YOUR_TOKEN \
  --testid "1UE ideal UDP bidirectional" \
  --gnb-cli "log --all_level=debug"
```
