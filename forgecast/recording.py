"""Local Recording Studio configuration and bounded previews. No media crosses Hub.

SPDX-License-Identifier: GPL-2.0-or-later
"""
import asyncio
import copy
import re
import time
import uuid
from pathlib import PureWindowsPath
from aiohttp import web
from .vertical import identity, number

DEFAULT = {'schema_version':1,'directory':'','collection':'','profiles':[]}


def settings(s):
    return copy.deepcopy(s.config.get('recording_studio',DEFAULT))


def directory(value):
    if not isinstance(value,str) or len(value)>2000 or any(ord(c)<32 for c in value):
        raise ValueError('Choose a local recording folder.')
    if not value:return ''
    path=PureWindowsPath(value)
    if not path.is_absolute() or not re.fullmatch(r'[A-Za-z]:',path.drive) or '..' in path.parts:
        raise ValueError('Choose a local folder such as C:\\Users\\YourName\\Videos. Network paths and URLs are not supported.')
    return str(path)


def layout(value,width,height,allowed):
    if not isinstance(value,dict):raise ValueError('Choose a recording layout.')
    background=value.get('background','#000000')
    if not isinstance(background,str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',background):raise ValueError('Choose a background color.')
    rows=value.get('regions',[])
    if not isinstance(rows,list) or not 1<=len(rows)<=4:raise ValueError('Use one to four recording pictures.')
    result=[]
    for row in rows:
        if not isinstance(row,dict):raise ValueError('Invalid recording picture.')
        source=row.get('source')
        if not isinstance(source,str) or source not in allowed:raise ValueError('Choose an existing OBS source for every picture. Refresh sources if it is missing.')
        name=row.get('name','Picture')
        if not isinstance(name,str) or len(name)>80:raise ValueError('Use a shorter picture name.')
        if row.get('fit','fit') not in ('fit','fill'):raise ValueError('Choose Fit or Fill.')
        x,y=number(row,'x',0,0,width-2),number(row,'y',0,0,height-2)
        w,h=number(row,'width',width,2,width),number(row,'height',height,2,height)
        if x+w>width or y+h>height:raise ValueError('Keep the picture inside the recording canvas.')
        crop=row.get('crop',{})
        if not isinstance(crop,dict):raise ValueError('Invalid picture crop.')
        cx,cy=number(crop,'x',0,0,.995),number(crop,'y',0,0,.995)
        cw,ch=number(crop,'width',1,.005,1),number(crop,'height',1,.005,1)
        if cx+cw>1.000001 or cy+ch>1.000001:raise ValueError('Keep the crop inside its source.')
        if type(row.get('visible',True)) is not bool or type(row.get('mirror',False)) is not bool:raise ValueError('Invalid picture visibility.')
        result.append(dict(source=source,name=name,fit=row.get('fit','fit'),visible=row.get('visible',True),mirror=row.get('mirror',False),x=x,y=y,width=w,height=h,
            crop=dict(x=cx,y=cy,width=cw,height=ch),zoom=number(row,'zoom',1,1,4),pan_x=number(row,'pan_x',0,-1,1),pan_y=number(row,'pan_y',0,-1,1)))
    if not any(r['visible'] for r in result):raise ValueError('Keep at least one picture visible.')
    return dict(background=background,regions=result)


def profile(value,catalog,encoders):
    if not isinstance(value,dict):raise ValueError('Choose a recording file.')
    uid=value.get('id')
    if not identity(uid):raise ValueError('Invalid recording ID.')
    name=value.get('name','Recording')
    if not isinstance(name,str) or not name.strip() or len(name)>60:raise ValueError('Name this recording (up to 60 characters).')
    picture=value.get('picture','stream')
    if picture not in ('stream','custom'):raise ValueError('Choose Same as stream or Custom layout.')
    width,height=value.get('width',1920),value.get('height',1080)
    if any(type(n) is not int or n<64 or n>3840 or n%2 for n in (width,height)) or width*height>8294400:
        raise ValueError('Use even recording dimensions from 64 to 3840, up to 4K pixels total.')
    bitrate=value.get('bitrate_kbps',12000)
    if type(bitrate) is not int or not 1000<=bitrate<=80000:raise ValueError('Choose a recording bitrate from 1 to 80 Mbps.')
    divisor=value.get('fps_divisor',1)
    if type(divisor) is not int or divisor not in (1,2,3,4):raise ValueError('Choose Same as OBS or a supported reduced frame rate.')
    encoder=value.get('encoder','auto')
    if not isinstance(encoder,str) or encoder not in {'auto','obs_x264'}|set(encoders):raise ValueError('Choose an available recording encoder. Refresh OBS first.')
    tracks=value.get('audio_tracks',[1])
    if not isinstance(tracks,list) or not 1<=len(tracks)<=6 or any(type(n) is not int or not 1<=n<=6 for n in tracks) or len(set(tracks))!=len(tracks):
        raise ValueError('Choose one to six OBS audio tracks (1–6).')
    follow=value.get('follow_scenes',True);linked=value.get('link_stream',False)
    if type(follow) is not bool or type(linked) is not bool:raise ValueError('Invalid scene-follow or automatic-recording choice.')
    scenes={s['id'] for s in catalog['scenes']}
    sources={'program'}|scenes|{s['id'] for s in catalog['sources']}
    scope=value.get('scene_id','*')
    if scope!='*' and scope not in scenes:raise ValueError('Choose an existing OBS scene.')
    layouts=value.get('layouts',{})
    if not isinstance(layouts,dict) or len(layouts)>129:raise ValueError('Too many recording scene layouts.')
    if picture=='custom' and '*' not in layouts:raise ValueError('Save a default recording layout first.')
    clean={}
    for key,row in layouts.items():
        if key!='*' and key not in scenes:raise ValueError('A saved recording scene is missing. Remove its layout or refresh OBS sources.')
        clean[key]=layout(row,width,height,sources)
    return dict(id=uid,name=name.strip(),picture=picture,width=width,height=height,bitrate_kbps=bitrate,fps_divisor=divisor,encoder=encoder,
        audio_tracks=sorted(tracks),follow_scenes=follow,link_stream=linked,scene_id=scope,layouts=clean)


class RecordingStudio:
    def __init__(self,state):
        self.s=state
        self.catalog={'scenes':[],'sources':[]}
        self.collection=''
        self.telemetry={}
        self.directory_request=None
        self.preview_lock=asyncio.Lock()
        self.last_preview=0

    def public(self):
        fresh=time.time()-self.s.native_seen<5
        return dict(settings=settings(self.s),connected=fresh and 'recording_studio_v1' in self.s.native_features,
            status=self.telemetry,catalog=self.catalog)

    def busy(self):
        return any(r.get('active') or r.get('busy') for r in self.telemetry.get('files',[])) or any(r.get('action')=='recording_start' and time.time()-r.get('created',0)<10 for r in self.s.commands)

    async def discover(self):
        s=self.s
        if not s.obs or not s.obs.connected:raise ValueError('Connect OBS in Connections, then refresh recording sources.')
        rows=await s.obs.request('GetSceneList');inputs=await s.obs.request('GetInputList')
        collections=await s.obs.request('GetSceneCollectionList')
        video=await s.obs.request('GetVideoSettings')
        self.collection=collections.get('currentSceneCollectionName','')
        if not isinstance(self.collection,str) or not self.collection:raise ValueError('OBS did not report the active scene collection.')
        audio_kinds={'wasapi_input_capture','wasapi_output_capture','pulse_input_capture','pulse_output_capture','coreaudio_input_capture','coreaudio_output_capture','alsa_input_capture'}
        self.catalog={'scenes':[dict(id=r['sceneUuid'],name=r['sceneName']) for r in rows.get('scenes',[]) if identity(r.get('sceneUuid'))][:128],
            'sources':[dict(id=r['inputUuid'],name=r['inputName'],kind=r.get('inputKind','')) for r in inputs.get('inputs',[]) if identity(r.get('inputUuid')) and r.get('inputKind') not in audio_kinds][:256],
            'scene_id':rows.get('currentProgramSceneUuid',''),'scene_name':rows.get('currentProgramSceneName',''),'collection':self.collection,
            'width':video.get('outputWidth',1920),'height':video.get('outputHeight',1080)}
        return {**self.public(),'catalog':self.catalog}

    async def action(self,data):
        s=self.s;op=data['op']
        fresh=time.time()-s.native_seen<5 and 'recording_studio_v1' in s.native_features
        if op in ('recording_start','recording_stop','recording_stop_all','recording_folder'):
            if not fresh:raise ValueError('The OBS recording module is offline. Open OBS with the latest FDGCast plugin.')
            if op=='recording_folder' and self.busy():raise ValueError('Stop Recording Studio files before changing their folder.')
            uid=data.get('id')
            if op in ('recording_start','recording_stop') and uid not in {p['id'] for p in settings(s)['profiles']}:raise ValueError('Save this recording file first.')
            if op=='recording_start' and any(r.get('action')==op and r.get('profile_id')==uid and time.time()-r.get('created',0)<10 for r in s.commands):
                raise ValueError('This recording start is already waiting for OBS.')
            if len(s.commands)>=30:raise ValueError('OBS is busy processing requests. Wait a moment.')
            command=dict(action=op,id=uuid.uuid4().hex,profile_id=uid,created=time.time())
            if op=='recording_folder':
                self.directory_request=uuid.uuid4().hex
                command['request_id']=self.directory_request
            s.commands.append(command)
            return {'ok':True,'message':'Request sent to OBS. Check recording status for confirmation.'}
        if op=='recording_save':
            if not fresh:raise ValueError('Connect the OBS recording module before saving recording settings.')
            if self.busy():raise ValueError('Stop Recording Studio files before changing saved recording settings. Your stream can continue.')
            if not self.collection:raise ValueError('Refresh recording sources first.')
            if not s.obs or not s.obs.connected:raise ValueError('Connect OBS before saving recording settings.')
            current=await s.obs.request('GetSceneCollectionList')
            if current.get('currentSceneCollectionName')!=self.collection:raise ValueError('OBS changed scene collections. Refresh recording sources first.')
            value=data.get('settings')
            if not isinstance(value,dict):raise ValueError('Choose recording settings.')
            rows=value.get('profiles',[])
            if not isinstance(rows,list) or not 1<=len(rows)<=3:raise ValueError('Save one recording file, with up to two optional extra files.')
            encoders={r['id'] for r in self.telemetry.get('encoders',[]) if isinstance(r,dict) and identity(r.get('id'))}
            profiles=[profile(row,self.catalog,encoders) for row in rows]
            if len({p['id'] for p in profiles})!=len(profiles):raise ValueError('Recording file IDs must be unique.')
            result=dict(schema_version=1,directory=directory(value.get('directory','')),collection=self.collection,profiles=profiles)
            s.config['recording_studio']=result;s.save()
            return {'ok':True,'settings':result}
        raise ValueError('Unknown recording action.')

    def accept(self,data,results):
        if isinstance(data,dict):
            self.telemetry={k:data.get(k) for k in ('files','default_directory','encoders','collection')}
            self.telemetry['files']=(data.get('files',[]) if isinstance(data.get('files'),list) else [])[:3]
            self.telemetry['files']=[r for r in self.telemetry['files'] if isinstance(r,dict)]
            self.telemetry['encoders']=(data.get('encoders',[]) if isinstance(data.get('encoders'),list) else [])[:32]
            self.telemetry['encoders']=[r for r in self.telemetry['encoders'] if isinstance(r,dict) and isinstance(r.get('id'),str) and isinstance(r.get('name'),str)]
        for row in results:
            if not isinstance(row,dict):continue
            if row.get('status') in ('recording_directory_chosen','recording_directory_cancelled') and row.get('request_id')==self.directory_request and self.directory_request:
                try:
                    if self.busy() or row.get('status')!='recording_directory_chosen':raise ValueError('Folder change cancelled.')
                    value=settings(self.s);value['directory']=directory(row.get('directory'))
                    self.s.config['recording_studio']=value;self.s.save()
                except ValueError:pass
                self.directory_request=None

    async def preview(self,data):
        s=self.s
        if not s.obs or not s.obs.connected:raise ValueError('Connect OBS to see recording previews.')
        ids=data.get('sources',[])
        allowed={r['id'] for r in self.catalog['sources']+self.catalog['scenes']}
        if not isinstance(ids,list) or len(ids)>4 or any(not isinstance(uid,str) or uid not in allowed for uid in ids):raise ValueError('Choose up to four known recording sources.')
        async with self.preview_lock:
            if time.monotonic()-self.last_preview<.9:raise ValueError('Preview is refreshing. Wait a moment.')
            self.last_preview=time.monotonic()
            current=await s.obs.request('GetCurrentProgramScene');uid=current.get('currentProgramSceneUuid','')
            if not identity(uid):raise ValueError('OBS did not report its live scene.')
            frames={};missing=[]
            for source in dict.fromkeys([uid]+ids):
                try:
                    row=await s.obs.request('GetSourceScreenshot',dict(sourceUuid=source,imageFormat='jpeg',imageWidth=640,imageCompressionQuality=60))
                    image=row.get('imageData','')
                    if not isinstance(image,str) or len(image)>1500000 or not re.fullmatch(r'data:image/(?:jpeg|jpg);base64,[A-Za-z0-9+/=]+',image):raise ValueError('Invalid preview')
                    frames[source]=image
                except (RuntimeError,ValueError):missing.append(source)
            return dict(scene_id=uid,scene_name=current.get('currentProgramSceneName',''),frames=frames,missing=missing)


async def catalog(request):
    return web.json_response(await request.app['state'].recording.discover(),headers={'Cache-Control':'no-store'})


async def preview(request):
    return web.json_response(await request.app['state'].recording.preview(await request.json()),headers={'Cache-Control':'no-store'})
