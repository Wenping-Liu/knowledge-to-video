"""Generate a Breeze audition or run the project's existing voice pipeline."""
import argparse,getpass,os,sys,json,hashlib
from pathlib import Path

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project');ap.add_argument('--scene');ap.add_argument('--text-file');ap.add_argument('--voice-id');ap.add_argument('--out');ap.add_argument('--prompt-key',action='store_true');ap.add_argument('--instruction',default='温和清晰地讲课，开场从容，句间自然停顿，提问带一点好奇。')
    a=ap.parse_args()
    from lib.environment import bootstrap_cli
    bootstrap_cli(Path(a.project).resolve().parent if a.project else Path.cwd())
    if not a.project and not all([a.text_file,a.voice_id,a.out]):ap.error('试听需要--text-file、--voice-id和--out；工程生成使用--project')
    if a.project:
        from lib.project_data import read
        if read(a.project).get('voice',{}).get('backend')!='breeze':ap.error('请先将工程voice.backend设为breeze；本命令不擅自切换声音')
    if a.prompt_key:
        if not sys.stdin.isatty():ap.error('请在终端隐藏输入密钥')
        print('将发送当前讲稿及表达指令到Breeze，并使用账号额度；本次不自动重试。',flush=True)
        os.environ['BREEZE_API_KEY']=getpass.getpass('Breeze API Key（隐藏输入）：').strip()
        os.environ['KTV_ALLOW_CLOUD_TTS']='1'
    try:
        if a.project:
            from voice import generate_project
            generate_project(a.project,a.scene)
        else:
            from lib.breeze_voice import breeze_audio
            from voice import normalize,bind_audio
            text=Path(a.text_file).read_text().strip();out=Path(a.out).resolve()
            if out.exists():raise ValueError('输出已存在，请试听已有文件或指定新路径，避免重复调用')
            v={'backend':'breeze','speaker':a.voice_id,'modelFamily':'BreezeBlue-TTS','languageCode':'zh','instruction':a.instruction,'guidanceScale':1,'speed':1}
            raw=breeze_audio(text,v);out.parent.mkdir(parents=True,exist_ok=True)
            # Preserve successful generation even if postprocessing later fails.
            out.with_suffix('.raw.wav').write_bytes(raw)
            raw=normalize(raw,out.parent);result=bind_audio(raw,text,v,{'provider':'BreezeBlue','type':'cloud-tts','voiceId':a.voice_id})
            out.write_bytes(raw);result.pop('src');result['voice']=v
            out.with_suffix('.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
            print('生成完成：'+str(out)+f"（{result['duration']:.2f}秒）",flush=True)
    finally:
        if a.prompt_key:os.environ.pop('BREEZE_API_KEY',None);os.environ.pop('KTV_ALLOW_CLOUD_TTS',None)
if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e) if isinstance(e,(ValueError,RuntimeError)) else type(e).__name__+'；执行失败，请检查运行环境',file=sys.stderr);sys.exit(1)
