# 测试样例与数值基准

五个样例逐字节复制自锁定提交的 `tests/testinp/`，本仓库路径为 `tests/fixtures/`。测试主题为 PbSO4 粉末衍射数据读取、相导入与 Rietveld 精修。上游用例：[`tests/test_scriptref.py`](https://github.com/AdvancedPhotonSource/GSAS-II/blob/2b4aba1bc44de63a3da9d4495944c3b99e389399/tests/test_scriptref.py)。

| 文件 | 字节 | SHA-256 |
| --- | ---: | --- |
| `PBSO4.XRA` | 49445 | `CA2DA02FC7E17D2FC912DE22A979F8101BA6140F2E8104F9D3AA64F030CA58BB` |
| `INST_XRY.PRM` | 794 | `E59413059BC3B12A51F1C6EEBC5D581470320D05A31F11A41DBB32E16D1D16B9` |
| `PBSO4.CWN` | 24190 | `59462BA6D7C72C9800B0B6BF41903F9933ED5AC5ADAB101D27022D5D25CF18BA` |
| `inst_d1a.prm` | 971 | `A1031174A9B509F889377752F5C095A1DAD49A25FB0A72C057F184F7B321FCEA` |
| `PbSO4-Wyckoff.cif` | 1569 | `22CBA0B64FB6BF89178FE828FDF63570BFFEBED1485313E78C50C2918A47A970` |

上游测试在五个精修阶段记录两个直方图的 `Rwp`：

| 阶段 | h1 | h2 |
| --- | ---: | ---: |
| 精修前 | 96.681098 | 99.748994 |
| 比例因子与背景 | 45.811562 | 17.864834 |
| 晶胞 | 32.475886 | 15.02412 |
| 微应变等参数 | 13.40599 | 6.36131 |
| 择优取向 | 13.16483 | 6.38230 |

数值来自上游测试文件，并非本项目已经在 HarmonyOS PC 上复测的结果。上游测试对 Rwp 使用相对容差 `1e-4`；移植验收应先在对应 Python/NumPy/SciPy 版本的桌面基线环境复测，再在鸿蒙设备上对比完整输出及残差，必要时明确合理的跨平台容差。不得只凭程序启动判定科学计算正确。

第一阶段校验命令：`powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\Verify-Fixtures.ps1`。它只校验文件完整性，不运行 GSAS-II。

