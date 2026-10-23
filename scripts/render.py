"""Render the project's exact Canvas function and current valid narration into H.264/AAC."""
import argparse,array,base64,functools,http.server,json,math,os,subprocess,tempfile,threading,wave
from pathlib import Path
from lib.project_data import read,write,validate,tool,pack,bytes_for,fingerprint,sha,settings
from lib.timeline import timeline,slug

def browser_path(root):return os.environ.get('KTV_CHROMIUM') or settings(root).get('chromium') or None

def render(path,out=None,height=None,fps=None,progress=lambda m:print(m,flush=True)):
    path=Path(path).resolve();root=path.parent;p=read(path);errors=validate(p,root,True)
    if errors:raise ValueError('\n'.join(errors))
    destination=Path(out).resolve() if out else root.parent/(slug(p['title'])+'.mp4');destination.parent.mkdir(parents=True,exist_ok=True)
    from playwright.sync_api import sync_playwright
    q=pack(p,root);width=p['canvas']['width'];native_height=p['canvas']['height'];height=height or native_height;output_width=round(width*height/native_height/2)*2
    fps=fps or p['canvas']['fps'];duration=sum(s['duration'] for s in p['scenes']);nframes=math.ceil(duration*fps);duration=nframes/fps
    refs=root.parent/'剪映素材/分镜画面参考';refs.mkdir(parents=True,exist_ok=True)
    ff=tool('ffmpeg',root);renderer=(root/'动画代码/renderer.js').read_text(encoding='utf-8')
    report={};encoder=None
    with tempfile.TemporaryDirectory(prefix='ktv-render-') as td:
        td=Path(td);html='<!doctype html><meta charset="utf-8"><canvas id="c"></canvas><script>'+renderer+'\nconst P='+json.dumps(q,ensure_ascii=False).replace('<','\\u003c')+';KTVRenderer.preload(P).then(()=>window.ready=true);window.draw=t=>{KTVRenderer.render(document.getElementById("c"),P,t);return document.getElementById("c").toDataURL("image/png").split(",")[1]};</script>'
        (td/'render.html').write_text(html,encoding='utf-8')
        class Quiet(http.server.SimpleHTTPRequestHandler):
            def log_message(self,*a):pass
        server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Quiet,directory=str(td)));threading.Thread(target=server.serve_forever,daemon=True).start()
        silent=td/'silent.mp4';log=td/'encoder.log'
        try:
            with log.open('wb') as err:
                encoder=subprocess.Popen([ff,'-v','error','-nostdin','-y','-f','image2pipe','-vcodec','png','-framerate',str(fps),'-i','-','-an','-vf',f'scale={output_width}:{height}','-c:v','libx264','-preset','veryfast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)],stdin=subprocess.PIPE,stderr=err)
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(executable_path=browser_path(root),args=['--disable-dev-shm-usage']);page=browser.new_page(viewport={'width':width,'height':native_height});page_errors=[];page.on('pageerror',lambda e:page_errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/render.html');page.wait_for_function('window.ready===true',timeout=120000)
                    for i in range(nframes):
                        encoded=page.evaluate('t=>window.draw(t)',i/fps);encoder.stdin.write(base64.b64decode(encoded))
                        if i%max(1,int(fps*3))==0:progress(f'画面 {i}/{nframes} 帧')
                    for j,s,start in timeline(p):
                        image=page.evaluate('t=>window.draw(t)',start+min(s['duration']/2,s['leadIn']+1));(refs/f'{j+1:03}-{slug(s["title"])}.png').write_bytes(base64.b64decode(image))
                    browser.close()
                    if page_errors:raise RuntimeError('页面错误：'+';'.join(page_errors))
                encoder.stdin.close()
                if encoder.wait():raise RuntimeError(log.read_text()[-2000:])
        finally:
            if encoder and encoder.poll() is None:encoder.kill();encoder.wait()
            server.shutdown();server.server_close()
        sr=24000;mix=array.array('h',[0])*round(duration*sr)
        for i,s,start in timeline(p):
            media=td/(s['id']+'.audio');media.write_bytes(bytes_for(root,s['audio']['src']))
            raw=subprocess.check_output([ff,'-v','error','-nostdin','-i',str(media),'-f','s16le','-ar',str(sr),'-ac','1','-'])
            samples=array.array('h');samples.frombytes(raw)
            if os.sys.byteorder!='little':samples.byteswap()
            expected=round(s['audio']['duration']*sr)
            if abs(len(samples)-expected)>sr*.1:raise ValueError('实际音频时长与工程不一致：'+s['id'])
            begin=round((start+s['leadIn'])*sr);count=min(len(samples),expected,len(mix)-begin);mix[begin:begin+count]=samples[:count]
        wav=td/'narration.wav'
        with wave.open(str(wav),'wb') as w:
            w.setparams((1,2,sr,0,'NONE','not compressed'))
            if os.sys.byteorder!='little':mix.byteswap()
            w.writeframes(mix.tobytes())
        result=subprocess.run([ff,'-hide_banner','-nostdin','-i',str(wav),'-af','loudnorm=I=-16:TP=-2:LRA=11:print_format=json','-f','null','-'],capture_output=True,text=True,check=True).stderr
        stats=json.loads(result[result.rfind('{'):result.rfind('}')+1])
        if stats['input_i']=='-inf':raise ValueError('完整旁白只有静音')
        loud='loudnorm=I=-16:TP=-2:LRA=11:linear=true:measured_I='+stats['input_i']+':measured_TP='+stats['input_tp']+':measured_LRA='+stats['input_lra']+':measured_thresh='+stats['input_thresh']+':offset='+stats['target_offset']
        rendered=td/'final.mp4';subprocess.run([ff,'-v','error','-nostdin','-y','-i',str(silent),'-i',str(wav),'-map','0:v','-map','1:a','-c:v','copy','-c:a','aac','-b:a','320k','-ar','48000','-af',loud,'-t',str(duration),'-movflags','+faststart',str(rendered)],check=True)
        # Validate the encoded result, not just the source WAV.
        from validate import check_video
        report=check_video(rendered,root,duration)
        if report['errors']:raise RuntimeError('; '.join(report['errors']))
        os.replace(rendered,destination)
    record={'projectFingerprint':fingerprint(p),'file':str(destination.relative_to(root.parent)) if destination.is_relative_to(root.parent) else str(destination),'sha256':sha(destination.read_bytes()),'duration':duration,'width':output_width,'height':height,'fps':fps,'technical':report,'visualAndListeningReview':'pending'}
    write(root.parent/'资料与来源/渲染记录.json',record);progress('有声MP4已生成：'+str(destination));return destination
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--out');ap.add_argument('--height',type=int);ap.add_argument('--fps',type=float);a=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(a.project).resolve().parent)
    try:render(a.project,a.out,a.height,a.fps)
    except Exception as e:ap.exit(1,str(e)+'\n')
