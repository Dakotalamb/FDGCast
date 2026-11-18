import atexit
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from forgecast.pc_health import StreamOptimizer
from forgecast.windows_tuning import WindowsTuning, HIGH_PERFORMANCE, options, SETTINGS_PAGES


class FakeWindows:
    def __init__(self):
        self.values={'window_animation':1,'client_animation':1,'power':'381b4222-f694-41f0-9685-ff5bb260df2e','game_mode':None}
        self.plugged=True
        self.writes=[]
        self.fail_setting=None
    def read(self,key):return self.values[key]
    def write(self,key,value):
        if key==self.fail_setting:raise OSError('setting denied')
        self.writes.append((key,value));self.values[key]=value
    def schemes(self):return [HIGH_PERFORMANCE]
    def ac_power(self):return self.plugged
    prepare=WindowsTuning.prepare


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.windows=FakeWindows()
        self.factory=patch('forgecast.pc_health.WindowsTuning',return_value=self.windows);self.factory.start();self.addCleanup(self.factory.stop)
        self.optimizer=StreamOptimizer(self.temp.name)
        self.addCleanup(atexit.unregister,self.optimizer.restore)

    def start(self,**selected):
        selected={'priority':False,'animations':True,'power':True,'game_mode':True,**selected}
        with patch.object(self.optimizer,'public',return_value={'supported':True}):
            self.optimizer.start(True,selected)

    def test_all_windows_changes_restore_exact_originals_on_stop(self):
        original=dict(self.windows.values)
        self.start()
        self.assertEqual(self.windows.values,{'window_animation':0,'client_animation':0,'power':HIGH_PERFORMANCE,'game_mode':1})
        self.assertEqual(len(self.optimizer.public()['applied']),4)
        self.optimizer.tick(False)
        self.assertEqual(self.windows.values,original)
        self.assertFalse(self.optimizer.path.exists())

    def test_denied_second_setting_rolls_back_first(self):
        original=dict(self.windows.values)
        self.windows.fail_setting='client_animation'
        with self.assertRaisesRegex(ValueError,'Restoration was attempted'):
            self.start()
        self.assertEqual(self.windows.values,original)
        self.assertFalse(self.optimizer.records)

    def test_recovery_on_next_launch_and_later_manual_changes(self):
        original=dict(self.windows.values)
        self.start()
        manual='a1841308-3541-4fab-bc81-f71556f20b4a'
        self.windows.values['power']=manual
        recovered=StreamOptimizer(self.temp.name)
        self.addCleanup(atexit.unregister,recovered.restore)
        self.assertEqual(self.windows.values,{**original,'power':manual})
        self.assertFalse(recovered.records)

    def test_unattempted_records_do_not_override_manual_changes(self):
        self.optimizer.records=[dict(kind='windows',setting='game_mode',original=None,applied=1,attempted=False)]
        self.windows.values['game_mode']=1
        self.optimizer.restore()
        self.assertEqual(self.windows.values['game_mode'],1)
        self.assertEqual(self.windows.writes,[])

    def test_battery_or_missing_plan_changes_nothing(self):
        original=dict(self.windows.values)
        self.windows.plugged=False
        with self.assertRaisesRegex(ValueError,'plugged-in'):self.start()
        self.assertEqual(self.windows.writes,[])
        self.assertFalse(self.optimizer.path.exists())
        self.windows.plugged=True
        self.windows.schemes=lambda:[]
        with self.assertRaisesRegex(ValueError,'no High performance'):self.start()
        self.assertEqual(self.windows.values,original)

    def test_unplugging_restores_all_temporary_changes(self):
        original=dict(self.windows.values)
        self.start()
        self.windows.plugged=False
        self.optimizer.tick(True)
        self.assertFalse(self.optimizer.enabled)
        self.assertEqual(self.windows.values,original)
        self.assertIn('plugged-in power',self.optimizer.message)

    def test_restore_failure_is_retained_and_can_be_retried(self):
        self.start()
        self.windows.fail_setting='window_animation'
        self.optimizer.restore()
        self.assertTrue(self.optimizer.public()['pending_restore'])
        journal=json.loads(self.optimizer.path.read_text())
        self.assertEqual([r['setting'] for r in journal],['window_animation'])
        self.windows.fail_setting=None
        self.optimizer.restore()
        self.assertFalse(self.optimizer.records)
        self.assertFalse(self.optimizer.path.exists())

    def test_every_windows_mutation_has_a_durable_attempt_record(self):
        original_write=self.windows.write
        def write(setting,value):
            records=json.loads(self.optimizer.path.read_text())
            record=next(r for r in records if r.get('setting')==setting)
            self.assertTrue(record['attempted'])
            return original_write(setting,value)
        self.windows.write=write
        self.start()
        self.optimizer.restore()

    def test_choice_validation_and_selected_settings_only(self):
        for value in ({'power':'yes'},{'unknown':True},[],{'priority':False,'animations':False,'power':False,'game_mode':False}):
            with self.assertRaises(ValueError):options(value)
        self.start(animations=True,power=False,game_mode=False)
        self.assertEqual(set(key for key,value in self.windows.writes),{'window_animation','client_animation'})
        self.optimizer.restore()

    def test_corrupt_journal_is_preserved_and_blocks_new_changes(self):
        for value in ('not json', '[123]', '[{"kind":"windows","setting":"arbitrary","original":0,"applied":1}]'):
            self.optimizer.path.write_text(value)
            broken=StreamOptimizer(self.temp.name)
            self.addCleanup(atexit.unregister,broken.restore)
            self.assertTrue(broken.public()['pending_restore'])
            broken.restore()
            self.assertEqual(broken.path.read_text(),value)
            with patch.object(broken,'public',return_value={'supported':True}):
                with self.assertRaisesRegex(ValueError,'Restore the previous'):
                    broken.start(True)

    def test_manual_settings_pages_are_fixed_not_arbitrary_commands(self):
        self.assertEqual(set(SETTINGS_PAGES),{'captures','game_mode','startup','notifications','power'})
        from forgecast.windows_tuning import open_settings
        with patch('forgecast.windows_tuning.os.name','nt'),patch('forgecast.windows_tuning.os.startfile',create=True) as launch:
            open_settings('captures')
            launch.assert_called_once_with('ms-settings:gaming-gamedvr')
            with self.assertRaises(ValueError):open_settings('cmd.exe')
            self.assertEqual(launch.call_count,1)


@unittest.skipUnless(os.name=='nt','Windows settings API integration')
class WindowsSettingsIntegrationTests(unittest.TestCase):
    def test_actual_windows_animation_apply_read_and_restore(self):
        windows=WindowsTuning()
        original={key:windows.read(key) for key in ('window_animation','client_animation')}
        try:
            for key,value in original.items():
                windows.write(key,1-value)
                self.assertEqual(windows.read(key),1-value)
        finally:
            for key,value in original.items():windows.write(key,value)
        self.assertEqual({key:windows.read(key) for key in original},original)

    def test_actual_windows_power_plan_and_same_plan_roundtrip(self):
        windows=WindowsTuning()
        original=windows.read('power')
        self.assertIn(original,windows.schemes())
        windows.write('power',original)
        self.assertEqual(windows.read('power'),original)

class GameModeRegistryTests(unittest.TestCase):
    def test_missing_preference_is_deleted_on_restore(self):
        from types import SimpleNamespace
        import contextlib
        values={}
        def query(key,name):
            if name not in values:raise FileNotFoundError()
            return values[name],4
        registry=SimpleNamespace(HKEY_CURRENT_USER=1,REG_DWORD=4,KEY_SET_VALUE=2,
            OpenKey=lambda *a,**k:contextlib.nullcontext('key'),CreateKeyEx=lambda *a,**k:contextlib.nullcontext('key'),
            QueryValueEx=query,SetValueEx=lambda key,name,reserved,kind,value:values.__setitem__(name,value),
            DeleteValue=lambda key,name:values.pop(name))
        windows=WindowsTuning.__new__(WindowsTuning)
        with patch.dict('sys.modules',{'winreg':registry}),patch('forgecast.windows_tuning.sys.getwindowsversion',return_value=SimpleNamespace(build=26100),create=True):
            self.assertIsNone(windows.read('game_mode'))
            windows.write('game_mode',1)
            self.assertEqual(windows.read('game_mode'),1)
            windows.write('game_mode',None)
            self.assertIsNone(windows.read('game_mode'))

    def test_windows_10_uses_guided_settings_instead(self):
        from types import SimpleNamespace
        windows=WindowsTuning.__new__(WindowsTuning)
        with patch('forgecast.windows_tuning.sys.getwindowsversion',return_value=SimpleNamespace(build=19045),create=True):
            with self.assertRaisesRegex(OSError,'Windows 11'):windows.read('game_mode')
            with self.assertRaisesRegex(OSError,'Windows 11'):windows.write('game_mode',1)

if __name__=='__main__':unittest.main()
