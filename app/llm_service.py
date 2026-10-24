"""LLM integration service with natural-language question interpretation, safety validation, and documented deterministic fallback."""
import json
import logging
import re
from typing import Dict, Any, Optional, Tuple
import requests
from google import genai

from app.config import settings
from app.query_service import (
    query_total_revenue,
    query_highest_revenue_product,
    query_monthly_revenue_trend,
    query_highest_sales_region,
    query_revenue_change_between_months,
    execute_safe_query,
    validate_sql_safety
)

logger = logging.getLogger(__name__)

# Supported intent constants
INTENT_TOTAL_REVENUE = "TOTAL_REVENUE"
INTENT_HIGHEST_REVENUE_PRODUCT = "HIGHEST_REVENUE_PRODUCT"
INTENT_MONTHLY_REVENUE_TREND = "MONTHLY_REVENUE_TREND"
INTENT_HIGHEST_SALES_REGION = "HIGHEST_SALES_REGION"
INTENT_REVENUE_CHANGE_BETWEEN_MONTHS = "REVENUE_CHANGE_BETWEEN_MONTHS"
INTENT_UNKNOWN = "UNKNOWN"

MONTH_NAMES_TO_NUM = {
    "jan": "01", "january": "01",
    "feb": "02", "february": "02",
    "mar": "03", "march": "03",
    "apr": "04", "april": "04",
    "may": "05",
    "jun": "06", "june": "06",
    "jul": "07", "july": "07",
    "aug": "08", "august": "08",
    "sep": "09", "september": "09",
    "oct": "10", "october": "10",
    "nov": "11", "november": "11",
    "dec": "12", "december": "12"
}
def extract_months_from_text(text: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract up to two month identifiers from question text."""
    lower_text = text.lower()

    # Match explicit YYYY-MM or YYYY/MM dates
    iso_matches = re.findall(
        r'\b(202[0-9])[-/](0[1-9]|1[0-2])\b',
        lower_text
    )

    if len(iso_matches) >= 2:
        return (
            f"{iso_matches[0][0]}-{iso_matches[0][1]}",
            f"{iso_matches[1][0]}-{iso_matches[1][1]}"
        )

    if len(iso_matches) == 1:
        return f"{iso_matches[0][0]}-{iso_matches[0][1]}", None

    # Match month names and abbreviations
    month_aliases = {
        "jan": "01", "january": "01",
        "feb": "02", "february": "02",
        "mar": "03", "march": "03",
        "apr": "04", "april": "04",
        "may": "05",
        "jun": "06", "june": "06",
        "jul": "07", "july": "07",
        "aug": "08", "august": "08",
        "sep": "09", "sept": "09", "september": "09",
        "oct": "10", "october": "10",
        "nov": "11", "november": "11",
        "dec": "12", "december": "12"
    }

    tokens = re.findall(r'\b[a-z]+\b', lower_text)
    found_months = []

    for token in tokens:
        if token in month_aliases:
            month_code = f"2026-{month_aliases[token]}"

            if month_code not in found_months:
                found_months.append(month_code)

            if len(found_months) == 2:
                break

    if len(found_months) >= 2:
        return found_months[0], found_months[1]

    if len(found_months) == 1:
        return found_months[0], None

    return None, None

def interpret_with_deterministic_fallback(question: str) -> Dict[str, Any]:
    """Interpret supported business questions using deterministic rules."""
    import re
    from difflib import SequenceMatcher

    q = question.strip().lower()
    q = re.sub(r"[^a-z0-9\s-]", " ", q)
    q = re.sub(r"\s+", " ", q).strip()

    if not q:
        return {
            "intent": INTENT_UNKNOWN,
            "confidence": 0.2,
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    # Normalize common spelling variations and typos.
    replacements = {
        "revanue": "revenue",
        "revenu": "revenue",
        "revnue": "revenue",
        "saless": "sales",
        "prodcut": "product",
        "prodcuts": "products",
        "regoin": "region",
        "regoin": "region",
        "montly": "monthly",
        "monhtly": "monthly",
        "reigonal": "regional",
        "higest": "highest",
        "higestt": "highest",
        "totl": "total",
        "revu": "revenue",
    }

    words = q.split()
    q = " ".join(replacements.get(word, word) for word in words)
    padded_q = f" {q} "

    def has_any(phrases):
        return any(
            f" {phrase} " in padded_q
            for phrase in phrases
        )

    # Intent 5: Compare revenue between months.
    comparison_words = [
        "compare", "comparison", "difference", "change",
        "growth", "increase", "decrease", "versus", "vs",
        "compared", "between"
    ]

    month_words = [
        "january", "february", "march", "april", "may",
        "june", "july", "august", "september", "october",
        "november", "december", "jan", "feb", "mar",
        "apr", "jun", "jul", "aug", "sep", "oct", "nov", "dec"
    ]

    if (
        has_any(comparison_words)
        and (
            has_any(month_words)
            or "two months" in q
            or "2 months" in q
            or "monthly revenue" in q
            or "monthly sales" in q
        )
    ):
        m1, m2 = extract_months_from_text(q)
        return {
            "intent": INTENT_REVENUE_CHANGE_BETWEEN_MONTHS,
            "confidence": 0.95,
            "source": "Deterministic Fallback Engine",
            "parameters": {
                "month1": m1 or "2026-05",
                "month2": m2 or "2026-06"
            }
        }

    # Intent 2: Highest-revenue product.
    product_phrases = [
        "which product", "what product", "top product",
        "best product", "highest product", "most profitable product",
        "product generated", "product makes the most",
        "product made the most", "product with highest revenue",
        "highest selling product", "best selling product",
        "best-selling product", "top selling product",
        "product earned the most", "product has the highest sales",
        "highest revenue product", "most revenue product"
    ]

    if has_any(product_phrases) or (
        has_any(["product", "products", "item", "items"])
        and has_any(["highest", "top", "best", "most", "revenue", "sales", "selling"])
    ):
        return {
            "intent": INTENT_HIGHEST_REVENUE_PRODUCT,
            "confidence": 0.93,
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    # Intent 4: Highest-sales region.
    region_phrases = [
        "which region", "what region", "top region",
        "best region", "highest region", "region generated",
        "highest sales by region", "region with highest sales",
        "region with most sales", "region made the most",
        "best performing region", "top performing region",
        "highest revenue region", "region earned the most",
        "sales by region"
    ]

    if has_any(region_phrases) or (
        has_any(["region", "regional", "area", "territory"])
        and has_any(["highest", "top", "best", "most", "revenue", "sales"])
    ):
        return {
            "intent": INTENT_HIGHEST_SALES_REGION,
            "confidence": 0.93,
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    # Intent 3: Monthly revenue trends.
    trend_phrases = [
        "monthly", "month over month", "month by month",
        "by month", "over time", "revenue trend",
        "sales trend", "monthly revenue", "monthly sales",
        "revenue each month", "sales each month",
        "revenue over the months", "sales over the months",
        "show the trend", "trend over time"
    ]

    if has_any(trend_phrases) or (
        has_any(["trend", "trends", "timeline"])
        and has_any(["revenue", "sales", "month", "monthly"])
    ):
        return {
            "intent": INTENT_MONTHLY_REVENUE_TREND,
            "confidence": 0.93,
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    # Intent 1: Total revenue.
    revenue_phrases = [
        "total revenue", "overall revenue", "total sales",
        "all revenue", "total turnover", "sum of sales",
        "total earnings", "overall sales", "total income",
        "how much money did we make", "how much did we make",
        "how much did we earn", "how much have we earned",
        "money made", "money earned", "total amount earned",
        "total amount made", "revenue generated",
        "total business revenue", "overall earnings",
        "total sales revenue", "how much revenue",
        "how much sales", "total revenue generated"
    ]

    if has_any(revenue_phrases) or (
        has_any(["revenue", "sales", "earnings", "income", "turnover"])
        and has_any(["total", "overall", "all", "sum", "entire", "whole"])
    ):
        return {
            "intent": INTENT_TOTAL_REVENUE,
            "confidence": 0.93,
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    # Conservative fuzzy matching for minor spelling errors.
    # Match only when the question closely resembles a known phrase.
    known_phrases = {
        INTENT_TOTAL_REVENUE: [
            "what is the total revenue",
            "show total sales",
            "how much money did we make",
            "what are the total earnings"
        ],
        INTENT_HIGHEST_REVENUE_PRODUCT: [
            "which product generated the highest revenue",
            "what is the best selling product"
        ],
        INTENT_MONTHLY_REVENUE_TREND: [
            "show monthly revenue trends",
            "show the sales trend over time"
        ],
        INTENT_HIGHEST_SALES_REGION: [
            "which region has the highest sales",
            "show the best performing region"
        ]
    }

    best_intent = None
    best_score = 0.0

    for intent, phrases in known_phrases.items():
        for phrase in phrases:
            score = SequenceMatcher(None, q, phrase).ratio()
            if score > best_score:
                best_score = score
                best_intent = intent

    if best_score >= 0.82:
        return {
            "intent": best_intent,
            "confidence": round(best_score, 2),
            "source": "Deterministic Fallback Engine",
            "parameters": {}
        }

    return {
        "intent": INTENT_UNKNOWN,
        "confidence": 0.2,
        "source": "Deterministic Fallback Engine",
        "parameters": {}
    }
def call_gemini_api(question: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Interpret a business question using the Google Gemini SDK."""

    system_instruction = """
You are an AI Business Intelligence assistant for a sales database.

Classify the user's question into exactly one of these intents:

TOTAL_REVENUE:
Questions about total revenue, overall earnings, total sales,
or how much money the business made.

HIGHEST_REVENUE_PRODUCT:
Questions about the product generating the most revenue.

MONTHLY_REVENUE_TREND:
Questions about monthly revenue, monthly sales, or sales trends over time.

HIGHEST_SALES_REGION:
Questions about the region generating the highest sales.

REVENUE_CHANGE_BETWEEN_MONTHS:
Questions comparing revenue between two months.

UNKNOWN:
Questions unrelated to these reports or requests that are unsafe.

Return valid JSON with these fields:
{
  "intent": "ONE_ALLOWED_INTENT",
  "confidence": 0.9,
  "month1": null,
  "month2": null
}

For month1 and month2, use YYYY-MM format when a month is mentioned.
Use null when a month is not specified.
Do not invent months.
Return only the JSON object.
"""

    allowed_intents = {
        INTENT_TOTAL_REVENUE,
        INTENT_HIGHEST_REVENUE_PRODUCT,
        INTENT_MONTHLY_REVENUE_TREND,
        INTENT_HIGHEST_SALES_REGION,
        INTENT_REVENUE_CHANGE_BETWEEN_MONTHS,
        INTENT_UNKNOWN,
    }

    try:
        client = genai.Client(
        api_key=api_key,
        http_options={"timeout": 10000}
)

        response = client.models.generate_content(
            model="gemini-3.8-flash",
            contents=(
                f"{system_instruction}\n\n"
                f"User question: {question}"
            ),
            config={
                "temperature": 0,
                "response_mime_type": "application/json",
            },
        )

        if not response.text:
            logger.warning("Gemini returned an empty response.")
            return None

        parsed = json.loads(response.text)

        intent = parsed.get("intent", INTENT_UNKNOWN)

        if intent not in allowed_intents:
            logger.warning("Gemini returned an unsupported intent.")
            return None

        confidence = float(parsed.get("confidence", 0.0))
        confidence = max(0.0, min(confidence, 1.0))

        month1 = parsed.get("month1")
        month2 = parsed.get("month2")

        # Accept only correctly formatted month parameters.
        month_pattern = re.compile(r"^202[0-9]-(0[1-9]|1[0-2])$")

        if not isinstance(month1, str) or not month_pattern.fullmatch(month1):
            month1 = None

        if not isinstance(month2, str) or not month_pattern.fullmatch(month2):
            month2 = None

        return {
            "intent": intent,
            "confidence": confidence,
            "source": "LLM (Google Gemini)",
            "parameters": {
                "month1": month1,
                "month2": month2,
            },
        }

    except Exception as e:
        logger.exception("Gemini interpretation failed: %s", e)
    return None
def call_openai_api(question: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Interpret natural-language question using OpenAI API."""
    url = "https://api.openai.com/v1/chat/completions"
    system_prompt = (
        "You are an AI Business Intelligence Analyst. Classify the user question into one of: "
        "TOTAL_REVENUE, HIGHEST_REVENUE_PRODUCT, MONTHLY_REVENUE_TREND, HIGHEST_SALES_REGION, "
        "REVENUE_CHANGE_BETWEEN_MONTHS, UNKNOWN. "
        "Return pure JSON with keys: intent, confidence, month1, month2, reasoning."
    )
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload, timeout=8)
        if response.status_code == 200:
            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            parsed = json.loads(content)
            return {
                "intent": parsed.get("intent", INTENT_UNKNOWN),
                "confidence": float(parsed.get("confidence", 0.9)),
                "source": "LLM (OpenAI)",
                "parameters": {
                    "month1": parsed.get("month1"),
                    "month2": parsed.get("month2")
                }
            }
        else:
            logger.warning(f"OpenAI API returned status {response.status_code}: {response.text}")
    except Exception as e:
        logger.error(f"Error calling OpenAI API: {e}")
        
    return None


def interpret_question(question: str) -> Dict[str, Any]:
    """Interpret user question via configured LLM or fallback interpreter."""
    clean_q = question.strip()

    if not clean_q:
        return {
            "intent": INTENT_UNKNOWN,
            "confidence": 0.0,
            "source": "Input Validator",
            "parameters": {},
            "error": "Question cannot be empty."
        }

    # Attempt Gemini if configured
    if settings.GEMINI_API_KEY and settings.LLM_PROVIDER in ["gemini", "auto"]:
        llm_result = call_gemini_api(clean_q, settings.GEMINI_API_KEY)
        if llm_result:
            return llm_result

        logger.warning(
            "Gemini interpretation failed. Using deterministic fallback."
        )

    # Attempt OpenAI if configured as the provider or as a fallback
    if settings.OPENAI_API_KEY and settings.LLM_PROVIDER in ["openai", "auto"]:
        llm_result = call_openai_api(clean_q, settings.OPENAI_API_KEY)
        if llm_result:
            return llm_result

        logger.warning(
            "OpenAI interpretation failed. Using deterministic fallback."
        )

    # Deterministic fallback
    result = interpret_with_deterministic_fallback(clean_q)
    result["source"] = "Deterministic Fallback Engine"
    return result


def process_business_question(question: str, db_path: Optional[Any] = None) -> Dict[str, Any]:
    """Full workflow: interpret natural language, validate safety, execute database query, and format structured response."""
    interpretation = interpret_question(question)
    intent = interpretation.get("intent", INTENT_UNKNOWN)
    source = interpretation.get("source", "Unknown")
    confidence = interpretation.get("confidence", 0.0)
    params = interpretation.get("parameters", {})
    
    if intent == INTENT_TOTAL_REVENUE:
        res = query_total_revenue(db_path=db_path)
    elif intent == INTENT_HIGHEST_REVENUE_PRODUCT:
        res = query_highest_revenue_product(db_path=db_path)
    elif intent == INTENT_MONTHLY_REVENUE_TREND:
        res = query_monthly_revenue_trend(db_path=db_path)
    elif intent == INTENT_HIGHEST_SALES_REGION:
        res = query_highest_sales_region(db_path=db_path)
    elif intent == INTENT_REVENUE_CHANGE_BETWEEN_MONTHS:
        m1 = params.get("month1")
        m2 = params.get("month2")
        # If parameters were not extracted, extract from question text
        if not m1 or not m2:
            extracted_m1, extracted_m2 = extract_months_from_text(question)
            m1 = m1 or extracted_m1 or "2026-05"
            m2 = m2 or extracted_m2 or "2026-06"
        res = query_revenue_change_between_months(month1=m1, month2=m2, db_path=db_path)
    else:
        # Graceful handling of unsupported / out-of-scope questions
        return {
            "status": "unsupported",
            "question": question,
            "intent": INTENT_UNKNOWN,
            "answer": (
                "I could not map your query to an approved analytical report. "
                "I currently support questions regarding: \n"
                "1. Total revenue\n"
                "2. Highest revenue product\n"
                "3. Monthly revenue trends\n"
                "4. Highest sales region\n"
                "5. Revenue change between two months (e.g., 'Compare May and June')"
            ),
            "figures": {},
            "supporting_table": [],
            "sql_query": "N/A (Query rejected or unsupported)",
            "chart_type": None,
            "confidence": confidence,
            "source": source
        }
        
    res["status"] = "success"
    res["original_question"] = question
    res["confidence"] = confidence
    res["source"] = source
    return res
