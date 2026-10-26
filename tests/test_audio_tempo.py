"""Verify real duration and pitch of explicit user-requested narration speed."""
import array,io,math,sys,unittest,wave
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from voice import apply_tempo,tempo_factor
from lib.project_data import tool
class TempoChecks(unittest.TestCase):
    def tone(self):
        samples=array.array('h',(round(4000*math.sin(2*math.pi*440*i/24000)) for i in range(72000)));s=io.BytesIO()
        with wave.open(s,'wb') as w:w.setparams((1,2,24000,0,'NONE','not compressed'));w.writeframes(samples.tobytes())
        return s.getvalue()
    def test_normal_rate_preserves_original_bytes(self):
        raw=self.tone();self.assertEqual(apply_tempo(raw,1,None),raw)
    def test_1_2_rate_shortens_audio_without_raising_pitch(self):
        try:tool('ffmpeg',None)
        except (FileNotFoundError,RuntimeError):self.skipTest('FFmpeg unavailable')
        raw=apply_tempo(self.tone(),1.2,None)
        with wave.open(io.BytesIO(raw)) as w:
            sr=w.getframerate();samples=array.array('h');samples.frombytes(w.readframes(w.getnframes()))
        self.assertAlmostEqual(len(samples)/sr,2.5,delta=.04)
        middle=samples[sr//2:sr*2];crossings=sum(a<=0<b for a,b in zip(middle,middle[1:]));hz=crossings/(len(middle)/sr)
        self.assertAlmostEqual(hz,440,delta=2)
    def test_invalid_rates_rejected(self):
        for value in [0,-1,.1,3,float('nan'),float('inf')]:
            with self.assertRaises(ValueError):tempo_factor(value)
if __name__=='__main__':unittest.main()
