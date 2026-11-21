# 栖衡 · AI Health Manager

在 Windows 10 / Windows 11 x64 上运行的健康记录桌面应用。使用你自己的 DeepSeek API Key，数据默认保存在本机。

## 功能

- 体重、睡眠时长、活动分钟和饮水量记录；支持补记日期、备注、修改和删除。
- 饮食支持自然语言、照片和手动添加；识别后核对食物、重量与重量范围，再确认保存。
- 内置 **7,793 项 USDA SR Legacy 食物**，可离线查找。50 个中文检索别名覆盖常见食材，其余使用英文关键词搜索。
- 按食物每100g数据计算热量、蛋白质、脂肪、碳水、纤维与钠；显示数据来源与缺失项。
- 今日概览、30天体重趋势、最近14天的 AI 健康回顾与鼓励。
- 本地 SQLite 存储，JSON 导入/导出；API Key 可仅本次使用或用 Windows DPAPI 加密保存。

## 使用

1. 打开 `AIHealthManager.exe`。打包版本无需安装 Python。
2. 在“设置与备份”填写自己的 DeepSeek API Key，点击保存。可先做少量计费的连接测试。
3. 在“身体记录”保存体重、睡眠等；睡眠日期按醒来当天填写。同日体重概览取最后一次，睡眠、活动和饮水取合计。
4. 在“饮食记录”描述这一餐或选择图片，点击“发送给 DeepSeek 识别”，核对列表中的食物与份量。可以手动匹配数据库或填写包装上每100g的营养值。
5. 在“健康回顾”预览最近14天摘要，再发送生成建议。未填写密钥时，离线记录、数据库、趋势和备份仍可使用。

照片在发送前缩放至最长1600像素并重新编码，去除 EXIF 元数据。原图不复制到数据目录，也不进入备份。仅点击识别或生成建议才发送相关记录；没有后台自动上传、遥测或自动付费重试。

## 营养分析怎么实现

AI 负责解析食物名称和估计份量，数据库负责数值，用户负责确认。模型只能引用候选数据库编号；未知编号不会变成模型编造的营养值。无匹配时允许保存，界面明确显示“待补充”，汇总显示缺失数量。份量范围只表示重量的不确定性，不代表经过统计校准的营养置信区间。

中餐配方、油糖用量和可食部重量是主要误差来源。首版使用数据库检索与用户修正，不训练新模型。实现取舍和后续评测见 [营养方案](docs/nutrition-design.md)。

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

Windows 工作流执行测试并上传可下载的构建目录。目标平台为 Win10/Win11 x64；本机 Win10 已验证，Win11 待独立设备验收。首版未签名。真实付费 API 与餐食识别准确率尚未完成实测，接口契约和异常路径已用模拟响应验证。

## 数据与接口来源

- [USDA FoodData Central 下载](https://fdc.nal.usda.gov/download-datasets/)：SR Legacy April 2018，CC0。完整归属和重建方式见 [数据说明](data/SOURCES.md)。
- [DeepSeek 图片输入](https://api-docs.deepseek.com/guides/vision/)：首版使用 `deepseek-flash` + Chat Completions 图片块。
- [DeepSeek JSON 输出](https://api-docs.deepseek.com/guides/json_mode/)：结构化结果经过本地校验。

AI 回顾面向生活习惯，不作诊断或调整用药。健康数据存储为本机明文数据库；Windows 加密仅用于 API Key，导出的 JSON 也包含原始健康记录。
