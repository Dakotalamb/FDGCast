// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <obs-module.h>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QColor>
#include <QDir>
#include <QFileInfo>
#include <QTemporaryFile>
#include <QStandardPaths>
#include <QStorageInfo>
#include <QDateTime>
#include <QElapsedTimer>
#include <QRegularExpression>
#include <QSet>
#include <QFile>
#include <vector>
#include <map>
#include <memory>
#include <mutex>
#include <condition_variable>
#include <chrono>
#include <cstring>
#include <cmath>
#include "portrait-layout.hpp"
#include "render-guard.hpp"

namespace fdgcast {
inline bool recordingIdentity(const QString &id) {return QRegularExpression("^[A-Za-z0-9_-]{1,80}$").match(id).hasMatch();}
inline QString recordingError(int code) {
    switch(code){
    case OBS_OUTPUT_SUCCESS:return {};
    case OBS_OUTPUT_NO_SPACE:return "The recording drive ran out of space.";
    case OBS_OUTPUT_BAD_PATH:return "The recording folder is unavailable or cannot be written.";
    case OBS_OUTPUT_ENCODE_ERROR:return "The recording encoder failed. Check GPU/CPU load and encoder capacity.";
    case OBS_OUTPUT_UNSUPPORTED:return "This recording codec or format is not supported by OBS.";
    default:return "Recording stopped with an output error. Check the OBS log.";
    }
}
struct RecordingPicture {
    obs_source_t *self;
    QJsonObject profile,layout;
    std::map<QString,obs_source_t *> children;
    std::recursive_mutex mutex;
    int width,height;
    QString rootId;
    RecordingPicture(obs_source_t *s,QJsonObject p):self(s),profile(p),width(p.value("width").toInt(1920)),height(p.value("height").toInt(1080)){}
    void remove(obs_source_t *source){obs_source_remove_active_child(self,source);obs_source_dec_showing(source);obs_source_release(source);}
    ~RecordingPicture(){for(auto &row:children)remove(row.second);}
    void tick(){
        std::lock_guard<std::recursive_mutex> lock(mutex);
        auto *program=obs_get_output_source(0);if(!program)return;
        auto *scene=obs_source_get_type(program)==OBS_SOURCE_TYPE_TRANSITION?obs_transition_get_active_source(program):obs_source_get_ref(program);
        const bool follow=profile.value("follow_scenes").toBool(true);
        const QString scope=follow?(scene?QString::fromUtf8(obs_source_get_uuid(scene)):QString()):profile.value("scene_id").toString("*");
        rootId=follow||scope=="*"?QString():scope;
        const auto layouts=profile.value("layouts").toObject();layout=layouts.value(scope).toObject();if(layout.isEmpty())layout=layouts.value("*").toObject();
        if(scene)obs_source_release(scene);obs_source_release(program);
        QSet<QString> wanted;if(!rootId.isEmpty())wanted.insert(rootId);
        for(const auto &entry:layout.value("regions").toArray()){
            const auto row=entry.toObject();const auto id=row.value("source").toString();
            if(row.value("visible").toBool(true)&&!id.isEmpty()&&id!="program")wanted.insert(id);
        }
        for(auto it=children.begin();it!=children.end();){if(!wanted.contains(it->first)||obs_source_removed(it->second)){remove(it->second);it=children.erase(it);}else ++it;}
        for(const auto &id:wanted)if(!children.count(id)){
            auto bytes=id.toUtf8();auto *source=obs_get_source_by_uuid(bytes.constData());if(!source)continue;
            if(source==self||!(obs_source_get_output_flags(source)&OBS_SOURCE_VIDEO)||!obs_source_add_active_child(self,source)){obs_source_release(source);continue;}
            obs_source_inc_showing(source);children[id]=source;
        }
    }
    void render(){
        RenderGuard guard;if(!guard)return;
        std::lock_guard<std::recursive_mutex> lock(mutex);
        auto *program=rootId.isEmpty()?obs_get_output_source(0):nullptr;
        auto *root=rootId.isEmpty()?program:children.count(rootId)?children.at(rootId):nullptr;
        const QColor bg(layout.value("background").toString("#000000"));vec4 color;
        vec4_set(&color,float(bg.redF()),float(bg.greenF()),float(bg.blueF()),1.f);gs_clear(GS_CLEAR_COLOR,&color,0.f,0);
        for(const auto &entry:layout.value("regions").toArray()){
            const auto row=entry.toObject();if(!row.value("visible").toBool(true))continue;
            const auto id=row.value("source").toString();auto it=children.find(id);
            auto *source=id=="program"?root:it==children.end()?nullptr:it->second;if(!source)continue;
            const int w=row.value("width").toInt(width),h=row.value("height").toInt(height),x=row.value("x").toInt(),y=row.value("y").toInt();
            if(w<2||h<2||x<0||y<0||x+w>width||y+h>height)continue;
            const float sw=float(obs_source_get_width(source)),sh=float(obs_source_get_height(source));const auto crop=row.value("crop").toObject();
            const float cx=float(crop.value("x").toDouble()),cy=float(crop.value("y").toDouble());
            const float cw=sw*float(crop.value("width").toDouble(1)),ch=sh*float(crop.value("height").toDouble(1));
            const auto p=regionLayout(cw,ch,float(w),float(h),row.value("fit").toString()!="fit",float(row.value("zoom").toDouble(1)),float(row.value("pan_x").toDouble()),float(row.value("pan_y").toDouble()));
            if(p.scale<=0)continue;const bool mirror=row.value("mirror").toBool();
            gs_viewport_push();gs_projection_push();gs_matrix_push();gs_set_viewport(x,y,w,h);
            const int left=int(std::ceil(std::max(0.f,p.x))),top=int(std::ceil(std::max(0.f,p.y)));
            gs_rect clip{x+left,y+top,std::max(0,int(std::floor(std::min(float(w),p.x+cw*p.scale)))-left),std::max(0,int(std::floor(std::min(float(h),p.y+ch*p.scale)))-top)};
            gs_set_scissor_rect(&clip);gs_ortho(0.f,float(w),0.f,float(h),-100.f,100.f);gs_matrix_identity();
            gs_matrix_translate3f(p.x+(mirror?cw*p.scale:0),p.y,0);gs_matrix_scale3f(mirror?-p.scale:p.scale,p.scale,1);gs_matrix_translate3f(-cx*sw,-cy*sh,0);
            obs_source_video_render(source);gs_set_scissor_rect(nullptr);gs_matrix_pop();gs_projection_pop();gs_viewport_pop();
        }
        if(program)obs_source_release(program);
    }
};
inline void registerRecordingPicture(){
    obs_source_info info{};info.id="fdgcast_recording_picture";info.type=OBS_SOURCE_TYPE_INPUT;
    info.output_flags=OBS_SOURCE_VIDEO|OBS_SOURCE_CUSTOM_DRAW|OBS_SOURCE_CAP_DISABLED|OBS_SOURCE_DO_NOT_DUPLICATE;
    info.get_name=[](void *){return "FDGCast recording picture";};
    info.create=[](obs_data_t *data,obs_source_t *source)->void *{return new RecordingPicture(source,QJsonDocument::fromJson(obs_data_get_string(data,"profile")).object());};
    info.destroy=[](void *data){delete static_cast<RecordingPicture *>(data);};
    info.get_width=[](void *data)->uint32_t{return uint32_t(static_cast<RecordingPicture *>(data)->width);};
    info.get_height=[](void *data)->uint32_t{return uint32_t(static_cast<RecordingPicture *>(data)->height);};
    info.video_tick=[](void *data,float){static_cast<RecordingPicture *>(data)->tick();};
    info.video_render=[](void *data,gs_effect_t *){static_cast<RecordingPicture *>(data)->render();};obs_register_source(&info);
}
inline QJsonArray recordingEncoders(){
    QJsonArray rows;const char *id=nullptr;
    for(size_t i=0;obs_enum_encoder_types(i,&id);++i){const auto *codec=obs_get_encoder_codec(id);
        if(!codec||std::strcmp(codec,"h264")!=0||(obs_get_encoder_caps(id)&(OBS_ENCODER_CAP_DEPRECATED|OBS_ENCODER_CAP_INTERNAL)))continue;
        rows.append(QJsonObject{{"id",id},{"name",obs_encoder_get_display_name(id)}});
    }return rows;
}
inline QString recordingEncoder(const QString &choice){
    const auto available=recordingEncoders();QString software,hardware;
    for(const auto &entry:available){const auto id=entry.toObject().value("id").toString();if(choice==id)return id;if(id=="obs_x264")software=id;}
    if(choice!="auto")return {};
    for(const auto &family:{"nvenc","amf","qsv","apple"}){
        for(const auto &entry:available){const auto id=entry.toObject().value("id").toString();if(id.contains(family))return id;}
    }return software;
}
struct RecordingVideo {
    obs_encoder_t *encoder=nullptr;obs_view_t *view=nullptr;bool added=false,reused=false;
    ~RecordingVideo(){if(encoder)obs_encoder_release(encoder);if(added)obs_view_remove(view);if(view)obs_view_destroy(view);}
    bool create(const QJsonObject &profile,obs_encoder_t *stream,QString &error){
        const bool custom=profile.value("picture").toString()=="custom";
        if(!custom&&stream){const char *codec=obs_encoder_get_codec(stream);
            if(codec&&(std::strcmp(codec,"h264")==0||std::strcmp(codec,"hevc")==0||std::strcmp(codec,"av1")==0)){encoder=obs_encoder_get_ref(stream);reused=true;return true;}}
        obs_video_info info{};if(!obs_get_video_info(&info)){error="OBS video is unavailable.";return false;}
        video_t *video=obs_get_video();
        if(custom){
            info.base_width=info.output_width=uint32_t(profile.value("width").toInt());info.base_height=info.output_height=uint32_t(profile.value("height").toInt());
            info.output_format=VIDEO_FORMAT_NV12;info.colorspace=VIDEO_CS_709;info.range=VIDEO_RANGE_PARTIAL;
            view=obs_view_create();if(!view){error="The recording view could not be created.";return false;}
            auto *settings=obs_data_create();const auto bytes=QJsonDocument(profile).toJson(QJsonDocument::Compact);obs_data_set_string(settings,"profile",bytes.constData());
            auto *source=obs_source_create_private("fdgcast_recording_picture","FDGCast independent recording picture",settings);obs_data_release(settings);
            if(!source){error="The recording layout is unavailable.";return false;}obs_view_set_source(view,0,source);obs_source_release(source);
            video=obs_view_add2(view,&info);if(!video){error="OBS could not add the recording view.";return false;}added=true;
        }
        const auto id=recordingEncoder(profile.value("encoder").toString("auto"));if(id.isEmpty()){error="The selected H.264 encoder is unavailable. Refresh recording sources.";return false;}
        auto *settings=obs_encoder_defaults(id.toUtf8().constData());if(!settings)settings=obs_data_create();
        obs_data_set_string(settings,"rate_control","CBR");obs_data_set_int(settings,"bitrate",profile.value("bitrate_kbps").toInt(12000));obs_data_set_int(settings,"keyint_sec",2);
        if(id=="obs_x264")obs_data_set_string(settings,"preset","veryfast");
        encoder=obs_video_encoder_create(id.toUtf8().constData(),"FDGCast recording video",settings,nullptr);obs_data_release(settings);
        if(!encoder){error="OBS could not create the recording encoder. Check encoder/GPU capacity.";return false;}
        obs_encoder_set_video(encoder,video);
        if(!obs_encoder_set_frame_rate_divisor(encoder,uint32_t(profile.value("fps_divisor").toInt(1)))){error="OBS could not apply the recording frame rate.";return false;}
        return true;
    }
};
struct RecordingAudio {
    obs_encoder_t *encoder=nullptr;
    ~RecordingAudio(){if(encoder)obs_encoder_release(encoder);}
    bool create(int track){
        auto *settings=obs_data_create();obs_data_set_int(settings,"bitrate",160);
        const auto name=QString("FDGCast recording audio track %1").arg(track).toUtf8();
        encoder=obs_audio_encoder_create("ffmpeg_aac",name.constData(),settings,size_t(track-1),nullptr);obs_data_release(settings);
        if(encoder)obs_encoder_set_audio(encoder,obs_get_audio());return encoder!=nullptr;
    }
};
struct RecordingFile {
    QString id,name,path,error;std::shared_ptr<RecordingVideo> video;std::vector<std::shared_ptr<RecordingAudio>> audio;
    obs_output_t *output=nullptr;bool accepted=false,stopping=false,automatic=false;int stopCode=0;bool started=false,stopped=false;
    std::mutex mutex;std::condition_variable complete;QElapsedTimer clock;
    static void onStart(void *data,calldata_t *){auto *s=static_cast<RecordingFile *>(data);std::lock_guard<std::mutex> lock(s->mutex);s->started=true;}
    static void onStop(void *data,calldata_t *event){auto *s=static_cast<RecordingFile *>(data);std::lock_guard<std::mutex> lock(s->mutex);s->stopCode=int(calldata_int(event,"code"));s->stopped=true;s->complete.notify_all();}
    bool begin(){
        auto *settings=obs_data_create();const auto bytes=path.toUtf8();obs_data_set_string(settings,"path",bytes.constData());
        output=obs_output_create("ffmpeg_muxer",("FDGCast recording "+id).toUtf8().constData(),settings,nullptr);obs_data_release(settings);
        if(!output){error="OBS file recording output is unavailable.";return false;}
        obs_output_set_video_encoder(output,video->encoder);
        for(size_t i=0;i<audio.size();++i)obs_output_set_audio_encoder(output,audio[i]->encoder,i);
        auto *signals=obs_output_get_signal_handler(output);signal_handler_connect(signals,"start",onStart,this);signal_handler_connect(signals,"stop",onStop,this);
        clock.start();accepted=obs_output_start(output);
        if(!accepted){const char *detail=obs_output_get_last_error(output);error=detail&&*detail?QString::fromUtf8(detail).left(600):"Recording could not start. Check the OBS log and encoder capacity.";}
        return accepted;
    }
    void stop(){if(!output||stopping)return;stopping=true;obs_output_stop(output);}
    bool done(){std::lock_guard<std::mutex> lock(mutex);return output&&stopped&&!obs_output_active(output);}
    QJsonObject status(){
        std::lock_guard<std::mutex> lock(mutex);const bool active=output&&obs_output_active(output);
        const auto issue=!error.isEmpty()?error:stopped?recordingError(stopCode):QString();
        return QJsonObject{{"id",id},{"name",name},{"path",path},{"active",active},{"busy",accepted&&!stopped&&(!started||stopping)},
            {"state",!issue.isEmpty()?"error":stopping&&!stopped?"stopping":stopped?"saved":started?"recording":"starting"},{"error",issue},
            {"bytes",output?double(obs_output_get_total_bytes(output)):0.0},{"frames",output?int(obs_output_get_total_frames(output)):0},
            {"seconds",clock.isValid()?double(clock.elapsed())/1000:0.0},{"width",video&&video->encoder?int(obs_encoder_get_width(video->encoder)):0},
            {"height",video&&video->encoder?int(obs_encoder_get_height(video->encoder)):0},{"reused_encoder",video&&video->reused},{"automatic",automatic}};
    }
    void finish(){
        if(output&&accepted&&!done()){
                stop();std::unique_lock<std::mutex> lock(mutex);
                if(!complete.wait_for(lock,std::chrono::seconds(8),[this]{return stopped;})){
                    lock.unlock();obs_output_force_stop(output);lock.lock();complete.wait_for(lock,std::chrono::seconds(2),[this]{return stopped;});
                }
        }
    }
    ~RecordingFile(){
        if(output){
            finish();
            auto *signals=obs_output_get_signal_handler(output);signal_handler_disconnect(signals,"start",onStart,this);signal_handler_disconnect(signals,"stop",onStop,this);
            obs_output_release(output);
        }
    }
};
class RecordingStudio {
    QJsonObject config;
    std::map<QString,std::unique_ptr<RecordingFile>> files;
    std::map<QString,QJsonObject> history;
    std::map<QByteArray,std::weak_ptr<RecordingVideo>> videos;
    std::map<int,std::weak_ptr<RecordingAudio>> audios;
public:
    QString defaultDirectory=QStandardPaths::writableLocation(QStandardPaths::MoviesLocation);
    void configure(const QJsonObject &value){
        if(busy()||value.value("schema_version").toInt()!=1||value.value("profiles").toArray().size()>3)return;
        config=value;QSet<QString> ids;for(const auto &entry:value.value("profiles").toArray())ids.insert(entry.toObject().value("id").toString());
        for(auto it=history.begin();it!=history.end();)if(!ids.contains(it->first))it=history.erase(it);else ++it;
    }
    QJsonObject profile(const QString &id)const{for(const auto &entry:config.value("profiles").toArray())if(entry.toObject().value("id").toString()==id)return entry.toObject();return {};}
    bool busy()const{return !files.empty();}
    QString start(const QString &id,const QString &collection,obs_encoder_t *stream=nullptr,bool automatic=false){
        tick();if(files.count(id))return "This recording is already active or stopping.";
        const auto p=profile(id);if(p.isEmpty()||!recordingIdentity(id))return "Save this recording file first.";
        if(config.value("collection").toString()!=collection)return "This recording belongs to a different OBS scene collection. Refresh sources and save it for this collection.";
        if(files.size()>=3)return "Three Recording Studio files are already running. Extra files require extra encoding capacity.";
        const bool custom=p.value("picture").toString()=="custom";
        const int w=p.value("width").toInt(),h=p.value("height").toInt(),rate=p.value("bitrate_kbps").toInt(),divisor=p.value("fps_divisor").toInt(1);
        if(w<64||h<64||w>3840||h>3840||w%2||h%2||int64_t(w)*h>8294400||rate<1000||rate>80000||divisor<1||divisor>4)return "Invalid recording dimensions, bitrate or frame rate.";
        if(p.value("picture").toString()!="custom"&&p.value("picture").toString()!="stream")return "Choose a recording picture.";
        if(custom){
            const auto layouts=p.value("layouts").toObject();if(!layouts.contains("*")||layouts.size()>129)return "Save a default recording layout first.";
            if(!p.value("follow_scenes").toBool(true)&&p.value("scene_id").toString("*")!="*"){
                auto *scene=obs_get_source_by_uuid(p.value("scene_id").toString().toUtf8().constData());
                const bool valid=scene&&obs_scene_from_source(scene);if(scene)obs_source_release(scene);if(!valid)return "The selected recording scene is missing. Refresh OBS sources.";
            }
            for(auto it=layouts.begin();it!=layouts.end();++it){const auto rows=it.value().toObject().value("regions").toArray();
                if(rows.isEmpty()||rows.size()>4)return "Use one to four recording pictures.";bool visible=false;
                for(const auto &entry:rows){const auto r=entry.toObject();const auto sourceId=r.value("source").toString();
                    if(sourceId!="program") {auto *source=obs_get_source_by_uuid(sourceId.toUtf8().constData());const bool valid=source&&(obs_source_get_output_flags(source)&OBS_SOURCE_VIDEO);if(source)obs_source_release(source);if(!valid)return "A recording source is missing. Refresh sources and choose its replacement.";}
                    const double x=r.value("x").toDouble(-1),y=r.value("y").toDouble(-1),rw=r.value("width").toDouble(),rh=r.value("height").toDouble();
                    const auto crop=r.value("crop").toObject();const double cx=crop.value("x").toDouble(),cy=crop.value("y").toDouble(),cw=crop.value("width").toDouble(1),ch=crop.value("height").toDouble(1);
                    if(!std::isfinite(x+y+rw+rh+cx+cy+cw+ch)||x<0||y<0||rw<2||rh<2||x+rw>w||y+rh>h||cx<0||cy<0||cw<.005||ch<.005||cx+cw>1.000001||cy+ch>1.000001)return "A recording picture has an invalid position or crop.";
                    visible=visible||r.value("visible").toBool(true);
                }if(!visible)return "Keep at least one recording picture visible.";
            }
        }
        const auto tracks=p.value("audio_tracks").toArray();if(tracks.isEmpty()||tracks.size()>6)return "Choose one to six OBS audio tracks.";
        QString dir=config.value("directory").toString();if(dir.isEmpty())dir=defaultDirectory;
        if(!QDir::isAbsolutePath(dir)||dir.startsWith("\\\\")||dir.startsWith("//"))return "Choose a local recording folder.";
        if(!QDir(dir).exists()&&!QDir().mkpath(dir))return "The recording folder could not be created.";
        QStorageInfo storage(dir);if(storage.isValid()&&storage.bytesAvailable()<256LL*1024*1024)return "The recording drive has less than 256 MB free. Choose another folder.";
        QTemporaryFile reservation(QDir(dir).filePath("FDGCast-"+id+"-"+QDateTime::currentDateTime().toString("yyyyMMdd-hhmmss")+"-XXXXXX.mkv"));
        reservation.setAutoRemove(false);if(!reservation.open())return "The recording folder cannot be written.";const auto path=reservation.fileName();reservation.close();
        auto s=std::make_unique<RecordingFile>();s->id=id;s->name=p.value("name").toString();s->path=path;s->automatic=automatic;
        QJsonObject signature=p;for(const auto &key:{"id","name","link_stream"})signature.remove(key);
        // Same-picture files share a video encoder only when their actual source/settings match.
        if(!custom&&stream)signature=QJsonObject{{"stream_encoder",QString::number(quintptr(stream))}};
        const auto key=QJsonDocument(signature).toJson(QJsonDocument::Compact);s->video=videos[key].lock();
        if(!s->video){s->video=std::make_shared<RecordingVideo>();if(!s->video->create(p,stream,s->error)){const auto message=s->error;QFile::remove(path);return message;}videos[key]=s->video;}
        QSet<int> seen;
        for(const auto &entry:tracks){const int track=entry.toInt();if(track<1||track>6||seen.contains(track)){QFile::remove(path);return "Invalid audio track selection.";}seen.insert(track);
            auto audio=audios[track].lock();if(!audio){audio=std::make_shared<RecordingAudio>();if(!audio->create(track)){QFile::remove(path);return "OBS AAC recording audio is unavailable.";}audios[track]=audio;}s->audio.push_back(audio);}
        if(!s->begin()){const auto message=s->error;history[id]=s->status();s.reset();if(QFileInfo(path).size()==0)QFile::remove(path);return message;}
        history.erase(id);files[id]=std::move(s);return {};
    }
    QString startChecked(const QString &id,const QString &collection,obs_encoder_t *stream=nullptr,bool automatic=false){
        const auto message=start(id,collection,stream,automatic);
        if(!message.isEmpty())history[id]=QJsonObject{{"id",id},{"name",profile(id).value("name")},{"state","error"},{"error",message}};
        return message;
    }
    void stop(const QString &id){auto it=files.find(id);if(it!=files.end())it->second->stop();}
    void stopAll(bool linkedOnly=false){for(auto &row:files)if(!linkedOnly||row.second->automatic)row.second->stop();}
    void startLinked(const QString &collection,obs_encoder_t *stream){for(const auto &entry:config.value("profiles").toArray()){const auto p=entry.toObject();if(p.value("link_stream").toBool()){
        const auto message=startChecked(p.value("id").toString(),collection,stream,true);if(!message.isEmpty())history[p.value("id").toString()]=QJsonObject{{"id",p.value("id")},{"name",p.value("name")},{"state","error"},{"error",message}};}}}
    void tick(){
        for(auto it=files.begin();it!=files.end();){auto &s=*it->second;
            if(s.done()){history[it->first]=s.status();it=files.erase(it);continue;}
            bool timedOut=false;
            if(s.clock.elapsed()>15000){std::lock_guard<std::mutex> lock(s.mutex);if(!s.started&&!s.stopping){s.error="Recording did not start within 15 seconds.";s.stopping=true;timedOut=true;}}
            if(timedOut)obs_output_force_stop(s.output);
            if(!s.stopping){QStorageInfo storage(QFileInfo(s.path).absolutePath());if(storage.isValid()&&storage.bytesAvailable()<128LL*1024*1024){s.error="Recording stopped because the drive has less than 128 MB free.";s.stop();}}
            ++it;
        }
        for(auto it=videos.begin();it!=videos.end();)if(it->second.expired())it=videos.erase(it);else ++it;
        for(auto it=audios.begin();it!=audios.end();)if(it->second.expired())it=audios.erase(it);else ++it;
    }
    void shutdown(){stopAll();for(auto &row:files){row.second->finish();history[row.first]=row.second->status();}files.clear();videos.clear();audios.clear();}
    QJsonObject status(const QString &collection){
        QJsonArray rows;for(const auto &entry:config.value("profiles").toArray()){const auto id=entry.toObject().value("id").toString();
            if(files.count(id))rows.append(files.at(id)->status());else if(history.count(id))rows.append(history.at(id));}
        return QJsonObject{{"files",rows},{"default_directory",defaultDirectory},{"encoders",recordingEncoders()},{"collection",collection}};
    }
    ~RecordingStudio(){shutdown();}
};
} // namespace fdgcast
