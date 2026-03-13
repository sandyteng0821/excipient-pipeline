"""
LLM Text Extraction Benchmark
比較不同 LLM provider 在 text extraction 任務上的表現
支援: Groq (Llama 3.3 70B) vs OpenAI (GPT-4o / GPT-4o-mini)

Usage:
    pip install langchain-groq langchain-openai python-dotenv pydantic
    python llm_extraction_benchmark.py
"""

import os
import json
import time
import csv
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

# ── 1. Pydantic Schemas ────────────────────────────────────────────────

class ArticleExtraction(BaseModel):
    """從文章中擷取結構化資料"""
    title: Optional[str] = Field(None, description="文章標題")
    author: Optional[str] = Field(None, description="作者姓名")
    date: Optional[str] = Field(None, description="發布日期，格式 YYYY-MM-DD")
    summary: Optional[str] = Field(None, description="50字內摘要")
    keywords: list[str] = Field(default_factory=list, description="3-5個關鍵字")
    sentiment: Optional[str] = Field(None, description="情感傾向: positive/neutral/negative")


class InvoiceExtraction(BaseModel):
    """從發票/收據中擷取資料"""
    vendor_name: Optional[str] = Field(None, description="廠商/店家名稱")
    invoice_number: Optional[str] = Field(None, description="發票號碼")
    date: Optional[str] = Field(None, description="發票日期")
    total_amount: Optional[float] = Field(None, description="總金額（數字）")
    currency: Optional[str] = Field(None, description="幣別，如 TWD/USD")
    items: list[dict] = Field(default_factory=list, description="品項列表 [{name, qty, price}]")


# ── 2. 測試資料 ────────────────────────────────────────────────────────

TEST_CASES = [
    {
        "id": "article_en",
        "name": "English Article",
        "schema": ArticleExtraction,
        "text": """
        OpenAI Releases GPT-5 with Improved Reasoning Capabilities
        By Sarah Chen | March 10, 2025

        OpenAI announced the release of GPT-5 yesterday, claiming significant improvements
        in mathematical reasoning and code generation. The new model reportedly scores 87%
        on the MATH benchmark, up from 72% in GPT-4o. CEO Sam Altman described the launch
        as "a milestone in our journey toward AGI." Analysts remain cautiously optimistic,
        noting that real-world performance often differs from benchmark results.
        """,
    },
    {
        "id": "article_zh",
        "name": "中文新聞文章",
        "schema": ArticleExtraction,
        "text": """
        台積電宣布擴大美國投資計畫
        記者：王小明 | 2025年3月8日

        台積電（TSMC）昨日宣布將在美國亞利桑那州增設第三座晶圓廠，總投資金額達650億美元。
        執行長魏哲家表示，此次擴廠計畫將創造約6,000個高薪職位，預計2028年正式量產。
        分析師普遍認為此舉對台美供應鏈關係具有正面意義，但也提醒投資人注意建廠成本超支的風險。
        台積電股價當日上漲2.3%，收於新台幣980元。
        """,
    },
    {
        "id": "invoice",
        "name": "Invoice / 發票",
        "schema": InvoiceExtraction,
        "text": """
        INVOICE #INV-2025-0342
        Date: 2025-03-05
        Vendor: TechSupply Co., Ltd.

        Bill To: Acme Corp
        Items:
        - MacBook Pro 14" M3  x1  @ $2,499.00
        - USB-C Hub            x3  @ $45.00
        - Wireless Keyboard    x2  @ $89.00

        Subtotal: $2,812.00
        Tax (5%): $140.60
        Total Due: $2,952.60 USD

        Payment due within 30 days.
        """,
    },
    {
        "id": "messy_text",
        "name": "Messy / 混亂格式",
        "schema": ArticleExtraction,
        "text": """
        written by john doe...sometime in feb 2025 maybe the 14th??
        so basically apple just dropped their new vision pro 2 thing
        its cheaper now like 2500 bucks instead of 3500
        people seem to like it more. some say its revolutionary others say meh
        cook was quoted saying "best product we've ever made" lol
        keywords: apple, vr, headset, vision pro
        """,
    },
]

# ── 3. Provider 初始化 ─────────────────────────────────────────────────

def get_providers():
    providers = {}

    groq_key = os.getenv("GROQ_API_KEY")
    if groq_key:
        try:
            from langchain_groq import ChatGroq
            providers["groq_llama33_70b"] = ChatGroq(
                model="llama-3.3-70b-versatile",
                temperature=0,
                api_key=groq_key,
            )
            print("✅ Groq (llama-3.3-70b) 初始化成功")
        except ImportError:
            print("❌ 請安裝: pip install langchain-groq")
    else:
        print("⚠️  GROQ_API_KEY 未設定，跳過 Groq")

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        try:
            from langchain_openai import ChatOpenAI
            providers["openai_gpt4o_mini"] = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0,
                api_key=openai_key,
            )
            providers["openai_gpt4o"] = ChatOpenAI(
                model="gpt-4o",
                temperature=0,
                api_key=openai_key,
            )
            print("✅ OpenAI (gpt-4o-mini + gpt-4o) 初始化成功")
        except ImportError:
            print("❌ 請安裝: pip install langchain-openai")
    else:
        print("⚠️  OPENAI_API_KEY 未設定，跳過 OpenAI")

    return providers

# ── 4. 執行單一測試 ────────────────────────────────────────────────────

def run_single_test(provider_name: str, llm, test_case: dict) -> dict:
    schema = test_case["schema"]
    prompt = f"""Extract structured information from the following text.
Return ONLY valid JSON matching the schema. No explanation, no markdown.

IMPORTANT rules:
- All list fields (e.g. keywords, items) MUST be JSON arrays, never comma-separated strings
- If a value is unknown, use null
- Numbers must be actual numbers, not strings

Schema fields: {json.dumps({k: (v.description or '') for k, v in schema.model_fields.items()})}

Text:
{test_case['text'].strip()}
"""

    start_time = time.time()
    error = None
    parsed_result = None
    raw_output = ""

    try:
        response = llm.invoke(prompt)
        raw_output = response.content.strip()
        elapsed = round(time.time() - start_time, 2)

        # 清理 markdown fences
        clean = raw_output
        if clean.startswith("```"):
            clean = clean.split("```")[1]
            if clean.startswith("json"):
                clean = clean[4:]
        clean = clean.strip()

        parsed_json = json.loads(clean)
        parsed_result = schema(**parsed_json)

    except json.JSONDecodeError as e:
        error = f"JSON parse error: {e}"
        elapsed = round(time.time() - start_time, 2)
    except Exception as e:
        error = f"Error: {e}"
        elapsed = round(time.time() - start_time, 2)

    # 計算填充率（有多少欄位有值）
    fill_rate = 0
    if parsed_result:
        fields = type(parsed_result).model_fields.keys()
        filled = sum(
            1 for f in fields
            if getattr(parsed_result, f) not in [None, [], ""]
        )
        fill_rate = round(filled / len(list(fields)) * 100)

    return {
        "provider": provider_name,
        "test_id": test_case["id"],
        "test_name": test_case["name"],
        "success": error is None,
        "fill_rate_pct": fill_rate,
        "latency_sec": elapsed,
        "error": error or "",
        "parsed_result": parsed_result.model_dump() if parsed_result else {},
        "raw_output": raw_output,
        "timestamp": datetime.now().isoformat(),
    }

# ── 5. 主程式 ─────────────────────────────────────────────────────────

def main():
    print("\n🚀 LLM Text Extraction Benchmark")
    print("=" * 50)

    providers = get_providers()
    if not providers:
        print("\n❌ 沒有可用的 provider，請設定至少一個 API key")
        return

    all_results = []
    summary_rows = []

    for provider_name, llm in providers.items():
        print(f"\n📦 測試 Provider: {provider_name}")
        print("-" * 40)

        for test_case in TEST_CASES:
            print(f"  ⏳ [{test_case['name']}] ...", end="", flush=True)
            result = run_single_test(provider_name, llm, test_case)
            all_results.append(result)

            status = "✅" if result["success"] else "❌"
            print(f" {status} {result['latency_sec']}s | fill: {result['fill_rate_pct']}%")
            if result["error"]:
                print(f"     └─ {result['error']}")

            # 收集 summary
            summary_rows.append({
                "provider": provider_name,
                "test_id": result["test_id"],
                "test_name": result["test_name"],
                "success": result["success"],
                "fill_rate_pct": result["fill_rate_pct"],
                "latency_sec": result["latency_sec"],
                "error": result["error"],
            })

            time.sleep(0.5)  # 避免 rate limit

    # ── 6. 儲存結果 ──────────────────────────────────────────────────

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV summary
    csv_path = f"benchmark_summary_{ts}.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=summary_rows[0].keys())
        writer.writeheader()
        writer.writerows(summary_rows)

    # JSON 詳細結果
    json_path = f"benchmark_detail_{ts}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    # ── 7. 印出 Summary Table ────────────────────────────────────────

    print("\n\n📊 Summary")
    print("=" * 65)
    print(f"{'Provider':<28} {'Test':<22} {'OK':>4} {'Fill%':>6} {'Sec':>6}")
    print("-" * 65)
    for row in summary_rows:
        ok = "✅" if row["success"] else "❌"
        print(f"{row['provider']:<28} {row['test_name']:<22} {ok:>4} {row['fill_rate_pct']:>5}% {row['latency_sec']:>5}s")

    # Per-provider 平均
    print("\n📈 Per-Provider Average")
    print("-" * 40)
    from collections import defaultdict
    stats = defaultdict(lambda: {"success": 0, "fill": 0, "latency": 0, "count": 0})
    for row in summary_rows:
        p = row["provider"]
        stats[p]["success"] += int(row["success"])
        stats[p]["fill"] += row["fill_rate_pct"]
        stats[p]["latency"] += row["latency_sec"]
        stats[p]["count"] += 1

    for p, s in stats.items():
        n = s["count"]
        print(f"  {p:<28}  success:{s['success']}/{n}  fill:{s['fill']//n}%  avg:{round(s['latency']/n,2)}s")

    print(f"\n💾 結果已儲存:")
    print(f"   CSV  → {csv_path}")
    print(f"   JSON → {json_path}")


if __name__ == "__main__":
    main()