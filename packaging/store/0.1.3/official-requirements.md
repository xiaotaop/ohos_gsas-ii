# 0.1.3 上架官方入口核对（2026-10-21）

- [华为：提交 HarmonyOS 应用](https://developer.huawei.com/consumer/cn/app/submit)：官方概览要求发布前测试、配置图标/截图等基本信息，并将应用打包为 APP 提交；审核资质以实际应用与账号的要求为准。本组的 0.1.3 APP 已签名，平台检测尚未执行。
- [工程级 build-profile](https://developer.huawei.com/consumer/cn/doc/doccenter-deveco-studio/ide-hmos-hvigor-build-profile-app)：产品级 assembleApp 与模块 HAP 区分；默认 APP 内为未独立签名模块，APP 外层签名。appWithSignedPkg 为额外 all 产物选项，本轮未启用。
- [华为：上架测试](https://developer.huawei.com/consumer/cn/doc/doccenter-testing/agc-help-cloudtest-releasetest-0000002289646673)：Release 签名包、应用所属账号和隐私声明/标签是相关测试前提；测试通过不保证平台审核通过。
- [官方应用配置入口](https://developer.huawei.com/consumer/cn/doc/app/agc-help-harmonyos-releaseapp-0000001914554900) 与 [发布流程入口](https://developer.huawei.com/consumer/cn/doc/app/agc-help-release-0000002235870050)：公开网页抓取未获得详细正文，未据此虚构 PC 截图比例/张数/大小规则。新名称原图为 3120×2080，仍需在已登录后台逐项对照当前提示；论坛建议不当作官方硬性规则。

账号实名/主体资质、可能适用的备案或授权材料、国家地区/定价/年龄分级均由实际账号持有人按平台表单确认；此文件不伪造资质、不预选未确认的商业信息。

## 隐私材料复核补充（2026-10-21）

- [华为：隐私测试](https://developer.huawei.com/consumer/cn/doc/doccenter-testing/agc-help-cloudtest-privacytest-0000002465035109)：检查隐私政策网址正常访问、应用内政策与标准化托管政策的一致性、数据目的/方式/范围及第三方组件披露等。政策正文和静态 HTML 完成不替代该测试，当前公开 APP 尚无平台检测结果。
- [GitHub 一般隐私声明](https://docs.github.com/zh/site-policy/privacy-policies/github-general-privacy-statement)：反馈采用 GitHub Issues 时，站点账号、访问及主动提交内容由 GitHub 按其政策处理；本应用政策明确公开反馈的范围与脱敏注意事项，不把 GitHub 当作本地计算必需的登录或数据上传服务。

本次检查应用管理入口时，原登录会话失效并跳转华为账号登录页；尚未核对任何需登录的实际版本表单，也未上传 APP 或提交审核。分类、价格、分级、强制联系方式及托管可用性仍按实际表单确认。
