"""Retiming uses actual aligned speech ranges; no proportional word timing."""
import copy

def speech_range(scene, beat):
    audio=scene.get('audio') or {};text=scene['narration'];speech=beat.get('speech','')
    begin=beat.get('charStart')
    if begin is None:
        begin=text.find(speech)
        if begin<0 or not speech:raise ValueError('教学节拍的speech必须是当前旁白的原样片段：'+beat.get('id',''))
        if text.find(speech,begin+1)>=0:raise ValueError('重复旁白需给出charStart：'+beat.get('id',''))
    if text[begin:begin+len(speech)]!=speech:raise ValueError('教学节拍的文字范围失效')
    finish=begin+len(speech);alignment=audio.get('alignment') or {}
    if alignment and (alignment.get('audioSHA256')!=audio.get('sha256') or alignment.get('text')!=text):raise ValueError('强制对齐对应旧音频或旧文稿')
    units=alignment.get('units',[])
    if not units:
        units=[];cursor=0
        for cue in audio.get('cues',[]):
            content=cue.get('text','');units.append({**cue,'charStart':cursor,'charEnd':cursor+len(content)});cursor+=len(content)
        if ''.join(c.get('text','') for c in audio.get('cues',[]))!=text:raise ValueError('需要当前音频强制对齐或完整的已核对字幕计时')
        # Cue-only timing is exact only when the requested phrase spans cue boundaries.
        if begin not in [u['charStart'] for u in units] or finish not in [u['charEnd'] for u in units]:raise ValueError('节拍边界位于字幕句中；请使用词级对齐或拆分并核对字幕')
    selected=[u for u in units if u['charEnd']>begin and u['charStart']<finish]
    if not selected:raise ValueError('教学节拍没有可用的声学时间')
    start=float(selected[0]['start'])+scene['leadIn'];end=float(selected[-1]['end'])+scene['leadIn']
    if end<=start:raise ValueError('教学节拍时长为空')
    return start,end

def anchor_time(anchor,beats,duration):
    if anchor.get('boundary') in ['sceneStart','sceneEnd']:
        at=0 if anchor['boundary']=='sceneStart' else duration
    else:
        b=beats.get(anchor.get('beat'))
        if not b:raise ValueError('动画锚点引用不存在的教学节拍：'+str(anchor.get('beat')))
        fraction=float(anchor.get('fraction',0))
        if not 0<=fraction<=1:raise ValueError('动画锚点fraction须在0至1之间')
        at=b['start']+(b['end']-b['start'])*fraction
    at+=float(anchor.get('offset',0))
    return round(max(0,min(duration,at)),4)

def retime_scene(scene):
    if not scene.get('beats'):return False
    resolved=copy.deepcopy(scene)
    for beat in resolved['beats']:
        beat['start'],beat['end']=map(lambda x:round(x,4),speech_range(resolved,beat))
    beats={b['id']:b for b in resolved['beats']};duration=resolved['duration']
    for layer in resolved.get('layers',[]):
        for key in ['start','end']:
            if layer.get(key+'Anchor'):layer[key]=anchor_time(layer[key+'Anchor'],beats,duration)
        for point in layer.get('keyframes',[]):
            if point.get('anchor'):point['at']=anchor_time(point['anchor'],beats,duration)
        layer['keyframes']=sorted(layer.get('keyframes',[]),key=lambda x:x['at'])
    a=resolved['audio'];resolved['timing']={'status':'resolved','audioSHA256':a['sha256'],'text':resolved['narration'],'leadIn':resolved['leadIn'],'duration':resolved['duration'],'method':(a.get('alignment') or {}).get('method','reviewed-cues')}
    scene.clear();scene.update(resolved);return True
