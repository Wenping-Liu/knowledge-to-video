# 首次安装与运行环境

Skill安装器通常只复制说明、脚本与素材，Python库、浏览器和模型需要一次运行环境准备。v1.1提供自动安装入口；成功后普通CLI和新工程自动复用配置。

## 最短使用路径

```sh
git clone https://github.com/Wenping-Liu/knowledge-to-video.git
cd knowledge-to-video
python3 scripts/setup.py --yes
python3 scripts/doctor.py --check
```

Windows也可用`py -3.12 scripts/setup.py --yes`。双击入口分别是根目录`安装环境.command`、`安装环境.cmd`、`安装环境.sh`；下载ZIP丢失可执行权限时可在终端执行`sh 安装环境.command`或`sh 安装环境.sh`。

推荐Python3.12。安装器优先找3.12；已有uv时可准备用户级Python。没有适合的Python且没有uv时，先从https://www.python.org/downloads/ 安装3.12。系统Python不被替换。基础脚本使用标准库，运行环境支持3.10–3.13；其他版本只作为安装引导，准备兼容解释器后再运行。

## 安装器做什么

1. 识别平台：Apple Silicon使用MLX；其他平台使用qwen/PyTorch。`--voice none`只准备渲染环境，配音可手动导入。
2. 在本机缓存建立隔离环境，按`requirements/render.txt`和对应语音清单安装；有uv时使用uv，否则使用venv/pip。
3. 准备Playwright Chromium，已有有效的本机配置或显式路径时复用。FFmpeg由imageio-ffmpeg wheel提供，可使用系统FFmpeg；ffprobe可选，缺少时回退到FFmpeg解析。
4. 复用已配置或指定的模型，缺少时从Hugging Face官方/MLX社区仓库下载并记录提交。MLX8bit模型约3.1GB；其他路线以模型仓库为准。部分下载保留，可重试；不上传教材或旁白。
5. 检查模型配置、词表、权重分片和声码器，再实际启动浏览器。默认生成Serena验证音频并导出有声MP4；仅渲染模式使用明确标注的测试音。
6. 验证成功后激活配置。失败保留旧配置和下载缓存，写错误与日志，不删除用户工程。

模型运行库、权重、浏览器各遵循自身许可。安装器下载已知模型，不自动改用其他声音。运行库依赖与模型下载需要网络；准备完成后，核心配音/渲染可本地离线执行。

## 常用选项

```sh
# 只看计划
python3 scripts/setup.py --plan
# 复用已有模型
python3 scripts/setup.py --yes --model-path "/本地1.7B-CustomVoice模型"
# 暂不下载声音模型
python3 scripts/setup.py --yes --voice none
# 只采用已配置好的环境，不向其中安装包
python3 scripts/setup.py --yes --use-python "/现有环境/bin/python" --model-path "/模型" --chromium-path "/Chromium可执行文件"
# 特定基础Python、安装器或声音路线
python3 scripts/setup.py --yes --python "/Python3.12" --installer pip --voice mlx
# 单独再做一次实际试制
python3 scripts/smoke_test.py
```

`--voice qwen`用于官方PyTorch路线。已有CUDA环境可用`--use-python`复用；新环境安装后检测CUDA，检测不到则用CPU float32，速度可能明显较慢。FlashAttention不作为强制依赖。Windows/Linux与CUDA组合需要实际机器验证，不承诺所有驱动和硬件通用。

`--skip-smoke`只在用户明确选择时跳过实际生成，报告标为configured-not-smoke-tested；不能称完整验证通过。`--model-revision`可固定管理目录内下载的模型提交；显式提供`--model-path`时以用户本地模型为准。

## 自动发现配置

默认缓存：macOS/Linux为`~/.cache/knowledge-to-video/`，Windows为`%LOCALAPPDATA%/knowledge-to-video/`。

- `runtime.settings.json`：当前有效的本机解释器、浏览器、FFmpeg与模型路径。
- `venv-mlx/`、`venv-qwen/`或`venv-none/`：隔离环境。
- `browsers/`、`models/`：已准备资源。
- `setup.log`、`setup-report.json`、`doctor-last.json`：安装与验证记录。
- `checks/`：实际验证短片。

如用`--home`更换缓存位置，后续命令需保持相同`KTV_HOME`环境变量。该选项主要用于独立测试和自定义磁盘位置。只读`--plan`不创建缓存。

配置优先级：显式`KTV_*`环境变量→工程中非空的runtime.settings.json→本机共享配置→自动检测。工程迁移后，缺失的旧本机路径可回退到兼容的本机有效配置；不同语音后端的模型不能静默互换，需明确调整工程并重新生成配音。`doctor`报告pathFallbacks。

每个CLI会在需要时转到已配置的Python，比较虚拟环境入口路径而非其共同的基础解释器，避免“明明装过依赖，却仍在系统Python中检测”的误报。新工程继承本机配置和配音后端；自定义profile仍按用户选择。

## 排查安装问题

- 仅看到“缺少依赖”：先执行setup命令，再运行doctor；不要只反复复制Skill。
- 网络失败：查看setup.log，检查PyPI/Hugging Face/Playwright下载站点是否可达，再重跑。已有本地模型可以用`--model-path`；网络/代理设置由用户决定，不擅自更换第三方镜像。
- Linux浏览器缺少系统库：按Playwright提示安装依赖，通常是`python -m playwright install-deps chromium`，其中系统包可能需要管理员权限。安装器会报告具体失败，不自行sudo。
- Python缺少venv/pip：使用完整Python3.12发行版或已安装的uv，或为系统安装对应venv组件。
- 模型文件不全：doctor列出缺失项；完整复制后重试，或让安装器补齐其管理目录内的下载。
- 安装异常中断留下setup.lock：先确认没有另一个安装进程，再删除锁并重跑；不删除模型/工程。
- 只需编辑与导入声音：使用`--voice none`；HTML自身的离线编辑无需安装配音模型。

## 本地服务与上游

启动`python3 scripts/serve.py --project <工程数据.json> --open`；仅监听127.0.0.1，随机端口和会话token。只允许工程范围内素材，检查Origin和token，不接受任意系统文件路径或命令。图片生成、资料搜索按当前工具与授权配置，独立于本地TTS。

上游：
- https://github.com/QwenLM/Qwen3-TTS
- https://github.com/Blaizzy/mlx-audio
- https://huggingface.co/mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit
- https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice
- https://playwright.dev/python/docs/browsers
- https://ffmpeg.org/documentation.html

依赖直接版本写入requirements，安装报告记录实际解析版本；上游有变化时修改清单并重新验证。默认不捆绑模型权重、密钥或个人路径。
