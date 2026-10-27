"""Opt-in Azure Speech adapter. Credentials are read only from the local environment."""
import os,re,urllib.request,urllib.error
from xml.sax.saxutils import escape,quoteattr

def azure_config():
    region=os.environ.get('AZURE_SPEECH_REGION','')
    key=os.environ.get('AZURE_SPEECH_KEY','')
    allowed=os.environ.get('KTV_ALLOW_CLOUD_TTS')=='1'
    return {'enabled':allowed,'keyConfigured':bool(key),'regionConfigured':bool(re.fullmatch('[a-z0-9-]{2,40}',region))}

def azure_audio(text,voice,opener=None):
    cfg=azure_config()
    if not cfg['enabled']:raise ValueError('Azure会发送当前旁白文字到微软；确认后设置KTV_ALLOW_CLOUD_TTS=1，再生成配音')
    if not cfg['keyConfigured'] or not cfg['regionConfigured']:raise ValueError('请在本机设置AZURE_SPEECH_KEY和AZURE_SPEECH_REGION；密钥不写入工程或HTML')
    speaker=voice.get('speaker','zh-CN-XiaoxiaoNeural')
    if not re.fullmatch('[A-Za-z0-9-]{3,100}',speaker):raise ValueError('Azure声音名称格式无效')
    ssml='<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN"><voice name='+quoteattr(speaker)+'>'+escape(text)+'</voice></speak>'
    url='https://'+os.environ['AZURE_SPEECH_REGION']+'.tts.speech.microsoft.com/cognitiveservices/v1'
    req=urllib.request.Request(url,data=ssml.encode(),headers={'Ocp-Apim-Subscription-Key':os.environ['AZURE_SPEECH_KEY'],'Content-Type':'application/ssml+xml','X-Microsoft-OutputFormat':'riff-24khz-16bit-mono-pcm','User-Agent':'knowledge-to-video'},method='POST')
    try:
        with (opener or urllib.request.urlopen)(req,timeout=60) as res:raw=res.read()
    except urllib.error.HTTPError as e:raise RuntimeError('Azure配音失败，HTTP '+str(e.code)+'；请核对区域、额度与声音名称') from None
    except urllib.error.URLError:raise RuntimeError('无法连接Azure语音服务；请检查本机网络后重试') from None
    if not raw.startswith(b'RIFF'):raise ValueError('Azure未返回预期WAV音频；没有绑定旧声音')
    return raw
