# 先看有声视频案例

先下载视频播放，再决定是否安装Skill。以下MP4均包含旁白；点击链接进入文件页后，选择Raw或Download下载到设备，用本地播放器打开。

| 视频 | 时长 | 入口 |
| --- | --- | --- |
| 知映KnowMotion 项目讲解与操作演示（曦曦出镜＋Serena旁白＋重点文字） | 约2分50秒 | [下载视频播放](media/project-demo.mp4) |
| 训练与推理 机制动画片段 | 约32秒 | [下载视频播放](media/training.mp4) |
| 为什么需要模型评测 | 约26秒 | [下载视频播放](media/evaluation.mp4) |
| LoRA参数适配示意 | 约19秒 | [下载视频播放](media/lora.mp4) |
| RAG先查资料再回答 | 约23秒 | [下载视频播放](media/rag.mp4) |
| 训练与推理完整可编辑样例 | 约3分11秒 | [下载完整视频播放](../../examples/notice-training/训练与推理可编辑示例.mp4) · [查看工程](../../examples/notice-training) |

| 训练与推理 | 模型评测 |
| --- | --- |
| [![训练与推理](media/training.jpg)](media/training.mp4) | [![模型评测](media/evaluation.jpg)](media/evaluation.mp4) |
| LoRA | RAG |
| [![LoRA](media/lora.jpg)](media/lora.mp4) | [![RAG](media/rag.jpg)](media/rag.mp4) |

需要自己制作或修改课程时，请克隆仓库并按使用指南运行源码与可编辑工程。展示入口只提供可下载播放的MP4，不再附需要本地环境的HTML和JSON链接。

[![知映KnowMotion 项目讲解与演示](media/project-demo.jpg)](media/project-demo.mp4)

新版演示以虚构教师“林老师”的备课任务为主线：从寻找合适视频的困难，到用自己的教材编写连贯讲稿、制作训练与推理动画，再到教师修改、重新配音和工程复用。采用 Serena 女声与简短重点文字，时长169.5秒。新版增加曦曦透明角色：沿用原旁白逐字时间轴驱动近似卡通口型，配合挥手与眨眼；角色位于画面右侧，原演示内容完整保留。成片为1600×900、30fps，只有一条旁白音轨。

片中包含真实编辑器操作与课程片段；配音校准和交付部分为流程示意。当前制作依赖智能体与本地工具，网页上传后自动生成属于后续研发方向。项目名称为“知映KnowMotion”，仓库及 Skill 调用标识仍为 `knowledge-to-video`。

## 案例依据与展示范围

案例直接基于GitLink上[Christin-liu / Full_Link_Development_of_Large_Models](https://www.gitlink.org.cn/Christin-liu/Full_Link_Development_of_Large_Models)仓库中“两天培训材料包”的知识点和实践任务开发，材料包源于《大模型全链路开发：基于书生开源体系的项目实战》。前五课共有27支独立知识点视频，修订版、短片与剪映副本不重复计数；这里公开精选案例和一套完整可编辑样例。

片段保留真实合成旁白和已制作动画，来源课次、时间区间和文件指纹保留在源码素材记录中。演示展示工程与画面效果；学校试点及教师学生学习效果测量属于后续计划。第三至第五课片段为历史实例，尚未全部按v1.3重制。原教材和个人材料未上传；曦曦仅按作者要求出现在本项目演示中，角色与品牌元素保留各自权利，不能随MIT代码许可自由再用。

## 自定义课堂声音试听

[Breeze音色定制与API图文教程](../breeze/README.md) · [试听voc_nc4uny6vhms2（约28秒）](../breeze/media/teacher-voc_nc4uny6vhms2.mp3)。支持用自己的Voice ID给视频配音。
