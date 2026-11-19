"""Decode production Recording Studio MKVs while a local RTMP stream runs."""
import argparse
import array
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import threading
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'encoded'))
from run import probe, color


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--exe',type=Path,required=True);parser.add_argument('--runtime',type=Path,required=True);parser.add_argument('--out',type=Path,required=True);a=parser.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=True);env=os.environ.copy();env['QT_QPA_PLATFORM']='offscreen';env['FDGCAST_RECORDING_QA_DIR']=str(out)
    log=(out/'recording-libobs.log').open('w',encoding='utf-8');lines=queue.Queue()
    native=subprocess.Popen([str(a.exe.resolve()),str(a.runtime.resolve()),'recording'],cwd=a.exe.resolve().parent,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,bufsize=1,env=env)
    def pump():
        for line in native.stdout:log.write(line);log.flush();lines.put(line.strip())
        lines.put('EXIT')
    threading.Thread(target=pump,daemon=True).start()
    def until(expected):
        deadline=time.monotonic()+90
        while True:
            line=lines.get(timeout=max(.1,deadline-time.monotonic()))
            if line==expected:return
            if line=='EXIT' or time.monotonic()>deadline:raise RuntimeError('Native recording test did not reach '+expected)
    receiver=None;error=None
    try:
        for cycle in range(2):
            until('READY '+str(cycle));error=(out/f'main-{cycle}-receiver.log').open('wb')
            receiver=subprocess.Popen(['ffmpeg','-y','-hide_banner','-loglevel','warning','-listen','1','-i','rtmp://127.0.0.1:19350/live/qa','-c','copy',str(out/f'main-{cycle}.flv')],stdout=subprocess.DEVNULL,stderr=error)
            time.sleep(1);native.stdin.write('start\n');native.stdin.flush();until('STOPPED '+str(cycle));receiver.wait(timeout=20);error.close()
        until('PASS native RTMP encoder lifecycle');assert native.wait(timeout=15)==0
    finally:
        if native.poll() is None:native.kill()
        if receiver and receiver.poll() is None:receiver.kill()
        if error:error.close()
        log.close()
    evidence=json.loads((out/'native-results.json').read_text());assert len(evidence)==6
    for row in evidence:
        path=Path(row['path']);assert path.exists() and path.stat().st_size>10000,row
        streams=probe(path);video=next(s for s in streams if s['codec_type']=='video');audio=[s for s in streams if s['codec_type']=='audio']
        size={'shared':(1920,1080),'clean':(640,360),'camera':(320,240)}[row['id']]
        assert (video['width'],video['height'])==size and video['codec_name']=='h264',streams
        assert len(audio)==2 and all(s['codec_name']=='aac' for s in audio),streams
        blue=(0,85,221);red=(221,34,0)
        color(path,100,100,red if row['id']=='camera' else blue)
        if row['id']=='shared':color(path,1800,1000,red)
        for track,hz in enumerate((440,880)):
            raw=subprocess.check_output(['ffmpeg','-v','error','-ss','1','-i',str(path),'-map',f'0:a:{track}','-t','.5','-ac','1','-ar','8000','-f','f32le','-'])
            values=array.array('f');values.frombytes(raw);assert len(values)>3000 and sum(v*v for v in values)/len(values)>.0001
            measured=sum(x<=0<y for x,y in zip(values,values[1:]))/(len(values)/8000);assert abs(measured-hz)<40,(row['id'],track,measured)
    for cycle in range(2):
        path=out/f'main-{cycle}.flv';v=next(s for s in probe(path) if s['codec_type']=='video');assert (v['width'],v['height'])==(1920,1080)
        color(path,100,100,(0,85,221));color(path,1800,1000,(221,34,0))
    assert len({r['path'] for r in evidence})==6
    print('PASS: real stream + three recording files, encoder/capture reuse, distinct layouts, two independent audio tracks, unique filenames, restart, linked/manual stop isolation and shutdown.')

if __name__=='__main__':main()
