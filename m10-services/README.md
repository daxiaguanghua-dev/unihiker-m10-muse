# M10 hardware and service notes

These files are from the tested Debian 12 M10 setup. They document the integration but do not constitute an unattended installer.

`m10_hardware_service.py` serves a fixed set of hardware operations through a local socket; it does not execute arbitrary shell commands. `m10_load_hardware.py` expects a particular PinPong installation and a kernel module matching the running kernel. It deliberately checks module compatibility and does not flash GD32 firmware. Review its paths and behavior before using it on a different M10 image.

The three `.service` files show how the hardware broker, Muse agent, and display were started on the tested board. They assume the `muse` account, X11 display `:0`, and specific `/root`, `/home/muse`, and `/usr/local/lib/muse-m10` paths. Back up and inspect any existing services before adapting them. A fresh installation must also install and verify the [official Muse Linux SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) and the M10 extensions in [`../sdk/linux/`](../sdk/linux/).

The IMU was not reliable on the internal test image. This repository does not include a replacement kernel module or GD32 firmware. Keep unavailable values explicit and do not bypass the kernel/module compatibility check.
