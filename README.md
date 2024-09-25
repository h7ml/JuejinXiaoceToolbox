# 掘金小册下载器

## 项目简介

掘金小册下载器是一个用 Python 编写的工具，用于将掘金平台上的小册内容下载并转换为 Markdown 格式。这个工具可以帮助用户离线阅读和管理他们购买的掘金小册内容。

## 主要功能

- 自动登录掘金平台
- 获取用户已购买的小册列表
- 下载小册内容并转换为 Markdown 格式
- 可选择性地下载和保存文章中的图片
- 支持异步操作，提高下载效率
- 详细的日志记录，方便追踪下载过程
- 图形用户界面(GUI)支持，方便操作
- 支持将下载内容保存为多种格式(Markdown、HTML 等)
- 支持将下载内容压缩为 ZIP 文件

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/h7ml/JuejinXiaoceToolbox.git
cd JuejinXiaoceToolbox
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

## 使用方法

### 命令行界面

1. 复制 `config.template.yml` 为 `config.yml`，并填写您的掘金账号信息。

2. 运行主程序：

```bash
python main.py
```

### 开发环境

如果您正在开发环境中运行：

1. 运行 GUI 版本（默认）：

   ```bash
   python main.py
   ```

2. 运行命令行版本：
   ```bash
   python main.py --cli
   ```

## 配置说明

在 `config.yml` 文件中，您可以设置以下选项：

- `cookie`: 掘金账号的 Cookie
- `save_dir`: 下载文件的保存目录
- `fetch_book_ids_online`: 是否在线获取小册列表
- `overwrite_existing`: 是否覆盖已存在的文件
- `save_images_locally`: 是否将文章中的图片保存到本地
- `book_ids`: 要下载的小册 ID 列表
- `resume_download`: 是否恢复上次的下载进度
- `save_format`: 保存格式(markdown、html 等)
- `compress_to_zip`: 是否将下载内容压缩为 ZIP 文件

请根据您的需求修改这些配置项。

## 项目结构

```
JuejinXiaoceToolbox/
├── .github/
│ └── workflows/ # GitHub Actions 工作流配置
│ ├── build_exe.yml # 构建可执行文件的工作流
│ └── scrape-and-upload.yml # 爬取和上传数据的工作流
├── plugins/
│ └── storage_plugin.py # 存储插件，用于数据持久化
├── resources/
│ └── version.txt # 存储项目版本信息
├── scripts/
│ └── build.py # 项目构建脚本
├── src/ # 源代码目录
│ ├── init.py
│ ├── gui.py # 图形用户界面实现
│ ├── juejin_downloader.py # 掘金小册下载器核心逻辑
│ └── utils.py # 实用工具函数
├── utils/ # 通用工具目录
│ ├── init.py
│ ├── config.py # 配置文件处理
│ └── logger.py # 日志处理
├── .gitignore # Git 忽略文件配置
├── LICENSE # 项目许可证
├── README.md # 项目说明文档
├── build_config.yml # 构建配置文件
├── config.template.yml # 配置文件模板
├── main.py # 主程序入口
└── requirements.txt # 项目依赖列表
```

## 开发

如果您想为项目做出贡献，请遵循以下步骤：

1. Fork 本仓库
2. 创建您的特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交您的更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 打开一个 Pull Request

## 构建

要创建独立的可执行文件，请按照以下步骤操作：

1. 确保已安装所有依赖：

```bash
pip install -r requirements.txt
```

2. 修改`build_config.yml`配置。

3. 运行构建脚本：

```bash
python scripts/build.py
```

如果需要指定自定义配置文件，可以使用 `--config` 参数：

```bash
python scripts/build.py --config custom_build_config.yml
```

构建完成后，可执行文件将位于 `dist` 目录中。

## GitHub Actions

本项目使用 GitHub Actions 进行自动化构建和发布。每当创建一个新的标签时，都会触发构建过程并创建一个新的发布版本。

## 注意事项

- 请确保您有合法的权限下载和使用小册内容。
- 下载的内容仅供个人学习使用，请勿传播或用于商业用途。
- 使用本工具时请遵守掘金平台的使用条款。

## 贡献

欢迎提交 issues 和 pull requests 来帮助改进这个项目。

## 许可证

本项目采用 MIT 许可证。详情请见 [LICENSE](LICENSE) 文件。

## 联系方式

如果您有任何问题或建议，请通过以下方式联系我们：

- 项目 Issues: [https://github.com/h7ml/JuejinXiaoceToolbox/issues](https://github.com/h7ml/JuejinXiaoceToolbox/issues)

## 致谢

感谢所有为这个项目做出贡献的开发者和用户。
