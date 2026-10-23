"""One-time local setup: isolated Python, render tools, optional Serena model, real smoke test."""
import argparse,datetime,importlib.util,json,os,platform,shutil,subprocess,sys,time,uuid,venv
from pathlib import Path
from lib.environment import runtime_home,merged_settings
from lib.model_assets import MODELS,check_model
from lib.project_data import read,write

SKILL=Path(__file__).resolve().parents[1]

def select_backend(requested,system=None,machine=None):
    system=system or platform.system();machine=(machine or platform.machine()).lower()
    apple=system=='Darwin' and machine in ['arm64','aarch64']
    if requested=='auto':return 'mlx' if apple else 'qwen'
    if requested=='mlx' and not apple:raise ValueError('MLX需要原生Apple Silicon环境。请选择 --voice qwen 或 --voice none。')
    return requested

def python_version(executable):
    raw=subprocess.check_output([str(executable),'-c','import json,sys;print(json.dumps(list(sys.version_info[:2])))'],text=True,timeout=30)
    return tuple(json.loads(raw.strip()))

def find_python(requested=None,allow_download=False):
    candidates=[]
    if requested:
        p=shutil.which(requested) or str(Path(requested).expanduser().absolute());candidates=[p]
    else:
        p=shutil.which('python3.12')
        if p:candidates.append(p)
        if os.name=='nt' and shutil.which('py'):
            r=subprocess.run(['py','-3.12','-c','import sys;print(sys.executable)'],capture_output=True,text=True)
            if r.returncode==0:candidates.append(r.stdout.strip())
        uv=shutil.which('uv')
        if uv:
            r=subprocess.run([uv,'python','find','--offline','3.12'],capture_output=True,text=True)
            if r.returncode==0:candidates.append(r.stdout.strip())
        if (3,10)<=sys.version_info[:2]<(3,14):candidates.append(sys.executable)
    for p in candidates:
        try:
            if (3,10)<=python_version(p)<(3,14):return str(Path(p).absolute())
        except (OSError,ValueError,subprocess.SubprocessError):pass
    if not requested and allow_download and shutil.which('uv'):
        subprocess.run([shutil.which('uv'),'python','install','3.12'],check=True)
        return find_python(''+subprocess.check_output([shutil.which('uv'),'python','find','--offline','3.12'],text=True).strip())
    raise RuntimeError('需要Python 3.10–3.13，推荐3.12。请安装Python 3.12或uv后重试，或加 --python 指定已有解释器。系统Python保持原样。')

def build_plan(args):
    backend=select_backend(args.voice);home=Path(args.home).expanduser().absolute() if args.home else runtime_home()
    return {'action':'plan','runtimeHome':str(home),'voice':backend,'environment':'复用指定解释器，不安装包' if args.use_python else '在缓存目录创建隔离环境，不修改系统Python','python':'优先Python 3.12，可用uv准备用户级Python','packages':['requirements/render.txt']+([] if backend=='none' else ['requirements/voice-'+backend+'.txt']),'browser':'复用指定Chromium' if args.chromium_path else '准备Playwright Chromium','model':None if backend=='none' else {**MODELS[backend],'localPath':args.model_path or os.environ.get('KTV_MODEL'),'download':'优先复用已有模型；缺少时从Hugging Face下载并缓存'},'verification':'跳过实际试制，仅检查配置' if args.skip_smoke else ('渲染测试音样片' if backend=='none' else '真实Serena配音并导出有声MP4')}

def execute(args):
    plan=build_plan(args);print(json.dumps(plan,ensure_ascii=False,indent=2),flush=True)
    if not args.yes or args.plan:
        print('这里只显示安装计划。开始安装：python3 scripts/setup.py --yes',flush=True);return plan
    home=Path(plan['runtimeHome']);home.mkdir(parents=True,exist_ok=True);os.environ['KTV_HOME']=str(home)
    if os.environ.get('KTV_SETTINGS'):raise RuntimeError('安装时请先取消KTV_SETTINGS；安装器只写入当前KTV_HOME，验证阶段自行使用临时配置。')
    lock=home/'setup.lock';lock_fd=None;log=None;candidate=None
    try:
        try:lock_fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(lock_fd,str(os.getpid()).encode())
        except FileExistsError:raise RuntimeError('已有安装锁：'+str(lock)+'。请先确认另一个安装已结束；中断残留时再删除该锁重试。')
        log=(home/'setup.log').open('a',encoding='utf-8');log.write('\n=== '+datetime.datetime.now().isoformat()+' ===\n')
        env=os.environ.copy();env['KTV_HOME']=str(home);env.pop('KTV_MODEL',None);env.pop('KTV_CHROMIUM',None);env.pop('KTV_PYTHON',None)
        def run(command,extra_env=None):
            command=[str(x) for x in command];print('执行：'+' '.join(command),flush=True);log.write(' '.join(command)+'\n');log.flush()
            e=env.copy();e.update(extra_env or {})
            with subprocess.Popen(command,cwd=SKILL,env=e,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1) as proc:
                for line in proc.stdout:print(line.rstrip(),flush=True);log.write(line);log.flush()
                code=proc.wait()
            if code:raise RuntimeError('安装步骤失败，退出码 '+str(code)+'；可重跑同一命令继续。日志：'+str(home/'setup.log'))
        def json_call(executable,code,values=(),extra_env=None,live=False):
            marker='KTV_JSON_RESULT:';e=env.copy();e.update(extra_env or {})
            command=[str(executable),'-c',code,*map(str,values)]
            if live:
                output=[]
                with subprocess.Popen(command,env=e,cwd=SKILL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1) as proc:
                    for line in proc.stdout:
                        output.append(line);log.write(line);log.flush()
                        if not line.startswith(marker):print(line.rstrip(),flush=True)
                    if proc.wait():raise RuntimeError('模型下载未完成；保留缓存，请重跑。详情：'+str(home/'setup.log'))
                stdout=''.join(output)
            else:
                r=subprocess.run(command,env=e,cwd=SKILL,capture_output=True,text=True,encoding='utf-8',errors='replace')
                log.write(r.stdout+'\n'+r.stderr+'\n');log.flush()
                if r.returncode:raise RuntimeError((r.stderr or r.stdout)[-2400:]+'\n详情：'+str(home/'setup.log'))
                stdout=r.stdout
            line=next((s[len(marker):] for s in reversed(stdout.splitlines()) if s.startswith(marker)),None)
            if line is None:raise RuntimeError('安装子步骤没有返回有效结果')
            return json.loads(line)
        backend=plan['voice'];old=merged_settings(None)
        if args.use_python:
            py=Path(args.use_python).expanduser().absolute()
            if not py.is_file():raise ValueError('--use-python路径不存在')
            if not (3,10)<=python_version(py)<(3,14):raise ValueError('复用环境需要Python 3.10–3.13')
        else:
            base=find_python(args.python,True);folder=home/('venv-'+backend);py=folder/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
            installer=shutil.which('uv') if args.installer in ['auto','uv'] else None
            if args.installer=='uv' and not installer:raise RuntimeError('未找到uv，请安装或使用 --installer pip')
            if not py.exists():
                if installer:run([installer,'venv','--python',base,str(folder)])
                else:run([base,'-m','venv',str(folder)])
            if python_version(py)!=python_version(base):raise RuntimeError('缓存环境Python版本与所选解释器不同，请指定匹配的--python，或使用新的--home')
            requirements=[SKILL/'requirements/render.txt']+([] if backend=='none' else [SKILL/('requirements/voice-'+backend+'.txt')])
            for req in requirements:
                if not req.is_file():raise RuntimeError('安装包缺少依赖清单：'+str(req))
                if installer:run([installer,'pip','install','--python',str(py),'-r',str(req)])
                else:run([str(py),'-m','pip','install','-r',str(req)])
        # imageio-ffmpeg wheel supplies FFmpeg on supported platforms.
        probes=json_call(py,"import json,shutil,imageio_ffmpeg;print('KTV_JSON_RESULT:'+json.dumps({'ffmpeg':shutil.which('ffmpeg') or imageio_ffmpeg.get_ffmpeg_exe(),'ffprobe':shutil.which('ffprobe') or ''}))")
        browser_override=args.chromium_path or (old.get('chromium') if old.get('chromium') and Path(old['chromium']).is_file() else None)
        if browser_override:
            chromium=Path(browser_override).expanduser().absolute()
            if not chromium.is_file():raise RuntimeError('Chromium路径不存在')
        else:
            env['PLAYWRIGHT_BROWSERS_PATH']=str(home/'browsers')
            browser_path=json_call(py,"import json;from playwright.sync_api import sync_playwright\nwith sync_playwright() as p:print('KTV_JSON_RESULT:'+json.dumps(p.chromium.executable_path))")
            chromium=Path(browser_path)
            if not chromium.is_file():run([py,'-m','playwright','install','chromium'])
        model='';model_source=None
        if backend!='none':
            explicit=args.model_path or os.environ.get('KTV_MODEL');previous=old.get('modelPath') if old.get('voiceBackend')==backend and not args.model_revision else None
            if explicit:
                model=str(Path(explicit).expanduser().absolute());errors=check_model(model,backend)
                if errors:raise RuntimeError('指定模型未通过完整性检查：'+'; '.join(errors))
                model_source={'type':'user-local','backend':backend}
            elif previous and not check_model(previous,backend):model=previous;model_source=old.get('modelSource',{'type':'existing-local','backend':backend})
            else:
                target=home/'models'/MODELS[backend]['repo'].split('/')[-1];model=str(target)
                if args.model_revision or check_model(target,backend):
                    print('首次准备Serena模型：'+MODELS[backend]['approximateDownload']+'；原文件与下载缓存会保留，可重跑继续。',flush=True)
                    result=json_call(py,"import json,sys;from huggingface_hub import HfApi,snapshot_download\nrepo,dest,revision=sys.argv[1:];info=HfApi(token=False).model_info(repo,revision=revision or None);path=snapshot_download(repo_id=repo,revision=info.sha,local_dir=dest,token=False);print('KTV_JSON_RESULT:'+json.dumps({'path':path,'repo':repo,'revision':info.sha}))",[MODELS[backend]['repo'],target,args.model_revision or ''],live=True)
                    model=result['path'];model_source={'type':'huggingface-download','repo':result['repo'],'revision':result['revision'],'license':MODELS[backend]['license']}
                else:model_source={'type':'existing-managed-cache','repo':MODELS[backend]['repo']}
                errors=check_model(model,backend)
                if errors:raise RuntimeError('下载后模型不完整：'+'; '.join(errors))
        device='cpu';dtype='float32'
        if backend=='qwen':
            hardware=json_call(py,"import json,torch;print('KTV_JSON_RESULT:'+json.dumps({'cuda':torch.cuda.is_available()}))")
            device='cuda:0' if hardware['cuda'] else 'cpu';dtype='float16' if hardware['cuda'] else 'float32'
            if device=='cpu':print('当前使用CPU生成Serena，可能较慢；可用 --voice none 导入现成配音，或复用已配置CUDA的环境。',flush=True)
        cfg={**old,'python':str(py),'ffmpeg':probes['ffmpeg'],'ffprobe':probes['ffprobe'],'chromium':str(chromium),'modelPath':str(model),'voiceBackend':backend if backend!='none' else select_backend('auto'),'voiceEnabled':backend!='none','device':device,'dtype':dtype,'modelSource':model_source,'setupVersion':'1.1.0'}
        candidate=home/('settings-candidate-'+uuid.uuid4().hex+'.json');write(candidate,cfg);verify_env={'KTV_SETTINGS':str(candidate),'KTV_ACTIVE_PYTHON':str(py)}
        doctor_file=home/'doctor-last.json';run([py,SKILL/'scripts/doctor.py','--verify-browser','--check','--out',doctor_file],verify_env)
        smoke_result=None
        if not args.skip_smoke:
            smoke_dir=home/'checks'/('setup-'+uuid.uuid4().hex[:10]);command=[py,SKILL/'scripts/smoke_test.py','--out',smoke_dir]
            if backend=='none':command.append('--render-only')
            run(command,verify_env);smoke_result=read(smoke_dir/'smoke-check.json')
        write(home/'runtime.settings.json',cfg)
        result={'status':'verified' if smoke_result else 'configured-not-smoke-tested','runtimeHome':str(home),'settingsFile':str(home/'runtime.settings.json'),'python':str(py),'voice':backend,'modelSource':model_source,'doctor':read(doctor_file),'smoke':smoke_result,'note':'后续python3 scripts/doctor.py等入口会自动使用已配置环境；模型和运行库仅在本机缓存。'}
        write(home/'setup-report.json',result);print(json.dumps({k:v for k,v in result.items() if k not in ['doctor','smoke']},ensure_ascii=False,indent=2),flush=True)
        if args.home:print('使用了自定义缓存；后续命令请保持 KTV_HOME='+str(home),flush=True)
        if smoke_result:print('请打开验证样片：'+smoke_result['video'],flush=True)
        return result
    except Exception as e:
        write(home/'setup-last-error.json',{'error':str(e),'time':datetime.datetime.now().isoformat(),'note':'保留已有模型和环境，不删除课程；修复后重跑同一命令。'})
        raise
    finally:
        if candidate and candidate.exists():candidate.unlink()
        if log:log.close()
        if lock_fd is not None:os.close(lock_fd);lock.unlink(missing_ok=True)

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--yes',action='store_true',help='安装/下载并默认生成验证样片');ap.add_argument('--plan',action='store_true',help='只显示计划，不写文件或下载');ap.add_argument('--voice',choices=['auto','mlx','qwen','none'],default='auto');ap.add_argument('--home',help='本机缓存目录，可用KTV_HOME固定后续命令的发现位置');ap.add_argument('--python',help='创建隔离环境的Python 3.10–3.13，推荐3.12');ap.add_argument('--use-python',help='只采用已有完整环境，不向其中安装包');ap.add_argument('--model-path',help='复用本地模型，省去下载');ap.add_argument('--model-revision',help='固定Hugging Face模型提交');ap.add_argument('--chromium-path',help='复用已有Chromium');ap.add_argument('--installer',choices=['auto','uv','pip'],default='auto');ap.add_argument('--skip-smoke',action='store_true',help='显式跳过实际生成，仅检查配置，报告会标注');args=ap.parse_args()
    try:execute(args)
    except Exception as e:ap.exit(1,'安装未完成：'+str(e)+'\n')
