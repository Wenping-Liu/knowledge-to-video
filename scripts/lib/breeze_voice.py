"""Breeze sync TTS. Fixed official host, explicit opt-in, no automatic paid retries."""
import json,math,os,re,ssl,urllib.request,urllib.error

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None

def breeze_config():
    return {'enabled':os.environ.get('KTV_ALLOW_CLOUD_TTS')=='1','keyConfigured':bool(os.environ.get('BREEZE_API_KEY','').strip())}

def breeze_audio(text,voice,opener=None):
    cfg=breeze_config()
    if not cfg['enabled']:raise ValueError('Breeze会发送本镜旁白和表达指令；确认后设置KTV_ALLOW_CLOUD_TTS=1')
    if not cfg['keyConfigured']:raise ValueError('请通过终端隐藏输入或本机环境设置BREEZE_API_KEY；不要写入工程')
    speaker=voice.get('speaker','')
    if not re.fullmatch(r'voc_[A-Za-z0-9]{6,80}',speaker):raise ValueError('Breeze需要有效的voc_开头Voice ID')
    if not text.strip() or len(text)>1000:raise ValueError('Breeze每镜旁白须为1—1000字，请按完整意思拆镜')
    instruction=voice.get('instruction','').strip()
    if len(instruction)>1000:raise ValueError('Breeze表达指令最多1000字')
    guidance=float(voice.get('guidanceScale',1))
    if not math.isfinite(guidance) or not 1<=guidance<=10:raise ValueError('guidanceScale应为1—10')
    language=voice.get('languageCode','zh')
    if not re.fullmatch('[a-zA-Z]{2}',language):raise ValueError('languageCode应为两字母语言码')
    body={'text':text,'language_code':language,'instructions':instruction,'voice_settings':{'guidance_scale':guidance}}
    if voice.get('modelId'):body['model_id']=voice['modelId']
    url='https://api.breeze.blue/v1/text-to-speech/'+speaker+'?output_format=wav&delivery=sync'
    req=urllib.request.Request(url,data=json.dumps(body,ensure_ascii=False).encode(),headers={'xi-api-key':os.environ['BREEZE_API_KEY'],'Content-Type':'application/json','User-Agent':'knowledge-to-video'},method='POST')
    if opener is None:
        ctx=ssl.create_default_context()
        if os.path.isfile('/etc/ssl/cert.pem'):ctx.load_verify_locations('/etc/ssl/cert.pem')
        opener=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),NoRedirect()).open
    try:
        with opener(req,timeout=180) as res:
            status=res.status;raw=res.read(30*1024*1024+1)
    except urllib.error.HTTPError as e:raise RuntimeError(f'Breeze HTTP {e.code}；核对密钥、声音权限、额度或参数。未自动重试；未输出服务端响应。') from None
    except (urllib.error.URLError,TimeoutError):raise RuntimeError('Breeze网络失败或超时；先检查平台历史是否已生成，避免重复计费') from None
    finally:req.headers.clear()
    if status!=200 or len(raw)>30*1024*1024 or not(raw.startswith(b'RIFF') and raw[8:12]==b'WAVE'):raise ValueError('Breeze未返回预期的同步WAV音频，没有绑定旧声音')
    return raw
