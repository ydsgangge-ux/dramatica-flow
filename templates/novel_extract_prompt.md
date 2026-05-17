# 小说世界观提取提示词

> **使用方法：** 将以下【提示词】和【JSON模板】一起复制粘贴到任意大模型网页版（DeepSeek、Kimi、通义千问、GLM 等），再把你的小说全文发给它，让它按格式输出。

---

## 【提示词】（复制这段给 AI）

```
你是一位资深的小说分析师。我有一本已完成的小说，请你仔细阅读全文，提取其中的角色信息、世界设定和关键事件。

请严格按照下面的 JSON 模板格式输出，直接输出 JSON，不要任何其他说明文字。

## 分析要求

### 角色提取
1. 提取所有有名字、有台词、有行动的角色，不限数量，尽可能完整
2. 根据角色在文本中的行为、对话和他人评价推断其性格特征
3. role 字段选择：protagonist（主角）/ antagonist（反派）/ mentor（导师）/ love_interest（恋人）/ supporting（配角）
4. 需要填写双层需求：external（外在目标，角色自己追求的）和 internal（内在渴望，角色潜意识里真正需要的）
5. behavior_lock：角色性格锁定的行为，即这个角色"绝对不可能做的事"
6. arc：角色弧线，从什么状态变化为什么状态
7. backstory：从文本推断的角色背景故事（2-3句话）

### 世界设定提取
1. locations：提取小说中所有出现的重要地点，填写描述和故事意义
2. factions：提取所有势力、组织、门派、家族等，填写描述和对主角的态度
3. rules：提取小说特有的世界规则、修炼体系、特殊设定等

### 事件提取
1. 将小说中的关键情节转化为事件
2. suggested_act：事件属于第几幕（1=第一幕建立，2=第二幕对抗，3=第三幕结局）
3. suggested_function 选择：setup（建立）/ inciting_incident（激励事件）/ turning_point（转折点）/ midpoint（中点）/ climax（高潮）/ resolution（结局）
4. characters_involved：填写事件涉及的角色 id

### id 命名规则
- 角色：char_001, char_002, char_003 ...
- 地点：loc_001, loc_002, loc_003 ...
- 势力：fac_001, fac_002, fac_003 ...
- 事件：evt_001, evt_002, evt_003 ...

注意：
- characters_involved 中引用的角色 id 必须与 characters 数组中的 id 对应
- 如果某个字段信息不足，请根据上下文合理推测填写
- events 中的事件数量建议 20-50 个，覆盖小说的主要情节节点
```

---

## 【JSON 模板】（复制这段给 AI）

```json
{
  "characters": [
    {
      "id": "char_001",
      "name": "角色姓名",
      "role": "protagonist",
      "need": {
        "external": "外在目标（一句话描述）",
        "internal": "内在渴望（一句话描述）"
      },
      "personality": ["性格特征1", "性格特征2", "性格特征3"],
      "behavior_lock": ["绝对不做的事1", "绝对不做的事2"],
      "arc": "角色弧线：从XX状态变为XX状态",
      "backstory": "角色背景故事（2-3句话）"
    }
  ],
  "world": {
    "locations": [
      {
        "id": "loc_001",
        "name": "地点名称",
        "description": "地点描述（地形、环境、氛围等）",
        "significance": "在故事中的意义"
      }
    ],
    "factions": [
      {
        "id": "fac_001",
        "name": "势力/组织名称",
        "description": "势力描述（成员、势力范围、特点等）",
        "stance": "对主角的态度（友好/敌对/中立/暗中帮助）"
      }
    ],
    "rules": [
      {
        "name": "规则/设定名称",
        "description": "具体描述（修炼等级、特殊能力、世界法则等）",
        "impact": "对故事的影响"
      }
    ]
  },
  "events": [
    {
      "id": "evt_001",
      "name": "事件名称",
      "description": "事件的详细描述",
      "suggested_act": 1,
      "suggested_function": "inciting_incident",
      "characters_involved": ["char_001"],
      "dramatic_question": "这个事件引发的戏剧性疑问"
    }
  ]
}
```

---

## 【操作步骤】

1. 复制上面的【提示词】和【JSON 模板】
2. 打开任意大模型网页版（推荐 DeepSeek 网页版，支持超长文本）
3. 先发送提示词 + JSON 模板
4. 再发送你的小说全文（支持 TXT 粘贴或文件上传）
5. AI 输出 JSON 后，复制整个 JSON 内容
6. 回到 Dramatica-Flow Web UI → Step 3 世界观配置 → 点击 **"导入 JSON"**
7. 粘贴 JSON → 点击保存

**推荐的大模型网页版（免费且支持长文本）：**
- DeepSeek 网页版：https://chat.deepseek.com （支持 1M 字超长文本）
- Kimi：https://kimi.moonshot.cn （支持 20 万字）
- 通义千问：https://tongyi.aliyun.com
- 智谱清言：https://chatglm.cn
