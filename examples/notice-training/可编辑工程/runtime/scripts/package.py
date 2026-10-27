"""Build current self-contained HTML and managed delivery, without deleting old or unique files."""
import argparse,base64,copy,json,os,shutil,subprocess,sys
from pathlib import Path
from lib.project_data import read,write,pack,materialize,validate,bytes_for,fingerprint,sha,tool,inside,render_fingerprint,content_fingerprint
from lib.timeline import srt,slug
SKILL=Path(__file__).resolve().parents[1]

def build_html(path):
    path=Path(path).resolve();root=path.parent;p=read(path);code=root/'动画代码';q=pack(p,root)
    shell=(code/'index.html').read_text(encoding='utf-8')
    for key,value in [('EDITOR_CSS',(code/'editor.css').read_text(encoding='utf-8')),('PROJECT_JSON',json.dumps(q,ensure_ascii=False).replace('<','\\u003c')),('RENDERER_JS',(code/'renderer.js').read_text(encoding='utf-8')),('EDITOR_JS',(code/'editor.js').read_text(encoding='utf-8'))]:shell=shell.replace('/* '+key+' */',value)
    out=root/'编辑器.html';out.write_text(shell,encoding='utf-8');return out

def launchers(out):
    out=Path(out)
    for system,name in [('macos','启动编辑器.command'),('windows','启动编辑器.cmd'),('linux','启动编辑器.sh')]:
        text=(SKILL/f'assets/delivery-templates/launchers/{system}.{dict(macos="command",windows="cmd",linux="sh")[system]}.template').read_text(encoding='utf-8')
        dest=out/name;dest.write_text(text,encoding='utf-8')
        if system!='windows':dest.chmod(0o755)

def package(path,video=None,preview720=False):
    path=Path(path).resolve();root=path.parent;out=root.parent;p=read(path);p=materialize(p,root);write(path,p)
    errors=validate(p,root,True)
    if errors:raise ValueError('\n'.join(errors))
    build_html(path);launchers(out)
    (out/'使用说明.txt').write_text((SKILL/'assets/delivery-templates/使用说明.template.txt').read_text(encoding='utf-8').replace('{{TITLE}}',p['title']),encoding='utf-8')
    dest=out/'剪映素材';dest.mkdir(exist_ok=True)
    for folder in ['分镜配音','分镜画面参考']:(dest/folder).mkdir(exist_ok=True)
    ff=tool('ffmpeg',root);spoken=[]
    for i,s in enumerate(p['scenes']):
        target=dest/f'分镜配音/{i+1:03}-{slug(s["title"])}.wav';data=bytes_for(root,s['audio']['src'])
        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.audio') as f:
            f.write(data);f.flush();subprocess.run([ff,'-v','error','-nostdin','-y','-i',f.name,'-ar','24000','-ac','1','-c:a','pcm_s16le',str(target)],check=True)
        spoken.append(f'{i+1:03} | {s["id"]} | {s["title"]}\n{s["narration"]}\n')
    (dest/'分镜旁白.txt').write_text('\n'.join(spoken),encoding='utf-8');(dest/'字幕.srt').write_text(srt(p),encoding='utf-8-sig')
    (dest/'分镜画面参考/说明.txt').write_text('这里是按镜头顺序编号的静态画面参考，不是动画视频本身。PNG供查看，SVG保留分组矢量图形和文字；导入的位图仍为位图。实际动画与语音锚点见成片及可编辑工程。\n',encoding='utf-8')
    main=out/(slug(p['title'])+'.mp4');record=out/'资料与来源/渲染记录.json';video_ready=False
    if video:
        source=Path(video).resolve()
        if not record.exists():raise ValueError('需先用render.py生成与当前工程对应的渲染记录')
        r=read(record)
        if r.get('projectFingerprint')!=content_fingerprint(p) or r.get('renderFingerprint')!=render_fingerprint(p,root) or r.get('sha256')!=sha(source.read_bytes()):raise ValueError('视频不属于当前工程版本，请重新渲染')
        if source!=main:shutil.copy2(source,main)
    if main.exists() and record.exists():
        r=read(record);video_ready=r.get('projectFingerprint')==content_fingerprint(p) and r.get('renderFingerprint')==render_fingerprint(p,root) and r.get('sha256')==sha(main.read_bytes())
    if video_ready:
        shutil.copy2(main,dest/'无旁白字幕版.mp4')
        if preview720:subprocess.run([ff,'-v','error','-nostdin','-y','-i',str(main),'-vf','scale=-2:720','-c:v','libx264','-preset','fast','-crf','23','-c:a','aac','-b:a','192k',str(dest/'无旁白字幕版-流畅播放720p.mp4')],check=True)
    data=out/'资料与来源';data.mkdir(exist_ok=True)
    write(data/'教材依据与覆盖.json',{'coverage':p.get('coverage',[]),'status':'recorded' if p.get('coverage') else 'pending'})
    write(data/'来源清单.json',{'sources':p.get('sources',[]),'status':'recorded' if p.get('sources') else 'pending'})
    write(data/'核验记录.json',{'review':p.get('review',{}),'note':'记录实际检查证据；缺失项待复核'})
    from validate import report
    write(data/'自动检查.json',report(path,True,False))
    from quality import inspect
    write(data/'教学与节奏检查.json',inspect(p,root,'final'))
    files=[]
    # Freeze actual files; runtime.settings.json may contain local paths, so never copy it to a public skill.
    for f in sorted(out.rglob('*')):
        if f.is_file() and f.name!='交付清单.json' and '__pycache__' not in f.parts and not f.name.endswith('.pyc'):
            inside(out,str(f.relative_to(out)));files.append({'path':str(f.relative_to(out)),'sha256':sha(f.read_bytes())})
    write(data/'交付清单.json',{'projectFingerprint':fingerprint(p),'videoReady':video_ready,'subtitleGranularity':'provided-cues' if all(s['audio'].get('cues') for s in p['scenes']) else 'scene-level fallback; refine if needed','files':files})
    return {'root':str(out),'videoReady':video_ready,'note':'请运行validate.py --delivery，并完成观看与试听'}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--video');ap.add_argument('--preview720',action='store_true');a=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(a.project).resolve().parent)
    try:print(json.dumps(package(a.project,a.video,a.preview720),ensure_ascii=False,indent=2))
    except Exception as e:ap.exit(1,str(e)+'\n')
