# 可编辑工程约定

project.schema.json定义portable v1结构。稳定镜头ID与顺序分开；图层ID在镜头内唯一。使用root=工程数据.json所在目录解析素材；交付工程采用相对路径或内嵌data URL，禁止依赖其他课程路径、机器用户名、临时下载目录。

模板提供播放、暂停、拖动、逐镜预览，旁白与屏上文字编辑，图层添加/删除、图片替换、位置大小显隐，镜头添加/删除/排序/时长调整，生成/导入音频，保存/加载工程、导出当前HTML及本地有声MP4。图片/音频导入、播放和内嵌HTML保存可离线；视频预处理、生成配音、保存到交付文件夹和MP4导出需要本地服务及相应依赖。

项目实体：课程信息、画幅、voice、approvals、sources、scenes。每镜narration、leadIn、gapAfter、duration、audio、layers；audio含text、signature、sha256、duration、provenance和可选cues。图层拥有位置尺寸及keyframes。界面修改尺寸时按比例缩放相应关键帧值，修改位置时平移相应关键帧坐标；用户可直接编辑关键帧JSON。

保存HTML先读取当前全部引用素材，内嵌当前工程和当前renderer/editor代码；失败时不下载残缺文件。JSON导出同样内嵌素材，可独立导回。保存到工程目录先materialize导入数据，所有新素材落入交付目录，再构建HTML。文件浏览器的默认下载目录由浏览器控制；本地服务导出MP4默认写根目录，前端不能承诺绕过浏览器目录权限。

项目自带runtime脚本与模板，离开原Skill目录也能运行。外部Python库、浏览器、模型/权重不捆绑；运行配置单独放本机，移机后doctor检测。启动入口可以用KTV_PYTHON指定解释器，也可读取runtime.settings.json中的python。

原有课程使用不同字段时，先 `project.py migrate --source ... --out <新文件夹>` 复制迁移，旧项目保持不变。迁移不能完整移植自定义绘图代码，须手工适配并审查，避免把“数据可读”误报“画面完全一致”。
