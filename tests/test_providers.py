import io,os,sys,tempfile,unittest,wave,struct,zlib
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.cloud_voice import azure_audio,azure_config
from lib.project_data import audio_valid,signature
from voice import synthesize
class Providers(unittest.TestCase):
 def test_azure_opt_in_required_without_network(self):
  with patch.dict(os.environ,{},clear=True):
   with self.assertRaisesRegex(ValueError,'确认'):azure_audio('test',{},opener=lambda *a,**k:self.fail('network'))
 def test_credentials_and_region_required(self):
  with patch.dict(os.environ,{'KTV_ALLOW_CLOUD_TTS':'1','AZURE_SPEECH_KEY':'fake-test','AZURE_SPEECH_REGION':'bad.host'},clear=True):
   with self.assertRaisesRegex(ValueError,'本机'):azure_audio('test',{})
 def test_ssml_escapes_text_and_uses_official_endpoint(self):
  seen=[]
  class R:
   def __enter__(self):return self
   def __exit__(self,*a):pass
   def read(self):return b'RIFFtest-fixture'
  def fake(req,timeout):seen.append(req);self.assertEqual(timeout,60);return R()
  with patch.dict(os.environ,{'KTV_ALLOW_CLOUD_TTS':'1','AZURE_SPEECH_KEY':'fake-key','AZURE_SPEECH_REGION':'eastasia'},clear=True):raw=azure_audio('水<冰 & 文字',{},fake)
  self.assertEqual(raw,b'RIFFtest-fixture');self.assertIn('&lt;',seen[0].data.decode());self.assertIn('&amp;',seen[0].data.decode());self.assertEqual(seen[0].full_url,'https://eastasia.tts.speech.microsoft.com/cognitiveservices/v1');self.assertNotIn(b'fake-key',seen[0].data)
 def test_external_voice_is_import_only(self):
  with self.assertRaisesRegex(ValueError,'导入'):synthesize('当前文稿',{'backend':'import'},None)
 def test_cloud_error_does_not_echo_secret(self):
  from urllib.error import HTTPError
  def fake(*a,**k):raise HTTPError('https://x',401,'contains-secret',None,None)
  with patch.dict(os.environ,{'KTV_ALLOW_CLOUD_TTS':'1','AZURE_SPEECH_KEY':'secret-value','AZURE_SPEECH_REGION':'eastasia'},clear=True):
   with self.assertRaisesRegex(RuntimeError,'401') as c:azure_audio('test',{},fake)
  self.assertNotIn('secret',str(c.exception))
 def test_provider_switch_invalidates_audio(self):
  from lib.project_data import effective_voice
  p={'voice':{'backend':'mlx','speaker':'Serena'}};s={'narration':'讲稿','audio':{'src':'x.wav','text':'讲稿','signature':signature('讲稿',p['voice'])}}
  self.assertTrue(audio_valid(s,p));p['voice']={'backend':'azure','speaker':'zh-CN-XiaoxiaoNeural'};self.assertFalse(audio_valid(s,p))
if __name__=='__main__':unittest.main()
