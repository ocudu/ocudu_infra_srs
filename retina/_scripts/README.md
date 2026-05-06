# Run a Retina Test in local

## TL;DR

### Terminal 1 - Start the testbed

```bash
# Setup following env variables

# your ocudu, retina and amarisoft folders
export OCUDU_PATH=/builds/ocudu/ocudu
export RETINA_PATH=/builds/ocudu/ocudu_infra_srs/retina
export AMARISOFT_PATH=~/workspace/amarisoft/2025-09-19/

# Amarisoft variables
export AMARISOFT_LICENSE_IP=your_license_server_ip
export AMARISOFT_UE_LICENSE_TAG=your_ue_tag
export AMARISOFT_MME_LICENSE_TAG=your_mme_tag

# profile: testbed to start. Look at "launcher" service inside "docker-compose.yml" to see all available profiles
export RETINA_PROFILE=zmq_amariue_mme

# Build gnb and zmq driver (call it when you change gnb code and first time)
$RETINA_PATH/_scripts/build_ocudu.sh

# Run the test
$RETINA_PATH/_scripts/retina_local.sh
```

### Terminal 2 - Run the test

```bash
docker exec launcher retina-launcher --retina-testbed=/workdir/retina/_scripts/testbed.yml <pytest-arguments>
```

## 1. Download repos

- Download ocudu repo
- Download ocudu_infra_srs repo

- If Docker must clone a private GitLab repository during image builds, please ensure your token is set as an environment variable.

```bash
export GITLAB_TOKEN=<your-gitlab-token>
```

## 2. Setup variables

- Generate .env file for the docker-compose. **This script needs to be called each time you make a change in the ocudu_infra_srs repo**. For example, when you checkout a new branch or update it.

```bash
cd ocudu_infra_srs/retina # where you checked out retina repo
cd _scripts
python3 generate_env.py --ocudu-path ~/workspace/ocudu --amari-path ~/workspace/amari

# ocudu-path: your ocudu repo folder.
# amari-path: folder where you have Amarisoft's artifacts (install.sh and tar.gz files).
  # Only mandatory if you're going to use Amarisoft.
```

## 3. Build ocudu apps and zmq driver

- Compile ocudu and amarisoft's zmq driver (if you needed it): To be sure your bin/lib is compatible with the retina containers, it's better to compile them again using the same process the ci does.

To build them with default flags and ZMQ enabled, you can run:

```bash
docker compose --profile builders up
```

By default, ocudu will be built with the following command:

```bash
builder.sh -b build_retina -c gcc -DBUILD_TESTING=False -DCMAKE_BUILD_TYPE=Release -DFORCE_DEBUG_INFO=False -DASSERT_LEVEL=PARANOID -DMARCH=x86-64-v3 /builds/ocudu/ocudu
```

where the default build folder is `build_retina` inside the ocudu repo.

Example console output during build process:

```bash
 ✔ Container amari-zmq-builder  Recreated                                                                                                                                                0.2s
 ✔ Container ocudu-builder      Recreated                                                                                                                                                0.2s
Attaching to amari-zmq-builder, ocudu-builder
ocudu-builder      | Cleaning build directory: build
amari-zmq-builder  | Cleaning build directory: build_trx_ocudu
amari-zmq-builder  | Statistics zeroed
ocudu-builder      | Statistics zeroed
ocudu-builder      | -- The C compiler identification is GNU 13.2.0
amari-zmq-builder  | -- The C compiler identification is GNU 13.2.0
amari-zmq-builder  | -- The CXX compiler identification is GNU 13.2.0
ocudu-builder      | -- The CXX compiler identification is GNU 13.2.0
...
amari-zmq-builder  | [100%] Built target trx_ocudu_test
amari-zmq-builder exited with code 0
...
ocudu-builder      | [100%] Built target gnb
ocudu-builder exited with code 0
```

If you want to customize the ocudu build cmd line you can call each container with different arguments:

```bash
docker compose run --rm ocudu-builder builder.sh -b build_retina -c gcc /builds/ocudu/ocudu
```

Remember to re-build your binary/libs every time you made a change or checkout new code.

## 4. Create local testing environment

Currently there are five available testbeds:

- zmq_amariue_mme: Amarisoft UE + 2 OCUDU gNB + 1 OCUDU CU + 2 OCUDU DUs + Amarisoft 5GC
- zmq_amariue_open5gs: Amarisoft UE + 2 OCUDU gNB + 1 OCUDU CU + 2 OCUDU DUs + Open5gs
- zmq_srsue: srsUE + OCUDU gNB + Open5gs + Flexric
- zmq_ntn: Amarisoft UE + 2 OCUDU gNB + 1 OCUDU CU + 2 OCUDU DUs + Open5gs + NTN Channel Emulator

### Testbed file

You can generate the testbed by running the script with the same profile:

```bash
python3 generate_testbed.py --profile zmq_amariue
```

this will generate a `testbed.yml` file in the scripts folder. Inside the launcher container, it will be mapped into `/workdir/retina/_scripts/testbed.yml`

### Docker compose

Select the testbed you want using `--profile`.

If you are going to use Amarisoft, you need to setup the following env variables:

```bash
export AMARISOFT_LICENSE_IP=your_license_server_ip
export AMARISOFT_UE_LICENSE_TAG=your_ue_tag
export AMARISOFT_MME_LICENSE_TAG=your_mme_tag
```

```bash
docker compose --profile zmq_amariue up --remove-orphans
```

The console output should be similar to:

```bash
[+] Running 6/0
 ✔ Container scripts-agent-image-1     Created                                                                                                                                           0.0s
 ✔ Container launcher                  Created                                                                                                                                           0.0s
 ✔ Container open5gs                   Created                                                                                                                                           0.0s
 ✔ Container scripts-gnb-base-image-1  Created                                                                                                                                           0.0s
 ✔ Container amariue                   Created                                                                                                                                           0.0s
 ✔ Container gnb                       Created                                                                                                                                           0.0s
Attaching to amariue, gnb, launcher, open5gs, agent-image-1, gnb-base-image-1
agent-image-1 exited with code 0
gnb-base-image-1 exited with code 0
amariue           | 2024-12-11 12:13:51,732 - INFO - Parameter grpc.maximum_workers set to 96
amariue           | 2024-12-11 12:13:51,732 - INFO - Parameter grpc.server_ports set to [50064, 50065, 50066, 50067]
amariue           | 2024-12-11 12:13:51,737 - INFO - Retina Agent for amarisoft-ue listening at port(s) 50064, 50065, 50066, 50067
gnb               | 2024-12-11 12:13:51,876 - INFO - Retina Agent for ocudu-gnb listening at port(s) 50051
open5gs           | 2024-12-11 12:13:53,579 - INFO - Parameter grpc.maximum_workers set to 96
open5gs           | 2024-12-11 12:13:53,579 - INFO - Parameter 5gc.tun_mask set to 24
open5gs           | 2024-12-11 12:13:53,583 - INFO - Retina Agent for open5gs-5gc listening at port(s) 50051
```

There are some containers running now. Although is not mandatory for running a test, you can **enter** into a container by doing:

```bash
docker exec -it <name> bash
```

## 5. Run an existing E2E test in local environment

You can run a test with the following command:

```bash
docker exec launcher retina-launcher --retina-testbed=/workdir/retina/_scripts/testbed.yml -x -m {marker} --force-download
```

Alternatively, You can also enter into the container and run your command:

```bash
docker exec -it launcher sh
```

And execute inside the container:

```bash
retina-launcher --retina-testbed=/workdir/retina/_scripts/testbed.yml -x -m example --force-download
```

This will:

- use our local testbed declared in the yml file -\> Retina will know which UEs/GNBs/COREs are available and their IPs
- Run tests that have `example` mark (tag/label) -\> That selects a 4UE ping
- Download all the artifacts even if the test passes

The console output should be similar to:

```bash
============================================================================ test session starts ============================================================================
platform linux -- Python 3.12.3, pytest-7.4.4, pluggy-1.5.0
Using --random-order-bucket=class
Using --random-order-seed=190668

rootdir: ~/workspace/ocudu_infra_srs/e2e
configfile: pyproject.toml
plugins: typeguard-2.13.3, rerunfailures-14.0, retina_launcher-0.0, json-0.4.0, xdist-3.6.1, html-3.2.0, random-order-1.1.1, metadata-3.1.1
collected 203 items / 202 deselected / 1 selected

tests/ping.py::test_example
------------------------------------------------------------------------------ live log setup -------------------------------------------------------------------------------
2024-12-04 14:25:26 [INFO] Testbed: ~/workspace/retina/scripts/testbed.yml
2024-12-04 14:25:26 [INFO] Register parameters: ()
2024-12-04 14:25:26 [INFO] Register templates: ()
2024-12-04 14:25:26 [INFO] Force download: False
------------------------------------------------------------------------------- live log call -------------------------------------------------------------------------------
2024-12-04 14:25:26 [INFO] Ping Test
2024-12-04 14:25:26 [INFO] Test config:
...
2024-12-04 14:25:27 [INFO] 5GC [131224370898048] started
2024-12-04 14:25:29 [INFO] GNB [131224370904144] started
2024-12-04 14:25:30 [INFO] UE [131224372693280] started
2024-12-04 14:25:30 [INFO] UE [131224391267872] started
2024-12-04 14:25:31 [INFO] UE [131224372885840] started
2024-12-04 14:25:31 [INFO] UE [131224370892672] started
2024-12-04 14:25:36 [INFO] UE [131224372693280] attached:
  imsi: "001010123456790"
  algo_str: "milenage"
  k: "00112233445566778899aabbccddeeff"
  opc: "63bfa50ee6523365ff14c1f45f88737d"
  amf: "8000"
  tel: 9876543201
  ipv4: "10.45.0.2"
  ipv4_gateway: "10.45.0.1"
 ...
2024-12-04 14:25:45 [INFO] Ping [10.45.0.2] 5GC -> UE:
  status: true
  sent: 10
  received: 10
  min: 8.69
  avg: 18.1
  max: 48.858
  mdev: 10.771
...
2024-12-04 14:25:47 [INFO] UE_1 has stopped
2024-12-04 14:25:50 [INFO] UE_2 has stopped
2024-12-04 14:25:53 [INFO] UE_3 has stopped
2024-12-04 14:26:01 [INFO] UE_4 has stopped
2024-12-04 14:26:02 [INFO] GNB has stopped
2024-12-04 14:26:02 [INFO] 5GC has stopped
PASSED                                                                                                                                                                [100%]
----------------------------------------------------------------------------- live log teardown -----------------------------------------------------------------------------
2024-12-04 14:26:02 [INFO] GNB has successfully stopped
2024-12-04 14:26:02 [INFO] 5GC has successfully stopped
2024-12-04 14:26:02 [INFO] UE_1 has successfully stopped
2024-12-04 14:26:02 [INFO] UE_2 has successfully stopped
2024-12-04 14:26:02 [INFO] UE_3 has successfully stopped
2024-12-04 14:26:02 [INFO] UE_4 has successfully stopped
2024-12-04 14:26:02 [INFO] Closing amarisoft-ue-0 [131224372693280]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.
2024-12-04 14:26:02 [INFO] Closing amarisoft-ue-1 [131224391267872]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.
2024-12-04 14:26:02 [INFO] Closing amarisoft-ue-2 [131224372885840]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.
2024-12-04 14:26:02 [INFO] Closing amarisoft-ue-3 [131224370892672]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.
2024-12-04 14:26:02 [INFO] Closing open5gs-5gc [131224370898048]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.
2024-12-04 14:26:02 [INFO] Closing ocudu-gnb [131224370904144]
2024-12-04 14:26:02 [INFO] Waiting for Keep alive thread to finish
2024-12-04 14:26:02 [INFO] Keep alive thread ended.


---------------------------------------------------- generated xml file: ~/workspace/ocudu_infra_srs/e2e/out.xml -----------------------------------------------------
-------------------------------------------- generated html file: file://~/workspace/ocudu_infra_srs/e2e/log/report.html ---------------------------------------------
==================================================================== 1 passed, 202 deselected in 36.28s =====================================================================
```

You can now access the test report in your PC inside your `ocudu-infra-srs` folder: `$OCUDU_INFRA_SRS_PATH/tests/e2e/log/report.html`.

You can add `--help` to see pytet's help, with info about how to select test and useful options like `--collect-only`

## 6. Retina Development

If retina dependencies and/or containers Dockerfile have been modified, you'll need to recreate the images locally. Do it by adding a `--build` flag to the script.

```bash
$RETINA_PATH/_scripts/retina_local.sh --build
```

### Change Amarisoft version

To use a different Amarisoft version, just run the `generate_env.py` script setting the `amari-path` for that version in your PC. The script will get the version presented in that folder and configure everything:

- Overwrite that value in the generated `.env`
- Extract `trx_uhd` driver (if not done already) so you can build zmq driver.
- Copy that folder inside amarisoft's retina images build context.

Not all Amarisoft's versions have an already existing image, so you will probably need to build it locally:

```bash
docker compose up amariue --build
```

this will rebuild amariue's image and also any previous image it depends on (like basic agent image).

## 7. Stopping the testing environment

To tear down your local setup, you can press `control-c` and Docker will stop the containers. **However, to do a complete cleanup (and removing networks, stopped containers and more) you need to run:**

```bash
docker compose --profile all down
```

## 8. Troubleshooting

### CPU scaling governor is not set to performance

If the test fails because there are multiple warnings in the gnb like:

```text
CPU0 scaling governor is not set to performance, which may hinder performance. You can set it to performance using the "ocudu_performance" script
CPU1 scaling governor is not set to performance, which may hinder performance. You can set it to performance using the "ocudu_performance" script
...
```

You can run the `ocudu_performance` script to get rid of those warnings, as the message suggest:

```bash
sudo ocudu/scripts/ocudu_performance
```

### Failed to create network

If your docker compose up command fails with a message like the following:

```bash
 ✘ Network retina_local_network  Error                                                                                                                                                   0.0s
failed to create network retina_local_network: Error response from daemon: invalid pool request: Pool overlaps with other one on this address space
```

You need to cleanup a network created by a previous execution:

```bash
docker compose --profile all down
```

Or, directly call the prune command

```bash
docker system prune
```


### Could not initialize RF driver

If your AmariUE fails to start with:
```bash
Could not load '/opt/lteue/trx_ocudu.so' (/opt/lteue/trx_ocudu.so: cannot read file data: Is a directory)
Could not initialize RF driver
...
```
When using [fish-shell](https://fishshell.com/) the UID and GID are not set but as the containers use volumes to create the build files on your local system, the UID and GID are passed to the containers. To fix this you manually need to run:
```bash
export UID=$(id -u)
export GID=$(id -g)
```
