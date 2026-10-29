# Breeze 自定义音色接入

用户选择Breeze时读取本页；默认Serena不受影响。面向用户的完整图文步骤见[音色定制与API教程](../docs/breeze/README.md)。

## 从选择音色到工程

1. 用户在Breeze网站通过智能体/音色设计生成声音，或使用本人及获授权的录音克隆声音；试听后保存，从“音色库→我的音色”复制Voice ID。
2. 使用用户指定的ID，不能把公开样例的私有声音ID设为所有人的默认。API Key与Voice ID用途不同：Key为凭据，ID为声音选择，拥有ID不保证有调用权限。
3. 创建工程时使用`assets/profiles/breeze-api.json`，将工程`voice.speaker`中的`YOUR_VOICE_ID`改为实际ID。`voice.backend=breeze`，逐镜`delivery.direction`会合并到`instructions`。只有选填`modelId`时才显式指定模型，省略时由服务选择；这不构成具体模型版本已固定的承诺。
4. 首次只用一个代表性镜头试听，再按用户授权的范围批量生成。密钥由用户在终端隐藏输入：

```sh
python3 scripts/breeze.py --project '我的知识点/可编辑工程/工程数据.json' --scene s01 --prompt-key
```

使用前核对实际工程路径和镜头ID。`--prompt-key`仅在本进程中启用云调用，程序结束清除变量，不写入磁盘；不要让用户在聊天中发送密钥。自动化可由宿主预先安全注入`BREEZE_API_KEY`和`KTV_ALLOW_CLOUD_TTS=1`。编辑器服务需要从具备这两个变量的终端启动，前端不接收Key。

## 音频与计时契约

- `voice.py`支持breeze，与Qwen、Azure共用绑定签名、归一化、导入与失效机制。改旁白、Voice ID、表达指令、guidanceScale或速度后旧音频失效。
- 同步POST只发送当前镜头文字与表达参数。固定官方域名`api.breeze.blue`，禁用重定向，不接受工程传入任意URL。最多1000字；按语义拆镜。401/403/404/422/429和超时明确停止；不自动重试，超时后先检查平台生成历史与额度。
- `guidanceScale`为1—10，连续旁白从1试听。自然语言指令控制语气，不保证秒级时长。`speed`使用本地保音高变速。
- 成功后真实音频决定时长；配置本地alignmentModelPath则自动对齐并更新beats。未配置时保留待校准，使用`align.py`或导入核对过的cues，禁止估算字数时间后冒称精确同步。不要把原音频替换后原封不动沿用旧字幕。
- 目前支持同步WAV，未实现Breeze异步任务、流式或平台时间戳接口。音色设计/克隆在网站完成；Skill只调用已保存声音。
- 不上传教材、图像、视频或克隆原音频。示例授权不代表用户可任意克隆他人声音。服务费用及输出许可按账号规则核对。

## 独立试听

```sh
python3 scripts/breeze.py --text-file 讲稿.txt --voice-id voc_你的声音ID --out 试听.wav --prompt-key
```

生成原始WAV、归一化试听WAV及无密钥的来源JSON。已存在输出拒绝再次收费调用；需要重新生成请明确换输出路径。成功音频先落盘，即使后处理失败也可恢复。

验证：`python3 -m unittest discover -s tests -p 'test_breeze.py'`。请求契约测试与真实生成分别记录，不能把模拟响应写成实测。听感需用户试听，不能用解码结果代替。
