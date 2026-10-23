"""Project and encoded-delivery checks; subjective review remains explicitly pending."""
import argparse,array,json,math,re,subprocess
from pathlib import Path
from lib.project_data import read,write,validate,probe,tool,fingerprint,sha,bytes_for
from lib.timeline import slug,cues

def check_video(path,root,expected=None):
    info=probe(path,root);streams=info.get('streams',[]);video=next((s for s in streams if s['codec_type']=='video'),None);audio=next((s for s in streams if s['codec_type']=='audio'),None);errors=[]
    if not video or video.get('codec_name')!='h264':errors.append('缺少H.264视频')
    if not audio or audio.get('codec_name')!='aac':errors.append('缺少AAC音频')
    duration=float(info.get('format',{}).get('duration',0))
    if expected and abs(duration-expected)>.15:errors.append('成片时长与工程不一致')
    ff=tool('ffmpeg',root)
    subprocess.run([ff,'-v','error','-xerror','-nostdin','-i',str(path),'-f','null','-'],check=True,capture_output=True)
    raw=subprocess.check_output([ff,'-v','error','-nostdin','-i',str(path),'-vn','-f','f32le','-ar','8000','-ac','1','-']);samples=array.array('f');samples.frombytes(raw)
    if __import__('sys').byteorder!='little':samples.byteswap()
    rms=math.sqrt(sum(x*x for x in samples)/max(1,len(samples)))
    if rms<.0001:errors.append('音轨为空或接近静音')
    measured=subprocess.run([ff,'-hide_banner','-nostdin','-i',str(path),'-vn','-af','loudnorm=I=-16:TP=-1:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True).stderr
    stats=json.loads(measured[measured.rfind('{'):measured.rfind('}')+1])
    if float(stats['input_tp'])>-.8:errors.append('编码后声音峰值过高')
    return {'duration':duration,'video':video and {k:video.get(k) for k in ['codec_name','width','height','avg_frame_rate']},'audio':audio and {k:audio.get(k) for k in ['codec_name','sample_rate','channels']},'rms':rms,'loudness':stats,'fullDecode':True,'errors':errors}

def report(path,require_audio=False,delivery=False):
    path=Path(path).resolve();p=read(path);root=path.parent;errors=validate(p,root,require_audio or delivery);warnings=[];details={}
    sourceids={s.get('id') for s in p.get('sources',[])}
    for entry in p.get('sources',[]):
        if entry.get('path'):
            from lib.project_data import inside
            try:
                if not inside(root.parent,entry['path']).is_file():errors.append('来源文件缺失：'+entry['path'])
            except ValueError as e:errors.append(str(e))
    for s in p['scenes']:
        for sid in s.get('sourceIds',[]):
            if sid not in sourceids:errors.append(s['id']+'来源ID不存在：'+sid)
        for term in p.get('profile',{}).get('excludedScreenTerms',[]):
            if any(term.lower() in l.get('text','').lower() for l in s['layers']):errors.append(s['id']+'画面含排除词：'+term)
    if not p.get('sources'):warnings.append('待补资料来源')
    if not p.get('coverage'):warnings.append('待补教材覆盖记录')
    if require_audio or delivery:
        try:cues(p)
        except (KeyError,ValueError,TypeError) as e:errors.append('字幕：'+str(e))
    if delivery:
        delivery_root=root.parent;main=delivery_root/(slug(p['title'])+'.mp4');record=delivery_root/'资料与来源/渲染记录.json'
        if not main.exists():errors.append('缺少主成片')
        elif not record.exists():errors.append('缺少当前渲染记录')
        else:
            r=read(record)
            if r.get('projectFingerprint')!=fingerprint(p):errors.append('成片对应旧工程，请重新导出')
            if r.get('sha256')!=sha(main.read_bytes()):errors.append('成片指纹不符')
            details['video']=check_video(main,root,sum(s['duration'] for s in p['scenes']));errors+=details['video']['errors']
        required=['可编辑工程/编辑器.html','使用说明.txt','剪映素材/无旁白字幕版.mp4','剪映素材/字幕.srt','剪映素材/分镜旁白.txt','资料与来源/交付清单.json']
        for rel in required:
            if not (delivery_root/rel).is_file():errors.append('交付缺文件：'+rel)
        for i,s in enumerate(p['scenes']):
            for folder,ext in [('分镜配音','wav'),('分镜画面参考','png')]:
                if not (delivery_root/f'剪映素材/{folder}/{i+1:03}-{slug(s["title"])}.{ext}').is_file():errors.append('分镜交付缺失：'+s['id']+folder)
        manifest=delivery_root/'资料与来源/交付清单.json'
        if manifest.exists():
            m=read(manifest)
            if m.get('projectFingerprint')!=fingerprint(p):errors.append('交付清单对应旧工程')
            for item in m.get('files',[]):
                from lib.project_data import inside
                try:
                    f=inside(delivery_root,item['path'])
                    if not f.is_file() or sha(f.read_bytes())!=item['sha256']:errors.append('交付文件指纹不符：'+item['path'])
                except ValueError as e:errors.append(str(e))
    review=p.get('review',{})
    if review.get('projectFingerprint')!=fingerprint({**p,'review':{}}) or not review.get('evidence'):warnings.append('教学、完整观看和听感待人工复核；自动检查不能代替')
    return {'status':'fail' if errors else 'pass','projectFingerprint':fingerprint(p),'errors':errors,'warnings':warnings,'details':details}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--require-audio',action='store_true');ap.add_argument('--delivery',action='store_true');ap.add_argument('--out');a=ap.parse_args()
    try:
        r=report(a.project,a.require_audio,a.delivery);print(json.dumps(r,ensure_ascii=False,indent=2))
        if a.out:write(a.out,r)
        ap.exit(1 if r['errors'] else 0)
    except Exception as e:ap.exit(1,str(e)+'\n')
