# 上游版本与溯源锁定

审查日期：2026-10-12（北京时间）。

| 项目 | 锁定值 |
| --- | --- |
| 上游组织/仓库 | `AdvancedPhotonSource/GSAS-II` |
| 官方源码 | https://github.com/AdvancedPhotonSource/GSAS-II |
| Git 提交 | `2b4aba1bc44de63a3da9d4495944c3b99e389399` |
| 提交页面 | https://github.com/AdvancedPhotonSource/GSAS-II/commit/2b4aba1bc44de63a3da9d4495944c3b99e389399 |
| 该提交源码包 | https://github.com/AdvancedPhotonSource/GSAS-II/archive/2b4aba1bc44de63a3da9d4495944c3b99e389399.tar.gz |
| `pyproject.toml` 包版本 | `2.0.0` |
| Python 要求 | `>=3.10` |
| 上游许可文件 | https://github.com/AdvancedPhotonSource/GSAS-II/blob/2b4aba1bc44de63a3da9d4495944c3b99e389399/LICENSE |

上游网站、安装器和 Python 包可能采用不同的版本/修订号；为避免歧义，本项目始终以完整 Git SHA 表示第一阶段基线。切换上游版本必须同步更新许可审查、依赖审查、样例哈希和数值基准。

复现方式：

```text
git clone https://github.com/AdvancedPhotonSource/GSAS-II.git
cd GSAS-II
git checkout 2b4aba1bc44de63a3da9d4495944c3b99e389399
git rev-parse HEAD
```

社区同名项目排查：2026-10-12 检查 GitCode `OpenHarmonyPCDeveloper` 的公开仓库列表（分页结果 428 个名称），未发现 GSAS-II 同名仓库。此检查不涵盖私有仓库、尚未批准的建仓申请或后续新增仓库；提交申请前应重新检查。

