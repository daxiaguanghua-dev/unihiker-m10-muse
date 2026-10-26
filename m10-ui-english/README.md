# English M10 interface source

This folder contains the English interface deployed to one cloned UNIHIKER M10 running Debian 12. It is an interface variant, **not a stand-alone installer**. The Chinese originals remain outside this publication folder.

| Source | Tested board path | Role |
| --- | --- | --- |
| `muse_status.py` | `/root/muse_status.py` | 240×320 touchscreen dashboard and work mode |
| `muse_ui_model.py` | `/root/muse_ui_model.py` | Text pagination and status formatting |
| `muse_connection.py` | `/root/muse_connection.py` | Live Muse connection status and retry diagnosis |
| `m10_agent.py` | `/home/muse/m10_agent.py` | Buttons, display requests, and voice workflow |
| `m10_history.py` | `/home/muse/m10_history.py` and `/root/m10_history.py` | Local text history shared by agent and display |
| `m10_voice.py` | `/home/muse/m10_voice.py` | Record and submit a short voice note |

It expects an active `musegadget` service with this repository's M10 SDK extensions, plus `muse-m10-hardware`, `muse-m10-agent`, and `muse-display-screen`. The UI communicates through local sockets and the display request file. The SDK token and paired identity must be configured on the board through the official pairing process; they are not supplied here.

On the tested image, the display service runs against the existing X11 desktop. The hardware service is privileged, while the Muse agent runs as the `muse` account. Inspect the service units and file permissions before adapting this layout. The source includes a direct Wi-Fi path as well as a local-proxy check used on the original test setup; neither path guarantees network access on another board.

The figures in [`figures/`](figures/) show the four dashboard pages and work states. The dashboard screenshots were captured from the running board. The work-state images use preview data to inspect layout; they do not establish that a new voice exchange completed during that capture. The voice-note request in `sdk/linux/src/musegadget/link_client.py` asks Muse to reply in English by default and show the actual reply on the M10, while allowing another language when explicitly requested. Muse generates the reply, so verify the language and screen delivery in a live conversation after deploying the updated SDK to the board.

Entering Work Mode shows the recording instructions first. It does not replay `last_reply.json` as the live page on every mode switch. A fresh `display.show` call from Muse replaces the instructions with the new reply; the agent also watches for a newly written `last_reply.json` and displays its title and text while Work Mode is active. This fallback covers Muse writing a reply file instead of calling `display.show`.

In Work Mode, A and B page from the current instruction or reply into earlier interactions; there is no separate History menu. The board keeps the 50 most recent voice-send timestamps and Muse reply texts in `/home/muse/.local/share/muse-m10/history.json`. It does not retain audio or claim to show a speech transcript. The log starts when this version is installed, with at most the previously saved last reply imported on first run.

An imported `last_reply.json` from before history tracking has no reliable source metadata. The UI labels that entry **Old Display / Source Unverified**, rather than claiming it is an authenticated Muse reply. Later replies recorded through the live device workflow remain labeled as Muse replies.

The on-screen reply card uses A/B navigation only. It groups an explicit line of Muse text on one page when it fits, and marks multi-page replies with a continuation label. The saved reply text remains intact; the small display removes unsupported symbols and normalizes spacing while rendering.

Once a Muse reply is on screen, a repeated Work Mode request leaves it visible. It stays until the user records again or switches to the dashboard. The touchscreen process uses a single-instance lock because the tested M10 image can launch it through both the board's desktop and the systemd service.

For a new board, first pair the [official Linux SDK](https://github.com/facebookincubator/muse-gadget-sdk/tree/main/linux) and verify `device.health`. Back up existing board files, integrate the SDK extensions and [hardware services](../m10-services/README.md), then deploy this UI and verify each function on-device. Do not transplant another board's identity, credentials, backup, or kernel module.

Run the pure-Python UI model tests with `python -m unittest discover -s m10-ui-english -p 'test_english.py'` from the repository root. Full hardware and Muse tests require an actual paired M10.
