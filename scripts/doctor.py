"""Read-only runtime detection. No downloads, installation, private-directory scans or uploads."""
import argparse,importlib.util,importlib.metadata,json,os,platform,sys
from pathlib import Path
from lib.project_data import tool,settings

def diagnose(root=None):
    cfg=settings(root) if root else {};result={'python':sys.version.split()[0],'executable':sys.executable,'platform':platform.platform(),'tools':{},'modules':{},'voice':{},'renderReady':False}
    for name in ['ffmpeg','ffprobe']:
        try:result['tools'][name]=tool(name,root)
        except RuntimeError as e:result['tools'][name]={'missing':str(e)}
    for name in ['playwright','numpy','mlx_audio','qwen_tts','jsonschema']:
        try:result['modules'][name]=importlib.util.find_spec(name) is not None
        except (ImportError,ValueError):result['modules'][name]=False
    chrom=os.environ.get('KTV_CHROMIUM') or cfg.get('chromium')
    if not chrom and result['modules']['playwright']:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:chrom=pw.chromium.executable_path
    result['tools']['chromium']={'path':chrom,'exists':bool(chrom and Path(chrom).is_file())}
    model=os.environ.get('KTV_MODEL') or cfg.get('modelPath','');backend=cfg.get('voiceBackend','mlx')
    result['voice']={'modelConfigured':bool(model),'configExists':bool(model and (Path(model).expanduser()/'config.json').is_file()),'backend':backend,'moduleReady':result['modules'].get({'mlx':'mlx_audio','qwen':'qwen_tts'}.get(backend,''),False),'speaker':'Serena','runtimeLoadVerified':False}
    result['versions']={}
    for distribution in ['playwright','imageio-ffmpeg','mlx-audio','numpy','torch','qwen-tts']:
        try:result['versions'][distribution]=importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:pass
    result['renderReady']=isinstance(result['tools']['ffmpeg'],str) and result['modules']['playwright'] and result['tools']['chromium']['exists']
    result['note']='路径与模块存在仅表示预检查；模型实际生成、浏览器启动和成片需另行验证。'
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project');ap.add_argument('--out');a=ap.parse_args();r=diagnose(Path(a.project).resolve().parent if a.project else None);raw=json.dumps(r,ensure_ascii=False,indent=2);print(raw)
    if a.out:Path(a.out).write_text(raw,encoding='utf-8')
