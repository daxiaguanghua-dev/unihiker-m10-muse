# English M10 interface source

This folder contains the English interface deployed to one cloned UNIHIKER M10 running Debian 12. It is an interface variant, **not a stand-alone installer**. The Chinese originals remain outside this publication folder.

| Source | Tested board path | Role |
| --- | --- | --- |
| `muse_status.py` | `/root/muse_status.py` | 240×320 touchscreen dashboard and work mode |
| `muse_ui_model.py` | `/root/muse_ui_model.py` | Text pagination and status formatting |
| `muse_connection.py` | `/root/muse_connection.py` | Live Muse connection status and retry diagnosis |
| `m10_agent.py` | `/home/muse/m10_agent.py` | Buttons, display requests, and voice workflow |
| `m10_voice.py` | `/home/muse/m10_voice.py` | Record and submit a short voice note |

It expects an active `musegadget` service with this repository's M10 SDK extensions, plus `muse-m10-hardware`, `muse-m10-agent`, and `muse-display-screen`. The UI communicates through local sockets and the display request file. The SDK token and paired identity must be configured on the board through the official pairing process; they are not supplied here.

On the tested image, the display service runs against the existing X11 desktop. The hardware service is privileged, while the Muse agent runs as the `muse` account. Inspect the service units and file permissions before adapting this layout. The source includes a direct Wi-Fi path as well as a local-proxy check used on the original test setup; neither path guarantees network access on another board.

The figures in [`figures/`](figures/) show the four dashboard pages and work states. The dashboard screenshots were captured from the running board. The work-state images use preview data to inspect layout; they do not establish that a new voice exchange completed during that capture. The voice-note request in `sdk/linux/src/musegadget/link_client.py` asks Muse to reply in English by default and show the actual reply on the M10, while allowing another language when explicitly requested. Muse generates the reply, so verify the language and screen delivery in a live conversation after deploying the updated SDK to the board.

For a new board, first pair the [official Linux SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) and verify `device.health`. Back up existing board files, integrate the SDK extensions and [hardware services](../m10-services/README.md), then deploy this UI and verify each function on-device. Do not transplant another board's identity, credentials, backup, or kernel module.

Run the pure-Python UI model tests with `python -m unittest discover -s m10-ui-english -p 'test_english.py'` from the repository root. Full hardware and Muse tests require an actual paired M10.
