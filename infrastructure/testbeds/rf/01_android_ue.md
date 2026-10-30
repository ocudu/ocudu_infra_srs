# Set up UE 

This procedure is generic for any Android UE.

## 1. Take a SIM and look for the SIM's IMSI number

A provisioned SIM is required. You will need the IMSI, the K (or "Ki"), and the OPC numbers.

## 2. Insert the configured SIM in the UE

Grab a paper clip and twist it so you can use a pointy end to open the SIM slot in the UE. Insert the SIM in the slot. Then turn on the UE.

## 3. Set the options in the OS wizard

If it is a new UE, the wizard for configuring it for the first time should appear. Connect to a WiFi when it asks for it. Set the Google mail account and its password. If it is not a new UE, reset the system to factory default so in the next boot the wizard appears, or you can also search in the settings the account management and change the account without resetting the system.

Activate the Developer mode by tapping 7 times the "Build number" option in "About phone" in the settings. With it, you can activate USB debugging, necessary for the pipeline; activate it.

Go to the SIM options, and set the APN like this:
```
Name: internet
APN: internet
```

Don't create a screen lock nor a PIN for the UE.

Turn off the WiFi when the configuration is ready.
       
## 4. Connect the UE through USB

Connect the UE to a USB cable and to your `machine`.
> PLACEHOLDER for the `machine`. It needs to be the machine we're going to use as cots server. Later we'll define the ue resource in retina for that machine.

For the UE to accept the adb key, select "Allow USB debugging" on the UE screen after connecting it.

Activate airplane mode.

## 5. Check the UE's serial number

Inside the machine, issue `adb devices`; the adb server might be turned off, but with this command it should turn on. Check the output for device serial numbers; an output example: 

```bash
user@host:~$ adb devices
List of devices attached
abcde	device
fghij	device
```

Then compare the serial numbers ("abcde" and "fghij") to the ones in your cluster definition file, `retina_info.yml` (make sure you use an up-to-date version). An example to create this file can be found here:

https://gitlab.com/ocudu/ocudu_infra_srs/-/blob/main/infrastructure/example/cluster_definition/retina_info.yml

A fake example (with fake values) of an Android resource in what would be your cluster definition file:

```yaml
    resources:
      - type: android
        model: xxxx
        connection: usb
        space: 1
        serial_id: abcde
        imsi: "000000000000001"
        k: 0123456789ABCDEF0123456789ABCDEF
        amf: "8000"
        opc: 0123456789ABCDEF0123456789ABCDEF
        adb_key: KEY...
```

> Note: `adb_key` is the same for all UEs.

Compare "serial_id" to the `adb devices` output. The serial ID "abcde" already exists in the fake example, so it is older, so the new UE's serial number is "fghij". Note it down.

> Note: You can also just do `adb devices` once, then disconnect the new UE then do `adb devices` again, so the not shown serial number is the new UE's. And, of course, connect it again afterwards.

After noting it down, issue "adb kill-server" to turn off the adb server. This is `important`, because the retina agent will start the adb server during the test.

## 6. Add the UE details in the cluster definition

Take the IMSI, the K (or "Ki"), the OPC and the UE's serial number (you noted down all of these numbers in previous steps), and push them in the repo in the aforementioned cluster definition file.

For example, the new (fake) entry would look like this:
```yaml

      - type: android
        model: yyyy
        connection: usb
        space: 1
        serial_id: fghij
        imsi: "000000000000001"
        k: 0123456789ABCDEF0123456789ABCDEF
        amf: "8000" 
        opc: 0123456789ABCDEF0123456789ABCDEF
        adb_key: KEY...
```

## 7. Install iperf3.9 on the Android UE

> Note: "fghij" is the fake example UE device ID. Replace it with the real one.

### 1. Get adb root access into the UE

Make sure the device is authorized (check the phone screen for the authorization when you connect it).

Then find the device id:
```bash
adb devices
```

Then create an adb shell into the UE:
```bash
adb -s fghij shell
```
> Note: the "-s" flag/argument is not needed if only one device is connected.

In the adb shell, switch to the root user:
```bash
su
```

### 2. Copy the iperf3.9 binary into the UE

Download in the host the prebuild binary (you most likely need the arm64-v8a one): https://github.com/ninjab3s/ogt_androidue_utilities

From the host shell, push the "iperf3.9" binary into the "/data/local/tmp" folder in the UE:
```bash
adb push -s fghij iperf3.9 /data/local/tmp
```

### 3. Symlink the binaries to "/system/bin"

From the adb shell with the root user, if "/" or "/system" are read-only, remount them as read-write:
```bash
mount -o remount,rw /system
mount -o remount,rw /
```

Then symlink the binaries:
```bash
ln -s /data/local/tmp/iperf3.9 /system/bin/iperf3
```

### 4. Verify installation

From the adb shell, run `iperf3` and `dropbearmulti` to verify they are working correctly:
```bash
iperf3 -v
dropbearmulti -h
```

## 8. Run a test RF pipeline

As a way to ensure the setup is working, run an RF pipeline.

## 9. Troubleshooting

When the UE is slow to attach or doesn't camp properly do this: open the hidden service menu by dialing `*#*#4636#*#*` on the phone, and there, under "Preferred network type", force it to NR so it camps on the cell faster instead of trying other RATs first.
