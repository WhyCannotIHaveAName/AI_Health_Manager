# Build 栖衡 Windows health manager with DeepSeek meal analysis

仓库原先只有项目说明。此改动增加可独立运行的中文 Windows 桌面应用，支持体重、睡眠、活动、饮水、文字/照片饮食记录和最近14天的 AI 健康回顾。

饮食分析采用 DeepSeek 识别名称与份量、USDA数据库计算、用户确认保存的流程。内置7,793项食物和50个中文检索别名；未知匹配保留缺失状态，支持包装标签覆盖，不使用模型编造的营养值。工作量与后训练取舍见 `docs/nutrition-design.md`。

本地SQLite存储；API Key可仅本次使用或通过Windows DPAPI加密保存。上传图片重新编码去除EXIF。导出/导入JSON不包含密钥。AI请求由用户主动触发，可预览近期摘要，无遥测或自动重试。

验证：本机Win10 x64的16项单元测试、六页面实际Tk烟雾测试、独立exe构建与安装启动检查通过。提供Windows CI构建产物。Win11独立设备、真实付费API和餐食识别准确率待用户验收，程序暂未签名。

本PR保持Draft，待用户审核后再合并到main。
