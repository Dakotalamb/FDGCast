import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import atexit
from forgecast.pc_health import PCMonitor, StreamOptimizer, gpu_engines
from forgecast.server import State, observed_stream_state


class PCHealthTests(unittest.TestCase):
    def test_gpu_sums_processes_only_within_same_engine(self):
        def name(pid, engine, kind='3D', luid='0x1_0x2'):
            return f'pid_{pid}_luid_{luid}_phys_0_eng_{engine}_engtype_{kind}'
        result = gpu_engines([(name(1,0),40),(name(2,0),35),(name(1,1,'VideoEncode'),60),(name(3,0,luid='0x9_0x8'),50),('garbage',99),(name(5,4),float('nan'))])
        self.assertEqual(result,dict(busy_percent=75,render_percent=75,encode_percent=60))
        self.assertIsNone(gpu_engines([]))

    def test_pressure_needs_sustained_measurements_and_clears(self):
        monitor=PCMonitor()
        monitor.current=dict(available=True,cpu_percent=95,memory_percent=91,gpu={'busy_percent':98})
        self.assertEqual(monitor.diagnose([],0),[])
        self.assertEqual(len(monitor.diagnose([],8)),3)
        obs=[dict(code='render',suggestion='Limit game FPS.')]
        result=monitor.diagnose(obs,9)
        self.assertIn('possible contributor',result[-1]['suggestion'])
        self.assertEqual(obs[0]['suggestion'],'Limit game FPS.')
        monitor.current=dict(available=True,cpu_percent=20,memory_percent=50,gpu=None)
        self.assertEqual(monitor.diagnose([],10),[])
        monitor.current['cpu_percent']=95
        self.assertEqual(monitor.diagnose([],11),[])

    def test_additional_output_keeps_optimizer_live(self):
        import time
        with TemporaryDirectory() as root:
            state=State(root,demo=True)
            self.assertIsNone(observed_stream_state(state))
            state.native_seen=time.time();state.native_outputs=[{'active':True}]
            self.assertTrue(observed_stream_state(state))
            state.native_outputs=[]
            self.assertFalse(observed_stream_state(state))


class FakeProcess:
    def __init__(self,pid=7,created=123,priority=32):
        self.pid,self.created,self.priority=pid,created,priority
        self.info={'name':'obs64.exe'}
        self.writes=[]
    def create_time(self):return self.created
    def nice(self,value=None):
        if value is None:return self.priority
        self.priority=value;self.writes.append(value)


class FakePsutil:
    NORMAL_PRIORITY_CLASS=32
    ABOVE_NORMAL_PRIORITY_CLASS=32768
    class Error(Exception):pass
    class NoSuchProcess(Error):pass
    def __init__(self,process):self.process=process
    def process_iter(self,*args,**kwargs):return [self.process]
    def Process(self,pid):return self.process


class OptimizerTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.process=FakeProcess();self.api=FakePsutil(self.process)
        self.patch=patch('forgecast.pc_health.psutil',self.api);self.patch.start();self.addCleanup(self.patch.stop)
        self.optimizer=StreamOptimizer(self.temp.name)
        self.addCleanup(atexit.unregister,self.optimizer.restore)

    def start(self):
        with patch.object(self.optimizer,'public',return_value={'supported':True}):
            self.optimizer.start(True)

    def test_journal_precedes_change_and_stop_restores_exact_value(self):
        old_nice=self.process.nice
        def nice(value=None):
            if value is not None:self.assertTrue(self.optimizer.path.exists())
            return old_nice(value)
        self.process.nice=nice
        self.start()
        self.assertEqual(self.process.priority,32768)
        self.optimizer.tick(False)
        self.assertEqual(self.process.priority,32)
        self.assertFalse(self.optimizer.path.exists())
        self.assertFalse(self.optimizer.enabled)

    def test_disconnect_grace_then_restores(self):
        self.start();self.optimizer.last_live=100
        self.optimizer.tick(None,109);self.assertTrue(self.optimizer.enabled)
        self.optimizer.tick(None,110);self.assertFalse(self.optimizer.enabled)
        self.assertEqual(self.process.priority,32)

    def test_startup_recovers_previous_change(self):
        self.start()
        recovered=StreamOptimizer(self.temp.name)
        self.assertEqual(self.process.priority,32)
        self.assertFalse(recovered.path.exists())

    def test_pid_reuse_and_manual_priority_change_are_not_overwritten(self):
        for reused in (False,True):
            self.process=FakeProcess();self.api.process=self.process
            self.optimizer=StreamOptimizer(self.temp.name)
            self.start()
            if reused:self.process.created+=1
            else:self.process.priority=128
            self.optimizer.restore()
            self.assertEqual(self.process.writes,[32768])

    def test_no_change_when_not_live_or_custom_priority(self):
        with patch.object(self.optimizer,'public',return_value={'supported':True}):
            with self.assertRaises(ValueError):self.optimizer.start(None)
            self.process.priority=128
            with self.assertRaises(ValueError):self.optimizer.start(True)
        self.assertEqual(self.process.writes,[])

    def test_failed_apply_rolls_back_and_retains_failed_restore(self):
        old_nice=self.process.nice
        def nice(value=None):
            if value is not None:raise self.api.Error()
            return old_nice(value)
        self.process.nice=nice
        with self.assertRaises(ValueError):self.start()
        self.assertFalse(self.optimizer.enabled)
        self.assertFalse(self.optimizer.path.exists())
        self.process.priority=32768
        self.optimizer.records=[dict(pid=7,created=123,original=32,applied=32768)]
        self.optimizer.restore()
        self.assertTrue(self.optimizer.public()['pending_restore'])
        self.assertTrue(self.optimizer.path.exists())


class PCPrivacyTests(unittest.TestCase):
    def test_demo_cleanup_preserves_real_optimizer_recovery_record(self):
        with TemporaryDirectory() as root:
            path=Path(root)/'optimizer-restore.json'
            path.write_text('[{"pid":123}]')
            optimizer=StreamOptimizer(root,demo=True)
            optimizer.restore()
            self.assertEqual(path.read_text(),'[{"pid":123}]')

    def test_report_excludes_process_names_and_paths(self):
        with TemporaryDirectory() as root:
            state=State(root,demo=True)
            state.pc_monitor.current={'available':True,'cpu_percent':83,'processes':[{'name':'PRIVATE-APP','pid':123}]}
            report=state.report()
            self.assertEqual(report['pc_health']['cpu_percent'],83)
            self.assertNotIn('PRIVATE-APP',json.dumps(report))
            self.assertNotIn('processes',report['pc_health'])


class PCIntegrationTests(unittest.TestCase):
    def test_real_system_sampling_and_optional_gpu_counters(self):
        import time
        monitor=PCMonitor()
        try:
            first=monitor.sample()
            time.sleep(.05)
            second=monitor.sample()
            self.assertTrue(second['available'],second)
            self.assertIsNotNone(second['cpu_percent'])
            self.assertGreater(second['memory_total_gb'],0)
            self.assertGreaterEqual(second['memory_percent'],0)
            self.assertLessEqual(second['memory_percent'],100)
            if second['gpu'] is not None:
                self.assertGreaterEqual(second['gpu']['busy_percent'],0)
                self.assertLessEqual(second['gpu']['busy_percent'],100)
        finally:monitor.close()

    def test_atexit_hook_restores_desktop_daemon_process_case(self):
        with TemporaryDirectory() as root, patch('forgecast.pc_health.atexit.register') as register:
            optimizer=StreamOptimizer(root)
            register.assert_called_once_with(optimizer.restore)
            process=FakeProcess();api=FakePsutil(process)
            with patch('forgecast.pc_health.psutil',api), patch.object(optimizer,'public',return_value={'supported':True}):
                optimizer.start(True)
                register.call_args.args[0]()
                self.assertEqual(process.priority,32)
                self.assertFalse(optimizer.enabled)

    def test_journal_write_failure_changes_nothing(self):
        with TemporaryDirectory() as root, patch('forgecast.pc_health.atexit.register'):
            optimizer=StreamOptimizer(root)
            process=FakeProcess();api=FakePsutil(process)
            with patch('forgecast.pc_health.psutil',api), patch.object(optimizer,'public',return_value={'supported':True}), patch('forgecast.pc_health.atomic_json',side_effect=OSError()):
                with self.assertRaisesRegex(ValueError,'No PC settings'):
                    optimizer.start(True)
            self.assertEqual(process.writes,[])
            self.assertFalse(optimizer.records)

if __name__=='__main__':unittest.main()
