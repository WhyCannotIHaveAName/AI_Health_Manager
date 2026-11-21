# 营养数据来源

本目录的 `foods.json` 包含 USDA FoodData Central **SR Legacy April 2018** 发布集的7,793项食物。原始发布文件在 FoodData Central 中的 publication_date 可为2019年，发布集名称沿用 April 2018。

- 发布方：U.S. Department of Agriculture, Agricultural Research Service
- 入口：https://fdc.nal.usda.gov/download-datasets/
- 原始 CSV ZIP：https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_csv_2018-04.zip
- 下载验证日期：2026-11-21
- 原始 ZIP SHA-256：`b80817294b8850530aaedf2e515c02593b1824f763a0ff356e5c2081643e6fd0`
- 许可：CC0-1.0 / public domain，归属 USDA FoodData Central。官方说明：https://fdc.nal.usda.gov/

保留 FDC ID、英文描述及每100g可食部的六种营养值：1008 Energy (kcal)、1003 Protein (g)、1004 Total lipid/fat (g)、1005 Carbohydrate by difference (g)、1079 Fiber (g)、1093 Sodium (mg)。原表缺失为 JSON null，不补零。原始 ZIP 不随程序分发。

`aliases.json` 是本项目编写的中文检索别名，不是中国食物成分表。别名保留生熟状态和重要配方差异，营养值始终来自对应 USDA 编号。中式混合菜需要拆分食材，并由用户检查配方、油糖与份量；无法匹配时使用包装标签或保留未知。

重建：下载上述官方 ZIP 后执行：

```powershell
python scripts/build_food_data.py path/to/usda.zip data/foods.json
```

重建器会保留原始档案的 SHA-256。更新数据集时需要同时复核中文别名和相关计算测试。
