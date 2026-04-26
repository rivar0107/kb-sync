---
name: kb-sync
description: |
  知识库自动同步系统。自动从 Claude Code 对话中提炼知识点，按主题分类写入知识库 Wiki；
  一键处理 Obsidian Web Clipper 同步到 01-Raw 的文章，提取概念/人物，建立双向链接。
  触发词：「同步知识库」「结束对话」「kb-sync」「/kb-sync」「process-clips」「/process-clips」
  场景：对话结束时自动触发，或手动运行 /kb-sync、/process-clips。
---

# kb-sync · 知识库自动同步

## 核心设计原则

1. **零配置启动**：首次运行自动检测或创建知识库结构
2. **路径可配置**：所有目录名、分类名均可自定义
3. **全局或项目级配置**：首次初始化可选择全局共享（`~/.kb-sync/`）或仅当前项目（`./.kb-sync/`）
4. **幂等同步**：同一内容多次同步不产生重复
5. **人在回路**：关键操作需要人类确认（创建新页面、覆盖已有内容）

## 执行入口

### 入口 1：对话同步（/kb-sync）

```
用户输入 /kb-sync
    ↓
Step 0: 检查是否已初始化
    ├─ 检查 ~/.kb-sync/config.json 是否存在
    ├─ 如果不存在，再检查 ./.kb-sync/config.json 是否存在
    ├─ 如果都不存在 → 提示用户运行 /kb-sync --setup 进行初始化
    └─ 如果存在 → 继续下一步
    ↓
Step 1: 读取 config.json，解析知识库路径
    ↓
Step 2: 读取 state.json，检查同步状态
    ↓
Step 2.5: 交互确认（人在回路）
    ├─ 如果存在 pending_session：
    │   向用户展示选择：
    │   "检测到待同步会话 [session_id]，是否同步到知识库？"
    │   ├─ 选项 A："同步" → 继续 Step 3（使用 pending_session 的 jsonl）
    │   └─ 选项 B："跳过" → 调用 StateManager.clear_pending_session()，输出"已跳过，该会话不再提醒"，结束流程
    └─ 如果不存在 pending_session，但当前最新会话也未同步：
        向用户展示选择：
        "当前会话尚未同步，是否同步？"
        ├─ 选项 A："同步" → 继续 Step 3
        └─ 选项 B："跳过" → 仅标记为已同步（不写入知识库），输出"已跳过"，结束流程
    ↓
Step 3: 调用 CLI 自动完成提炼和写入
    ├─ 先运行：`python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --preview`
    │   └─ 内部流程：
    │       1. 读取 pending_session 对应的 jsonl
    │       2. 调用 LLM（extract_dialogue Prompt）提炼知识点
    │       3. 过滤置信度 < 0.7 的条目
    │       4. 输出预览（标题、分类、confidence、摘要）
    ├─ 用户预览后确认写入 → 运行：`python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --sync`
    │   └─ 内部流程：
    │       1. 复用预览结果，调用 SyncEngine.write_note() 写入知识库
    │       2. 自动建立双向链接
    │       3. 更新 state.json（mark_session_synced）
    └─ 用户选择取消 → 结束流程（不写入，不标记为已同步）
    ↓
输出同步摘要（处理了 X 个概念、更新了 Y 个页面）
```

### 入口 2：文章处理（/process-clips）

```
用户输入 /process-clips
    ↓
Step 1: 读取 config.json，解析知识库路径
    ↓
Step 2: 扫描 01-Raw/ 目录，找出未处理的文章
    ↓
Step 3: 对每篇文章：
    ↓
    Step 3.1: 调用 process_article Prompt 提取概念/人物
    ↓
    Step 3.2: 检查概念/人物是否已存在于 Wiki
    ↓
    Step 3.3: 生成新页面或更新已有页面
    ↓
    Step 3.4: 建立双向链接
    ↓
Step 4: 更新 state.json，标记文章为已处理
    ↓
输出速览表格（核心论点、提取的概念、与已有资料的差异）
```

### 入口 3：首次初始化（/kb-sync --setup）

```
用户输入 /kb-sync --setup
    ↓
Step 1: 扫描当前目录，检测是否已有知识库
    ↓
Step 2: 询问用户配置模式
    ├─ 选项 A：全局共享模式（推荐）
    │   配置存放在 ~/.kb-sync/，所有项目共享同一个知识库
    │   知识库路径在 config.json 中以绝对路径存储
    ├─ 选项 B：项目级模式
    │   配置存放在 ./.kb-sync/，仅当前项目使用
    │   知识库路径以相对路径存储
    ↓
Step 3: 如果已有知识库 → 询问是否使用；如果没有 → 提供创建选项
    ↓
Step 4: 创建默认知识库结构（Karpathy 风格）
    ↓
Step 5: 生成默认模板（concept.md, figure.md），并在 Wiki 子目录下放置 _template.md 副本
    ↓
Step 6: 写入 config.json 和 state.json
    ↓
提示用户配置 .claude/settings.json 的 hook
```

**配置查找优先级**：
1. 优先使用当前项目目录下的 `./.kb-sync/`（项目级配置）
2. 如果项目级不存在，回退到用户主目录下的 `~/.kb-sync/`（全局配置）
3. 两者都不存在时，提示运行 `/kb-sync --setup` 进行初始化

## 辅助命令

- `/kb-sync --status`：查看同步状态（待同步会话、未处理文章数、已同步文件数、上次同步时间）
- `/kb-sync --rollback-last`：撤销上次同步
  ```
  Step 1: 列出上次同步的所有 Wiki 文件路径
  Step 2: 询问用户是否物理删除这些文件
  ├─ 确认删除 → 逐个删除物理文件 + 调用 StateManager.clear_synced_files()
  └─ 仅撤销记录 → 仅调用 StateManager.clear_synced_files()（保留物理文件）
  ```
- `/kb-sync --clips`：等同于 /process-clips

## Prompt 规范

### extract_dialogue（对话提炼）

**输入**：Claude Code 对话文本（User + Assistant 交互）

**输出格式**：JSON
```json
{
  "entries": [
    {
      "title": "知识点标题",
      "category": "概念/项目/人物/工具/未确定",
      "body": "核心要点描述（200-500字）",
      "tags": ["标签1"],
      "confidence": 0.92,
      "reason": "为什么值得保存"
    }
  ]
}
```

**保存标准**：概念定义、决策记录、技术知识点、流程步骤、灵感观点
**过滤标准**：闲聊、纯执行命令、重复内容
**约束**：confidence < 0.7 不输出，最多 10 个 entries

### classify（内容分类）

**输入**：文本摘要

**输出**：仅输出分类名称（单行）
```
概念 / 项目 / 人物 / 工具 / 未确定
```

### process_article（文章处理）

**输入**：一篇文章的完整 Markdown 内容

**输出格式**：JSON
```json
{
  "core_argument": "文章核心论点（一句话）",
  "concepts": [
    {
      "name": "概念名称",
      "action": "create/update",
      "summary": "概念定义和核心要点（200字以内）",
      "links": ["相关概念1"]
    }
  ],
  "figures": [
    {
      "name": "人物名称",
      "action": "create/update",
      "summary": "身份背景和核心观点"
    }
  ],
  "consensus": "与已有资料的共识",
  "differences": "与已有资料的差异",
  "next_steps": "建议下一步行动"
}
```
