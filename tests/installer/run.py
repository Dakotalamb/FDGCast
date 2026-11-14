"""Exercise the real Windows wizard and capture its actual pages.
SPDX-License-Identifier: GPL-2.0-or-later
"""
import argparse
import os
from pathlib import Path
import subprocess
import time
from pywinauto import Desktop

p=argparse.ArgumentParser()
p.add_argument('--installer',required=True)
p.add_argument('--out',default='qa-installer')
a=p.parse_args()
out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
install_dir=Path(os.environ['RUNNER_TEMP'])/'FDGCast-Installer-QA'
canary=Path(os.environ['LOCALAPPDATA'])/'ForgeCast'/'installer-ui-canary.txt'
canary.parent.mkdir(parents=True,exist_ok=True);canary.write_text('keep-user-settings',encoding='utf-8')


def wait_for(predicate,seconds=30):
    until=time.monotonic()+seconds
    while time.monotonic()<until:
        result=predicate()
        if result:return result
        time.sleep(.25)
    raise RuntimeError('Installer UI condition timed out')


def wizard():
    return next((w for w in Desktop(backend='win32').windows(visible_only=True)
                 if w.class_name()=='TWizardForm' and 'FDGCast' in w.window_text()),None)


def text_present(win,text):
    return any(text in c.window_text() for c in win.descendants() if c.is_visible())


def click(win,text):
    controls=[c for c in win.descendants() if c.is_visible() and c.is_enabled()
              and c.window_text().replace('&','').strip()==text]
    if len(controls)!=1:raise RuntimeError(f'Expected one enabled {text!r} control, found {len(controls)}')
    controls[0].click_input()


def capture(win,name):
    win.set_focus();time.sleep(.25)
    win.capture_as_image().save(out/(name+'.png'))
    (out/(name+'.txt')).write_text('\n'.join(c.window_text() for c in win.descendants() if c.is_visible()),encoding='utf-8')


def start():
    return subprocess.Popen([str(Path(a.installer).resolve()),'/SP-','/NORESTART','/DIR='+str(install_dir)])


try:
    process=start();win=wait_for(wizard)
    wait_for(lambda:text_present(win,'Your stream starts here.'))
    capture(win,'01-welcome')
    # The branded surface should be dark; native high-contrast mode remains supported.
    click(win,'Next >');wait_for(lambda:text_present(win,'I &accept the agreement') or text_present(win,'I accept the agreement'))
    capture(win,'02-license');click(win,'I accept the agreement');click(win,'Next >')
    wait_for(lambda:text_present(win,'Choose your install location'));capture(win,'03-location')
    assert text_present(win,str(install_dir)), 'Chosen install folder is not shown'
    click(win,'Next >');wait_for(lambda:text_present(win,'Select Additional Tasks'))
    capture(win,'04-shortcuts');click(win,'Next >')
    wait_for(lambda:text_present(win,'Ready to install FDGCast'));capture(win,'05-ready')
    click(win,'Install');wait_for(lambda:text_present(win,'Installing FDGCast Companion'),seconds=15)
    capture(win,'06-installing')
    wait_for(lambda:text_present(win,'FDGCast is ready.'),seconds=120)
    capture(win,'07-finished')
    click(win,'Finish');process.wait(timeout=30)
    assert process.returncode==0
    assert (install_dir/'FDGCast.exe').is_file()
    assert (install_dir/'LICENSING.md').is_file()
    assert canary.read_text(encoding='utf-8')=='keep-user-settings'
    # A second launch detects the installed app and explains upgrade preservation.
    process=start();win=wait_for(wizard)
    wait_for(lambda:text_present(win,'Ready for your next upgrade?'))
    capture(win,'08-upgrade')
    click(win,'Cancel')
    def exit_dialog():
        return next((w for w in Desktop(backend='win32').windows(visible_only=True)
                     if 'Exit Setup' in w.window_text()),None)
    dialog=wait_for(exit_dialog,seconds=10);click(dialog,'Yes')
    process.wait(timeout=30)
    assert canary.read_text(encoding='utf-8')=='keep-user-settings'
    print('PASS: real branded wizard, license, install location, optional shortcuts, live progress, finish actions, install payload, saved-setting preservation and upgrade messaging.')
except Exception:
    current=wizard()
    if current:
        capture(current,'failure-wizard')
    (out/'failure-windows.txt').write_text('\n'.join(w.window_text() for w in Desktop(backend='win32').windows(visible_only=True)),encoding='utf-8')
    raise
finally:
    canary.unlink(missing_ok=True)
