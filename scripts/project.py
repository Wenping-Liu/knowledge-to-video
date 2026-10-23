"""Create independent lesson folders; import media or migrate legacy data without overwriting originals."""
import argparse,copy,json,os,shutil,sys
from pathlib import Path
from lib.project_data import read,write,pack,materialize,settings
from lib.media_paths import ingest

SKILL=Path(__file__).resolve().parents[1]

def install_runtime(root):
    root=Path(root);runtime=root/'runtime';runtime.mkdir(exist_ok=True)
    shutil.copytree(SKILL/'scripts',runtime/'scripts',dirs_exist_ok=True,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    shutil.copytree(SKILL/'assets',runtime/'assets',dirs_exist_ok=True)
    if (SKILL/'requirements').is_dir():shutil.copytree(SKILL/'requirements',runtime/'requirements',dirs_exist_ok=True)
    (runtime/'requirements.txt').write_text('-r requirements/render.txt\n# Voice: requirements/voice-mlx.txt or requirements/voice-qwen.txt\n',encoding='utf-8')
    shutil.copytree(SKILL/'assets/editor-template',root/'动画代码',dirs_exist_ok=True)

def create(out,title,profile=None):
    out=Path(out).resolve()
    if out.exists():raise ValueError('目标目录已存在，请选择新目录，避免覆盖已有工程')
    root=out/'可编辑工程';root.mkdir(parents=True)
    for folder in ['图片','案例视频','配音']:(root/folder).mkdir()
    for folder in ['剪映素材/分镜配音','剪映素材/分镜画面参考','资料与来源']:(out/folder).mkdir(parents=True)
    explicit_profile=profile is not None
    profile=read(profile or SKILL/'assets/profiles/xixi-comic-serena.json')
    cfg=settings(None)
    if not explicit_profile and cfg.get('voiceBackend') in ['mlx','qwen']:profile['voice']['backend']=cfg['voiceBackend']
    p={'schemaVersion':1,'title':title,'revision':1,'canvas':{'width':1280,'height':720,'fps':30},'profile':profile,'voice':profile['voice'],'approvals':{'sample':{'status':'pending','evidence':''}},'sources':[],'coverage':[],'review':{},'scenes':[{'id':'s01','title':'待编写的教学分镜','narration':'大家好，我是曦曦。本节我们要来学习，请填写本节知识点。','leadIn':profile['leadIn'],'gapAfter':profile['gapAfter'],'duration':8,'audio':None,'sourceIds':[],'layers':[{'id':'title','type':'text','text':title,'fontSize':54,'fill':'#171717','x':100,'y':70,'width':1080,'height':160,'scale':1,'visible':True},{'id':'object','type':'shape','shape':'rect','x':140,'y':320,'width':300,'height':220,'scale':1,'fill':'#FFCE45','dots':True,'visible':True,'keyframes':[{'at':0,'x':140},{'at':3,'x':760},{'at':6,'x':140}]}]}]}
    write(root/'工程数据.json',p);write(root/'runtime.settings.json',{k:cfg.get(k,'') for k in ['python','ffmpeg','ffprobe','chromium','modelPath','voiceBackend','device','dtype']})
    install_runtime(root)
    (out/'资料与来源/AI生成说明.txt').write_text('待制作：逐项记录实际生成的文字、图片、声音、模型、提示词和使用限制。\n',encoding='utf-8')
    from package import build_html,launchers
    build_html(root/'工程数据.json');launchers(out)
    template=(SKILL/'assets/delivery-templates/使用说明.template.txt').read_text(encoding='utf-8');(out/'使用说明.txt').write_text(template.replace('{{TITLE}}',title),encoding='utf-8')
    return root/'工程数据.json'

def migrate(source,out):
    source=Path(source).resolve();old=read(source);path=create(out,old.get('title','迁移课程'));root=path.parent;p=read(path)
    if old.get('schemaVersion')==1:
        p=materialize(pack(old,source.parent),root)
    else:
        p['scenes']=[]
        for i,s in enumerate(old['scenes']):
            layers=[]
            for j,l in enumerate(s.get('layers',[])):
                if l.get('type') in ['text','image']:
                    layer=copy.deepcopy(l);layer.setdefault('id',f'l{j:02}');layer.setdefault('width',900);layer.setdefault('height',300);layers.append(layer)
            p['scenes'].append({'id':s.get('id',f's{i+1:02}'),'title':s.get('title','迁移分镜'),'narration':s['narration'],'duration':s['duration'],'leadIn':s.get('leadIn',.22),'gapAfter':s.get('gapAfter',.5),'audio':None,'layers':layers,'sourceIds':[]})
        # Legacy custom graphics and audio signatures need explicit adaptation/rebinding.
        p=materialize(pack(p,source.parent),root);p['migrationNote']='仅迁移讲稿、时长和兼容图层；自定义绘图及音频需适配，未经画面一致性确认。'
    write(path,p)
    from package import build_html
    build_html(path);return path

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);sp=ap.add_subparsers(dest='action',required=True)
    a=sp.add_parser('init');a.add_argument('--out',required=True);a.add_argument('--title',required=True);a.add_argument('--profile')
    a=sp.add_parser('migrate');a.add_argument('--source',required=True);a.add_argument('--out',required=True)
    a=sp.add_parser('media');a.add_argument('--project',required=True);a.add_argument('--scene',required=True);a.add_argument('--layer',required=True);a.add_argument('--source',required=True);a.add_argument('--kind',choices=['image','video'],required=True)
    args=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(args.project).resolve().parent if args.action=='media' else None)
    try:
        if args.action=='init':print(create(args.out,args.title,args.profile))
        elif args.action=='migrate':print(migrate(args.source,args.out))
        else:
            path=Path(args.project).resolve();p=read(path);s=next(s for s in p['scenes'] if s['id']==args.scene);l=next((l for l in s['layers'] if l['id']==args.layer),None)
            if not l:l={'id':args.layer,'x':100,'y':150,'width':1080,'height':520,'scale':1,'visible':True};s['layers'].append(l)
            l.update(ingest(path.parent,args.source,args.kind),type='clip' if args.kind=='video' else 'image');p['revision']+=1;write(path,p);print(path)
    except Exception as e:ap.exit(1,str(e)+'\n')
