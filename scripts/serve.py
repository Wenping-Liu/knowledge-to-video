"""Token-protected loopback editor service. No arbitrary paths or shell commands in requests."""
import argparse,base64,copy,http.server,json,os,secrets,sys,threading,webbrowser
from pathlib import Path
from lib.project_data import read,write,validate,materialize,pack,settings
from package import build_html,package
from voice import synthesize
from render import render
from lib.media_paths import ingest

MAX_BODY=120*1024*1024

def make_server(project,port=0):
    project=Path(project).resolve();root=project.parent;token=secrets.token_urlsafe(32);jobs={};mutex=threading.Lock();jobs_lock=threading.Lock()
    def commit(p,require_audio=False):
        errors=validate(p,root,require_audio)
        if errors:raise ValueError('; '.join(errors))
        p=materialize(p,root);write(project,p);build_html(project);return p
    class Handler(http.server.BaseHTTPRequestHandler):
        def log_message(self,*a):pass
        def origin_allowed(self):
            origin=self.headers.get('Origin')
            return origin in (None,'null',f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}')
        def response_headers(self,code,kind):
            self.send_response(code);self.send_header('Content-Type',kind);self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
            if self.headers.get('Origin') and self.origin_allowed():self.send_header('Access-Control-Allow-Origin',self.headers['Origin'])
            self.end_headers()
        def send(self,data,code=200):
            raw=json.dumps(data,ensure_ascii=False,allow_nan=False).encode();self.response_headers(code,'application/json; charset=utf-8');self.wfile.write(raw)
        def authorized(self):
            return self.origin_allowed() and secrets.compare_digest(self.headers.get('X-KTV-Token',''),token)
        def do_OPTIONS(self):
            if not self.origin_allowed():self.send({'error':'不允许的来源'},403);return
            self.send_response(204);self.send_header('Access-Control-Allow-Origin',self.headers.get('Origin','null'));self.send_header('Access-Control-Allow-Headers','Content-Type,X-KTV-Token');self.send_header('Access-Control-Allow-Methods','POST,GET');self.end_headers()
        def do_GET(self):
            from urllib.parse import urlparse,parse_qs
            parts=urlparse(self.path)
            if parts.path=='/':
                if not secrets.compare_digest(parse_qs(parts.query).get('token',[''])[0],token):self.send({'error':'请使用启动器提供的带令牌地址'},403);return
                text=(root/'编辑器.html').read_text(encoding='utf-8');bootstrap='<script data-service-bootstrap>window.KTVService='+json.dumps({'url':f'http://127.0.0.1:{self.server.server_port}','token':token})+';</script>'
                text=text.replace('<script id="project-data"',bootstrap+'<script id="project-data"');self.response_headers(200,'text/html; charset=utf-8');self.wfile.write(text.encode());return
            if not self.authorized():self.send({'error':'本地服务令牌或来源无效'},403);return
            if parts.path=='/api/health':self.send({'status':'ready','version':1});return
            if parts.path.startswith('/api/jobs/'):
                with jobs_lock:r=copy.deepcopy(jobs.get(parts.path.rsplit('/',1)[-1],{'status':'error','error':'找不到任务'}))
                self.send(r);return
            self.send({'error':'没有此接口'},404)
        def do_POST(self):
            if not self.authorized():self.send({'error':'本地服务令牌或来源无效'},403);return
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0<length<=MAX_BODY:raise ValueError('请求大小超出限制，请压缩素材或使用CLI导入')
                data=json.loads(self.rfile.read(length));action=self.path.removeprefix('/api/')
                if action=='save':
                    if not mutex.acquire(False):self.send({'error':'正在处理任务，请完成后保存'},409);return
                    try:commit(data['project']);self.send({'path':str(project)})
                    finally:mutex.release()
                    return
                if action not in ['voice','media','export']:self.send({'error':'没有此接口'},404);return
                if not mutex.acquire(False):self.send({'error':'已有处理任务，请稍后重试'},409);return
                jid=secrets.token_hex(12)
                with jobs_lock:
                    if len(jobs)>20:
                        for old in list(jobs)[:-10]:del jobs[old]
                    jobs[jid]={'status':'running','message':'正在处理'+action}
                def worker():
                    try:
                        if action=='voice':result=synthesize(data['text'],data['voice'],root)
                        elif action=='media':
                            if data.get('kind')!='video' or not data.get('src','').startswith('data:video/'):raise ValueError('只接受本地视频数据')
                            media={'type':'clip',**ingest(root,data['src'],'video')};result=pack({'scenes':[{'layers':[media]}]},root)['scenes'][0]['layers'][0]
                        else:
                            commit(data['project'],True)
                            def progress(message):
                                with jobs_lock:jobs[jid]['message']=message
                            target=render(project,progress=progress);package(project,target);result={'path':str(target)}
                        with jobs_lock:jobs[jid]={'status':'done','result':result}
                    except Exception as e:
                        with jobs_lock:jobs[jid]={'status':'error','error':str(e)}
                    finally:mutex.release()
                threading.Thread(target=worker,daemon=True).start();self.send({'id':jid})
            except Exception as e:self.send({'error':str(e)},400)
    server=http.server.ThreadingHTTPServer(('127.0.0.1',port),Handler);server.daemon_threads=True
    server.ktv_token=token;server.ktv_url=f'http://127.0.0.1:{server.server_port}/?token={token}'
    return server

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--port',type=int,default=0);ap.add_argument('--open',action='store_true');a=ap.parse_args()
    path=Path(a.project).resolve();cfg=settings(path.parent);interpreter=os.environ.get('KTV_PYTHON') or cfg.get('python')
    if interpreter and not os.environ.get('KTV_REEXEC') and Path(interpreter).resolve()!=Path(sys.executable).resolve():
        if not Path(interpreter).is_file():ap.exit(1,'配置的Python路径不存在\n')
        os.environ['KTV_REEXEC']='1';os.execv(interpreter,[interpreter,str(Path(__file__).resolve()),*sys.argv[1:]])
    build_html(path);server=make_server(path,a.port);print('编辑器：'+server.ktv_url,flush=True)
    if a.open:webbrowser.open(server.ktv_url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()
