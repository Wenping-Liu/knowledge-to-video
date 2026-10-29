"""Qwen local voices and explicitly enabled Azure/Breeze Speech; no silent provider switches."""
import argparse, base64, io, json, math, os, subprocess, tempfile, threading, wave
from pathlib import Path
from lib.project_data import read,write,settings,signature,sha,fit_duration,audio_valid,tool,inside,effective_voice
_ENGINES={};_LOCK=threading.Lock()

def tempo_factor(value):
    factor=float(value)
    if not math.isfinite(factor) or not .5<=factor<=2:raise ValueError('配音speed须为0.5至2.0倍；通过保音高处理调整')
    return factor

def apply_tempo(raw,factor,root):
    factor=tempo_factor(factor)
    if factor==1:return raw
    return subprocess.check_output([tool('ffmpeg',root),'-v','error','-nostdin','-i','pipe:0','-af',f'atempo={factor:g}','-ar','24000','-ac','1','-c:a','pcm_s16le','-f','wav','pipe:1'],input=raw)

def synthesize(text,voice,root):
    if not text.strip() or len(text)>3000:raise ValueError('每段旁白须为1–3000字')
    backend=voice.get('backend','mlx');speed=tempo_factor(voice.get('speed',1));cfg=settings(root)
    if backend=='import':raise ValueError('当前选用外部配音导入，请先在所选平台生成，再导入与本镜文稿一致的音频')
    if backend=='breeze':
        from lib.breeze_voice import breeze_audio
        raw=normalize(apply_tempo(breeze_audio(text,voice),speed,root),root)
        result=bind_audio(raw,text,voice,{'type':'cloud-tts','provider':'BreezeBlue','speaker':voice.get('speaker'),'modelFamily':voice.get('modelFamily'),'sentData':'current scene narration and performance instructions','instructionSupport':True})
        if speed!=1:result['provenance']['tempo']={'method':'ffmpeg-atempo','factor':speed,'preservePitch':True}
        return maybe_align(result,raw,text,root,cfg)
    if backend=='azure':
        from lib.cloud_voice import azure_audio
        raw=normalize(apply_tempo(azure_audio(text,voice),speed,root),root)
        result=bind_audio(raw,text,voice,{'type':'cloud-tts','provider':'Microsoft Azure Speech','speaker':voice.get('speaker'),'modelFamily':voice.get('modelFamily'),'sentData':'current scene narration only','instructionSupport':'Named neural voice; free-form scene instructions are not translated by this adapter'})
        if speed!=1:result['provenance']['tempo']={'method':'ffmpeg-atempo','factor':speed,'preservePitch':True}
        return maybe_align(result,raw,text,root,cfg)
    if voice.get('speaker')!='Serena' or '1.7B' not in voice.get('modelFamily',''):raise ValueError('本地适配器需要指定的Qwen3-TTS 1.7B Serena')
    cfg=settings(root);model=Path(os.environ.get('KTV_MODEL') or cfg.get('modelPath','')).expanduser()
    if not model.is_dir() or not (model/'config.json').is_file():raise RuntimeError('请在runtime.settings.json中配置本地1.7B CustomVoice模型路径，或设置KTV_MODEL')
    backend=voice.get('backend','mlx')
    if cfg.get('voiceBackend') and cfg['voiceBackend']!=backend:raise ValueError('voiceBackend与工程voice.backend不同；修改工程声音配置后重新生成全部配音')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import numpy as np
    with _LOCK:
        key=(backend,str(model.resolve()),cfg.get('device'),cfg.get('dtype'))
        if backend=='mlx':
            import mlx.core as mx
            from mlx_audio.tts.utils import load_model
            if key not in _ENGINES:_ENGINES[key]=load_model(str(model))
            engine=_ENGINES[key]
            if getattr(engine.config,'tts_model_size',None)=='0b6':raise ValueError('需要1.7B，检测到0.6B模型')
            mx.random.seed(int(voice.get('seed',42)));limit=max(1000,min(14000,len(text)*8))
            results=list(engine.generate_custom_voice(text=text,speaker='Serena',language=voice.get('language','Chinese'),instruct=voice.get('instruction',''),temperature=voice.get('temperature',.65),max_tokens=limit,verbose=False))
            if not results:raise RuntimeError('没有生成语音')
            if any(isinstance(getattr(x,'token_count',None),int) and x.token_count>=limit for x in results):raise RuntimeError('达到生成长度限制，请拆分此镜头')
            audio=np.concatenate([np.asarray(x.audio) for x in results]);sr=results[0].sample_rate
        elif backend=='qwen':
            import torch
            from qwen_tts import Qwen3TTSModel
            device=cfg.get('device','cpu')
            if device=='auto':device='cuda:0' if torch.cuda.is_available() else 'cpu'
            dtype=getattr(torch,cfg.get('dtype','float16' if device.startswith('cuda') else 'float32'))
            if key not in _ENGINES:_ENGINES[key]=Qwen3TTSModel.from_pretrained(str(model),device_map=device,dtype=dtype)
            torch.manual_seed(int(voice.get('seed',42)))
            waves,sr=_ENGINES[key].generate_custom_voice(text=text,language=voice.get('language','Chinese'),speaker='Serena',instruct=voice.get('instruction',''),temperature=voice.get('temperature',.65))
            audio=np.asarray(waves[0])
        else:raise ValueError('配音backend支持mlx或qwen；不自动替换供应商')
    if not audio.size or not np.isfinite(audio).all() or float(np.sqrt(np.mean(audio**2)))<.0001:raise RuntimeError('配音为空、无效或仅有静音')
    stream=io.BytesIO()
    with wave.open(stream,'wb') as w:w.setparams((1,2,int(sr),0,'NONE','not compressed'));w.writeframes(np.int16(np.clip(audio,-1,1)*32767).tobytes())
    raw=normalize(apply_tempo(stream.getvalue(),speed,root),root)
    result=bind_audio(raw,text,voice,{'type':'local-tts','backend':backend,'modelFamily':voice['modelFamily'],'speaker':'Serena','seed':voice.get('seed',42),'temperature':voice.get('temperature',.65),'modelConfigHash':sha((model/'config.json').read_bytes())})
    if speed!=1:result['provenance']['tempo']={'method':'ffmpeg-atempo','factor':speed,'preservePitch':True}
    return maybe_align(result,raw,text,root,cfg)

def maybe_align(result,raw,text,root,cfg):
    if cfg.get('alignmentModelPath'):
        try:
            from align import align_audio
            result['cues'],result['alignment']=align_audio(raw,text,result['duration'],root,cfg['alignmentModelPath'])
        except Exception as e:result['alignmentError']=str(e)
    return result

def normalize(raw,root):
    with tempfile.TemporaryDirectory(prefix='ktv-voice-') as td:
        source=Path(td)/'source.audio';out=Path(td)/'voice.wav';source.write_bytes(raw);ff=tool('ffmpeg',root)
        result=subprocess.run([ff,'-hide_banner','-nostdin','-i',str(source),'-af','loudnorm=I=-16:TP=-2:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True).stderr
        stats=json.loads(result[result.rfind('{'):result.rfind('}')+1])
        if stats['input_i']=='-inf':raise ValueError('导入或生成的配音只有静音')
        filt='loudnorm=I=-16:TP=-2:LRA=11:linear=true:measured_I='+stats['input_i']+':measured_TP='+stats['input_tp']+':measured_LRA='+stats['input_lra']+':measured_thresh='+stats['input_thresh']+':offset='+stats['target_offset']
        subprocess.run([ff,'-v','error','-nostdin','-y','-i',str(source),'-af',filt,'-ar','24000','-ac','1','-c:a','pcm_s16le',str(out)],check=True)
        return out.read_bytes()

def bind_audio(raw,text,voice,provenance):
    with wave.open(io.BytesIO(raw)) as w:duration=w.getnframes()/w.getframerate()
    return {'src':'data:audio/wav;base64,'+base64.b64encode(raw).decode(),'text':text,'signature':signature(text,voice),'sha256':sha(raw),'duration':duration,'cues':[],'provenance':provenance}

def generate_project(path,scene_id=None,import_path=None):
    path=Path(path).resolve();p=read(path);root=path.parent;count=0
    for s in p['scenes']:
        if scene_id and s['id']!=scene_id:continue
        count+=1
        if import_path:
            if not scene_id:raise ValueError('导入音频须指定--scene')
            raw=normalize(Path(import_path).read_bytes(),root);a=bind_audio(raw,s['narration'],effective_voice(p,s),{'type':'user-import','file':Path(import_path).name,'transcriptConfirmedByUser':True})
        elif audio_valid(s,p):continue
        else:a=synthesize(s['narration'],effective_voice(p,s),root)
        raw=base64.b64decode(a['src'].split(',',1)[1]);rel='配音/'+s['id']+'-'+a['sha256'][:12]+'.wav';dest=inside(root,rel);dest.parent.mkdir(exist_ok=True);dest.write_bytes(raw);a['src']=rel;s['audio']=a;fit_duration(s)
        if s.get('beats'):
            try:
                from lib.teaching_timing import retime_scene
                retime_scene(s)
            except ValueError as e:s['timing']={'status':'pending','reason':str(e),'audioSHA256':a['sha256']}
        p['revision']=p.get('revision',0)+1;write(path,p)
        print(s['id'],round(a['duration'],2),'秒',flush=True)
    if not count:raise ValueError('找不到指定镜头')
    return p
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--scene');ap.add_argument('--import-audio');a=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(a.project).resolve().parent)
    try:generate_project(a.project,a.scene,a.import_audio)
    except Exception as e:ap.exit(1,str(e)+'\n')
