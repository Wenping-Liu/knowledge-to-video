"""Add an explicitly requested Xixi PNG layer; this is not automatic lip sync."""
import argparse,math
from pathlib import Path
from lib.project_data import read,write
from lib.media_paths import ingest
from package import build_html

def attach(path,image,scene_id=None,x=980,y=350,width=250,height=340):
    if any(not math.isfinite(v) for v in [x,y,width,height]) or width<=0 or height<=0:raise ValueError('角色位置须为有限数值，宽高须大于0')
    path=Path(path).resolve();p=read(path)
    if not Path(image).is_file():raise ValueError('请选择已有且获准使用的角色PNG')
    import struct
    raw=Path(image).read_bytes()
    if not raw.startswith(b'\x89PNG\r\n\x1a\n') or raw[25] not in [4,6]:raise ValueError('请使用带Alpha通道的PNG；不会自动抠图或生成口型')
    targets=[s for s in p['scenes'] if scene_id is None or s['id']==scene_id]
    if not targets:raise ValueError('找不到指定分镜')
    media=ingest(path.parent,str(Path(image).resolve()),'image')
    for s in targets:
        layer={'id':'xixi-avatar','type':'image',**media,'x':float(x),'y':float(y),'width':float(width),'height':float(height),'scale':1,'visible':True,'semanticRole':'decorative','motionPurpose':'layout','role':'optional-avatar'}
        s['layers']=[l for l in s['layers'] if l['id']!='xixi-avatar']+[layer]
    p.setdefault('profile',{})['characterEnabled']=True
    p['profile']['character']={'name':'曦曦','mode':'user-supplied-alpha-png','lipSync':False,'note':'角色图层不计作知识机制动画；须核对遮挡与素材许可'}
    p['revision']=p.get('revision',0)+1;write(path,p);build_html(path);return path
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--image',required=True);ap.add_argument('--scene');ap.add_argument('--x',type=float,default=980);ap.add_argument('--y',type=float,default=350);ap.add_argument('--width',type=float,default=250);ap.add_argument('--height',type=float,default=340);a=ap.parse_args()
    try:print(attach(a.project,a.image,a.scene,a.x,a.y,a.width,a.height))
    except Exception as e:ap.exit(1,str(e)+'\n')
