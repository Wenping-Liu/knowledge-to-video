"""Regression tests for demonstrated narrative/timing failure modes; synthetic timing only."""
import copy,json,shutil,subprocess,sys,unittest,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'scripts'))
from lib.project_data import effective_voice,signature,audio_valid,render_fingerprint,content_fingerprint,sha
from lib.teaching_timing import retime_scene
from quality import inspect,motion_intervals,max_gap

def fixture():
    texts=['大家好，我是曦曦，今天我们要学习电流，看看灯泡为什么亮。','电流是电荷的定向移动，让我们沿导线跟着电荷走。','本节课我们学习了电流，它就是电荷的定向移动，灯泡的案例帮助我们看到电路里的关系。本节课的学习就到这里了，同学们再见。']
    p={'title':'功能测试，不是课程','voice':{'instruction':'亲切讲解','speaker':'Serena'},'sources':[{'id':'fixture'}],'teaching':{'version':1,'objective':'解释电荷与电流','anchor':{'id':'lamp','situation':'灯泡亮','question':'电荷怎样运动','resolution':'定向运动形成电流'},'claims':[{'id':'current','text':'电荷的定向移动形成电流','sourceId':'fixture','locator':'测试输入段1','evidence':'本用例自建定义，仅验证字段与计时','treatment':'fixture'}],'concepts':[{'term':'电流','definition':'电荷的定向移动','boundary':'水流类比只说明流动关系','sceneId':'s02','claimId':'current'}],'maxIdleSeconds':5},'scenes':[]}
    for i,text in enumerate(texts):
        s={'id':f's{i+1:02}','narration':text,'leadIn':.2,'gapAfter':.8,'duration':8,'audio':{'src':'synthetic.wav','text':text,'sha256':'fixture-'+str(i),'duration':7,'cues':[{'start':0,'end':7,'text':text}]},'teaching':{'role':['hook','mechanism','recap'][i],'purpose':'解释电荷运动','connectionFromPrevious':'从灯泡问题追踪电荷','caseLink':'灯泡','claimIds':['current']},'beats':[{'id':'b01','speech':text,'change':'电荷沿导线从左到右移动','layerIds':['charge']}],'layers':[{'id':'charge','type':'shape','shape':'circle','semanticRole':'data','motionPurpose':'transfer','x':0,'y':20,'width':50,'height':50,'scale':1,'keyframes':[{'at':0,'x':0,'anchor':{'beat':'b01','fraction':0}},{'at':1,'x':500,'anchor':{'beat':'b01','fraction':1}}]},{'id':'term','type':'text','semanticRole':'concept','text':'电流：电荷定向运动','visible':True}]}
        s['audio']['signature']=signature(text,effective_voice(p,s));retime_scene(s);p['scenes'].append(s)
    return p

class TeachingChecks(unittest.TestCase):
    def test_existing_voice_signatures_are_preserved_without_direction(self):
        p=fixture();s=p['scenes'][0];self.assertEqual(effective_voice(p,s),p['voice']);self.assertTrue(audio_valid(s,p))
    def test_delivery_change_invalidates_old_voice(self):
        p=fixture();s=p['scenes'][0];s['delivery']={'direction':'定义稍慢并强调定向'};self.assertFalse(audio_valid(s,p));self.assertIn('定义稍慢',effective_voice(p,s)['instruction'])
    def test_anchors_follow_real_new_cues_not_old_scene_ratio(self):
        s=fixture()['scenes'][0];s['audio']['cues'][0].update(start=1,end=5);s['audio']['sha256']='replacement';retime_scene(s)
        self.assertEqual(s['beats'][0]['start'],1.2);self.assertEqual(s['layers'][0]['keyframes'][1]['at'],5.2);self.assertEqual(s['timing']['audioSHA256'],'replacement')
    def test_retiming_is_atomic_when_script_changed(self):
        s=fixture()['scenes'][0];s['beats'][0]['speech']='已经不存在的文字';before=copy.deepcopy(s)
        with self.assertRaises(ValueError):retime_scene(s)
        self.assertEqual(s,before)
    def test_forced_alignment_cannot_bind_another_audio(self):
        s=fixture()['scenes'][0];s['audio']['alignment']={'audioSHA256':'old','text':s['narration'],'units':[]}
        with self.assertRaises(ValueError):retime_scene(s)
    def test_missing_plan_is_not_misreported_as_teaching_pass(self):
        self.assertEqual(inspect({'scenes':[]})['status'],'not-assessed')
    def test_valid_mechanism_remains_pending_subjective_review(self):
        r=inspect(fixture(),stage='timing');self.assertEqual(r['errors'],[]);self.assertEqual(r['readiness'],'ready-for-review');self.assertTrue(all(v=='pending' for v in r['manualReview'].values()))
    def test_decorative_wiggle_cannot_cover_silent_teaching_gap(self):
        p=fixture();p['scenes'][1]['layers'][0]['semanticRole']='decorative';r=inspect(p,stage='timing');self.assertTrue(any('缺少有效教学变化' in x for x in r['errors']))
    def test_repeated_loop_cannot_cover_teaching_gap(self):
        p=fixture();p['scenes'][1]['layers'][0]['keyframes']=[{'at':i,'x':i%2*100} for i in range(8)];self.assertEqual(motion_intervals(p['scenes'][1]['layers'][0],8),[])
    def test_whole_illustration_pan_is_not_mechanism(self):
        l=fixture()['scenes'][0]['layers'][0];l.update(type='image',semanticRole='evidence');self.assertEqual(motion_intervals(l,8),[])
    def test_subpixel_drift_is_not_observable_activity(self):
        l=fixture()['scenes'][0]['layers'][0];l['keyframes']=[{'at':0,'x':0},{'at':7,'x':.002}];self.assertEqual(motion_intervals(l,8),[])
    def test_unexplained_three_point_wiggle_is_not_teaching(self):
        l=fixture()['scenes'][0]['layers'][0];l.pop('motionPurpose');l['keyframes']=[{'at':0,'x':0},{'at':3,'x':100},{'at':7,'x':0}];self.assertEqual(motion_intervals(l,8),[])
    def test_perceptibility_is_independent_of_keyframe_density(self):
        l=fixture()['scenes'][0]['layers'][0];l['keyframes']=[{'at':0,'x':0},{'at':7,'x':100}];sparse=motion_intervals(l,8)
        l['keyframes']=[{'at':i*.07,'x':i} for i in range(101)]
        self.assertEqual(max_gap(sparse,8),max_gap(motion_intervals(l,8),8))
    def test_two_repeated_back_and_forth_cycles_are_excluded(self):
        l=fixture()['scenes'][0]['layers'][0];l['keyframes']=[{'at':i*1.75,'x':50*(i%2)} for i in range(5)]
        self.assertEqual(motion_intervals(l,8),[])
    def test_lead_in_or_duration_change_requires_retiming(self):
        for field in ['leadIn','duration']:
            p=fixture();p['scenes'][0][field]+=.1
            self.assertTrue(any('尚未重新校准' in x for x in inspect(p)['errors']))
    def test_old_resolved_marker_cannot_hide_tampered_derived_times(self):
        p=fixture();p['scenes'][0]['layers'][0]['keyframes'][1]['at']-=1
        self.assertTrue(any('锚点时间' in x for x in inspect(p)['errors']))
    def test_audio_change_requires_new_animation_timing(self):
        p=fixture();p['scenes'][0]['audio']['sha256']='new';self.assertTrue(any('尚未重新校准' in x for x in inspect(p)['errors']))
    def test_unverified_source_and_missing_link_are_blocked(self):
        p=fixture();p['teaching']['claims'][0]['sourceId']='missing';p['scenes'][1]['teaching']['connectionFromPrevious']='';r=inspect(p,stage='script');self.assertTrue(any('真实来源' in x for x in r['errors']));self.assertTrue(any('衔接' in x for x in r['errors']))
    def test_five_second_hold_is_reported_with_range(self):
        self.assertEqual(max_gap([(0,1),(7,8)],8),(6,[1,7]))
    def test_replacing_media_at_same_path_invalidates_render_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'动画代码').mkdir();(root/'动画代码/renderer.js').write_text('renderer');(root/'image.svg').write_text('<svg/>')
            p={'scenes':[{'layers':[{'type':'image','src':'image.svg'}]}]};old=render_fingerprint(p,root);(root/'image.svg').write_text('<svg><rect/></svg>');self.assertNotEqual(old,render_fingerprint(p,root))
    def test_renderer_change_invalidates_render_fingerprint(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);(root/'动画代码').mkdir();file=root/'动画代码/renderer.js';file.write_text('renderer v1');p={'scenes':[]};old=render_fingerprint(p,root);file.write_text('renderer v2');self.assertNotEqual(old,render_fingerprint(p,root))
    def test_review_binds_actual_video_renderer_media_and_evidence(self):
        with tempfile.TemporaryDirectory() as td:
            base=Path(td);root=base/'可编辑工程';root.mkdir();(root/'动画代码').mkdir();(root/'动画代码/renderer.js').write_text('v1')
            (root/'photo.svg').write_text('<svg/>');(root/'synthetic.wav').write_bytes(b'test fixture')
            p=fixture();p['scenes'][0]['layers'].append({'id':'photo','type':'image','src':'photo.svg'})
            video=base/(p['title']+'.mp4');video.write_bytes(b'video fixture')
            evidence=base/'review.md';evidence.write_text('Test fixture evidence, not a course review')
            p['review']={'projectFingerprint':content_fingerprint(p),'renderFingerprint':render_fingerprint(p,root),'videoSHA256':sha(video.read_bytes()),'checks':{k:{'status':'pass','evidence':'review.md','sha256':sha(evidence.read_bytes())} for k in ['accuracy','narrative','visual','listening']}}
            self.assertEqual(inspect(p,root)['readiness'],'reviewed')
            for file,data in [(video,b'new video'),(evidence,b'changed evidence'),(root/'photo.svg',b'<svg><rect/></svg>'),(root/'动画代码/renderer.js',b'v2')]:
                before=file.read_bytes();file.write_bytes(data)
                self.assertEqual(inspect(p,root)['readiness'],'ready-for-review');file.write_bytes(before)
    def test_python_and_browser_retime_agree(self):
        if not shutil.which('node'):self.skipTest('Node unavailable')
        scene=fixture()['scenes'][0];scene['audio']['cues'][0].update(start=.45,end=6.1);expected=copy.deepcopy(scene);retime_scene(expected)
        js="global.window={};"+(ROOT/'assets/editor-template/renderer.js').read_text()+"const s=JSON.parse(require('fs').readFileSync(0,'utf8'));window.KTVRenderer.retimeScene(s);process.stdout.write(JSON.stringify(s));"
        actual=json.loads(subprocess.check_output(['node','-e',js],input=json.dumps(scene).encode()))
        self.assertEqual(actual,expected)
if __name__=='__main__':unittest.main()
