# 运行环境与适配

基础命令采用Python 3.10+标准库。MP4渲染需Playwright和Chromium、FFmpeg；优先使用ffprobe探测；缺少时回退到FFmpeg解析。项目中runtime/requirements.txt列出浏览器渲染依赖。Qwen配音可选：
- Apple Silicon：mlx-audio、numpy，本地MLX Qwen3-TTS 12Hz 1.7B CustomVoice（可选8bit）。
- 官方PyTorch路线：qwen-tts、torch、numpy，本地Qwen3-TTS-12Hz-1.7B-CustomVoice。设备/精度在settings配置；当前平台未实测时明确标注。

先检测，缺少时提供安装命令和许可来源；不要为单纯文字修改强制下载大模型。Playwright浏览器安装：`python -m playwright install chromium`；已有浏览器可配置chromium绝对路径。FFmpeg/ffprobe可系统安装，FFmpeg也支持imageio-ffmpeg回退。离线首次运行前须准备依赖和模型。模型路径只填本机settings或环境变量，不进公共profile。

runtime.settings.json：

```json
{"python":"","ffmpeg":"","ffprobe":"","chromium":"","modelPath":"","voiceBackend":"mlx","device":"cpu","dtype":"float32"}
```

路径可以在本机是绝对路径；移机后重新配置。KTV_MODEL、KTV_CHROMIUM、KTV_FFMPEG、KTV_FFPROBE、KTV_PYTHON可覆盖。doctor不自动下载、不扫描私人目录、不上传资料。生成配音默认本地，禁止偷偷访问云端。网络搜索/图片生成按当前工具与用户许可执行，记录来源。

接口：启动 `python serve.py --project <工程数据.json>`；随机可用本地端口、随机会话token、仅绑定127.0.0.1。启动浏览器URL携带token，本地API校验token和Origin。只允许项目内素材；不支持任意系统文件读写、上传服务器、运行用户传入命令。渲染读取项目动画代码，代码应来自可审查工程，禁止把不可信教材代码直接当renderer运行。

启动器解析顺序：KTV_PYTHON→工程settings.python→当前系统python3/python。模型不是必要依赖目录中的几GB附件。第三方代码/字体/模型单独保留许可；本包editor和runtime为独立实现，huashu仅作为可选创作/检查方法来源。

上游资料：
- https://agentskills.io/specification
- https://github.com/openai/codex/tree/main/codex-rs/skills/src/assets/samples/skill-creator
- https://github.com/alchaincyf/huashu-art-motion
- https://github.com/QwenLM/Qwen3-TTS
- https://github.com/Blaizzy/mlx-audio
- https://playwright.dev/python/docs/intro
- https://ffmpeg.org/documentation.html

外部版本可能变化；实际安装时核对上游接口和许可，保存锁定版本与doctor结果。自动下载或安装不会由Skill文字本身完成。
