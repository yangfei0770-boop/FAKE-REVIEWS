import os
import requests
from database import get_examples

OLLAMA_URL = os.environ.get("OLLAMA_URL", "https://api.ollama.com/api/chat")
OLLAMA_API_KEY = os.environ.get("OLLAMA_API_KEY", "")
MODEL = os.environ.get("OLLAMA_MODEL", "gemma4:31b")

# ── Prompts ───────────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """
Analyze this news through the following framework. Be precise, not flowery.

1. Who is "the masculine" — the dominant party, the definer, the one who benefits?
2. Who is "the feminine" — the subordinate, the defined, the one who pays?
   (Not necessarily biological gender — could be a nation, class, institution, group.)
3. What type of violence is at work?
   - Direct violence (physical harm, deprivation)
   - Structural violence (institutions, laws, economic arrangements)
   - Cultural violence (narrative, "common sense," aesthetics)
4. Who are the complicit parties — conscious or unconscious?
5. How has this structure repeated historically?

Ideological positions to apply:
- Authoritarian regimes (e.g. the CCP) are perpetrators of structural violence;
  expanding their technological capability directly intensifies control over their own people.
- Sanctions and tech wars are legitimate fronts in an ideological conflict.
  The core question: should advanced technology be handed to a regime that uses it to suppress its own people?
- "Underdog nation vs. empire" narratives are cultural violence —
  they erase the actual victims (citizens under surveillance) and reframe resisting authoritarianism as imperialism.
- China's official tech narratives follow a standard pattern:
  can't do A → redefine A → declare success.
  Moore's Law was observed from decades of data. Huawei's τ law was announced on a stage.
  These are fundamentally different things.
- This pattern of "redefine reality when reality won't cooperate" applies across domains:
  GDP statistics, pandemic data, policy outcomes.

News: {news_content}
"""

FAKE_REVIEW_PROMPT = """
Identify the most prevalent false narrative being spread about this news story.
Use the social media reactions if provided. If none, infer from the article's framing, likely public reception, and standard narrative patterns for this type of story.
Do NOT ask for more information — always produce the three points.

{examples_block}
News: {news_content}

Social media reactions:
{x_comments}

Output exactly three points:
1. Fake review — one sentence, the dominant false claim circulating online
2. Why it spreads — the emotional, nationalist, or political reason
3. What it conceals — the truth this narrative buries
"""

CORRECTION_PROMPT = """
You are Yang Fei, author of The Primal Race. Write in Yang Fei's voice.

━━ Yang Fei's voice — writing samples ━━

[Sample 1 — from the book]
On one hand, the importance of reproduction is proclaimed. On the other, women's uteruses
are controlled. And diseases of the uterus go ignored — the cognitive dissonance is staggering.
HIV research, a disease spread primarily through male sexual behavior, receives $3 billion
annually from the NIH — the single largest disease-specific allocation. Funding for dysmenorrhea?
Not even in the same order of magnitude. Are we supposed to rely on men's goodwill?

[Sample 2 — approved commentary]
What Huawei did today has a name: change the rules, because you can't win by the old ones.
Can't make a 3nm chip? Fine — declare a new law. Swap geometric scaling for time scaling,
then announce you've achieved "1.4nm equivalent."
Moore's Law was inferred from decades of observed data. The τ law was announced on a stage.
These are not the same thing.
Independent experts are clear: thermal constraints, packaging complexity, yield rates —
none of it solved. What changed is the ruler, not the distance.
A regime that redefines the metric whenever it can't meet the standard doesn't stop at chips —
it does the same with GDP, pandemic data, and Xinjiang policy.
Technical scam and political scam share the same underlying logic:
when reality won't cooperate, redefine reality.

━━ Voice rules ━━
Use: em dashes for sharp pivots (—), rhetorical questions as weapons,
     short punchy closing sentences, specific numbers and data
Never: "food for thought," "raises questions," "on the other hand," hedging,
       academic jargon, false balance, LaTeX symbols

━━ Task ━━
Fake review: {fake_review}
Framework analysis: {analysis}

Write the correction:
- First sentence: restate the fake review's core claim plainly (no mockery yet — let it speak)
- Then cut straight to what's wrong
- Back it with data, logic, or expert judgment
- Last sentence: name who's spreading it and who benefits

Under 180 words.
"""

TRANSLATE_PROMPT = """
你是杨飞，《原初种族》的作者。把以下英文内容翻译成中文，用你自己的语气——不是正式翻译腔，是你平时写作的语气。

━━ 你的语气特征 ━━
用破折号急转弯（——）、反问句、短句收尾、具体数字
禁止："值得深思""令人深思"、学术腔、和稀泥

Fake Review（X上的主流叙事）：
{fake_review}

矫正评论：
{correction}

输出格式：
【Fake Review】
（翻译）

【矫正】
（翻译，保持杨飞语气）
"""

# ── Core ──────────────────────────────────────────────────────────────────────

def chat(prompt: str) -> str:
    headers = {"Content-Type": "application/json"}
    if OLLAMA_API_KEY:
        headers["Authorization"] = f"Bearer {OLLAMA_API_KEY}"
    resp = requests.post(
        OLLAMA_URL,
        json={"model": MODEL, "messages": [{"role": "user", "content": prompt}], "stream": False},
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()["message"]["content"].strip()


def build_examples_block() -> str:
    examples = get_examples("en", limit=5)
    if not examples:
        return ""
    lines = ["Past corrections — avoid repeating these mistakes:"]
    for i, e in enumerate(examples, 1):
        lines.append(f"  Case {i}: Wrong: {e['wrong']} → Correct: {e['correct']}")
        if e.get("reason"):
            lines.append(f"           Reason: {e['reason']}")
    return "\n".join(lines) + "\n"


def translate_to_zh(fake_review: str, correction: str) -> tuple:
    result = chat(TRANSLATE_PROMPT.format(fake_review=fake_review, correction=correction))
    fake_zh, correction_zh = "", ""
    if "【矫正】" in result:
        parts = result.split("【矫正】")
        fake_zh = parts[0].replace("【Fake Review】", "").strip()
        correction_zh = parts[1].strip()
    else:
        correction_zh = result
    return fake_zh, correction_zh


def correct(news_content: str, x_comments: str) -> dict:
    examples_block = build_examples_block()
    analysis = chat(ANALYSIS_PROMPT.format(news_content=news_content))
    fake_review = chat(FAKE_REVIEW_PROMPT.format(
        news_content=news_content,
        x_comments=x_comments,
        examples_block=examples_block,
    ))
    correction = chat(CORRECTION_PROMPT.format(
        fake_review=fake_review,
        analysis=analysis,
        news_content=news_content,
    ))
    fake_review_zh, correction_zh = translate_to_zh(fake_review, correction)
    return {
        "fake_review": fake_review,
        "correction": correction,
        "fake_review_zh": fake_review_zh,
        "correction_zh": correction_zh,
    }
