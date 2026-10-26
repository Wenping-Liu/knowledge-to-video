"""Run isolated, observable regression checks. Optional browser/video/real Serena tests."""
import argparse,array,base64,copy,functools,http.server,io,json,math,os,shutil,subprocess,sys,threading,time,urllib.request,urllib.error,uuid,wave
from pathlib import Path
SKILL=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SKILL/'scripts'))
from lib.environment import bootstrap_cli
from project import create
from package import build_html,package
from lib.project_data import read,write,validate,materialize,pack,signature,bytes_for,fingerprint,sha,tool
from lib.timeline import srt
from voice import bind_audio,generate_project
from serve import make_server
from render import render,browser_path
from validate import report
from lib.media_paths import ingest

def tone(duration=2,frequency=440):
    sr=24000;stream=io.BytesIO();samples=array.array('h',(round(2500*math.sin(2*math.pi*frequency*i/sr)) for i in range(round(sr*duration))))
    with wave.open(stream,'wb') as w:w.setparams((1,2,sr,0,'NONE','not compressed'));w.writeframes(samples.tobytes())
    return stream.getvalue()

def main(a):
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True);run=out/('run-'+uuid.uuid4().hex[:8]);run.mkdir();checks=[]
    def check(name,fn):
        try:
            r=fn();checks.append({'name':name,'status':'pass','detail':r});write(run/'checks.json',{'checks':checks,'passed':sum(x['status']=='pass' for x in checks),'failed':sum(x['status']=='fail' for x in checks),'status':'running'})
        except Exception as e:
            checks.append({'name':name,'status':'fail','error':str(e)});write(run/'checks.json',{'checks':checks,'passed':sum(x['status']=='pass' for x in checks),'failed':1,'status':'fail'});raise
    path=create(run/'01-电路示例','电路中的电流（功能测试）');root=path.parent;p=read(path);p.pop('teaching',None)
    p['canvas']={'width':960,'height':540,'fps':12};p['scenes'][0].update(title='电荷移动',narration='电流表示电荷的定向移动。')
    p['scenes'][0]['layers']=[{'id':'wire','type':'shape','shape':'rect','x':60,'y':220,'width':840,'height':90,'scale':1,'visible':True,'fill':'#FFCE45','dots':True},{'id':'charge','type':'shape','shape':'circle','x':100,'y':230,'width':70,'height':70,'scale':1,'visible':True,'fill':'#F07846','keyframes':[{'at':0,'x':100},{'at':2.72,'x':750}]},{'id':'label','type':'text','text':'电荷沿导线定向移动','x':80,'y':70,'width':800,'height':100,'scale':1,'fontSize':42,'fill':'#171717','visible':True}]
    p['scenes'].append(copy.deepcopy(p['scenes'][0]));p['scenes'][1].update(id='s02',title='比喻的边界',narration='水流帮助理解流动，电荷沿电路移动。')
    p['sources']=[{'id':'fixture','title':'功能测试自建示例，待正式教材审定','license':'test-only'}];p['coverage']=[{'sourceId':'fixture','scenes':['s01','s02'],'note':'仅验证功能，不作为学生课程交付'}]
    for i,s in enumerate(p['scenes']):
        s['leadIn']=.22;s['gapAfter']=.5;s['sourceIds']=['fixture'];s['audio']=bind_audio(tone(2,440+i*110),s['narration'],p['voice'],{'type':'synthetic-test-tone','notSerena':True});s['duration']=2.72
    p=materialize(p,root);write(path,p);build_html(path)
    check('valid current audio',lambda:assert_empty(validate(p,root,True)))
    check('materialize-pack audio MIME roundtrip',lambda:assert_true(all(s['audio']['src'].startswith('data:audio/') for s in pack(p,root)['scenes'])))
    check('signature integers canonical',lambda:assert_equal(signature('例子',{'speed':1.0}),signature('例子',{'speed':1})))
    q=copy.deepcopy(p);q['scenes'][0]['narration']='已改文稿'
    check('edited narration invalidates audio',lambda:assert_true(any('失效' in x for x in validate(q,root,True))))
    q=copy.deepcopy(p);q['voice']['temperature']=.8
    check('changed voice invalidates audio',lambda:assert_true(any('失效' in x for x in validate(q,root,True))))
    q=copy.deepcopy(p);q['scenes'][1]['id']='s01'
    check('duplicate IDs rejected',lambda:assert_true(any('ID' in x for x in validate(q,root))))
    q=copy.deepcopy(p);q['scenes'][0]['audio']['src']='../secret.wav'
    check('path traversal rejected',lambda:assert_true(any('越出' in x for x in validate(q,root))))
    q=copy.deepcopy(p);q['scenes'][0]['audio']['src']='配音/missing.wav'
    check('missing media rejected',lambda:assert_true(bool(validate(q,root))))
    q=copy.deepcopy(p);q['scenes'][0]['audio']['sha256']='bad'
    check('changed bytes detected',lambda:assert_true(any('指纹' in x for x in validate(q,root))))
    q=copy.deepcopy(p);q['scenes'][0]['duration']=1
    check('short scene rejected',lambda:assert_true(any('短于' in x for x in validate(q,root,True))))
    check('SRT uses audio interval and sequence',lambda:assert_true('00:00:00,220 --> 00:00:02,220' in srt(p) and '\n2\n' in srt(p)))
    q=copy.deepcopy(p);q['scenes'][0]['audio']['cues']=[{'start':0,'end':4,'text':'超出'}]
    check('invalid subtitle cues rejected',lambda:assert_raises(lambda:srt(q),ValueError))
    import struct,zlib
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    pixels=bytearray()
    for y in range(160):
        pixels.append(0)
        for x in range(160):
            d=((x-80)**2+(y-80)**2)**.5
            pixels.extend((23,23,23,255) if 65<d<72 else (240,120,70,255) if d<=65 else (255,255,255,0))
    image=run/'fixture.png';image.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',160,160,8,6,0,0,0))+chunk(b'IDAT',zlib.compress(pixels))+chunk(b'IEND',b''))
    server=make_server(path);threading.Thread(target=server.serve_forever,daemon=True).start();url=f'http://127.0.0.1:{server.server_port}';token=server.ktv_token
    def request(endpoint,body=None,auth=True,origin=None):
        headers={'X-KTV-Token':token} if auth else {}
        if origin:headers['Origin']=origin
        if body is not None:headers['Content-Type']='application/json'
        req=urllib.request.Request(url+endpoint,data=json.dumps(body).encode() if body is not None else None,headers=headers)
        with urllib.request.urlopen(req) as r:return json.loads(r.read())
    check('service token enforced',lambda:assert_raises(lambda:request('/api/health',auth=False),urllib.error.HTTPError))
    check('foreign Origin rejected',lambda:assert_raises(lambda:request('/api/health',origin='https://example.invalid'),urllib.error.HTTPError))
    check('authenticated health',lambda:assert_equal(request('/api/health')['status'],'ready'))
    if a.browser or a.video:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=browser_path(root),args=['--autoplay-policy=no-user-gesture-required']);page=browser.new_page(accept_downloads=True,viewport={'width':1440,'height':1100});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(server.ktv_url);page.wait_for_function('!!window.KTVEditor')
            check('browser agrees audio signature',lambda:assert_true(page.evaluate('KTVEditor.getProject().scenes.every(KTVEditor.valid)')))
            page.locator('#direction').fill('定义稍慢，强调电荷');page.wait_for_function('!KTVEditor.valid(KTVEditor.getProject().scenes[0])')
            check('scene delivery edit invalidates old voice in UI',lambda:assert_true(not page.evaluate('KTVEditor.valid(KTVEditor.getProject().scenes[0])')))
            page.locator('#direction').fill('');page.wait_for_function('KTVEditor.valid(KTVEditor.getProject().scenes[0])')
            with page.expect_download() as d:page.locator('#saveSVG').click()
            svg=run/'editable-scene.svg';d.value.save_as(svg)
            import xml.etree.ElementTree as ET
            svg_root=ET.fromstring(svg.read_text())
            check('SVG retains editable text and named object groups',lambda:assert_true(svg_root.tag.endswith('svg') and any(e.attrib.get('id')=='charge' for e in svg_root.iter()) and any(e.tag.endswith('text') for e in svg_root.iter())))
            native=page.evaluate('''()=>{const p=KTVEditor.getProject(),src='data:image/svg+xml;base64,'+btoa('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><defs><pattern id="dot" width="10" height="10" patternUnits="userSpaceOnUse"><circle r="1"/></pattern></defs><g id="body"><rect width="90" height="90" fill="url(#dot)"/></g></svg>');p.scenes[0].layers=[{id:'a',type:'image',src,x:0,y:0,width:100,height:100},{id:'b',type:'image',src,x:200,y:0,width:100,height:100}];return KTVRenderer.toSVG(p,0)}''')
            native_root=ET.fromstring(native);ids=[e.attrib['id'] for e in native_root.iter() if 'id' in e.attrib]
            check('SVG sources retain nested vector groups with unique IDs',lambda:assert_true(len(ids)==len(set(ids)) and sum(e.tag.endswith('rect') for e in native_root.iter())>=2 and not any(e.tag.endswith('image') for e in native_root.iter())))
            page.screenshot(path=str(run/'editor-preview.png'),full_page=True)
            page.locator('#narration').fill('电荷定向移动形成电流。');page.wait_for_timeout(100)
            check('UI edit stops stale audio',lambda:assert_true(page.evaluate('!KTVEditor.valid(KTVEditor.getProject().scenes[0])')))
            # Real async file import begins on scene 1, then select scene 2 before completion.
            wav=run/'import.wav';wav.write_bytes(tone(1.5,660));page.locator('#audioFile').set_input_files(str(wav));page.evaluate('KTVEditor.select(1)');page.wait_for_function('KTVEditor.getProject().scenes[0].audio.provenance.type==="user-import"')
            check('async import binds original scene',lambda:assert_equal(page.evaluate('KTVEditor.getProject().scenes[1].audio.provenance.type'),'synthetic-test-tone'))
            page.locator('#imageFile').set_input_files(str(image));page.wait_for_timeout(250)
            check('image added',lambda:assert_true(page.evaluate('KTVEditor.getProject().scenes[1].layers.some(l=>l.type==="image")')))
            page.locator('#layer').select_option('3')
            for key,value in [('x','750'),('y','350'),('width','120'),('height','120')]:page.locator('#'+key).fill(value);page.locator('#'+key).dispatch_event('change')
            # Deterministic mocked job transport exercises actual UI async guards without calling a second voice service.
            mock=page.evaluate('KTVEditor.getProject().scenes.find(s=>s.id==="s02").audio');mock['provenance']={'type':'mock-async-job','notRealTTS':True}
            page.route('**/api/voice',lambda route:route.fulfill(json={'id':'mockvoice'}))
            page.route('**/api/jobs/mockvoice',lambda route:route.fulfill(json={'status':'done','result':mock}))
            page.evaluate('KTVEditor.select(1)');page.locator('#generate').click();page.evaluate('KTVEditor.select(0)')
            page.wait_for_function('KTVEditor.getProject().scenes.find(s=>s.id==="s02").audio.provenance.type==="mock-async-job"')
            check('async TTS binds original scene',lambda:assert_equal(page.evaluate('KTVEditor.getProject().scenes.find(s=>s.id==="s01").audio.provenance.type'),'user-import'))
            page.evaluate('KTVEditor.select(1)');page.locator('#generate').click();page.locator('#narration').fill('生成期间修改文稿');page.wait_for_timeout(1000)
            check('stale TTS response rejected after text edit',lambda:assert_true('未绑定' in page.locator('#status').text_content() and not page.evaluate('KTVEditor.valid(KTVEditor.getProject().scenes[1])')))
            page.locator('#narration').fill(mock['text']);page.wait_for_timeout(100);page.unroute('**/api/voice');page.unroute('**/api/jobs/mockvoice')
            page.evaluate('KTVEditor.select(0)');page.locator('#layer').select_option('1');page.locator('#x').fill('300');page.locator('#x').dispatch_event('change')
            check('moving animated layer shifts its keyframes',lambda:assert_equal(page.evaluate('KTVEditor.getProject().scenes[0].layers[1].keyframes[0].x'),300))
            page.locator('#x').fill('100');page.locator('#x').dispatch_event('change');page.locator('#layer').select_option('2');page.locator('#layerText').fill('电荷定向移动 → 电流')
            page.evaluate('KTVEditor.select(1)')
            page.locator('#down').click();page.locator('#up').click()
            with page.expect_download() as d:page.locator('#saveProject').click()
            saved=run/'saved-project.json';d.value.save_as(saved);q=read(saved)
            check('JSON snapshot embeds audio/images',lambda:assert_true(all(s['audio']['src'].startswith('data:') for s in q['scenes']) and next(s for s in q['scenes'] if s['id']=='s02')['layers'][-1]['src'].startswith('data:')))
            with page.expect_download() as d:page.locator('#saveHTML').click()
            html=run/'saved-editor.html';d.value.save_as(html)
            second=browser.new_page();second.goto(html.as_uri());second.wait_for_function('!!window.KTVEditor')
            check('saved HTML restores current narration and media',lambda:assert_equal(second.evaluate('KTVEditor.getProject().scenes.find(s=>s.id==="s01").narration'),'电荷定向移动形成电流。'))
            check('saved HTML excludes session token',lambda:assert_true(token not in html.read_text()))
            page.locator('#loadProject').set_input_files(str(saved));page.wait_for_timeout(200)
            page.locator('#play').click();page.wait_for_timeout(650);page.locator('#stop').click();check('actual playback advances timeline',lambda:assert_true(float(page.locator('#timeline').input_value())>.1))
            page.locator('#saveLocal').click();page.wait_for_function('document.getElementById("status").textContent.startsWith("已保存：") || document.getElementById("status").classList.contains("error")');check('local save response',lambda:assert_true(page.locator('#status').text_content().startswith('已保存：') or (_ for _ in []).throw(AssertionError(page.locator('#status').text_content()))))
            check('service saves edited project',lambda:assert_equal(next(s for s in read(path)['scenes'] if s['id']=='s01')['narration'],'电荷定向移动形成电流。'))
            if a.video:
                page.locator('#export').click();page.wait_for_function('document.getElementById("status").textContent.startsWith("已导出：") || document.getElementById("status").classList.contains("error")',timeout=120000)
                check('editor export button completes real voiced MP4 job',lambda:assert_true(page.locator('#status').text_content().startswith('已导出：') or (_ for _ in []).throw(AssertionError(page.locator('#status').text_content()))))
            with page.expect_download(timeout=30000) as d:page.locator('#webm').click()
            webm=run/'offline-with-audio.webm';d.value.save_as(webm)
            from lib.project_data import probe
            check('offline WebM has audio and video',lambda:assert_true({s['codec_type'] for s in probe(webm,root)['streams']}=={'audio','video'}))
            gated=read(saved);gated['teaching']={'version':1};gate_file=run/'pending-timing.json';write(gate_file,gated)
            page.locator('#loadProject').set_input_files(str(gate_file));page.wait_for_timeout(200)
            for button in ['export','webm']:
                page.locator('#'+button).click();page.wait_for_function('document.getElementById("status").classList.contains("error")')
                check(button+' rejects unresolved teaching timing in UI',lambda:assert_true('计时待校准' in page.locator('#status').text_content()))
            check('no browser errors',lambda:assert_empty(errors));page.screenshot(path=str(run/'editor-edited.png'),full_page=True);browser.close()
        p=read(path)
    server.shutdown();server.server_close()
    if a.video:
        clip=run/'source-clip.mp4';subprocess.run([tool('ffmpeg',root),'-v','error','-nostdin','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=12','-t','1','-c:v','libx264','-pix_fmt','yuv420p',str(clip)],check=True)
        media=ingest(root,str(clip),'video');p['scenes'][1]['layers'].append({'id':'clip','type':'clip',**media,'x':160,'y':350,'width':640,'height':160,'scale':1,'visible':True});write(path,p);build_html(path)
        check('video import retains original and frame sequence',lambda:assert_true(len(media['frames'])==12 and media['frameFps']==12 and (root/media['src']).exists()))
        target=render(path);package(path,target);r=report(path,delivery=True);write(run/'video-check.json',r)
        check('actual voiced MP4 and complete delivery',lambda:assert_empty(r['errors']))
        bad=copy.deepcopy(p);bad['teaching']={'version':1};write(path,bad)
        check('render blocks an incomplete teaching plan',lambda:assert_raises(lambda:render(path,progress=lambda m:None),ValueError))
        write(path,p)
        changed=copy.deepcopy(p);changed['revision']+=1;write(path,changed)
        check('old video rejected after saved project change',lambda:assert_true(any('旧工程' in x for x in report(path,delivery=True)['errors'])))
        write(path,p)
        # Preview/export image comparison at the same frame time after moving the whole lesson folder.
        moved=run/'moved-lesson';shutil.copytree(path.parent.parent,moved,ignore=shutil.ignore_patterns('__pycache__','*.pyc'));mp=moved/'可编辑工程/工程数据.json'
        check('moved project references exist',lambda:assert_empty(validate(read(mp),mp.parent,True)))
        proc=subprocess.run([sys.executable,str(mp.parent/'runtime/scripts/validate.py'),'--project',str(mp),'--delivery'],capture_output=True,text=True)
        check('copied runtime validates without original skill',lambda:assert_equal(proc.returncode,0))
        target2=render(mp,progress=lambda m:None);check('moved project renders',lambda:assert_true(target2.exists()))
        # Single-frame native preview and encoded frame compared with FFmpeg psnr (compression allowed).
        preview=run/'reference.png';encoded=run/'encoded.png'
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            b=pw.chromium.launch(executable_path=browser_path(root));page=b.new_page();page.goto((root/'编辑器.html').as_uri());page.wait_for_function('!!window.KTVEditor');raw=page.evaluate('()=>{KTVRenderer.render(document.getElementById("stage"),KTVEditor.getProject(),1);return document.getElementById("stage").toDataURL().split(",")[1]}');preview.write_bytes(base64.b64decode(raw));b.close()
        subprocess.run([tool('ffmpeg',root),'-v','error','-nostdin','-y','-ss','1','-i',str(target),'-frames:v','1',str(encoded)],check=True)
        result=subprocess.run([tool('ffmpeg',root),'-hide_banner','-nostdin','-i',str(preview),'-i',str(encoded),'-lavfi','psnr','-f','null','-'],capture_output=True,text=True,check=True)
        import re
        psnr=re.search(r'average:([\d.]+)',result.stderr)
        check('preview/export PSNR above 30dB',lambda:assert_true(psnr and float(psnr[1])>30))
        write(run/'preview-export-comparison.json',{'timeSeconds':1,'psnrDb':float(psnr[1]),'thresholdDb':30,'preview':'reference.png','encodedFrame':'encoded.png'})
    if a.serena:
        voice_out=run/'02-Serena真实生成';vp=create(voice_out,'Serena配音实测');q=read(vp);q.pop('teaching',None);q['scenes'][0].update(narration='大家好，我是曦曦。本节我们要来学习电流。',title='Serena课堂开场');write(vp,q);generate_project(vp);build_html(vp)
        check('actual Serena local generation',lambda:assert_empty(validate(read(vp),vp.parent,True)))
        if a.video:target=render(vp);package(vp,target);check('actual Serena voiced MP4',lambda:assert_empty(report(vp,delivery=True)['errors']))
    write(run/'checks.json',{'checks':checks,'passed':len(checks),'failed':0,'testAudio':'synthetic tones clearly labelled, plus real Serena only when --serena','subjectiveReview':'pending','platform':sys.platform});print(json.dumps({'output':str(run),'passed':len(checks)},ensure_ascii=False))
    return run

def assert_true(x):
    if not x:raise AssertionError('condition is false')
def assert_equal(a,b):
    if a!=b:raise AssertionError(f'{a!r} != {b!r}')
def assert_empty(x):
    if x:raise AssertionError(str(x))
def assert_raises(fn,cls):
    try:fn()
    except cls:return
    raise AssertionError('expected '+cls.__name__)
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',required=True);ap.add_argument('--browser',action='store_true');ap.add_argument('--video',action='store_true');ap.add_argument('--serena',action='store_true');a=ap.parse_args();bootstrap_cli();main(a)
