"""Deterministic video import: original + frame sequence, no autoplay dependency."""
import base64, mimetypes, shutil, subprocess
from pathlib import Path
from .project_data import inside, sha, tool, bytes_for

def ingest(root, source, kind, fps=8):
    raw=bytes_for(root,source) if source.startswith('data:') else Path(source).read_bytes()
    mime=source[5:source.index(';')] if source.startswith('data:') else mimetypes.guess_type(source)[0]
    if not mime or not mime.startswith(kind+'/'):raise ValueError('请选择匹配的本地素材')
    ext=mimetypes.guess_extension(mime) or '.bin';folder={'video':'案例视频','image':'图片','audio':'配音'}[kind]
    rel=folder+'/'+sha(raw)[:20]+ext;dest=inside(root,rel);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    result={'src':rel}
    if kind=='video':
        frames=dest.parent/(dest.stem+'-frames');frames.mkdir(exist_ok=True)
        subprocess.run([tool('ffmpeg',root),'-v','error','-nostdin','-y','-i',str(dest),'-t','30','-vf',f'fps={fps},scale=960:-2','-q:v','3',str(frames/'%04d.jpg')],check=True)
        files=sorted(frames.glob('*.jpg'))
        if not files:raise ValueError('短片没有可解码的视频帧')
        result.update(frameFps=fps,frames=[{'src':str(f.relative_to(root))} for f in files],loop=False)
    return result
