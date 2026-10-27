"""Create and render a tiny verification lesson, optionally with real Serena. No course files changed."""
import argparse,array,base64,io,json,math,sys,uuid,wave
from pathlib import Path
from lib.environment import bootstrap_cli,runtime_home
from lib.project_data import read,write,settings,materialize
from project import create
from voice import generate_project,bind_audio
from render import render
from package import package
from validate import report

def smoke(out=None,voice=True):
    folder=Path(out).resolve() if out else runtime_home()/'checks'/('smoke-'+uuid.uuid4().hex[:10])
    path=create(folder,'安装验证样片');p=read(path);p.pop('teaching',None);p['canvas']={'width':960,'height':540,'fps':12};s=p['scenes'][0]
    s.update(leadIn=.22,gapAfter=.5,title='安装验证',narration='大家好，我是曦曦。现在可以开始制作知识点讲解视频了。',duration=8)
    s['layers']=[{'id':'heading','type':'text','text':'安装验证 · 画面与声音','fontSize':46,'fill':'#171717','x':70,'y':60,'width':820,'height':100,'scale':1,'visible':True},{'id':'track','type':'shape','shape':'rect','x':80,'y':230,'width':800,'height':100,'scale':1,'visible':True,'fill':'#FFCE45','dots':True},{'id':'moving','type':'shape','shape':'circle','x':100,'y':245,'width':70,'height':70,'scale':1,'visible':True,'fill':'#F07846','keyframes':[{'at':0,'x':100},{'at':4,'x':780}]},{'id':'note','type':'text','text':'Serena 本地配音验证' if voice else '渲染测试音 · 尚未启用自动配音','fontSize':26,'fill':'#171717','x':80,'y':410,'width':800,'height':70,'scale':1,'visible':True}]
    p['sources']=[{'id':'self-check','title':'安装器生成的功能验证样例，非教材课程'}];p['coverage']=[{'sourceId':'self-check','purpose':'只验证动画、配音和有声MP4导出'}];s['sourceIds']=['self-check'];write(path,p)
    if voice:generate_project(path)
    else:
        sr=24000;buffer=io.BytesIO();pcm=array.array('h',(round(2400*math.sin(2*math.pi*440*i/sr)) for i in range(sr*2)))
        with wave.open(buffer,'wb') as w:w.setparams((1,2,sr,0,'NONE','not compressed'));w.writeframes(pcm.tobytes())
        s['audio']=bind_audio(buffer.getvalue(),s['narration'],p['voice'],{'type':'synthetic-test-tone','notSerena':True});s['duration']=2.72;write(path,materialize(p,path.parent))
    movie=render(path);package(path,movie);r=report(path,delivery=True)
    result={'status':'pass' if not r['errors'] else 'fail','realSerena':voice,'video':str(movie),'project':str(path),'checks':r,'subjectiveListening':'请打开样片试听；技术检查不评价自然度'}
    write(folder/'smoke-check.json',result)
    if r['errors']:raise RuntimeError('; '.join(r['errors']))
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out');ap.add_argument('--render-only',action='store_true');a=ap.parse_args()
    try:bootstrap_cli();print(json.dumps(smoke(a.out,not a.render_only),ensure_ascii=False,indent=2))
    except Exception as e:ap.exit(1,str(e)+'\n')
