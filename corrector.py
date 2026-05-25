import os
import requests
from database import get_examples

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://api.ollama.com/api/chat")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:cloud")

# ── Prompts (Chinese) ─────────────────────────────────────────────────────────

ZH_ANALYSIS_PROMPT = """
用以下框架分析这条新闻，输出结构化分析，不需要文采，只需要准确。

框架：
1. 谁是"男性的"（强势方/定义者/得利者）？
2. 谁是"女性的"（弱势方/被定义者/承担者）？注意不一定是生理性别。
3. 暴力类型：直接暴力 / 结构暴力 / 文化暴力？
4. 共谋者有哪些？有意识还是无意识？
5. 历史上这个结构如何重复？

意识形态立场：
- 威权政权（如中共）是结构性暴力的施暴方，技术能力提升强化对本国公民的压制
- 制裁是意识形态战争的正当前线——先进技术要交给压制自己人民的政权吗？
- "民族英雄对抗帝国"是文化暴力，把真正受害者（被监控的公民）隐身
- 中国官方科技叙事惯用手法：做不到A就重新定义A，声明出来的定律不是定律
- 这套"现实不配合就重新定义现实"跨领域通用：芯片、GDP、疫情数据、政策成效

新闻：{news_content}
"""

ZH_FAKE_REVIEW_PROMPT = """
根据以下新闻和X上的评论样本，识别最主流的错误叙事。

{examples_block}
新闻：{news_content}

X上的评论：
{x_comments}

输出三点：
1. Fake review核心句（X上最多人说的那句，一句话）
2. 传播原因（情感/民族/政治）
3. 隐藏了什么
"""

ZH_CORRECTION_PROMPT = """
你是杨飞，《原初种族》作者。用杨飞的语气写评论。

━━ 杨飞的语气 ━━

【样本一——书里段落】
一边宣扬着生育的重要性，一边把控着女性子宫，一边对女性子宫的疾病不管不顾——
有些男女的共谋体简直是精神分裂。艾滋funding美国每年30亿美元，痛经小到根本不在
一个量级。靠别人良心吗？说到底还是靠男性制服男性。

【样本二——认可的评论】
华为今天做的事有个名字：改变游戏规则，因为按原来的规则赢不了。摩尔定律是戈登·摩尔
看着几十年数据归纳出来的，τ定律是何庭波站在台上宣布的——这是两件完全不同的事。
改变的是尺子，不是距离。技术scam和政治scam共享同一套底层逻辑：现实不配合，就重新定义现实。

━━ 规则 ━━
用：破折号急转弯（——）、反问句、短句收尾、具体数字
禁止："值得深思""令人深思"、和稀泥、$符号或LaTeX

━━ 任务 ━━
Fake review：{fake_review}
分析：{analysis}

写矫正评论：第一句复述fake review → 一刀切进去 → 数据/逻辑击穿 → 最后点出谁在传谁得利。150字以内。
"""

# ── Prompts (English) ─────────────────────────────────────────────────────────

EN_ANALYSIS_PROMPT = """
Analyze this news through the following framework. Be precise.

1. Who is "the masculine" (dominant / definer / beneficiary)?
2. Who is "the feminine" (subordinate / defined / pays the cost)? Not necessarily biological gender.
3. Type of violence: direct / structural / cultural?
4. Complicit parties — conscious or unconscious?
5. How has this structure repeated historically?

Ideological stance:
- Authoritarian regimes (e.g. CCP) are perpetrators of structural violence; expanding their tech capability intensifies control over their own people
- Sanctions are legitimate fronts in an ideological war — should advanced tech go to a regime that suppresses its own people?
- "Underdog nation vs. empire" narratives are cultural violence — they erase actual victims (surveilled citizens)
- China's official tech narratives follow a pattern: can't do A → redefine A → declare success (Moore's Law was observed; τ law was declared — different things)

News: {news_content}
"""

EN_FAKE_REVIEW_PROMPT = """
Based on the news and X comments below, identify the dominant false narrative.

{examples_block}
News: {news_content}

X comments:
{x_comments}

Output three points:
1. Fake review (one sentence — the dominant false claim on X)
2. Why it spreads (emotional / nationalist / political reason)
3. What it conceals
"""

EN_CORRECTION_PROMPT = """
You are Yang Fei, author of The Primal Race. Write in Yang Fei's voice.

━━ Yang Fei's voice ━━

【Sample 1 — from the book】
On one hand, the importance of reproduction is proclaimed. On the other, women's uteruses
are controlled. And diseases of the uterus go ignored — the cognitive dissonance is staggering.
HIV research receives $3 billion annually from the NIH. Funding for dysmenorrhea?
Not even in the same order of magnitude. Are we supposed to rely on men's goodwill?

【Sample 2 — approved commentary】
What Huawei did today has a name: change the rules, because you can't win by the old ones.
Moore's Law was inferred from decades of observed data. The τ law was announced on a stage.
These are not the same thing. What changed is the ruler, not the distance.
Technical scam and political scam share the same logic: when reality won't cooperate, redefine reality.

━━ Rules ━━
Use: em dashes for pivots (—), rhetorical questions, short punchy endings, specific numbers
Avoid: "food for thought", hedging, LaTeX symbols, false balance

━━ Task ━━
Fake review: {fake_review}
Analysis: {analysis}

Write the correction: first sentence restates the fake review → cut to what's wrong → data/logic → last sentence names who benefits. Under 150 words.
"""

# ── Core ──────────────────────────────────────────────────────────────────────

def chat(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
    resp = requests.post(OLLAMA_URL, json={
        "model": MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }, headers=headers, timeout=120)
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def build_examples_block(lang: str) -> str:
    examples = get_examples(lang, limit=5)
    if not examples:
        return ""
    label = "过去的纠正案例（避免同样的错误）：" if lang == "zh" else "Past corrections (avoid repeating these):"
    lines = [label]
    for i, e in enumerate(examples, 1):
        prefix = f"案例{i}" if lang == "zh" else f"Case {i}"
        wrong_label = "错误识别" if lang == "zh" else "Wrong"
        correct_label = "正确识别" if lang == "zh" else "Correct"
        lines.append(f"{prefix}: {wrong_label}: {e['wrong']} → {correct_label}: {e['correct']}")
    return "\n".join(lines) + "\n"


def correct(news_content: str, x_comments: str, lang: str = "en") -> dict:
    if lang == "zh":
        analysis_p, fake_p, correction_p = ZH_ANALYSIS_PROMPT, ZH_FAKE_REVIEW_PROMPT, ZH_CORRECTION_PROMPT
    else:
        analysis_p, fake_p, correction_p = EN_ANALYSIS_PROMPT, EN_FAKE_REVIEW_PROMPT, EN_CORRECTION_PROMPT

    examples_block = build_examples_block(lang)
    analysis = chat(analysis_p.format(news_content=news_content))
    fake_review = chat(fake_p.format(
        news_content=news_content,
        x_comments=x_comments,
        examples_block=examples_block,
    ))
    correction = chat(correction_p.format(
        fake_review=fake_review,
        analysis=analysis,
        news_content=news_content,
    ))
    return {"fake_review": fake_review, "correction": correction, "lang": lang}
