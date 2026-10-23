"""Fast stdlib tests for installation decisions, config reuse and failure behavior."""
import argparse,contextlib,copy,io,json,os,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
SKILL=Path(__file__).resolve().parents[1];sys.path.insert(0,str(SKILL/'scripts'))
import setup as installer
from lib.environment import merged_settings,bootstrap_cli,runtime_home
from lib.model_assets import check_model
from lib.project_data import write,read

class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ktv-setup-test-');self.root=Path(self.temp.name);self.env=patch.dict(os.environ,{'KTV_HOME':str(self.root/'home'),'KTV_SETTINGS':'','KTV_ACTIVE_PYTHON':'','KTV_PYTHON':'','KTV_NO_REEXEC':''});self.env.start()
    def tearDown(self):self.env.stop();self.temp.cleanup()
    def model(self,backend='mlx'):
        p=self.root/'model';p.mkdir(exist_ok=True);(p/'speech_tokenizer').mkdir(exist_ok=True)
        config={'model_type':'qwen3_tts','tts_model_size':'1b7','tts_model_type':'custom_voice'}
        if backend=='mlx':config['quantization']={'bits':8}
        write(p/'config.json',config)
        for rel in ['tokenizer_config.json','vocab.json','merges.txt','speech_tokenizer/config.json']:(p/rel).write_text('{}')
        for rel in ['model.safetensors','speech_tokenizer/model.safetensors']:(p/rel).write_bytes(b'unit-test-placeholder-not-inference-weights')
        return p
    def args(self,**kwargs):
        d=dict(voice='none',home=str(self.root/'home'),use_python=None,python=None,chromium_path=None,model_path=None,skip_smoke=False,yes=False,plan=False,installer='auto',model_revision=None);d.update(kwargs);return argparse.Namespace(**d)
    def test_auto_apple(self):self.assertEqual(installer.select_backend('auto','Darwin','arm64'),'mlx')
    def test_auto_windows(self):self.assertEqual(installer.select_backend('auto','Windows','AMD64'),'qwen')
    def test_auto_linux(self):self.assertEqual(installer.select_backend('auto','Linux','x86_64'),'qwen')
    def test_no_mlx_on_intel(self):
        with self.assertRaises(ValueError):installer.select_backend('mlx','Darwin','x86_64')
    def test_render_only_has_no_model(self):self.assertIsNone(installer.build_plan(self.args())['model'])
    def test_plan_no_writes(self):
        with contextlib.redirect_stdout(io.StringIO()):installer.execute(self.args(plan=True))
        self.assertFalse((self.root/'home').exists())
    def test_no_yes_no_writes(self):
        with contextlib.redirect_stdout(io.StringIO()):installer.execute(self.args())
        self.assertFalse((self.root/'home').exists())
    def test_local_model_complete(self):self.assertEqual(check_model(self.model(),'mlx'),[])
    def test_partial_model_rejected(self):
        p=self.model();(p/'speech_tokenizer/model.safetensors').unlink();self.assertTrue(check_model(p,'mlx'))
    def test_wrong_size_rejected(self):
        p=self.model();c=read(p/'config.json');c['tts_model_size']='0b6';write(p/'config.json',c);self.assertTrue(any('1.7B' in s for s in check_model(p,'mlx')))
    def test_wrong_backend_rejected(self):self.assertTrue(check_model(self.model(),'qwen'))
    def test_native_qwen_accepted(self):self.assertEqual(check_model(self.model('qwen'),'qwen'),[])
    def test_cache_symlinks_accepted(self):
        p=self.model();weights=p/'model.safetensors';weights.unlink();blob=self.root/'cached-blob';blob.write_bytes(b'fixture');weights.symlink_to(blob);write(p/'model.safetensors.index.json',{'weight_map':{'tensor':'model.safetensors'}});self.assertEqual(check_model(p,'mlx'),[])
    def test_index_traversal_rejected(self):
        p=self.model();write(p/'model.safetensors.index.json',{'weight_map':{'tensor':'../unrelated'}});self.assertTrue(check_model(p,'mlx'))
    def test_global_config_and_local_override(self):
        write(runtime_home()/'runtime.settings.json',{'modelPath':'global-model','python':'global-python','device':'cpu'});project=self.root/'project';write(project/'runtime.settings.json',{'python':'','device':'cuda:0'});cfg=merged_settings(project);self.assertEqual(cfg['python'],'global-python');self.assertEqual(cfg['device'],'cuda:0');self.assertEqual(cfg['modelPath'],'global-model')
    def test_moved_project_uses_valid_local_python(self):
        write(runtime_home()/'runtime.settings.json',{'python':sys.executable});project=self.root/'moved-project';write(project/'runtime.settings.json',{'python':'/missing/old-machine/python'})
        cfg=merged_settings(project);self.assertEqual(cfg['python'],sys.executable);self.assertEqual(cfg['pathFallbacks'][0]['field'],'python')
    def test_different_model_backend_is_not_silently_replaced(self):
        model=self.model();write(runtime_home()/'runtime.settings.json',{'modelPath':str(model),'voiceBackend':'mlx'});project=self.root/'other-backend';write(project/'runtime.settings.json',{'modelPath':'/missing/qwen/model','voiceBackend':'qwen'})
        self.assertEqual(merged_settings(project)['modelPath'],'/missing/qwen/model')
    def test_explicit_settings(self):
        write(runtime_home()/'runtime.settings.json',{'device':'cpu'});p=self.root/'candidate.json';write(p,{'device':'cuda:0'})
        with patch.dict(os.environ,{'KTV_SETTINGS':str(p)}):self.assertEqual(merged_settings()['device'],'cuda:0')
    def test_same_base_python_still_reexecutes_venv(self):
        venv=self.root/'another-venv-python';venv.symlink_to(sys.executable);write(runtime_home()/'runtime.settings.json',{'python':str(venv)})
        with patch('lib.environment.os.execv') as execv:bootstrap_cli();execv.assert_called_once();self.assertEqual(execv.call_args[0][0],str(venv))
    def test_failed_setup_preserves_active_config(self):
        home=self.root/'home';before={'python':'old-python','customField':'keep'};write(home/'runtime.settings.json',before)
        with contextlib.redirect_stdout(io.StringIO()),self.assertRaises(ValueError):installer.execute(self.args(yes=True,use_python=str(self.root/'missing')))
        self.assertEqual(read(home/'runtime.settings.json'),before);self.assertFalse((home/'setup.lock').exists());self.assertTrue((home/'setup-last-error.json').exists())
    def test_model_type_rejected(self):
        p=self.model();c=read(p/'config.json');c['tts_model_type']='base';write(p/'config.json',c);self.assertTrue(check_model(p,'mlx'))
    def test_new_project_inherits_runtime(self):
        from project import create
        write(runtime_home()/'runtime.settings.json',{'voiceBackend':'qwen','python':'configured-python','modelPath':'configured-model','device':'cuda:0','dtype':'float16'})
        p=create(self.root/'new-lesson','新的课程');self.assertEqual(read(p)['voice']['backend'],'qwen');self.assertEqual(read(p.parent/'runtime.settings.json')['python'],'configured-python')
    def test_requirements_are_separate(self):
        self.assertNotIn('qwen-tts',(SKILL/'requirements/voice-mlx.txt').read_text());self.assertNotIn('mlx-audio',(SKILL/'requirements/voice-qwen.txt').read_text())

if __name__=='__main__':unittest.main(verbosity=2)
