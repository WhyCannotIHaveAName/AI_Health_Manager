# Build 栖衡 Windows health manager with DeepSeek meal analysis

仓库原先只有项目说明。此改动增加可独立运行的中文 Windows 桌面应用，支持体重、睡眠、活动、饮水、文字/照片饮食记录和最近14天的 AI 健康回顾。

饮食分析采用“可靠来源优先、智能估算兜底”：内置7,793项USDA食物，AI检索完整库；品牌/条码查询Open Food Facts公开商品标签，无匹配时估算常见配方。显示来源链接、估算依据、范围和补齐字段，支持g/ml。旧餐食可一键补算缺失营养，确认后才更新，已知营养及原数量保持。工作量与后训练取舍见 `docs/nutrition-design.md`。

本地SQLite存储；API Key可仅本次使用或通过Windows DPAPI加密保存。上传图片重新编码去除EXIF。导出/导入JSON不包含密钥。AI请求由用户主动触发，可预览近期摘要，无遥测或自动重试。

验证：本机Win10 x64的34项单元测试、六页面Tk烟雾测试、冻结exe TLS/DPAPI/HTTPS检查通过。公开商品标签读取与安装版真实DeepSeek合成餐单分析通过，合成草稿不保存。提供Windows CI构建产物；Win11、真实照片与餐食营养准确率待进一步验收，程序暂未签名。

本PR保持Draft，待用户审核后再合并到main。
