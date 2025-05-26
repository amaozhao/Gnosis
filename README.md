# Gnosis

智能字幕翻译系统，基于 Agno 框架和大语言模型实现高质量的翻译、审核和改进流程。

## 项目概述

Gnosis 是一个专注于字幕翻译的智能系统，它使用 Agno 框架的团队组件，整合了翻译、审核和改进三个关键步骤，确保翻译结果的高质量和准确性。系统采用协调模式（Coordinate Mode），由团队领导者分解任务并分配给专门的智能体，形成一个完整的翻译流水线。

### 主要特点

- **智能体团队协作**：使用 Agno 框架的团队组件，实现翻译、审核和改进的无缝协作
- **高质量翻译**：通过多步骤流程确保翻译质量，包括初步翻译、质量审核和针对性改进
- **批量处理能力**：支持批量处理多个字幕文件，提高工作效率
- **灵活的配置**：支持多种语言模型和配置选项，可根据需求进行调整
- **命令行界面**：提供简单易用的命令行工具，方便集成到现有工作流程中

## 系统架构

### 智能体团队

Gnosis 使用 Agno 框架的团队组件，由三个核心智能体组成：

1. **翻译专家 (Translator)**：负责初步翻译，将原始字幕从源语言翻译到目标语言
2. **审核专家 (Reviewer)**：分析翻译质量，识别问题并提供改进建议
3. **改进专家 (Improver)**：根据审核反馈优化翻译结果，提高翻译质量

这三个智能体在 `TranslationTeam` 类的协调下协同工作，形成一个完整的翻译-审核-改进流程。

### 工作流程

1. 接收原始字幕内容
2. 翻译专家进行初步翻译
3. 审核专家评估翻译质量，返回 JSON 格式的审核结果
4. 如有问题，改进专家根据审核反馈优化翻译
5. 返回最终高质量翻译结果

## 安装与配置

### 环境要求

- Python 3.9+
- 依赖包：agno, httpx, pydantic, tqdm

### 安装步骤

1. 克隆仓库：
   ```bash
   git clone https://github.com/yourusername/gnosis.git
   cd gnosis
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 配置环境变量：
   创建 `.env` 文件并设置必要的 API 密钥：
   ```
   DEEPSEEK_API_KEY=your_api_key_here
   OPENAI_API_KEY=your_api_key_here
   ```

## 使用指南

### 命令行工具

Gnosis 提供了两个命令行工具：

1. `cli.py`：命令行工具，使用 `TranslationTeam` 类提供完整的翻译-审核-改进流程

### 基本翻译

```bash
# 翻译文本
python cli_team.py translate --text "Hello, this is a test."

# 翻译文件
python cli_team.py translate --file input.srt --output translated.srt

# 指定语言
python cli_team.py translate --file input.srt --source en --target zh --output translated.srt
```

### 批量翻译

```bash
# 批量翻译目录中的所有 .srt 文件
python cli_team.py batch --input-dir ./subtitles --output-dir ./translated

# 指定语言和文件扩展名
python cli_team.py batch --input-dir ./subtitles --output-dir ./translated --source en --target fr --extension txt
```

## 开发指南

### 项目结构

```
gnosis/
├── gnosis/                  # 主代码目录
│   ├── agents/             # 智能体模块
│   │   ├── improver.py     # 改进智能体
│   │   ├── reviewer.py     # 审核智能体
│   │   ├── team.py         # 翻译团队
│   │   └── translator.py   # 翻译智能体
│   ├── core/               # 核心模块
│   │   ├── config.py       # 配置管理
│   │   └── logger.py       # 日志管理
│   └── services/           # 服务模块
│       └── subtitle.py     # 字幕处理服务
├── tests/                  # 测试目录
├── cli.py                  # 命令行工具
├── cli_team.py             # 新的命令行工具（使用团队）
└── requirements.txt        # 依赖列表
```

### 扩展指南

#### 添加新的智能体

1. 在 `gnosis/agents/` 目录下创建新的智能体模块
2. 使用 `agno.agent.Agent` 类创建智能体实例
3. 在 `TranslationTeam` 类中集成新的智能体

#### 自定义翻译流程

可以通过修改 `TranslationTeam` 类中的 `translate` 方法来自定义翻译流程，例如添加预处理或后处理步骤。

## 贡献指南

欢迎贡献代码、报告问题或提出改进建议。请遵循以下步骤：

1. Fork 仓库
2. 创建功能分支：`git checkout -b feature/your-feature-name`
3. 提交更改：`git commit -m 'Add some feature'`
4. 推送到分支：`git push origin feature/your-feature-name`
5. 提交 Pull Request

## 许可证

[MIT License](LICENSE)