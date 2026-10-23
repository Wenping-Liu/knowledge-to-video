"""Read-only checks with actionable installation hints; reuses the managed interpreter."""
import argparse,importlib.util,importlib.metadata,json,os,platform,sys
from pathlib import Path
from lib.project_data import tool,settings
from lib.environment import runtime_home,settings_file,bootstrap_cli
from lib.model_assets import check_model

def diagnose(root=None,verify_browser=False):
    cfg=settings(root);result={'python':sys.version.split()[0],'executable':sys.executable,'platform':platform.platform(),'settingsFile':str(settings_file()),'runtimeHome':str(runtime_home()),'pathFallbacks':cfg.get('pathFallbacks',[]),'tools':{},'modules':{},'voice':{},'renderReady':False}
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
    result['tools']['chromium']={'path':chrom,'exists':bool(chrom and Path(chrom).is_file()),'launchVerified':False}
    browser_error=None
    if verify_browser and result['tools']['chromium']['exists']:
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                b=pw.chromium.launch(executable_path=chrom);page=b.new_page();page.set_content('<canvas></canvas>');page.screenshot();b.close()
            result['tools']['chromium']['launchVerified']=True
        except Exception as e:browser_error=str(e);result['tools']['chromium']['launchError']=browser_error
    model=os.environ.get('KTV_MODEL') or cfg.get('modelPath','');backend=cfg.get('voiceBackend') or ('mlx' if platform.system()=='Darwin' and platform.machine().lower() in ['arm64','aarch64'] else 'qwen')
    model_errors=check_model(model,backend)
    result['voice']={'requested':cfg.get('voiceEnabled',True),'modelConfigured':bool(model),'modelFilesReady':not model_errors,'modelErrors':model_errors,'backend':backend,'moduleReady':result['modules'].get({'mlx':'mlx_audio','qwen':'qwen_tts'}.get(backend,''),False),'speaker':'Serena','runtimeLoadVerified':False}
    result['versions']={}
    for distribution in ['playwright','imageio-ffmpeg','mlx-audio','numpy','torch','qwen-tts','huggingface-hub']:
        try:result['versions'][distribution]=importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:pass
    result['renderReady']=isinstance(result['tools']['ffmpeg'],str) and result['modules']['playwright'] and result['tools']['chromium']['exists'] and not browser_error
    result['voiceReady']=result['voice']['moduleReady'] and result['modules']['numpy'] and not model_errors
    result['configurationReady']=result['renderReady'] and (not result['voice']['requested'] or result['voiceReady'])
    setup=Path(__file__).resolve().parent/'setup.py'
    result['nextSteps']=[] if result['configurationReady'] else ['运行：python3 "'+str(setup)+'" --yes','已有模型可加 --model-path "本地模型目录"；暂不生成配音可加 --voice none']
    result['note']='缺少ffprobe不影响基础出片，使用FFmpeg探测回退。配置就绪仍需实际配音/成片验证；首次安装默认会执行该验证。'
    return result
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project');ap.add_argument('--out');ap.add_argument('--verify-browser',action='store_true');ap.add_argument('--check',action='store_true',help='配置未就绪时返回非零');a=ap.parse_args()
    try:
        root=Path(a.project).resolve().parent if a.project else None;bootstrap_cli(root);r=diagnose(root,a.verify_browser);raw=json.dumps(r,ensure_ascii=False,indent=2);print(raw)
        if a.out:Path(a.out).write_text(raw,encoding='utf-8')
        if a.check and not r['configurationReady']:ap.exit(1)
    except Exception as e:ap.exit(1,str(e)+'\n')
