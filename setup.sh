#!/usr/bin/env bash
# kb-sync 一键安装脚本
# 用法: bash setup.sh

set -euo pipefail

# ─── 颜色定义 ───
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC}   $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
err()   { echo -e "${RED}[ERR]${NC}  $*"; }

# ─── 路径定义 ───
SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DST="${HOME}/.claude/skills/kb-sync"
SETTINGS="${HOME}/.claude/settings.json"
KB_SYNC_DIR="${HOME}/.kb-sync"

# ─── Step 1: 检查 Claude Code ───
info "检查 Claude Code 环境..."
if ! command -v claude &> /dev/null; then
    err "未找到 claude 命令。请先安装 Claude Code: https://claude.ai/code"
    exit 1
fi
ok "Claude Code 已安装 ($(claude --version 2>/dev/null | head -1))"

# ─── Step 2: 安装 Skill ───
info "安装 kb-sync skill..."
if [ -d "$SKILL_DST" ] && [ "$SKILL_SRC" != "$SKILL_DST" ]; then
    warn "已存在 ${SKILL_DST}，备份为 ${SKILL_DST}.bak"
    mv "$SKILL_DST" "${SKILL_DST}.bak.$(date +%s)"
fi

if [ "$SKILL_SRC" != "$SKILL_DST" ]; then
    mkdir -p "$(dirname "$SKILL_DST")"
    cp -R "$SKILL_SRC" "$SKILL_DST"
fi
chmod +x "${SKILL_DST}/scripts/hook_runner.py"
ok "Skill 已安装到 ${SKILL_DST}"

# ─── Step 3: 安装 Python 依赖 ───
info "安装 Python 依赖..."
if python3 -c "import anthropic" 2>/dev/null; then
    ok "anthropic SDK 已安装"
else
    warn "anthropic SDK 未安装，正在安装..."
    if python3 -m pip install anthropic -q; then
        ok "anthropic SDK 安装成功"
    else
        err "anthropic SDK 安装失败，请手动运行: python3 -m pip install anthropic"
        exit 1
    fi
fi

# ─── Step 4: 检查 API Key ───
info "检查 API Key..."
if [ -n "${ANTHROPIC_API_KEY:-}" ] || [ -n "${ANTHROPIC_AUTH_TOKEN:-}" ]; then
    ok "检测到 API Key 环境变量"
else
    warn "未检测到 ANTHROPIC_API_KEY 或 ANTHROPIC_AUTH_TOKEN"
    echo "       请确保 Claude Code 已配置 API Key，skill 将复用 Claude Code 的环境变量。"
    echo "       配置方式: 在 ~/.claude/settings.json 的 env 字段中添加:"
    echo "         \"ANTHROPIC_AUTH_TOKEN\": \"your-key-here\""
fi

# ─── Step 5: 自动注入 Hooks ───
info "配置 Claude Code Hooks..."

# 生成 hooks 配置片段
read -r -d '' HOOKS_JSON << 'HOOKS_EOF' || true
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --session-start"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --session-end"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --prompt-submit"
          }
        ]
      }
    ]
  }
}
HOOKS_EOF

if [ ! -f "$SETTINGS" ]; then
    # 新建 settings.json
    mkdir -p "$(dirname "$SETTINGS")"
    echo "$HOOKS_JSON" > "$SETTINGS"
    ok "已创建 ${SETTINGS} 并注入 hooks"
else
    # 备份
    cp "$SETTINGS" "${SETTINGS}.bak.$(date +%s)"

    # 检查是否已存在 kb-sync hooks
    if grep -q "kb-sync/scripts/hook_runner.py" "$SETTINGS" 2>/dev/null; then
        warn "settings.json 中已存在 kb-sync hooks，跳过注入"
    else
        # 合并：如果已有 hooks 字段，追加；否则新建
        python3 -c "
import json, sys

with open('${SETTINGS}', 'r', encoding='utf-8') as f:
    data = json.load(f)

# kb-sync hooks 定义
kb_hooks = {
    'SessionStart': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --session-start'}]}],
    'SessionEnd':   [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --session-end'}]}],
    'UserPromptSubmit': [{'matcher': '', 'hooks': [{'type': 'command', 'command': 'python3 ~/.claude/skills/kb-sync/scripts/hook_runner.py --prompt-submit'}]}]
}

if 'hooks' not in data:
    data['hooks'] = {}

for key, value in kb_hooks.items():
    if key not in data['hooks']:
        data['hooks'][key] = value
    else:
        # 检查是否已有 kb-sync 命令
        existing = data['hooks'][key]
        already_has = any(
            h.get('type') == 'command' and 'kb-sync' in h.get('command', '')
            for item in existing
            for h in item.get('hooks', [])
        )
        if not already_has:
            existing.extend(value)

with open('${SETTINGS}', 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print('已合并 hooks 到 settings.json')
" || {
            err "合并 settings.json 失败，已备份到 ${SETTINGS}.bak.*"
            exit 1
        }
        ok "已合并 hooks 到 ${SETTINGS}"
    fi
fi

# ─── Step 6: 初始化全局配置 ───
info "初始化全局配置..."
mkdir -p "$KB_SYNC_DIR"

if [ ! -f "${KB_SYNC_DIR}/config.json" ]; then
    python3 -c "
import json, os

default_config = {
    'paths': {
        'knowledge_base': os.path.expanduser('~/知识库'),
        'clips_dir': '01-Raw',
        'wiki_dir': '02-Wiki',
        'concepts_dir': '概念',
        'figures_dir': '人物',
        'projects_dir': '项目',
        'tools_dir': '工具',
        'staging_dir': '待整理',
        'templates_dir': 'templates'
    },
    'triggers': {
        'pre_exit': True,
        'keywords': ['结束对话', 'bye', 'quit', '先这样', '今天就到这'],
        'manual_command': True
    },
    'filters': {
        'min_confidence': 0.7,
        'max_entries_per_session': 10,
        'skip_code_only_sessions': True
    },
    'output': {
        'default_category': 'staging',
        'date_in_filename': True,
        'include_raw_context': True
    },
    'remedy': {
        'check_on_startup': True,
        'preview_before_sync': False
    }
}

kb_dir = os.path.expanduser('~/.kb-sync')
os.makedirs(kb_dir, exist_ok=True)

config_path = os.path.join(kb_dir, 'config.json')
if not os.path.exists(config_path):
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(default_config, f, ensure_ascii=False, indent=2)
    print('已创建默认 config.json')
else:
    print('config.json 已存在，跳过')

state_path = os.path.join(kb_dir, 'state.json')
if not os.path.exists(state_path):
    with open(state_path, 'w', encoding='utf-8') as f:
        json.dump({
            'last_synced_session': None,
            'last_synced_at': None,
            'pending_session': None,
            'processed_clips': [],
            'synced_files': []
        }, f, ensure_ascii=False, indent=2)
    print('已创建默认 state.json')
else:
    print('state.json 已存在，跳过')
"
    ok "全局配置已初始化"
else
    ok "全局配置已存在"
fi

# ─── Step 7: 验证 ───
info "验证安装..."
if python3 "${SKILL_DST}/scripts/hook_runner.py" --status &>/dev/null; then
    ok "hook_runner.py 可正常执行"
else
    warn "hook_runner.py --status 执行异常，可能需要检查 Python 环境"
fi

# ─── 完成 ───
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║            kb-sync 安装完成                                  ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
ok "Skill 路径: ${SKILL_DST}"
ok "配置路径: ${KB_SYNC_DIR}"
ok "Hooks 配置: ${SETTINGS}"
echo ""
info "使用方式:"
echo "  /kb-sync          手动同步当前对话到知识库"
echo "  /kb-sync --status 查看同步状态"
echo "  /kb-sync --setup  重新运行初始化设置"
echo ""
warn "注意:"
echo "  1. 首次使用前请确认 ~/.claude/settings.json 中已配置 API Key"
echo "  2. 知识库默认路径: ~/知识库"
echo "  3. 如需更改路径，编辑 ${KB_SYNC_DIR}/config.json"
