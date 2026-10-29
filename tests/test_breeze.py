import unittest,sys,os,json,io,wave,urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from lib.breeze_voice import breeze_audio,NoRedirect
from lib.project_data import signature,audio_valid,effective_voice
class Response:
 status=200
 def __init__(self,data):self.data=data
 def __enter__(self):return self
 def __exit__(self,*a):pass
 def read(self,*a):return self.data
class Breeze(unittest.TestCase):
 def setUp(self):
  self.env=patch.dict(os.environ,{'BREEZE_API_KEY':'fake-test-key','KTV_ALLOW_CLOUD_TTS':'1'},clear=True);self.env.start();self.addCleanup(self.env.stop)
  self.voice={'backend':'breeze','speaker':'voc_nc4uny6vhms2','instruction':'清晰讲解','guidanceScale':1}
 def test_request_contract(self):
  def send(req,**kw):
   self.assertEqual(req.host,'api.breeze.blue');self.assertIn(self.voice['speaker'],req.full_url)
   self.assertEqual(req.get_header('Xi-api-key'),'fake-test-key')
   body=json.loads(req.data);self.assertEqual(body['text'],'知识');self.assertEqual(body['instructions'],'清晰讲解');self.assertEqual(body['language_code'],'zh')
   self.assertNotIn('model_id',body)
   return Response(b'RIFF0000WAVEdata')
  self.assertTrue(breeze_audio('知识',self.voice,send).startswith(b'RIFF'))
 def test_permission_gate(self):
  os.environ['KTV_ALLOW_CLOUD_TTS']='0'
  with self.assertRaises(ValueError):breeze_audio('知识',self.voice,lambda *a,**k:self.fail('network'))
 def test_missing_key(self):
  os.environ.pop('BREEZE_API_KEY')
  with self.assertRaises(ValueError):breeze_audio('知识',self.voice)
 def test_bad_input_never_sent(self):
  for v in [{'speaker':'https://evil.invalid'}, {'guidanceScale':float('nan')},{'languageCode':'Chinese'}]:
   with self.assertRaises(ValueError):breeze_audio('知识',{**self.voice,**v},lambda *a,**k:self.fail('network'))
  with self.assertRaises(ValueError):breeze_audio('字'*1001,self.voice)
 def test_failure_redacted_no_retry(self):
  calls=[]
  def send(*a,**k):calls.append(1);raise urllib.error.HTTPError('url',401,'bad',{},io.BytesIO(b'fake-test-key'))
  with self.assertRaises(RuntimeError) as e:breeze_audio('知识',self.voice,send)
  self.assertNotIn('fake-test-key',str(e.exception));self.assertEqual(len(calls),1)
 def test_non_audio_rejected(self):
  with self.assertRaises(ValueError):breeze_audio('知识',self.voice,lambda *a,**k:Response(b'{"job":"pending"}'))
 def test_redirect_disabled(self):self.assertIsNone(NoRedirect().redirect_request(None,None,None,None,None,None))
 def test_voice_and_direction_invalidate(self):
  p={'voice':self.voice};s={'narration':'知识','delivery':{'direction':'慢讲'}}
  s['audio']={'src':'x.wav','text':'知识','signature':signature('知识',effective_voice(p,s))}
  self.assertTrue(audio_valid(s,p));s['delivery']['direction']='轻快';self.assertFalse(audio_valid(s,p))
  s['delivery']['direction']='慢讲';p['voice']['speaker']='voc_different';self.assertFalse(audio_valid(s,p))
 def test_pipeline_routes_breeze(self):
  import voice
  b=io.BytesIO()
  with wave.open(b,'wb') as w:w.setparams((1,2,24000,0,'NONE',''));w.writeframes(b'\0\0'*240)
  with patch('lib.breeze_voice.breeze_audio',return_value=b.getvalue()),patch('voice.normalize',side_effect=lambda raw,root:raw),patch('voice.settings',return_value={}):
   a=voice.synthesize('知识',self.voice,Path('.'))
  self.assertEqual(a['provenance']['provider'],'BreezeBlue');self.assertEqual(a['signature'],signature('知识',self.voice));self.assertGreater(a['duration'],0)
if __name__=='__main__':unittest.main()
