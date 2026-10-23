"""Shared exact timeline. SRT uses explicit cues or clearly labelled sentence-level spans."""
import re

def timeline(p):
    now=0
    for i,s in enumerate(p['scenes']):
        yield i,s,now
        now+=s['duration']

def stamp(t):
    ms=round(t*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);sec,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{sec:02},{ms:03}'

def cues(p):
    result=[]
    for i,s,start in timeline(p):
        a=s['audio'];base=start+s['leadIn'];duration=a['duration']
        if a.get('cues'):
            end=0
            for c in a['cues']:
                if not end<=c['start']<c['end']<=duration+.001:raise ValueError('字幕时间码超出音频或发生重叠')
                result.append((base+c['start'],base+c['end'],c['text']));end=c['end']
        else:
            # Honest fallback: one cue per scene, exact speech interval; no invented word alignment.
            result.append((base,base+duration,s['narration']))
    return result

def srt(p):
    return '\n\n'.join(f'{i}\n{stamp(a)} --> {stamp(b)}\n{text}' for i,(a,b,text) in enumerate(cues(p),1))+'\n'

def slug(text):
    text=re.sub(r'[<>:"/\\|?*\x00-\x1f]','-',text).strip(' .')[:90]
    return text or '未命名视频'
