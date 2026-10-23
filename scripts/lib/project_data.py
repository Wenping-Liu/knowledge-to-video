"""Portable project I/O. Standard library; every media reference stays in the project."""
import base64, copy, hashlib, json, math, mimetypes, os, re, shutil, subprocess, tempfile
from pathlib import Path
from .environment import merged_settings

SCHEMA_VERSION=1
MEDIA_TYPES={'audio':('audio/', '配音'), 'image':('image/', '图片'), 'video':('video/', '案例视频')}

def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))

def write(path, data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    raw=json.dumps(data,ensure_ascii=False,indent=2,allow_nan=False)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.ktv-',suffix='.tmp')
    try:
        with os.fdopen(fd,'w',encoding='utf-8') as f:f.write(raw)
        os.replace(tmp,path)
    finally:
        if Path(tmp).exists():Path(tmp).unlink()

def sha(data):return hashlib.sha256(data).hexdigest()
def canonical(value):
    if isinstance(value,float) and value.is_integer():return int(value)
    if isinstance(value,dict):return {k:canonical(v) for k,v in value.items()}
    if isinstance(value,list):return [canonical(v) for v in value]
    return value
def signature(text, voice):return sha(json.dumps(canonical({'text':text,'voice':voice}),sort_keys=True,ensure_ascii=False,separators=(',',':')).encode())
def fingerprint(p):return sha(json.dumps(p,sort_keys=True,ensure_ascii=False,allow_nan=False).encode())
def inside(root, rel):
    root=Path(root).resolve()
    if not isinstance(rel,str) or not rel or Path(rel).is_absolute() or '\\' in rel:raise ValueError('素材路径必须是工程内的相对路径')
    p=(root/rel).resolve()
    if not p.is_relative_to(root):raise ValueError('路径越出工程目录：'+rel)
    return p

def bytes_for(root,src):
    if src.startswith('data:'):
        head,encoded=src.split(',',1)
        if ';base64' not in head:raise ValueError('素材须为base64数据或相对路径')
        return base64.b64decode(encoded,validate=True)
    return inside(root,src).read_bytes()

def media_refs(p):
    for s in p.get('scenes',[]):
        a=s.get('audio')
        if a and a.get('src'):yield a,'src','audio'
        for l in s.get('layers',[]):
            if l.get('type')=='image' and l.get('src'):yield l,'src','image'
            if l.get('type')=='clip':
                if l.get('src'):yield l,'src','video'
                for frame in l.get('frames',[]):yield frame,'src','image'

def pack(p,root):
    q=copy.deepcopy(p)
    for owner,key,kind in media_refs(q):
        src=owner[key]
        if not src.startswith('data:'):
            mime=mimetypes.guess_type(src)[0]
            if not mime or not mime.startswith(MEDIA_TYPES[kind][0]):mime={'audio':'audio/wav','image':'image/png','video':'video/mp4'}[kind]
            owner[key]='data:'+mime+';base64,'+base64.b64encode(bytes_for(root,src)).decode()
    return q

def materialize(p,root):
    q=copy.deepcopy(p)
    for owner,key,kind in media_refs(q):
        src=owner[key]
        if src.startswith('data:'):
            mime=src[5:src.index(';')]
            if not mime.startswith(MEDIA_TYPES[kind][0]):raise ValueError('素材类型不匹配：'+kind)
            data=bytes_for(root,src);ext={'audio/wav':'.wav','audio/x-wav':'.wav','image/png':'.png','image/jpeg':'.jpg','video/mp4':'.mp4'}.get(mime) or mimetypes.guess_extension(mime) or '.bin'
            rel=MEDIA_TYPES[kind][1]+'/'+sha(data)[:20]+ext
            path=inside(root,rel);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data);owner[key]=rel
        else:inside(root,src)
    return q

def audio_valid(s,p):
    a=s.get('audio') or {}
    return bool(a.get('src') and a.get('signature')==signature(s.get('narration',''),p.get('voice',{})) and a.get('text')==s.get('narration'))

def fit_duration(s):
    s['duration']=round(float(s.get('leadIn',.22))+float((s.get('audio') or {}).get('duration',0))+float(s.get('gapAfter',.5)),4)

def settings(root):
    return merged_settings(root)

def tool(name,root=None):
    config=settings(root)
    requested=os.environ.get('KTV_'+name.upper()) or config.get(name)
    if requested:
        p=Path(requested).expanduser()
        if not p.is_file():raise RuntimeError(name+'配置路径不存在：'+str(p))
        return str(p.resolve())
    found=shutil.which(name)
    if found:return found
    if name=='ffmpeg':
        try:
            import imageio_ffmpeg
            return imageio_ffmpeg.get_ffmpeg_exe()
        except ImportError:pass
    raise RuntimeError('缺少'+name+'；请安装或在runtime.settings.json配置其路径')

def probe(path,root=None):
    try:ffprobe=tool('ffprobe',root)
    except RuntimeError:ffprobe=None
    if ffprobe:return json.loads(subprocess.check_output([ffprobe,'-v','error','-show_streams','-show_format','-of','json',str(path)],text=True))
    # Strict fallback for ordinary encoded lesson videos, never fabricate unavailable fields.
    result=subprocess.run([tool('ffmpeg',root),'-hide_banner','-nostdin','-i',str(path)],capture_output=True,text=True)
    text=result.stderr;duration=re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)',text)
    if not duration:raise ValueError('FFmpeg无法探测媒体时长；请安装ffprobe进行完整探测')
    h,m,sec=map(float,duration.groups());streams=[]
    for line in text.splitlines():
        v=re.search(r'Video: (\w+)',line);a=re.search(r'Audio: (\w+)',line)
        if v:
            size=re.search(r'(\d{2,5})x(\d{2,5})',line);fps=re.search(r'(\d+(?:\.\d+)?) fps',line)
            streams.append({'codec_type':'video','codec_name':v[1],'width':int(size[1]) if size else None,'height':int(size[2]) if size else None,'avg_frame_rate':fps[1] if fps else None})
        if a:
            sr=re.search(r'(\d+) Hz',line);streams.append({'codec_type':'audio','codec_name':a[1],'sample_rate':sr[1] if sr else None,'channels':2 if 'stereo' in line else 1 if 'mono' in line else None})
    return {'streams':streams,'format':{'duration':h*3600+m*60+sec},'probeMethod':'ffmpeg-text-fallback'}

def validate(p,root,require_audio=False):
    errors=[]
    if p.get('schemaVersion')!=SCHEMA_VERSION:errors.append('不支持的工程版本；使用project.py migrate迁移')
    for key in ['title','voice','scenes','canvas']:
        if key not in p:errors.append('缺少字段：'+key)
    scenes=p.get('scenes',[])
    if not 1<=len(scenes)<=200:errors.append('分镜数量须为1–200')
    ids=set();seconds=0
    def number(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)
    for dim in ['width','height','fps']:
        v=p.get('canvas',{}).get(dim)
        if not number(v) or v<=0 or v>(120 if dim=='fps' else 8192) or (dim!='fps' and (int(v)!=v or v%2)):errors.append('画幅宽高须为偶数正整数，帧率须大于零：'+dim)
    for s in scenes:
        sid=s.get('id','')
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,64}',sid) or sid in ids:errors.append('镜头ID重复或无效：'+sid)
        ids.add(sid)
        if not isinstance(s.get('narration'),str) or not s.get('narration','').strip():errors.append(sid+'旁白为空')
        for field in ['duration','leadIn','gapAfter']:
            v=s.get(field)
            if not number(v) or v<0 or (field=='duration' and v<=0) or (field!='duration' and v>1):errors.append(sid+'时长/停顿无效：'+field)
        if number(s.get('duration')):seconds+=s['duration']
        if require_audio and not audio_valid(s,p):errors.append(sid+'配音缺失或已失效')
        if s.get('audio'):
            a=s['audio'];d=a.get('duration')
            if not number(d) or d<=0:errors.append(sid+'音频时长无效')
            elif number(s.get('duration')) and s['duration']+.001<float(s.get('leadIn',0))+d+float(s.get('gapAfter',0)):errors.append(sid+'镜头短于音频与停顿之和')
        lids=set()
        for l in s.get('layers',[]):
            lid=l.get('id')
            if not isinstance(lid,str) or not lid or lid in lids:errors.append(sid+'图层ID重复或缺失')
            lids.add(lid)
            if l.get('type') not in ['text','shape','image','clip']:errors.append(sid+'不支持图层类型')
            for key in ['x','y','width','height','scale','rotation','opacity']:
                if key in l and not number(l[key]):errors.append(sid+'图层数值无效：'+key)
            if l.get('type')=='clip' and not l.get('frames'):errors.append(sid+'视频须先提取预览帧')
            previous=-1
            for k in l.get('keyframes',[]):
                if not number(k.get('at')) or k['at']<previous:errors.append(sid+'关键帧时间应有序')
                previous=k.get('at',previous)
    if seconds>3600:errors.append('当前运行器支持每支视频最多一小时，请拆分知识点')
    try:
        for owner,key,kind in media_refs(p):
            src=owner[key];raw=bytes_for(root,src)
            if not raw:errors.append('素材为空：'+src[:80])
            if kind=='audio' and owner.get('sha256') and owner['sha256']!=sha(raw):errors.append('音频指纹不一致')
    except (ValueError,OSError,KeyError) as e:errors.append(str(e))
    return errors
