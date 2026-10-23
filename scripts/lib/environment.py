"""User-local runtime discovery. Installation is separate from Skill discovery."""
import json,os,platform,sys
from pathlib import Path

def runtime_home():
    if os.environ.get('KTV_HOME'):return Path(os.environ['KTV_HOME']).expanduser().absolute()
    if os.name=='nt':return Path(os.environ.get('LOCALAPPDATA',str(Path.home()/'AppData/Local')))/'knowledge-to-video'
    return Path.home()/'.cache/knowledge-to-video'

def settings_file():
    return Path(os.environ['KTV_SETTINGS']).expanduser() if os.environ.get('KTV_SETTINGS') else runtime_home()/'runtime.settings.json'

def merged_settings(root=None):
    result={};paths=[settings_file()]
    if root is not None:
        local=Path(root)/'runtime.settings.json'
        if local!=paths[0]:paths.append(local)
    for path in paths:
        if path.is_file():
            data=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(data,dict):raise ValueError('运行配置须为JSON对象：'+str(path))
            for key,value in data.items():
                if value is None or value=='':continue
                # Moved projects may still contain the author's absolute paths. Reuse a valid
                # local installation where it is compatible, while preserving explicit env overrides.
                if key in ['python','ffmpeg','ffprobe','chromium','modelPath'] and path!=paths[0]:
                    previous=result.get(key)
                    compatible=key!='modelPath' or data.get('voiceBackend',result.get('voiceBackend'))==result.get('voiceBackend')
                    if isinstance(value,str) and not Path(value).expanduser().exists() and previous and Path(previous).expanduser().exists() and compatible:
                        result.setdefault('pathFallbacks',[]).append({'field':key,'reason':'工程路径在本机不存在，使用已安装的本机配置'})
                        continue
                result[key]=value
    return result

def bootstrap_cli(root=None):
    """Use configured venv even if its python symlink points at the same base executable."""
    target=os.environ.get('KTV_PYTHON') or merged_settings(root).get('python')
    if not target or os.environ.get('KTV_NO_REEXEC')=='1':return
    target=str(Path(target).expanduser().absolute())
    current=os.path.normcase(os.path.abspath(sys.executable))
    if os.path.normcase(target)==current or os.environ.get('KTV_ACTIVE_PYTHON')==target:return
    if not Path(target).is_file():raise RuntimeError('已配置的Python不存在；请重新运行 scripts/setup.py --yes：'+target)
    os.environ['KTV_ACTIVE_PYTHON']=target
    os.execv(target,[target,str(Path(sys.argv[0]).absolute()),*sys.argv[1:]])
