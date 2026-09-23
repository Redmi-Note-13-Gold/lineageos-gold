# 更新策略

当前维护 Global OS3.0.5.0.VNQMIXM / LineageOS 23.2 的完整 A/B OTA。尚未启用自动更新源，也未完成当前基线的保数据升级、快照合并和回退验收。

- 第一阶段只验证标准构建生成的完整 ZIP，同设备、同布局、同签名基线升级。
- CN R1 到 Global 属于跨基线迁移，不能承诺保数据；已发布 CN 包的最终安装说明独立保留在 [releases/CN-R1.md](releases/CN-R1.md)。
- 日常更新不清除 data/metadata，不使用 wipe-super，不强制切槽或重刷两槽启动链。错误码本身不能证明需要重建布局。
- 后续接入现有 Lineage Updater；遵循 manifest 锁定版本的实际协议。服务器、元数据 URL 和发行密钥流程未部署时，不提供虚构更新入口。
- 当前开发包使用测试证书；正式发布需独立的 APK/APEX、OTA/payload、AVB 签名与信任链验证。

包内不含 wipe/downgrade 标志只是必要条件。安装成功以 Recovery 最终结果为准，之后仍需验证解密、用户数据、再次进入 Recovery、Virtual A/B 合并及硬件。当前证据见 [STATUS](STATUS.md)。
