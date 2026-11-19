const {spawn}=require('node:child_process'),fs=require('node:fs'),path=require('node:path'),os=require('node:os'),assert=require('node:assert/strict');
const {chromium}=require(require.resolve('playwright',{paths:[process.env.CODEX_PRIMARY_RUNTIME_NODE_MODULES||process.cwd()]}));
async function main(){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'fdgcast-recording-'));
 const server=spawn(process.env.PYTHON||'python',['-u','-m','forgecast.server','--demo','--no-browser','--data-dir',directory],{cwd:path.resolve(__dirname,'..')});let browser;
 try{
  const url=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Startup timeout')),15000);server.stdout.on('data',data=>{out+=data;const m=out.match(/http:\/\/127\.0\.0\.1:17654\/#\S+/);if(m){clearTimeout(timer);resolve(m[0]);}});server.on('exit',code=>reject(Error('Server exit '+code)));});
  browser=await chromium.launch({headless:true,args:['--no-sandbox']});const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));page.on('dialog',d=>d.accept());
  const pictures=await page.evaluate(()=>{const make=color=>{const c=document.createElement('canvas');c.width=640;c.height=360;const ctx=c.getContext('2d');ctx.fillStyle=color;ctx.fillRect(0,0,640,360);return c.toDataURL('image/jpeg');};return{program:make('#1058dd'),game:make('#1058dd'),camera:make('#dd2222')};});
  let config={schema_version:1,directory:'',collection:'Gaming',profiles:[]},files=[],connected=true,previews=0,scene='scene-one',actions=[];
  const catalog={collection:'Gaming',width:1920,height:1080,scenes:[{id:'scene-one',name:'Gameplay'},{id:'scene-two',name:'BRB'}],sources:[{id:'game',name:'Existing game',kind:'game_capture'},{id:'camera',name:'Existing webcam',kind:'dshow_input'}]};
  const rec=()=>({settings:config,connected,status:{files,encoders:[{id:'obs_x264',name:'Software x264'}]},catalog});
  await page.route('**/api/state',async route=>{const r=await route.fetch(),data=await r.json();data.demo=false;data.obs_connected=true;data.recording_studio=rec();await route.fulfill({response:r,json:data});});
  await page.route('**/api/recording',route=>route.fulfill({json:rec()}));
  await page.route('**/api/recording/preview',route=>{previews++;return route.fulfill({json:{scene_id:scene,scene_name:scene==='scene-one'?'Gameplay':'BRB',frames:{[scene]:pictures.program,game:pictures.game,camera:pictures.camera},missing:[]}});});
  await page.route('**/api/action',route=>{const d=route.request().postDataJSON();actions.push(d.op);if(d.op==='recording_save'){config=structuredClone(d.settings);return route.fulfill({json:{ok:true,settings:config}});}if(d.op==='recording_folder'){config={...config,directory:'C:\\PickedVideos'};return route.fulfill({json:{ok:true}});}if(d.op==='recording_start'){files=[{id:d.id,name:'My recording',active:true,busy:false,state:'recording',frames:90,bytes:1500000,width:1920,height:1080,path:'C:\\Videos\\recording.mkv'}];return route.fulfill({json:{ok:true}});}if(d.op==='recording_stop_all'||d.op==='recording_stop'){files=files.map(r=>({...r,active:false,state:'saved'}));return route.fulfill({json:{ok:true}});}return route.continue();});
  await page.goto(url);await page.locator('[data-tab=recording]').click();await page.waitForFunction(()=>document.querySelector('#rsLiveName').textContent.includes('live snapshot'));
  assert.equal(await page.locator('#rsMode').inputValue(),'stream');assert.equal(await page.locator('#rsFollow').isChecked(),true);assert.equal(await page.locator('#rsLink').isChecked(),false);assert.equal(await page.locator('#rsLayoutControls').isVisible(),false);assert.equal(await page.locator('#rsDirectory').isVisible(),false);
  await page.locator('[data-rs-preset=camera]').click();assert.equal(await page.locator('#rsSource').inputValue(),'camera');assert.equal(await page.locator('#rsLayer option').count(),2);assert.equal(await page.locator('#rsStart').isDisabled(),true);
  const canvas=page.locator('#rsCanvas');await canvas.focus();const left=Number(await page.locator('#rsX').inputValue());await page.keyboard.press('ArrowLeft');assert.equal(Number(await page.locator('#rsX').inputValue()),left-1);
  await page.locator('#rsProfileName').fill('My custom recording');
  const advanced=page.locator('#recording details').filter({has:page.locator('#rsDirectory')});await advanced.locator('summary').click();await page.locator('#rsFolder').click();await page.waitForFunction(()=>document.querySelector('#rsDirectory').value==='C:\\PickedVideos');await advanced.locator('summary').click();
  await page.locator('#rsSave').click();await page.waitForFunction(()=>document.querySelector('#rsSaved').textContent.startsWith('Saved.'));
  assert.equal(await page.locator('#rsProfileName').inputValue(),'My custom recording','Save must not restore stale polled settings');
  assert.equal(config.directory,'C:\\PickedVideos','Folder chosen during other unsaved edits must be retained');
  assert.equal(config.profiles.length,1);assert.equal(config.profiles[0].layouts['scene-one'].regions[1].source,'camera');
  await page.locator('#rsStart').click();await page.waitForFunction(()=>document.querySelector('#rsFiles').textContent.includes('recording · recording'));assert.equal(await page.locator('#rsSave').isDisabled(),true);assert.equal(await page.locator('#rsStopAll').isDisabled(),false);
  await page.locator('#rsStop').click();await page.waitForFunction(()=>document.querySelector('#rsFiles').textContent.includes('saved'));assert.equal(await page.locator('#rsSave').isDisabled(),false);
  await page.locator('#rsFollow').uncheck();await page.locator('#rsScene').selectOption('scene-two');assert.equal(await page.locator('#rsStart').isDisabled(),true,'Changing manual scene requires saving');await page.locator('#rsSave').click();assert.equal(config.profiles[0].scene_id,'scene-two');
  const output=path.resolve(__dirname,'../qa-next');fs.mkdirSync(output,{recursive:true});await page.screenshot({path:path.join(output,'recording-studio-desktop.png'),fullPage:true});
  await page.locator('#rsPause').click();const count=previews;await page.waitForTimeout(2300);assert.ok(previews<=count+1);await page.locator('[data-tab=live]').click();const hidden=previews;await page.waitForTimeout(2300);assert.equal(previews,hidden);
  connected=false;await page.locator('[data-tab=recording]').click();await page.waitForFunction(()=>document.querySelector('#rsConnection').textContent.includes('offline'));assert.equal(await page.locator('#rsStart').isDisabled(),true);assert.match(await page.locator('#rsFiles').textContent(),/state unknown/);
  await page.setViewportSize({width:390,height:844});assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Mobile overflow');await page.screenshot({path:path.join(output,'recording-studio-mobile.png'),fullPage:true});assert.deepEqual(errors,[]);assert.ok(actions.every(op=>op.startsWith('recording_')),'Recording UI must not send broadcast commands');
  console.log('PASS: simple defaults, existing source presets, keyboard positioning, explicit save/start/stop, manual scene persistence, disconnected status, hidden preview polling and mobile layout');
 }finally{if(browser)await browser.close();server.kill('SIGINT');}
}
main().catch(e=>{console.error(e);process.exitCode=1;});
