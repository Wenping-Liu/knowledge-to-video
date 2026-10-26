# 教学计划、节拍与锚点数据

结构沿用portable schemaVersion=1，新增字段向后兼容。旧工程没有`teaching`时只报告技术检查，不能被标为符合新标准。新工程生成的是待填写计划；实际内容必须来自本次教材。

```json
{
  "teaching": {
    "version": 1,
    "objective": "学生能用同一份通知解释训练与推理的差别",
    "anchor": {"id":"notice","situation":"把秋游通知交给模型写摘要","question":"模型怎样学会生成，又怎样回答这一次输入？","resolution":"训练更新参数，普通推理使用已有参数逐步生成"},
    "claims": [{"id":"c-train","text":"训练根据误差更新参数","sourceId":"book","locator":"教材相关章小节","evidence":"从实际材料摘录支持该断言的短句","treatment":"paraphrase"}],
    "concepts": [{"term":"训练","definition":"用数据和误差调整模型参数的过程","boundary":"练习的比喻只说明反复调整，不代表模型有人的学习体验","sceneId":"s02","claimId":"c-train"}],
    "maxIdleSeconds": 5,
    "openingPrefix": "大家好，我是曦曦，今天我们要学习",
    "closingPhrase": "本节课的学习就到这里了，同学们再见。"
  }
}
```

`claims.evidence`示例是填写说明，不是真实引文；正式工程须替换为已读取的材料。`sourceId`必须对应实际` sources`条目，引用文件必须随交付提供，外部链接记录日期。

每镜增加：

```json
{
  "teaching": {"role":"mechanism","purpose":"解释误差怎样导致参数更新","connectionFromPrevious":"已有预测，现在用真实后文检查它","caseLink":"通知示例的用词来自此前学到的规律","claimIds":["c-train"]},
  "delivery": {"direction":"解释参数更新时稍慢，轻强调误差和更新，讲完整意思再停顿"},
  "beats": [{"id":"b01","speech":"模型把预测和真实后文比较。","change":"预测卡片与目标并排，误差显示出来","layerIds":["prediction","target","error"]}],
  "layers": [{"id":"prediction","type":"shape","shape":"rect","semanticRole":"data","x":80,"y":220,"width":220,"height":120,"scale":1,"keyframes":[{"at":0,"x":80,"anchor":{"beat":"b01","fraction":0}},{"at":1,"x":400,"anchor":{"beat":"b01","fraction":1}}]}]
}
```

`role`为`hook / definition / mechanism / application / boundary / recap`。节拍可跨完整句，须填写当前旁白原样片段；重复片段用`charStart`明确位置。每个`layerIds`都指真实、可编辑的对象。

`semanticRole`为`concept / data / relationship / evidence / decorative / camera`。`image`整图平移缩放默认不算机制；独立对象图片可标`isolatedObject:true`，其动作是否合理仍须审片。真实短片需`contentAction`说明观察什么，循环短片不自动计入教学变化。

运行配音/对齐后，节拍生成场景相对的`start/end`。`keyframes[].anchor`按节拍的fraction和offset重排；显示区间用`startAnchor/endAnchor`。`timing`绑定当前音频SHA、讲稿、开口留白和镜头时长；检查时还重新计算节拍与锚点，手动改秒数或沿用旧的resolved标记会失效。改文稿、声音表达或音频后，必须重新对齐；旧的绝对秒数无法冒充当前计时。

终审证据在顶层`review`，指纹计算时把`review`替换为空对象：

```json
{"review":{
  "projectFingerprint":"当前工程清空review后的SHA256",
  "renderFingerprint":"工程内容、实际素材字节与renderer代码的组合SHA256",
  "videoSHA256":"被审查MP4的SHA256",
  "checks":{
    "visual":{"status":"pass","evidence":"审片/视觉审查.md","sha256":"证据文件的SHA256"},
    "listening":{"status":"pending","evidence":""}
  }
}}
```

证据必须真实存在并说明观看/试听范围，accuracy/narrative/visual/listening分别记录。更换同名素材、渲染器代码、MP4或证据文件都会让旧审查失效，不能只改状态。允许仅补充review元数据而不重新渲染；包清单仍需刷新。数据完整只提高可检查性，不等同于讲稿好或模型读音自然。

图层`motionPurpose`描述可见动作目的，参见分镜参考。`align:left|center|right`控制原生文本对齐，`fit:contain|stretch`控制图片布局；stretch适用于为预留文字位置制作的纸张背景，照片通常保持contain。SVG源文件在静帧SVG导出中保留嵌套分组与矢量形状，位图仍是位图。
