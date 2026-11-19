"""Recording configuration, loopback boundaries and safe command lifecycle."""
import copy
import tempfile
import time
import unittest
from unittest.mock import AsyncMock
from aiohttp.test_utils import TestClient, TestServer
from forgecast.server import State, create_app
from forgecast.recording import directory, profile


def recording():
    return dict(id='recording-one',name='Clean gameplay',picture='custom',width=1920,height=1080,bitrate_kbps=12000,
                encoder='auto',fps_divisor=1,audio_tracks=[1,2],follow_scenes=True,link_stream=False,scene_id='*',
                layouts={'*':dict(background='#000000',regions=[dict(name='Game',source='game',x=0,y=0,width=1920,height=1080)])})


class RecordingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.s=State(self.tmp.name,demo=True)
        self.s.native_seen=time.time();self.s.native_features={'recording_studio_v1'}
        self.client=TestClient(TestServer(create_app(self.s)));await self.client.start_server()
        self.s.obs=type('Obs',(),{'connected':True,'close':AsyncMock(),'request':AsyncMock(side_effect=self.request)})()
        self.headers={'Host':'127.0.0.1:17654','Authorization':'Bearer '+self.s.browser_key}
        await self.s.recording.discover()
    async def asyncTearDown(self):
        await self.client.close();self.tmp.cleanup()
    async def request(self,kind,data=None):
        if kind=='GetSceneList':return dict(currentProgramSceneUuid='scene-one',scenes=[dict(sceneUuid='scene-one',sceneName='Live'),dict(sceneUuid='scene-two',sceneName='BRB')])
        if kind=='GetInputList':return dict(inputs=[dict(inputUuid='game',inputName='Existing game',inputKind='game_capture'),dict(inputUuid='camera',inputName='Existing webcam',inputKind='dshow_input'),dict(inputUuid='mic',inputName='Mic',inputKind='wasapi_input_capture')])
        if kind=='GetSceneCollectionList':return dict(currentSceneCollectionName='Gaming')
        if kind=='GetCurrentProgramScene':return dict(currentProgramSceneUuid='scene-one',currentProgramSceneName='Live')
        if kind=='GetSourceScreenshot':return dict(imageData='data:image/jpeg;base64,YWJj')
        if kind=='GetVideoSettings':return dict(outputWidth=1920,outputHeight=1080)
        raise AssertionError('Recording must not change OBS: '+kind)
    async def save(self,rows=None,**options):
        return await self.s.recording.action(dict(op='recording_save',settings=dict(profiles=rows or [recording()],**options)))
    async def test_saves_reuses_existing_inputs_and_restores_without_starting(self):
        result=await self.save(directory=r'C:\Users\Streamer\Videos')
        self.assertEqual(result['settings']['profiles'][0]['audio_tracks'],[1,2]);self.assertEqual(list(self.s.commands),[])
        restored=State(self.tmp.name,demo=True)
        self.assertEqual(restored.config['recording_studio'],result['settings'])
        self.assertEqual({r['id'] for r in self.s.recording.catalog['sources']},{'camera','game'})
        self.assertTrue(result['settings']['profiles'][0]['follow_scenes']);self.assertFalse(result['settings']['profiles'][0]['link_stream'])
    async def test_validation_blocks_unknown_inputs_invalid_crop_quality_and_tracks(self):
        for key,value in [('width',1921),('height',float('nan')),('bitrate_kbps',0),('fps_divisor',9),('encoder','unknown'),('audio_tracks',[]),('audio_tracks',[1,1]),('audio_tracks',[True]),('follow_scenes','false'),('picture','vertical')]:
            bad=recording();bad[key]=value
            with self.assertRaises(ValueError,msg=key):await self.save([bad])
        for key,value in [('source','deleted'),('source','https://example.com'),('x',float('inf')),('width',4000),('visible',False),('crop',dict(x=.9,width=.5))]:
            bad=recording();bad['layouts']['*']['regions'][0][key]=value
            with self.assertRaises(ValueError,msg=key):await self.save([bad])
        bad=recording();bad['layouts']['removed']=bad['layouts']['*']
        with self.assertRaises(ValueError):await self.save([bad])
        with self.assertRaises(ValueError):await self.save([recording()]*2)
        with self.assertRaises(ValueError):await self.save([recording()]*4)
    def test_local_folder_validation(self):
        self.assertEqual(directory(''),'');self.assertEqual(directory('C:/Users/Streamer/Videos'),r'C:\Users\Streamer\Videos')
        for value in ('relative',r'\\server\share',r'C:\Videos\..\secret','https://example.com','C:\x00Videos'):
            with self.assertRaises(ValueError):directory(value)
    async def test_commands_are_expiring_bounded_and_cannot_duplicate_pending_start(self):
        await self.save();await self.s.recording.action(dict(op='recording_start',id='recording-one'))
        command=self.s.commands[-1];self.assertEqual(command['profile_id'],'recording-one');self.assertLess(time.time()-command['created'],1)
        self.assertNotIn('server',command);self.assertNotIn('key',command)
        with self.assertRaisesRegex(ValueError,'already waiting'):await self.s.recording.action(dict(op='recording_start',id='recording-one'))
        with self.assertRaisesRegex(ValueError,'Stop Recording'):await self.save()
        self.s.commands[-1]['created']=time.time()-15
        self.assertFalse(self.s.recording.busy())
        self.s.demo=False
        native_headers={**self.headers,'Authorization':'Bearer '+self.s.native_key}
        response=await self.client.post('/native/poll',headers=native_headers,json={'features':['recording_studio_v1']})
        self.assertEqual(response.status,200);self.assertEqual((await response.json())['commands'],[])
    async def test_saving_during_recording_or_collection_change_is_blocked_but_stop_allowed(self):
        await self.save();self.s.recording.accept({'files':[{'id':'recording-one','active':True}]},[])
        with self.assertRaisesRegex(ValueError,'Stop Recording'):await self.save()
        await self.s.recording.action(dict(op='recording_stop',id='recording-one'))
        self.assertEqual(self.s.commands[-1]['action'],'recording_stop');self.s.commands.clear()
        self.s.recording.accept({'files':[]},[])
        self.s.recording.collection='Different'
        with self.assertRaisesRegex(ValueError,'changed scene collections'):await self.save()
    async def test_native_folder_request_matching_and_no_mid_recording_folder_change(self):
        await self.save();await self.s.recording.action(dict(op='recording_folder'))
        req=self.s.recording.directory_request;self.s.commands.clear()
        self.s.recording.accept({},[dict(status='recording_directory_chosen',request_id='wrong',directory=r'C:\Wrong')])
        self.assertEqual(self.s.config['recording_studio']['directory'],'')
        self.s.recording.accept({},[dict(status='recording_directory_chosen',request_id=req,directory=r'C:\Videos')])
        self.assertEqual(self.s.config['recording_studio']['directory'],r'C:\Videos')
        await self.s.recording.action(dict(op='recording_folder'));req=self.s.recording.directory_request;self.s.commands.clear()
        self.s.recording.accept(dict(files=[dict(active=True)]),[dict(status='recording_directory_chosen',request_id=req,directory=r'C:\Other')])
        self.assertEqual(self.s.config['recording_studio']['directory'],r'C:\Videos')
    async def test_preview_is_bounded_and_never_exposes_media_or_local_paths_in_report(self):
        await self.save();self.s.obs.request.reset_mock()
        result=await self.s.recording.preview(dict(sources=['camera','camera']))
        self.assertEqual(set(result['frames']),{'scene-one','camera'})
        calls=[r for r in self.s.obs.request.call_args_list if r.args[0]=='GetSourceScreenshot'];self.assertEqual(len(calls),2)
        self.assertEqual(calls[0].args[1]['imageWidth'],640);self.assertNotIn('imageHeight',calls[0].args[1])
        self.s.recording.accept(dict(files=[dict(path=r'C:\Private\Recording.mkv',error='LOCAL_ONLY')]),[])
        self.assertNotIn('LOCAL_ONLY',str(self.s.report()));self.assertNotIn('Private',str(self.s.report()));self.assertNotIn('frames',self.s.public()['recording_studio'])
        with self.assertRaisesRegex(ValueError,'refreshing'):await self.s.recording.preview(dict(sources=[]))
        with self.assertRaises(ValueError):await self.s.recording.preview(dict(sources=['unknown']))
    async def test_auth_demo_and_disconnected_controls(self):
        r=await self.client.get('/api/recording',headers=self.headers);self.assertEqual(r.status,200);self.assertEqual(r.headers['Cache-Control'],'no-store')
        r=await self.client.post('/api/recording/preview',headers={'Host':'127.0.0.1:17654'},json={});self.assertEqual(r.status,401)
        r=await self.client.post('/api/action',headers=self.headers,json=dict(op='recording_start',id='recording-one'));self.assertEqual(r.status,400)
        self.s.native_seen=0
        with self.assertRaisesRegex(ValueError,'offline'):await self.s.recording.action(dict(op='recording_stop_all'))
        self.assertFalse(self.s.recording.public()['connected'])
