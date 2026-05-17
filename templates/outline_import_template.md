# 大纲导入模板

将此提示词和模板一起发给大模型（如 DeepSeek Chat、ChatGPT 等），让它从你的小说中提取结构化大纲，然后将输出的 JSON 复制到 Dramatica-Flow 中导入。

---

## 提示词（直接发给大模型）

```
你是一位专业的小说结构分析师。请根据我提供的小说内容，提取以下两种大纲 JSON。

## 要求
1. 故事大纲：将小说划分为若干序列（每个序列覆盖一段完整的情节弧），标注每个序列的戏剧功能
2. 章节大纲：为每一章生成标题、摘要、节拍序列（2-3个beats）、情感弧线
3. dramatic_function 只能使用以下值：setup / inciting / turning / midpoint / crisis / climax / reveal / decision / consequence / transition
4. 如果小说没有明确的章节分割，请按情节节点自行划分章节

## 输出格式
请分别输出两个 JSON：

### 第一个 JSON：故事大纲
{粘贴下方的故事大纲模板}

### 第二个 JSON：章节大纲
{粘贴下方的章节大纲模板}
```

---

## 故事大纲 JSON 模板

```json
{
  "id": "outline_001",
  "title": "书名",
  "logline": "一句话概括全书：主角必须在XX前完成XX，但XX",
  "genre": "题材（玄幻/都市/科幻/言情/悬疑/历史/其他）",
  "sequences": [
    {
      "id": "seq_001",
      "number": 1,
      "act": 1,
      "summary": "序列摘要（50-100字，概括这个序列发生了什么）",
      "narrative_goal": "这个序列要完成的叙事任务",
      "dramatic_function": "setup",
      "key_events": ["关键事件1", "关键事件2"],
      "estimated_scenes": 10,
      "end_hook": "这个序列结尾的悬念钩子（一句话，要有画面感）"
    },
    {
      "id": "seq_002",
      "number": 2,
      "act": 1,
      "summary": "...",
      "narrative_goal": "...",
      "dramatic_function": "inciting",
      "key_events": ["..."],
      "estimated_scenes": 8,
      "end_hook": "..."
    }
  ],
  "emotional_roadmap": [
    {"chapter": "1", "target_emotion": "平静"},
    {"chapter": "50", "target_emotion": "愤怒"},
    {"chapter": "100", "target_emotion": "坚定"},
    {"chapter": "200", "target_emotion": "释然"}
  ]
}
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | 是 | 大纲唯一标识，任意字符串即可 |
| `title` | 是 | 书名 |
| `logline` | 是 | 一句话概括核心冲突 |
| `genre` | 是 | 题材分类 |
| `sequences` | 是 | 序列数组 |
| `sequences[].id` | 是 | 序列ID，格式如 seq_001、seq_002 |
| `sequences[].number` | 是 | 序列序号，从1开始 |
| `sequences[].act` | 是 | 所属幕数：1（铺垫）、2（冲突）、3（结局） |
| `sequences[].summary` | 是 | 序列摘要 |
| `sequences[].narrative_goal` | 是 | 叙事目标 |
| `sequences[].dramatic_function` | 是 | 戏剧功能（见下方枚举值） |
| `sequences[].key_events` | 否 | 关键事件列表 |
| `sequences[].estimated_scenes` | 是 | 该序列预计覆盖的章节数 |
| `sequences[].end_hook` | 是 | 结尾悬念钩子 |
| `emotional_roadmap` | 否 | 全书情感路线图 |

### dramatic_function 枚举值

| 值 | 含义 | 适用场景 |
|----|------|----------|
| `setup` | 铺垫 | 建立角色/世界/规则 |
| `inciting` | 激励事件 | 打破平衡，推动主角行动 |
| `turning` | 转折点 | 方向改变，新信息/新冲突 |
| `midpoint` | 中点 | 承诺升级或假胜利 |
| `crisis` | 危机 | 最低点，一切似乎失败 |
| `climax` | 高潮 | 终极对决/最大冲突 |
| `reveal` | 揭示 | 关键信息揭示，改变认知 |
| `decision` | 抉择 | 角色做出关键选择 |
| `consequence` | 后果 | 行动的后果落地 |
| `transition` | 过渡 | 节奏调节，场景转换 |

---

## 章节大纲 JSON 模板

```json
[
  {
    "chapter_number": 1,
    "title": "第一章 少年离家",
    "summary": "主角在村庄中受到欺辱，意外获得神秘传承",
    "sequence_id": "seq_001",
    "beats": [
      {
        "id": "beat_1_1",
        "description": "主角被同村少年围堵",
        "dramatic_function": "setup"
      },
      {
        "id": "beat_1_2",
        "description": "意外触发神秘力量",
        "dramatic_function": "inciting"
      }
    ],
    "emotional_arc": {"start": "屈辱", "end": "震惊"},
    "mandatory_tasks": ["建立主角性格", "埋下传承伏笔"],
    "target_words": 4000
  },
  {
    "chapter_number": 2,
    "title": "第二章 初入修途",
    "summary": "主角离开村庄，前往最近的修炼宗门",
    "sequence_id": "seq_001",
    "beats": [
      {"id": "beat_2_1", "description": "路途中遇到危险", "dramatic_function": "turning"},
      {"id": "beat_2_2", "description": "被神秘人救下", "dramatic_function": "reveal"}
    ],
    "emotional_arc": {"start": "期待", "end": "感激"},
    "mandatory_tasks": ["引入导师角色"],
    "target_words": 4000
  }
]
```

### 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `chapter_number` | 是 | 章节序号，从1开始 |
| `title` | 是 | 章节标题 |
| `summary` | 是 | 章节摘要（50-200字） |
| `sequence_id` | 否 | 所属序列ID（对应故事大纲中的 sequences[].id） |
| `beats` | 否 | 节拍数组，每章2-3个 |
| `beats[].id` | 是 | 节拍ID，格式如 beat_1_1 |
| `beats[].description` | 是 | 节拍描述（20字以内） |
| `beats[].dramatic_function` | 是 | 戏剧功能（同上枚举值） |
| `emotional_arc` | 否 | 情感弧线 {"start": "起始情绪", "end": "结束情绪"} |
| `mandatory_tasks` | 否 | 本章必须完成的叙事任务 |
| `target_words` | 否 | 目标字数，默认4000 |

---

## 使用提示

1. 如果小说很长（100章以上），建议分批让大模型提取章节大纲，每次50-100章
2. `estimated_scenes` 的总和应该等于总章节数
3. 导入时系统会自动补缺缺失字段，所以不必追求完美
4. beats 的 id 格式建议为 `beat_{章节号}_{序号}`，如 `beat_1_1`、`beat_42_3`
