"""Teaching-plan structure and observable motion checks. No automatic claims of good teaching/listening."""
import argparse,json,math,copy
from pathlib import Path
from lib.project_data import read,write,fingerprint,render_fingerprint,sha
STAGES=['script','storyboard','timing','final']
ROLES={'hook','definition','mechanism','application','boundary','recap'}
SEMANTIC={'concept','data','relationship','evidence'}
PURPOSES={'transfer','compare','update','construct','transform','trace','highlight'}
FIELDS=['x','y','scale','rotation','opacity','width','height']

def repeated_points(points):
    if len(points)<5:return False
    current={};states=[]
    for point in points:
        current.update({k:round(float(point[k]),4) for k in FIELDS if k in point});states.append(tuple(sorted(current.items())))
    for period in range(2,min(12,(len(states)-1)//2)+1):
        if len(set(states[:period]))>1 and all(states[i]==states[i%period] for i in range(len(states))):return True
    return False

def motion_intervals(layer,duration):
    if layer.get('visible') is False or layer.get('semanticRole') not in SEMANTIC or layer.get('loop') or layer.get('motionPurpose') not in PURPOSES:return []
    points=layer.get('keyframes',[])
    if repeated_points(points):return []
    start=max(0,float(layer.get('start',0)));end=min(duration,float(layer.get('end',duration)))
    if end<=start:return []
    intervals=[]
    if start>0:intervals.append((max(0,start-.1),min(duration,start+.3)))
    if end<duration:intervals.append((max(0,end-.1),min(duration,end+.3)))
    # Perceptibility is measured over monotone runs, not per exported keyframe.
    # Dense exports of a real path must behave like the equivalent two-point path.
    threshold={'x':8,'y':8,'width':5,'height':5,'rotation':8,'scale':.035,'opacity':.1}
    allowed=FIELDS if layer.get('type')!='image' or layer.get('isolatedObject') else ['opacity']
    states=[];previous=dict(layer)
    for point in points:
        previous={**previous,**point};states.append(previous)
    for field in allowed:
        samples=[state for state,point in zip(states,points) if field in point]
        run=[];direction=0;distance=0
        def flush():
            if distance>=threshold[field]:
                for a,b in run:
                    if max(float(a.get('opacity',1)),float(b.get('opacity',1)))<=.05:continue
                    x=max(start,float(a['at']));y=min(end,float(b['at']))
                    if y>x:intervals.append((x,y))
        for a,b in zip(samples,samples[1:]):
            delta=float(b[field])-float(a[field]);sign=1 if delta>0 else -1 if delta<0 else 0
            if not sign or direction and sign!=direction:
                flush();run=[];distance=0
            if sign:
                run.append((a,b));distance+=abs(delta)
            direction=sign
        flush()
    if layer.get('type')=='clip' and layer.get('frames') and layer.get('contentAction'):
        intervals.append((start,min(end,start+len(layer['frames'])/layer.get('frameFps',8))))
    return intervals

def max_gap(intervals,duration):
    cursor=0;gaps=[]
    for a,b in sorted(intervals):
        a=max(0,min(duration,a));b=max(0,min(duration,b))
        if a>cursor:gaps.append((cursor,a))
        cursor=max(cursor,b)
    if duration>cursor:gaps.append((cursor,duration))
    longest=max(gaps,key=lambda x:x[1]-x[0],default=(0,0))
    return round(longest[1]-longest[0],3),[round(x,3) for x in longest]

def inspect(p,root=None,stage='timing'):
    errors=[];warnings=[];manual={k:'pending' for k in ['accuracy','narrative','visual','listening']};details=[]
    plan=p.get('teaching')
    if not plan:return {'status':'not-assessed','readiness':'legacy-technical-only','errors':[],'warnings':['旧工程没有教学计划，技术通过不表示满足新版教学标准。'],'manualReview':manual,'scenes':[]}
    level=STAGES.index(stage);sources={x.get('id') for x in p.get('sources',[])};scenes=p.get('scenes',[]);byid={s.get('id'):s for s in scenes}
    if root:
        base=Path(root).parent.resolve()
        for source in p.get('sources',[]):
            if source.get('path'):
                target=(base/source['path']).resolve()
                if not target.is_relative_to(base) or not target.is_file():errors.append('来源文件缺失或越出交付目录：'+source['path'])
    if not plan.get('objective'):errors.append('缺少学生可理解的学习目标')
    anchor=plan.get('anchor',{})
    for key in ['id','situation','question','resolution']:
        if not anchor.get(key):errors.append('贯穿案例缺少'+key)
    claims={}
    for claim in plan.get('claims',[]):
        cid=claim.get('id')
        if not cid or cid in claims:errors.append('知识断言ID缺失或重复')
        claims[cid]=claim
        if claim.get('sourceId') not in sources:errors.append(str(cid)+'缺少真实来源ID')
        for key in ['text','locator','evidence']:
            if not claim.get(key):errors.append(str(cid)+'缺少'+key)
    if not claims:errors.append('缺少“知识断言—来源—原文位置”映射')
    concepts=plan.get('concepts',[])
    if not concepts:errors.append('缺少核心概念定义与适用边界')
    for c in concepts:
        if not all(c.get(k) for k in ['term','definition','boundary','sceneId','claimId']):errors.append('概念缺少定义、边界或场景/断言引用')
        if c.get('sceneId') not in byid or c.get('claimId') not in claims:errors.append('概念引用不存在的场景或断言')
    opening=plan.get('openingPrefix','大家好，我是曦曦，今天我们要学习')
    closing=plan.get('closingPhrase','本节课的学习就到这里了，同学们再见。')
    if scenes and not scenes[0].get('narration','').startswith(opening):errors.append('开头须先问好并明确学习主题：'+opening)
    if scenes and (not scenes[-1].get('narration','').endswith(closing) or '本节课我们学习了' not in scenes[-1].get('narration','')):errors.append('结尾须回收本节机制并使用约定告别语')
    used=set();case_count=0;limit=float(plan.get('maxIdleSeconds',5))
    if not math.isfinite(limit) or not 0<limit<=5:errors.append('当前课程maxIdleSeconds须大于0且不超过5秒');limit=5
    for i,s in enumerate(scenes):
        sid=s['id'];teaching=s.get('teaching',{});layers={l['id']:l for l in s.get('layers',[])};beats=s.get('beats',[])
        if teaching.get('role') not in ROLES:errors.append(sid+'缺少有效教学角色')
        if not teaching.get('purpose'):errors.append(sid+'未说明本镜解决什么学生问题')
        if i and not teaching.get('connectionFromPrevious'):errors.append(sid+'缺少与上一镜的因果/问题衔接')
        if teaching.get('caseLink'):case_count+=1
        for cid in teaching.get('claimIds',[]):
            if cid not in claims:errors.append(sid+'引用不存在的知识断言：'+cid)
            used.add(cid)
        if level==0:continue
        if not beats:errors.append(sid+'缺少逐句教学节拍')
        ids=set();intervals=[]
        for b in beats:
            bid=b.get('id')
            if not bid or bid in ids:errors.append(sid+'节拍ID缺失或重复')
            ids.add(bid)
            if not b.get('speech') or b['speech'] not in s['narration']:errors.append(sid+'/'+str(bid)+'没有绑定真实旁白片段')
            if not b.get('change'):errors.append(sid+'/'+str(bid)+'缺少可观察的知识状态变化')
            refs=b.get('layerIds',[])
            if not refs or any(l not in layers for l in refs):errors.append(sid+'/'+str(bid)+'缺少真实对象图层引用')
            if level>=2:
                a,z=b.get('start'),b.get('end')
                if not isinstance(a,(int,float)) or not isinstance(z,(int,float)) or not 0<=a<z<=s['duration']+.001:errors.append(sid+'/'+str(bid)+'缺少有效声学计时');continue
                active=[]
                for lid in refs:
                    if lid in layers:active += [(max(a,x),min(z,y)) for x,y in motion_intervals(layers[lid],s['duration']) if min(z,y)>max(a,x)]
                if not active and z-a>=limit:errors.append(sid+'/'+str(bid)+'只有装饰、整图运镜、重复动作或静态标注，未找到对应对象变化')
                intervals+=active
        if level>=2:
            a=s.get('audio') or {};timing=s.get('timing') or {}
            if timing.get('status')!='resolved' or timing.get('audioSHA256')!=a.get('sha256') or timing.get('text')!=s['narration'] or timing.get('leadIn')!=s['leadIn'] or timing.get('duration')!=s['duration']:errors.append(sid+'旁白或停顿更新后尚未重新校准动画')
            try:
                from lib.teaching_timing import retime_scene
                expected=copy.deepcopy(s);retime_scene(expected)
                actual_times=([(b['id'],b.get('start'),b.get('end')) for b in s.get('beats',[])],[(l['id'],l.get('start'),l.get('end'),[k['at'] for k in l.get('keyframes',[])]) for l in s['layers']])
                expected_times=([(b['id'],b.get('start'),b.get('end')) for b in expected.get('beats',[])],[(l['id'],l.get('start'),l.get('end'),[k['at'] for k in l.get('keyframes',[])]) for l in expected['layers']])
                if actual_times!=expected_times:errors.append(sid+'节拍/锚点时间与当前配音不一致')
            except ValueError as e:errors.append(sid+'无法重新计算语音锚点：'+str(e))
            longest,where=max_gap(intervals,float(s['duration']))
            if longest>=limit:errors.append(f'{sid}有{longest:.2f}秒缺少有效教学变化（{where}），超出{limit:g}秒限制')
            details.append({'id':sid,'semanticBeats':len(beats),'maxDeclaredActivityGapSeconds':longest,'longestHold':where})
        if not any(l.get('type')=='text' and l.get('semanticRole')=='concept' and l.get('visible') is not False for l in layers.values()):warnings.append(sid+'尚无可编辑的概念/关系文字')
    if case_count<min(3,len(scenes)):errors.append('贯穿案例未在引入、讲解和结尾至少三处呼应')
    if set(claims)-used:errors.append('有知识断言未落实到镜头：'+', '.join(sorted(set(claims)-used)))
    review=p.get('review') or {};fresh=False
    if root:
        from lib.timeline import slug
        video=Path(root).parent/(slug(p['title'])+'.mp4')
        try:fresh=review.get('projectFingerprint')==fingerprint({**p,'review':{}}) and review.get('renderFingerprint')==render_fingerprint({**p,'review':{}},root) and video.is_file() and review.get('videoSHA256')==sha(video.read_bytes())
        except (OSError,ValueError):fresh=False
    for k in manual:
        evidence=(review.get('checks') or {}).get(k,{})
        if fresh and evidence.get('status') in ['pass','fail'] and evidence.get('evidence'):
            path=(Path(root).parent/evidence['evidence']).resolve() if root else None
            base=Path(root).parent.resolve() if root else None
            if path and base and path.is_relative_to(base) and path.is_file() and evidence.get('sha256')==sha(path.read_bytes()):manual[k]=evidence['status']
    if 'fail' in manual.values():errors.append('人工复核发现未修复的问题')
    pending=[k for k,v in manual.items() if v=='pending']
    return {'status':'fail' if errors else 'structural-pass','readiness':'revise' if errors else 'ready-for-review' if pending else 'reviewed','scope':'structure-and-observable-motion; source truth, story quality and listening require evidence','projectFingerprint':fingerprint(p),'stage':stage,'errors':errors,'warnings':warnings,'manualReview':manual,'scenes':details}
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--project',required=True);ap.add_argument('--stage',choices=STAGES,default='timing');ap.add_argument('--out');ap.add_argument('--require-reviewed',action='store_true');a=ap.parse_args()
    try:
        path=Path(a.project).resolve();r=inspect(read(path),path.parent,a.stage);print(json.dumps(r,ensure_ascii=False,indent=2))
        if a.out:write(a.out,r)
        ap.exit(1 if r['errors'] or a.require_reviewed and r['readiness']!='reviewed' else 0)
    except Exception as e:ap.exit(1,str(e)+'\n')
