# 栖衡 · AI Health Manager

在 Windows 10 / Windows 11 x64 上运行的健康记录桌面应用。使用你自己的 DeepSeek API Key，数据默认保存在本机。

## 功能

- 体重、睡眠时长、活动分钟和饮水量记录；支持补记日期、备注、修改和删除。
- 饮食支持自然语言、照片和手动添加；识别后核对食物、重量与重量范围，再确认保存。
- 内置 **7,793 项 USDA SR Legacy 食物**，可离线查找。AI会生成英文检索词，在完整数据库中寻找候选；也支持50个常见中文别名。
- 品牌或条码优先查询 Open Food Facts 公开商品标签；数据库无合适匹配时自动智能估算，区分精确数据、参考估算及估算补齐字段。
- 按每100g或100ml计算热量、蛋白质、脂肪、碳水、纤维与钠；显示来源链接、估算依据与范围。
- 今日概览、30天体重趋势、最近14天的 AI 健康回顾与鼓励。
- 本地 SQLite 存储，JSON 导入/导出；API Key 可仅本次使用或用 Windows DPAPI 加密保存。

## 使用

1. 打开 `AIHealthManager.exe`。打包版本无需安装 Python。
2. 在“设置与备份”填写自己的 DeepSeek API Key，点击保存。可先做少量计费的连接测试。
3. 在“身体记录”保存体重、睡眠等；睡眠日期按醒来当天填写。同日体重概览取最后一次，睡眠、活动和饮水取合计。
4. 在“饮食记录”描述这一餐或选择图片，点击“识别并计算营养”，核对列表中的食物与份量。可以在“修改/匹配”里填写条码查询公开商品标签，或手动填写包装上每100g/100ml的营养值。旧餐食点“补算缺失营养”，核对后保存，无需重新录入。
5. 在“健康回顾”预览最近14天摘要，再发送生成建议。未填写密钥时，离线记录、数据库、趋势和备份仍可使用。

照片在发送前缩放至最长1600像素并重新编码，去除 EXIF 元数据。原图不复制到数据目录，也不进入备份。仅点击识别、补算或生成建议才发送相关记录；没有后台自动上传、遥测或自动付费重试。

## 营养分析怎么实现

先查可匹配的数据库或商品标签，找不到时使用明确标注的智能估算。模型引用的数据库/商品编号必须存在于实际检索候选中，不能制造数据来源。营养不足的标签优先保留原数值，仅对缺失字段估算，并记录哪些字段来自估算。公开商品标签来自Open Food Facts社区收录，不保证等于当前包装；可点击来源核对品牌、口味与规格。

范围同时结合份量上下界与配方估计；AI估算的营养密度使用中心值的65%–140%作为提示范围，不是统计置信区间。g和ml分开记录，不自动当成相同密度。未能获得合理估算的项仍保留未知，避免以零代替未知。

中餐配方、油糖用量和可食部重量是主要误差来源。当前采用数据库检索、AI估算和用户修正，不训练新模型。实现取舍和后续评测见 [营养方案](docs/nutrition-design.md)。

## 从源码运行

需要 Python 3.12 x64（包含 Tcl/Tk）。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe run.py
```

```powershell
# 单元测试与实际 Tk 界面检查（后者会短暂打开测试窗口）
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m tests.gui_smoke

# 构建独立应用，再安装到当前用户目录，无需管理员权限
.\scripts\build.ps1 -Python .\.venv\Scripts\python.exe
.\scripts\install.ps1
```

构建产物为 `dist/AIHealthManager/`，需保留整个目录。`install.ps1 -InstallDir 'C:\Apps\AIHealthManager' -Portable` 可使用其他有写入权限的目录；便携模式数据保存在安装目录的 `userdata/`。普通模式为 `%LOCALAPPDATA%\AIHealthManager`。更新时先关闭应用，再运行安装脚本，已有数据不会被移除。移除程序目录即可卸载；健康数据与密钥需要另行保留或删除。

Windows 工作流执行测试并上传可下载的构建目录。目标平台为 Win10/Win11 x64；本机 Win10 已验证，Win11 待独立设备验收。当前版本未签名。文字饮食分析已通过安装版的真实API合成餐单验收；图片请求结构、异常路径和来源优先级有自动测试，真实餐食准确率仍需独立称重样本评测。

构建还会运行独立 exe 的 TLS、密钥加密和网络诊断。网络检查仅向官方接口发送虚构的无效密钥，预期收到401，不读取用户密钥或健康数据。`AIHealthManager.exe --diagnose` 可手动重复检查，结果写入同目录的 `diagnostics.json`。界面错误的本地诊断为 `userdata/last-error.json`（普通模式在数据目录），只包含异常类型、数字错误码和代码位置，不包含错误原文、密钥或健康内容。

## 数据与接口来源

- [USDA FoodData Central 下载](https://fdc.nal.usda.gov/download-datasets/)：SR Legacy April 2018，CC0。完整归属和重建方式见 [数据说明](data/SOURCES.md)。
- [DeepSeek 图片输入](https://api-docs.deepseek.com/guides/vision/)：首版使用 `deepseek-flash` + Chat Completions 图片块。
- [DeepSeek JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)：结构化结果经过本地校验。
- [Open Food Facts API](https://openfoodfacts.github.io/documentation/docs/Product-Opener/api/)：只读查询公开商品标签，使用兼容v2接口的营养字段。数据ODbL、单项内容DbCL，保留来源与许可说明，不把OFF数据混入随程序分发的USDA库。查商品只发送品牌或条码，不发送健康备注或DeepSeek密钥。

AI 回顾面向生活习惯，不作诊断或调整用药。健康数据存储为本机明文数据库；Windows 加密仅用于 API Key，导出的 JSON 也包含原始健康记录。
