// Test-only real libobs recording exercises. Never installed.
#include "recording-studio.hpp"
#include <QFile>
void recordingQA(obs_output_t *main,obs_encoder_t *video,obs_scene_t *sceneOne,obs_source_t *sound){
 const auto dir=qEnvironmentVariable("FDGCAST_RECORDING_QA_DIR");check(!dir.isEmpty(),"QA media directory missing");
 auto *gameItem=obs_scene_find_source(sceneOne,"Blue background"),*camItem=obs_scene_find_source(sceneOne,"Camera color");check(gameItem&&camItem,"Existing sources missing");
 auto *game=obs_sceneitem_get_source(gameItem),*camera=obs_sceneitem_get_source(camItem);
 auto picture=[](const char *id,const QString &source,int w,int h,bool custom,bool linked){
  return QJsonObject{{"id",id},{"name",id},{"picture",custom?"custom":"stream"},{"width",w},{"height",h},{"bitrate_kbps",3000},{"encoder","obs_x264"},{"fps_divisor",1},{"audio_tracks",QJsonArray{1,2}},{"follow_scenes",true},{"scene_id","*"},{"link_stream",linked},
   {"layouts",QJsonObject{{"*",QJsonObject{{"background","#000000"},{"regions",QJsonArray{QJsonObject{{"source",source},{"x",0},{"y",0},{"width",w},{"height",h},{"fit","fit"}}}}}}}}};
 };
 const auto shared=picture("shared","program",1920,1080,false,true),clean=picture("clean",obs_source_get_uuid(game),640,360,true,false),cam=picture("camera",obs_source_get_uuid(camera),320,240,true,false);
 auto cfg=QJsonObject{{"schema_version",1},{"collection","QA"},{"directory",dir},{"profiles",QJsonArray{shared,clean,cam}}};
 fdgcast::RecordingStudio recordings;recordings.configure(cfg);obs_source_set_audio_mixers(sound,1);
 auto *audioData=obs_data_create();obs_data_set_double(audioData,"frequency",880);auto *secondSound=obs_source_create_private("qa_tone","Second track",audioData);obs_data_release(audioData);check(secondSound,"Second audio source missing");
 obs_source_set_audio_mixers(secondSound,2);obs_set_output_source(2,secondSound);
 auto wait=[&](bool finished){for(int i=0;i<200;++i){recordings.tick();const auto rows=recordings.status("QA").value("files").toArray();bool good=finished?!recordings.busy():rows.size()==3;
  if(!finished)for(const auto &entry:rows){const auto row=entry.toObject();good=good&&row.value("state").toString()=="recording"&&row.value("frames").toInt()>20;}
  if(good)return;std::this_thread::sleep_for(50ms);}throw std::runtime_error("Recording lifecycle timed out");};
 QJsonArray evidence;
 for(int cycle=0;cycle<2;++cycle){
  std::cout<<"READY "<<cycle<<std::endl;std::string command;std::getline(std::cin,command);check(command=="start","Missing receiver command");
  check(obs_output_start(main),"Main start failed");waitActive(main);
  recordings.startLinked("QA",video);
  check(recordings.startChecked("clean","QA",video).isEmpty(),"Clean recording start rejected");check(recordings.startChecked("camera","QA",video).isEmpty(),"Camera recording start rejected");
  wait(false);std::this_thread::sleep_for(2500ms);
  auto rows=recordings.status("QA").value("files").toArray();bool reused=false;
  for(auto entry:rows){auto row=entry.toObject();if(row.value("id")=="shared")reused=row.value("reused_encoder").toBool();row.insert("cycle",cycle);evidence.append(row);}
  check(reused,"Same-picture recording failed to share active stream encoder");check(obs_output_get_video_encoder(main)==video,"Recording replaced main encoder");
  auto *same=obs_get_source_by_uuid(obs_source_get_uuid(camera));check(same==camera,"Recording reopened camera source");obs_source_release(same);
  if(cycle==0){
   recordings.stopAll(true);std::this_thread::sleep_for(500ms);recordings.tick();
   rows=recordings.status("QA").value("files").toArray();int manual=0;for(const auto &entry:rows){const auto row=entry.toObject();if(row.value("id")!="shared"&&row.value("active").toBool())++manual;}check(manual==2,"Linked stop also stopped manual files");
   const auto before=obs_output_get_total_frames(main);recordings.stopAll();wait(true);std::this_thread::sleep_for(300ms);check(obs_output_active(main)&&obs_output_get_total_frames(main)>before,"Recording stop interrupted main stream");stop(main);
  }else{
   stop(main);std::this_thread::sleep_for(500ms);recordings.tick();
   rows=recordings.status("QA").value("files").toArray();for(const auto &entry:rows)check(entry.toObject().value("active").toBool(),"Manual recording did not continue after stream stopped");
   recordings.shutdown();check(!recordings.busy(),"Shutdown left recording outputs active");
  }
  std::cout<<"STOPPED "<<cycle<<std::endl;
 }
 // Configuration errors must be isolated from an otherwise valid OBS stream.
 check(!recordings.startChecked("clean","Wrong collection",video).isEmpty(),"Wrong collection was accepted");
 auto bad=cam;bad.insert("encoder","not_a_real_encoder");auto badCfg=cfg;badCfg.insert("profiles",QJsonArray{bad});recordings.configure(badCfg);
 check(!recordings.startChecked("camera","QA").isEmpty(),"Unavailable encoder silently accepted");
 badCfg.insert("directory","not-an-absolute-folder");recordings.configure(badCfg);check(!recordings.startChecked("camera","QA").isEmpty(),"Invalid folder silently accepted");
 QFile report(QDir(dir).filePath("native-results.json"));check(report.open(QIODevice::WriteOnly),"Cannot write QA evidence");report.write(QJsonDocument(evidence).toJson());report.close();
 obs_set_output_source(2,nullptr);obs_source_release(secondSound);recordings.shutdown();std::cout<<"PASS native recording lifecycle"<<std::endl;
}
