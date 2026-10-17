# UNIHIKER M10 × Muse

An experimental UNIHIKER M10 project that pairs a Debian 12 board with Muse's Linux Device SDK and adds a touchscreen dashboard, button navigation, voice notes, and on-screen replies.

Start with the illustrated [English guide](guide/English%20Tutorial.md) or its [PDF](guide/output/pdf/UNIHIKER-M10-Muse-Guide.pdf). The guide covers pairing and shows the expected interaction. This repository preserves the source used for the demonstrated interface; it is **not yet a one-command installer for a fresh M10**.

![Four photos of the M10 dashboard and work mode](guide/images/m10-live-story-2x2.jpg)

## What is here

| Path | Contents |
| --- | --- |
| [`guide/`](guide/) | English tutorial, preview HTML, PDF, and article images |
| [`m10-ui-english/`](m10-ui-english/) | English touchscreen, agent, voice, connection code, and UI captures |
| [`m10-services/`](m10-services/) | Hardware broker, board-specific PinPong loader, and systemd unit examples |
| [`sdk/linux/`](sdk/linux/) | A working snapshot of the Muse Linux SDK with M10-specific extensions; see [provenance and license](sdk/README.md) |

The official [Muse Linux Device SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) handles device pairing and the Muse session. This project's additions expose M10 hardware and screen operations and coordinate the local UI. Muse's SDK does not install the dashboard by itself.

## Before using the code on a board

1. Confirm the exact board, Debian and kernel versions, network route, Bluetooth, and installed PinPong package. This code was tested on a specific Debian 12 M10 image; paths and hardware devices can differ on other images.
2. Follow the [official Linux SDK instructions](https://github.com/facebookincubator/muse-gadget-sdk/blob/main/linux/README.md) to pair and verify a real `device.health` call from the Muse app. Keep the SDK token and paired identity out of this repository.
3. Read the [English UI deployment notes](m10-ui-english/README.md) and [service notes](m10-services/README.md). Back up existing files and services before integrating the M10-specific pieces. The local UI expects the extended SDK and hardware service, and the service examples use paths tied to the tested board.
4. Check each stage on the actual M10: dashboard readings, A/B pages, recording, upload, Muse reply on screen, and recovery after reboot. Preview images are design checks, not proof of a live end-to-end run on a new board.

The chip temperature is **not** ambient temperature. Light is a raw ADC reading, not lux. Audio level is relative dBFS, not calibrated dBA. The IMU did not return reliable data on the test image and should show unavailable rather than invented values. The plant-care image in the guide is concept art, not a tested pump-control build.

## Publication status

This is an initial source and documentation snapshot for review. A reproducible installer, clean-board validation, and English voice-reply localization remain to be completed before presenting it as a turnkey project. In particular, do not copy the board-specific PinPong loader to a different kernel without checking its module version and hardware behavior.

The repository does not contain SDK tokens, paired-device credentials, personal network settings, or board backups. If you adapt it, keep those out of Git history too.

## Attribution

The code under [`sdk/linux/`](sdk/linux/) derives from Meta's [muse-gadget-sdk](https://github.com/facebookincubator/muse-gadget-sdk) at commit `812c46f9fe42b69d916613a9dc702cbac5ff7b54`; its Apache-2.0 license is preserved in [`sdk/LICENSE`](sdk/LICENSE). The M10 operating system, PinPong package, and kernel module are separate dependencies and are not redistributed here. A license for the original M10-specific code and article imagery has not yet been selected; do not assume the SDK's Apache-2.0 license applies to those files.
