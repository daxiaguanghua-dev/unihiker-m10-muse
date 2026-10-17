"""Load this test image's matching PinPong module without flashing firmware."""
import ctypes
import fcntl
import os
from pathlib import Path
import subprocess
import sys
import time

BASE = Path('/opt/unihiker/venv312/lib/python3.12/site-packages/pinpong/base/gd32')
MODULE = BASE / 'pinpong_linux_module_6_1.ko'


def load():
    release = os.uname().release
    version = subprocess.check_output(['modinfo', '-F', 'vermagic', str(MODULE)], text=True).split()[0]
    if version != release:
        raise RuntimeError('PinPong module does not match running kernel')
    if not Path('/sys/module/pinpong_linux_module').exists():
        original = BASE / 'anaysis.py'
        source = original.read_text(encoding='utf-8')
        suffix = '\n    pinConfig()'
        if not source.rstrip().endswith('pinConfig()') or suffix not in source:
            raise RuntimeError('Unexpected bundled loader; stop before executing it')
        # Keep the bundled mode map and module arguments. Omit the final routine
        # that can reset or flash the coprocessor on a version error.
        source = source.rsplit(suffix, 1)[0]
        namespace = {'__name__': '__main__', '__file__': str(original)}
        exec(compile(source, str(original), 'exec'), namespace)
    for _ in range(20):
        if Path('/dev/pinpong_config').exists():
            break
        time.sleep(0.1)
    # Use the device interfaces directly, without the library's automatic
    # firmware flashing fallback. Individual reads report their own errors.
    for device in ('/dev/pinpong_config', '/dev/pinpong_count', '/dev/icm20689', '/dev/buzzer'):
        if not Path(device).exists():
            raise RuntimeError('Missing PinPong device: ' + device)
    print('Matching PinPong kernel module and hardware device nodes ready', flush=True)


if __name__ == '__main__':
    load()
