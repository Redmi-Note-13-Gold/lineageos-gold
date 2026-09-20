# 目录与环境

## 源码仓库

```text
lineageos-gold/
├── README.md                 当前入口
├── device/xiaomi/gold/       设备配置、init、overlay、HAL、SELinux、提取配方
├── vendor/xiaomi/gold/ims/   IMS 集成源码与兼容输入说明
├── manifests/               固定 Android 项目提交
├── patches/                 平台补丁及 series.json
├── firmware/                Global/CN 官方输入锁
├── tools/                   恢复、提取、构建、产物验证
│   └── host/                科研机入口及可选 Soong 宿主补丁
├── tests/                   主机工具测试
├── docs/                    当前最终文档
│   └── releases/CN-R1.md    已发布 CN 版本最终说明
├── validation/              最终构建/安装/实机证据与本轮审查摘要
├── archive/hybrid/          v1 Python 参考代码；不参与当前构建
├── LICENSES/
└── NOTICE.md
```

中间迁移、调试、失败尝试文档和重复的中间 JSON 已从当前检出移除，历史由 Git 保存。源码仓库不保存原厂闭源文件、用户日志或密钥。

## 科研机

```text
/srv/build/
├── build-gold.sh                         统一构建与验证入口（指向项目脚本）
├── lineage-23.2-gold/                    overlay lower，迁入的 Android 基础树
├── ccache-gold-betterr/                  可复用编译缓存
├── stock-rom/                           官方输入归档
├── logs/                                宿主构建日志
├── build-jobs/                          构建任务记录
├── home/                                goldbuild 的现有工作环境
└── migration/gold-architecture-20260914/
    ├── project/                         本项目主线 Git 仓库
    ├── source/                          当前挂载的可写 Android 源码
    │   └── out-gold-standard/           唯一日常增量输出
    ├── source-upper/                    overlay 修改层
    ├── source-work/                     overlay 工作目录
    ├── source-out/                      迁移保留目录，不是日常 OUT_DIR
    ├── vendor/                          提取原料和已有生成输入
    └── history/                         已结束实验、诊断脚本及迁移过程记录
```

`source` 是 overlay 挂载点；当前 lower/upper/work 路径仍是系统挂载依赖，不移动或当成重复文件删除。`vendor` 及历史目录可能包含私有厂商输入和设备证据，不同步到公开源码仓库。目录整理采用同盘移动，路径映射存于 `history/layout-moves-20260920.json`。

实时初查：8 vCPU，系统可见约 14 GiB RAM、23 GiB swap；数据盘 344 GiB，约 52 GiB 可用；构建进程空闲。后续磁盘/进程状态以现场读取为准。
