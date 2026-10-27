"""Optional local forced alignment for accurate SRT and speech-driven animation anchors."""
import argparse,base64,copy,json,os,re,unicodedata,subprocess
from pathlib import Path
from lib.project_data import read,write,settings,tool,sha,bytes_for,audio_valid
from lib.teaching_timing import retime_scene
_ENGINES={}
def clean(text):return ''.join(c.lower() for c in text if unicodedata.category(c)[0] in 'LN' or c=="'")
def align_audio(raw,text,duration,root,model_path):
    model_path=Path(model_path).expanduser()
    if not (model_path/'config.json').is_file():raise RuntimeError('请配置本地Qwen3-ForcedAligner模型；未自动下载或上传音频')
    os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    import numpy as np
    from mlx_audio.stt import load
    key=str(model_path.resolve())
    if key not in _ENGINES:_ENGINES[key]=load(key)
    pcm=subprocess.check_output([tool('ffmpeg',root),'-v','error','-nostdin','-i','pipe:0','-ar','16000','-ac','1','-f','f32le','-'],input=raw)
    words=copy.deepcopy(_ENGINES[key].generate(audio=np.frombuffer(pcm,dtype='<f4').copy(),text=text,language='Chinese').segments)
    pointer=0;previous=0
    for word in words:
        token=clean(word['text']);start=pointer
        while start<len(text) and not clean(text[start]):start+=1
        end=start;found=''
        while end<len(text) and len(found)<len(token):found+=clean(text[end]);end+=1
        if found!=token:raise ValueError('对齐文本覆盖不一致；保留原始配音，需复核专有词')
        a,b=float(word['start']),float(word['end'])
        if not 0<=a<=b<=duration+.32 or a<previous-.001:raise ValueError('声学对齐时间越界或倒序')
        word.update(charStart=start,charEnd=end,start=min(a,duration),end=min(b,duration));pointer=end;previous=word['end']
    if clean(''.join(w['text'] for w in words))!=clean(text):raise ValueError('对齐文字未覆盖当前讲稿')
    cues=[];first=0;char_begin=0
    for i,w in enumerate(words):
        endchar=words[i+1]['charStart'] if i+1<len(words) else len(text)
        gap=text[w['charEnd']:endchar]
        if i+1==len(words) or re.search('[。！？；]',gap):
            a,b=words[first]['start'],w['end'];content=text[char_begin:endchar]
            if (b-a<.4 or len(clean(content))<3) and cues:cues[-1]['text']+=content;cues[-1]['end']=max(cues[-1]['end'],b)
            else:cues.append({'start':round(a,3),'end':round(b,3),'text':content})
            first=i+1;char_begin=endchar
    if not cues or ''.join(c['text'] for c in cues)!=text or any(c['end']<=c['start'] for c in cues):raise ValueError('字幕计时需人工修正')
    return cues,{'method':'local-forced-alignment','modelFamily':'Qwen3-ForcedAligner-0.6B','audioSHA256':sha(raw),'text':text,'units':words,'note':'强制对齐只定位给定文字，不证明声音实际无漏读；仍需核听或独立ASR。'}
def align_project(path,model=None,scene_id=None):
    path=Path(path).resolve();p=read(path);root=path.parent;model=model or settings(root).get('alignmentModelPath')
    if not model:raise RuntimeError('缺少alignmentModelPath；也可导入已核对的字幕计时后retime')
    for scene in p['scenes']:
        if scene_id and scene['id']!=scene_id:continue
        if not audio_valid(scene,p):raise ValueError('请先更新当前文稿配音：'+scene['id'])
        a=scene['audio'];a['cues'],a['alignment']=align_audio(bytes_for(root,a['src']),scene['narration'],a['duration'],root,model)
        if scene.get('beats'):retime_scene(scene)
        p['revision']=p.get('revision',0)+1;write(path,p);print(scene['id'],len(a['cues']),'个声学计时句',flush=True)
    return p
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--scene');ap.add_argument('--model');a=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(a.project).resolve().parent)
    try:align_project(a.project,a.model,a.scene)
    except Exception as e:ap.exit(1,str(e)+'\n')
