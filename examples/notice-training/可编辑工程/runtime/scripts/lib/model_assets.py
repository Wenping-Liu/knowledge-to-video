"""Known Serena model sources and offline completeness checks; no inference at import."""
import json
from pathlib import Path
MODELS={
 'mlx':{'repo':'mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit','approximateDownload':'约3.1 GB','license':'Apache-2.0'},
 'qwen':{'repo':'Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice','approximateDownload':'数GB，大小以模型仓库为准','license':'Apache-2.0'}
}

def check_model(path,backend):
    if backend not in MODELS:return ['未知的语音后端']
    if not path:return ['未配置模型路径']
    root=Path(path).expanduser();errors=[]
    for rel in ['config.json','tokenizer_config.json','vocab.json','merges.txt','speech_tokenizer/config.json']:
        if not (root/rel).is_file():errors.append('缺少 '+rel)
    config=root/'config.json'
    if config.is_file():
        try:
            d=json.loads(config.read_text(encoding='utf-8'))
            if d.get('tts_model_size')!='1b7':errors.append('需要1.7B模型（tts_model_size=1b7）')
            if d.get('tts_model_type')!='custom_voice':errors.append('需要CustomVoice模型')
            if d.get('model_type')!='qwen3_tts':errors.append('需要Qwen3-TTS模型')
            quantized=bool(d.get('quantization') or d.get('quantization_config'))
            if backend=='mlx' and not quantized:errors.append('MLX安装器需要转换后的量化模型')
            if backend=='qwen' and quantized:errors.append('官方qwen后端需要原始PyTorch模型，不能直接用MLX量化权重')
        except (ValueError,OSError) as e:errors.append('模型配置无法读取：'+str(e))
    def weights(folder):
        index=folder/'model.safetensors.index.json'
        if index.is_file():
            try:
                data=json.loads(index.read_text());names=set(data['weight_map'].values())
                if not names:errors.append(str(folder.name)+'权重索引为空')
                for name in names:
                    f=(folder/name).resolve()
                    if Path(name).is_absolute() or '..' in Path(name).parts or not f.is_file() or f.stat().st_size==0:errors.append('权重分片缺失或路径无效：'+name)
            except (ValueError,KeyError,OSError) as e:errors.append('权重索引无效：'+str(e))
        elif not any(f.is_file() and f.stat().st_size>0 for f in folder.glob('*.safetensors')):errors.append('缺少 '+str(folder.relative_to(root))+' safetensors权重')
    if root.is_dir():weights(root);weights(root/'speech_tokenizer')
    else:errors.append('模型目录不存在')
    return errors
