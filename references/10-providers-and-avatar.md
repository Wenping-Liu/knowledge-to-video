# 声音 编程智能体和曦曦角色

## 声音选项

| 方案 | 当前接入状态 | 依赖和使用条件 |
|---|---|---|
| Qwen3-TTS 12Hz 1.7B CustomVoice Serena | 默认，本地实际生成已验证；Apple Silicon为MLX，其他机器提供qwen/PyTorch适配器 | 模型先下载并按许可证使用；本机计算，不按次调用云API；Windows/Linux实际推理仍需实机验证 |
| Microsoft Azure 晓晓 zh-CN-XiaoxiaoNeural | 官方REST适配器已实现并做模拟请求测试；本轮未使用真实付费账号调用 | Azure Speech资源、区域和密钥；明确允许发送本镜旁白；额度和费用按账号当前规则 |
| BreezeBlue 自选音色 | 同步REST适配器与音频导入；[图文教程](../docs/breeze/README.md) | 账号Key和有权访问的Voice ID；详见[Breeze接入](11-breeze-api.md) |
| 其他声音或教师本人录音 | 导入音频 | 需确认声音授权与文稿一致，重新校准并核听；不会自动克隆真人 |

Qwen profile为`assets/profiles/xixi-comic-serena.json`；Azure为`azure-xiaoxiao.json`；Breeze API为`breeze-api.json`，手动导入为`breeze-import.json`。创建工程时：

```sh
python3 scripts/project.py init --out 我的知识点 --title 我的知识点 --profile assets/profiles/azure-xiaoxiao.json
```

Azure凭证只放本机环境：`AZURE_SPEECH_KEY`、`AZURE_SPEECH_REGION`。用户确认后设置`KTV_ALLOW_CLOUD_TTS=1`才允许调用。不要把密钥放入工程JSON、HTML、Git或截图；不接受浏览器提交任意云端地址。适配器只发送当前镜头的旁白文字，不上传教材、图片或参考视频。当前Azure使用命名神经声音，逐镜自然语言表达指令不会被自动翻译为SSML情感控制；Qwen支持这类指令。生成后仍需试听，不能用技术检查证明声音自然。

导入Breeze或其他声音：编辑器“导入配音”，或`voice.py --project 工程数据.json --scene s01 --import-audio 当前镜头.wav`。更换声音后同一支视频所有镜头统一处理；新音频校准并更新SRT，避免文字改了而音频沿用旧版。

## 编程模型与宿主

Codex是当前实际验证的编程智能体宿主，具体模型由用户在宿主里选择，本Skill不擅自切换模型。宿主完成资料理解、连续讲稿、分镜、代码创作和检查；Python、Canvas、FFmpeg等负责确定性执行。Skill本身不包含独立LLM API网关。

其他厂商的编程智能体或本地模型可尝试同一流程：能读取SKILL.md及references，读取教材文件、执行Python与浏览器，编辑工程JSON并解释失败；满足这些条件后用同一测试和真实样片验证。它们是可适配目标，不能把“可读文档”写成“所有智能体已经兼容”。只有聊天能力、没有文件和执行工具的模型，适合审稿或分镜草案。

## 曦曦虚拟讲解角色

默认保留纯知识动画。用户明确要出镜时，可把已授权的透明PNG作为独立图层：

```sh
python3 scripts/avatar.py --project 工程数据.json --image 透明曦曦.png --scene s01 --x 980 --y 350 --width 250 --height 340
```

位置、大小、显隐及关键帧可在HTML中修改；角色是装饰图层，不计入教学动作检查。当前功能是图像合成，不等同自动口型同步或真人数字人生成。带Alpha视频可随剪映素材作为独立轨道交接；当前普通短片缓存为JPEG，不承诺保留Alpha。角色源图及相关品牌的许可独立记录，公共仓库不默认开放用户私有角色素材。

## 官方资料

核对日期2026-10-27。费用、声音可用性和账号权限需在使用时再查。

- Qwen3-TTS：https://github.com/QwenLM/Qwen3-TTS
- Azure REST：https://learn.microsoft.com/en-us/azure/ai-services/speech-service/rest-text-to-speech
- BreezeBlue：https://breezeblue.ai/ 与 https://docs.breezeblue.ai/
- Codex Skills：https://developers.openai.com/codex/skills/
