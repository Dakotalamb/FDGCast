"""Bounded local PC telemetry and reversible, session-only OBS priority assist.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import ctypes
import atexit
from ctypes import wintypes
import json
import math
import os
from pathlib import Path
import re
import time
import threading
import uuid
from functools import wraps

try:
    import psutil
except ImportError:
    psutil = None

from .storage import atomic_json
from .windows_tuning import WindowsTuning, LABELS, HIGH_PERFORMANCE, options as optimizer_options


def synchronized(method):
    @wraps(method)
    def call(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return call


def gpu_engines(rows):
    """Aggregate processes per physical engine; never add independent engines."""
    engines = {}
    for name, value in rows:
        match = re.search(r'luid_(.+?)_phys_(\d+)_eng_(\d+)_engtype_(.+?)(?:#\d+)?$', name)
        if not match or not math.isfinite(value) or value < 0:
            continue
        key = match.groups()
        engines[key] = engines.get(key, 0) + value
    if not engines:
        return None
    return {
        'busy_percent': round(min(100, max(engines.values())), 1),
        'render_percent': round(min(100, max((v for k,v in engines.items() if k[3].lower() in ('3d', 'graphics')), default=0)), 1),
        'encode_percent': round(min(100, max((v for k,v in engines.items() if 'encod' in k[3].lower()), default=0)), 1),
    }


class WindowsGPU:
    """Windows GPU Engine counters; no shell, driver downloads or admin access."""
    def __init__(self):
        self.query = ctypes.c_void_p()
        self.counter = ctypes.c_void_p()
        self.api = None
        if os.name != 'nt':
            return
        class Number(ctypes.Union):
            _fields_ = [('doubleValue', ctypes.c_double), ('largeValue', ctypes.c_longlong)]
        class Value(ctypes.Structure):
            _anonymous_ = ('number',)
            _fields_ = [('CStatus', wintypes.DWORD), ('number', Number)]
        class Item(ctypes.Structure):
            _fields_ = [('name', wintypes.LPWSTR), ('value', Value)]
        self.Item = Item
        # LOAD_LIBRARY_SEARCH_SYSTEM32: never resolve a DLL from the working directory.
        self.api = ctypes.WinDLL('pdh.dll', winmode=0x800)
        api = self.api
        api.PdhOpenQueryW.argtypes = [wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        api.PdhAddEnglishCounterW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR, ctypes.c_size_t, ctypes.POINTER(ctypes.c_void_p)]
        api.PdhCollectQueryData.argtypes = [ctypes.c_void_p]
        api.PdhCloseQuery.argtypes = [ctypes.c_void_p]
        api.PdhGetFormattedCounterArrayW.argtypes = [ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p]
        for name in ('PdhOpenQueryW','PdhAddEnglishCounterW','PdhCollectQueryData','PdhCloseQuery','PdhGetFormattedCounterArrayW'):
            getattr(api, name).restype = wintypes.DWORD
        if api.PdhOpenQueryW(None, 0, ctypes.byref(self.query)) or api.PdhAddEnglishCounterW(self.query, r'\GPU Engine(*)\Utilization Percentage', 0, ctypes.byref(self.counter)):
            self.close()
            return
        api.PdhCollectQueryData(self.query)

    def sample(self):
        if not self.api or not self.query.value or not self.counter.value:
            return None
        if self.api.PdhCollectQueryData(self.query):
            return None
        size, count = wintypes.DWORD(), wintypes.DWORD()
        status = self.api.PdhGetFormattedCounterArrayW(self.counter, 0x200, ctypes.byref(size), ctypes.byref(count), None)
        if status != 0x800007D2 or not 0 < size.value <= 8_000_000:
            return None
        buffer = ctypes.create_string_buffer(size.value)
        if self.api.PdhGetFormattedCounterArrayW(self.counter, 0x200, ctypes.byref(size), ctypes.byref(count), buffer):
            return None
        if count.value * ctypes.sizeof(self.Item) > len(buffer):
            return None
        items = ctypes.cast(buffer, ctypes.POINTER(self.Item))
        return gpu_engines((items[i].name or '', items[i].value.doubleValue) for i in range(count.value) if items[i].value.CStatus in (0,1))

    def close(self):
        if self.api and self.query.value:
            self.api.PdhCloseQuery(self.query)
        self.query.value = None
        self.counter.value = None


class PCMonitor:
    def __init__(self):
        self._lock = threading.RLock()
        self.current = {'available':False, 'message':'Waiting for the first PC sample.'}
        self.previous = None
        self.processes = {}
        self.since = {}
        self.gpu = None
        self.last_diagnosis = None
        self.last_scan = 0
        self.process_rows = []
        self.cpu_before = None

    @synchronized
    def sample(self, now=None):
        now = time.monotonic() if now is None else now
        if not psutil:
            self.current = {'available':False, 'message':'PC monitoring component is missing. Reinstall the latest FDGCast build.'}
            return self.current
        try:
            times = psutil.cpu_times()
            # Explicit baselines remain correct when asyncio uses a different worker thread.
            busy = sum(getattr(times,k,0) for k in ('user','system','nice','irq','softirq','steal'))
            total = busy + times.idle + getattr(times,'iowait',0)
            cpu = None
            if self.cpu_before:
                old_busy, old_total = self.cpu_before
                if total > old_total:
                    cpu = round(min(100,max(0,100*(busy-old_busy)/(total-old_total))),1)
            self.cpu_before = (busy,total)
            memory = psutil.virtual_memory()
            network, disk = psutil.net_io_counters(), psutil.disk_io_counters()
            if self.gpu is None:
                try: self.gpu = WindowsGPU()
                except (OSError, AttributeError): self.gpu = False
            gpu = self.gpu.sample() if self.gpu else None
            if now-self.last_scan >= 6 or not self.processes:
                rows, alive = [], {}
                cpus = psutil.cpu_count() or 1
                for process in psutil.process_iter(['pid','name','create_time','memory_info'], ad_value=None):
                    try:
                        info = process.info
                        identity = (info['pid'], info['create_time'])
                        tracked = self.processes.get(identity, process)
                        usage = tracked.cpu_percent(interval=None) / cpus
                        alive[identity] = tracked
                        if identity in self.processes and info['memory_info']:
                            rows.append({'pid':info['pid'], 'name':str(info['name'] or 'Protected process')[:80], 'cpu_percent':round(min(100,usage),1), 'memory_mb':round(info['memory_info'].rss/1048576)})
                    except (psutil.Error, OSError): pass
                self.processes, self.last_scan = alive, now
                by_cpu = sorted(rows, key=lambda r:r['cpu_percent'], reverse=True)[:5]
                by_ram = sorted(rows, key=lambda r:r['memory_mb'], reverse=True)[:5]
                self.process_rows = list({r['pid']:r for r in by_cpu+by_ram}.values())
            rates = {'upload_mbps':None, 'download_mbps':None, 'disk_read_mbps':None, 'disk_write_mbps':None}
            if self.previous:
                stamp, old_net, old_disk = self.previous
                elapsed = now-stamp
                if 0 < elapsed <= 20:
                    for key, current, old, attribute, scale in [
                        ('upload_mbps', network, old_net, 'bytes_sent', 8/1e6),
                        ('download_mbps', network, old_net, 'bytes_recv', 8/1e6),
                        ('disk_read_mbps', disk, old_disk, 'read_bytes', 1/1e6),
                        ('disk_write_mbps', disk, old_disk, 'write_bytes', 1/1e6)]:
                        if current and old:
                            rates[key] = round(max(0,getattr(current,attribute)-getattr(old,attribute))*scale/elapsed,2)
            self.previous = (now, network, disk)
            self.current = dict(available=True, sampled_at=time.time(), cpu_percent=cpu,
                memory_percent=round(memory.percent,1), memory_used_gb=round((memory.total-memory.available)/1073741824,1),
                memory_total_gb=round(memory.total/1073741824,1), gpu=gpu, processes=self.process_rows, **rates)
        except (psutil.Error, OSError):
            self.current = {'available':False, 'message':'Windows PC measurements are temporarily unavailable.'}
        return self.current

    def diagnose(self, obs_issues, now=None):
        now = time.monotonic() if now is None else now
        if self.last_diagnosis is not None and now-self.last_diagnosis > 10:
            self.since.clear()
        self.last_diagnosis = now
        pc = self.current
        if not pc.get('available'):
            self.since.clear()
            return []
        results, observed = [], set()
        for key, label, value, tip in [
            ('cpu','CPU is nearly fully used',pc.get('cpu_percent'),'Limit game FPS or reduce background work. Review the busiest apps below.'),
            ('memory','PC memory is nearly full',pc.get('memory_percent'),'Close unused apps or browser tabs. Memory pressure can cause paging and stutters.'),
            ('gpu','GPU is nearly fully used',(pc.get('gpu') or {}).get('busy_percent'),'Limit game FPS to leave GPU headroom for OBS; reduce scene effects or game graphics if needed.')]:
            if value is not None and value >= 90:
                observed.add(key)
                since = self.since.setdefault(key, now)
                if now-since >= 8:
                    results.append(dict(code='pc_'+key,title=label,evidence=f'{value:.1f}% used across the PC for at least eight seconds.',
                        suggestion=tip,confidence='high',severity='warning',time=time.time()))
        self.since = {k:v for k,v in self.since.items() if k in observed}
        for issue in obs_issues:
            match = 'gpu' if issue.get('code')=='render' else 'cpu' if issue.get('code')=='encode' else None
            if match in observed:
                issue = dict(issue)
                issue['suggestion'] += ' Whole-PC '+match.upper()+' is also above 90%; resource contention is a possible contributor, not a proven cause.'
            results.append(issue)
        return results

    @synchronized
    def close(self):
        if self.gpu: self.gpu.close()


def valid_restore_record(record):
    if not isinstance(record,dict) or ('attempted' in record and not isinstance(record['attempted'],bool)):
        return False
    if record.get('kind') == 'windows':
        setting,original,applied = record.get('setting'),record.get('original'),record.get('applied')
        if setting == 'power':
            try: return str(uuid.UUID(original)) == original and applied == HIGH_PERFORMANCE
            except (ValueError,TypeError,AttributeError): return False
        if setting in ('window_animation','client_animation'):
            return type(original) is int and original in (0,1) and applied == 0
        if setting == 'game_mode':
            return (original is None or type(original) is int and original in (0,1)) and applied == 1
        return False
    created = record.get('created')
    return (record.get('kind') in (None,'priority') and type(record.get('pid')) is int and record['pid'] > 0
        and type(created) in (int,float) and math.isfinite(created) and created > 0
        and record.get('original') == 32 and record.get('applied') == 32768)


class StreamOptimizer:
    """Opt-in for the current stream only. Write restoration journal BEFORE mutation."""
    def __init__(self, directory, demo=False):
        self._lock = threading.RLock()
        self.path = Path(directory)/'optimizer-restore.json'
        self.demo = demo
        self.records = []
        self.windows = None
        self.applied = []
        self.enabled = False
        self.recovery_error = False
        self.message = 'Off. No PC settings changed.'
        self.last_live = time.monotonic()
        if not demo:
            atexit.register(self.restore)
        if not demo and self.path.exists():
            try:
                records = json.loads(self.path.read_text(encoding='utf-8'))
                if not isinstance(records,list) or len(records)>16 or not all(valid_restore_record(r) for r in records):
                    raise ValueError('Invalid restoration record')
                self.records = records
                self.restore()
            except (ValueError, OSError, TypeError):
                self.recovery_error = True
                self.message = 'Previous restoration record could not be read. Review your Windows settings and restart OBS to clear its temporary priority.'

    def public(self):
        return dict(supported=bool(psutil and os.name=='nt' and not self.demo), enabled=self.enabled,
            pending_restore=bool(self.recovery_error or self.records and not self.enabled), message=self.message, applied=list(self.applied))

    @synchronized
    def start(self, live, selected=None):
        if not self.public()['supported']:
            raise ValueError('Stream Optimizer is available in the Windows desktop app, outside demo mode.')
        if live is not True:
            raise ValueError('Start a stream first, then enable Stream Optimizer for this session.')
        if self.records or self.enabled or self.recovery_error:
            raise ValueError('Restore the previous optimization before enabling it again.')
        # Preserve the old priority-only contract when called by an older client.
        selected = optimizer_options(selected) if selected is not None else dict(priority=True,animations=False,power=False,game_mode=False)
        records = []
        for process in psutil.process_iter(['name'], ad_value=None):
            try:
                if not selected['priority']: continue
                if (process.info['name'] or '').lower() not in ('obs64.exe','obs32.exe'):
                    continue
                original = process.nice()
                if original != psutil.NORMAL_PRIORITY_CLASS:
                    continue
                records.append(dict(pid=process.pid,created=process.create_time(),original=int(original),applied=int(psutil.ABOVE_NORMAL_PRIORITY_CLASS)))
            except (psutil.Error, OSError): pass
        if len(records)>1:
            raise ValueError('More than one OBS instance is running. Close unused instances before using Stream Optimizer.')
        if any(selected[k] for k in ('animations','power','game_mode')):
            try:
                if self.windows is None: self.windows = WindowsTuning()
                records += self.windows.prepare(selected)
            except OSError as exc:
                raise ValueError('Windows settings could not be prepared. No changes were made. '+str(exc))
        if not records:
            raise ValueError('The selected settings already match, or OBS has a custom priority. No changes were needed.')
        for record in records: record['attempted'] = False
        self.records = records
        self.applied = []
        try:
            atomic_json(self.path, records)
        except OSError:
            self.records = []
            raise ValueError('The restoration record could not be saved. No PC settings were changed.')
        changed = False
        try:
            for record in records:
                if record.get('kind') == 'windows':
                    if self.windows.read(record['setting']) != record['original']:
                        raise OSError('A Windows setting changed while the optimizer was preparing. Try again.')
                    record['attempted'] = True
                    try: atomic_json(self.path,self.records)
                    except OSError:
                        record['attempted'] = False
                        raise
                    self.windows.write(record['setting'],record['applied'])
                    if self.windows.read(record['setting']) != record['applied']:
                        raise OSError('Windows did not confirm the requested setting.')
                    self.applied.append(LABELS[record['setting']])
                    changed = True
                else:
                    process = psutil.Process(record['pid'])
                    if process.create_time()==record['created'] and process.nice()==record['original']:
                        record['attempted'] = True
                        try: atomic_json(self.path,self.records)
                        except OSError:
                            record['attempted'] = False
                            raise
                        process.nice(record['applied'])
                        self.applied.append(LABELS['priority'])
                        changed = True
        except (psutil.Error, OSError):
            self.restore()
            raise ValueError('Windows did not confirm all selected changes. Restoration was attempted; check the status and use Restore now if needed.')
        self.enabled = changed
        self.last_live = time.monotonic()
        self.message = 'Active: '+', '.join(self.applied)+'. These changes are temporary.' if changed else 'No eligible changes remained. No optimization was applied.'
        if not changed: self.restore()

    @synchronized
    def restore(self):
        if self.demo or self.recovery_error:
            return
        self.enabled = False
        pending = []
        for record in reversed(self.records):
            try:
                if record.get('attempted') is False: continue
                if record.get('kind') == 'windows':
                    if self.windows is None: self.windows = WindowsTuning()
                    if self.windows.read(record['setting']) == record['applied']:
                        self.windows.write(record['setting'],record['original'])
                        if self.windows.read(record['setting']) != record['original']:
                            raise OSError('Windows setting restoration was not confirmed.')
                    continue
                if not psutil: pending.append(record); continue
                process = psutil.Process(int(record['pid']))
                if process.create_time()==record['created'] and int(process.nice())==record['applied']:
                    process.nice(record['original'])
            except Exception as exc:
                if psutil and isinstance(exc,psutil.NoSuchProcess): continue
                pending.append(record)
        self.records = list(reversed(pending))
        if not pending: self.applied = []
        if pending:
            try: atomic_json(self.path, pending)
            except OSError: pass
            self.message = 'Restoration needs attention: '+', '.join(LABELS.get(r.get('setting'),'OBS scheduling priority') for r in pending)+'. Try Restore now again; Windows settings may need manual review.'
        else:
            try:
                self.path.unlink(missing_ok=True)
            except OSError:
                self.message = 'Settings restored. The recovery record could not be removed; restart Companion to retry cleanup.'
                return
            self.message = 'Off. Temporary changes restored; later manual changes were kept.'

    @synchronized
    def tick(self, live, now=None):
        now = time.monotonic() if now is None else now
        if not self.enabled: return
        if any(r.get('setting')=='power' for r in self.records):
            try:
                if not self.windows.ac_power():
                    self.restore()
                    self.message += ' Power optimization ended because plugged-in power is no longer confirmed.'
                    return
            except OSError:
                self.restore()
                return
        if live is True: self.last_live = now
        elif live is False or now-self.last_live >= 10:
            self.restore()
