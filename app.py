import streamlit as st
import feedparser
import yfinance as yf
from datetime import datetime, timedelta
import pandas as pd
from docx import Document
from fpdf import FPDF
import os

# -----------------------------
# CONFIG
# -----------------------------
RSS_FEEDS = {
    "Bigpara": "https://www.bigpara.com/rss/",
    "BloombergHT": "https://www.bloomberght.com/rss",
    "ReutersTR": "https://feeds.reuters.com/reuters/TurkeyNews"
}

KEYWORDS = {
    "high": ["TCMB", "faiz", "enflasyon", "Fed", "ECB", "bilanço", "KAP"],
    "medium": ["BIST", "endeks", "döviz", "CDS", "rezerv", "petrol"],
}

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# -----------------------------
# DATA FUNCTIONS
# -----------------------------

def fetch_news():
    articles = []
    for source, url in RSS_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            published = datetime(*entry.published_parsed[:6]) if hasattr(entry, "published_parsed") else datetime.now()
            if published > datetime.now() - timedelta(hours=18):
                articles.append({
                    "title": entry.title,
                    "summary": entry.get("summary", ""),
                    "source": source,
                    "published": published
                })
    return articles


def score_news(article):
    score = 0
    text = (article["title"] + article["summary"]).lower()

    for kw in KEYWORDS["high"]:
        if kw.lower() in text:
            score += 3
    for kw in KEYWORDS["medium"]:
        if kw.lower() in text:
            score += 1
    if article["source"] in ["ReutersTR", "BloombergHT"]:
        score += 2
    hours_old = (datetime.now() - article["published"]).seconds / 3600
    score += max(0, 3 - hours_old)
    return score


def select_top_news(articles, n=3):
    for a in articles:
        a["score"] = score_news(a)
    articles.sort(key=lambda x: x["score"], reverse=True)
    return articles[:n]


def get_market_data():
    bist = yf.Ticker("XU100.IS").history(period="1d")
    usdtry = yf.Ticker("USDTRY=X").history(period="1d")
    return {
        "bist_close": round(bist["Close"][-1], 2),
        "bist_change": round((bist["Close"][-1] / bist["Open"][-1] - 1) * 100, 2),
        "usdtry": round(usdtry["Close"][-1], 2)
    }


def generate_market_summary(market):
    direction = "yükselişle" if market["bist_change"] > 0 else "düşüşle"
    return (
        f"BIST 100 günü %{abs(market['bist_change'])} {direction} "
        f"{market['bist_close']} seviyesinde tamamladı. "
        f"USD/TRY {market['usdtry']} seviyesinde izleniyor."
    )

# -----------------------------
# WHY THIS MATTERS (RULE-BASED + LLM-READY)
# -----------------------------

def why_this_matters(news):
    title = news["title"].lower()

    if any(k in title for k in ["faiz", "tcmb", "merkez bankası"]):
        return "Faiz ve para politikası kararları, bankacılık hisseleri başta olmak üzere tüm piyasa değerlemelerini doğrudan etkiler."

    if any(k in title for k in ["bilanço", "kar", "zarar"]):
        return "Bilanço verileri şirketin operasyonel gücünü ve fiyatlamaların sürdürülebilirliğini gösterir."

    if any(k in title for k in ["fed", "abd", "enflasyon"]):
        return "Küresel makro gelişmeler, gelişen piyasalara yönelik risk iştahını ve sermaye akımlarını belirler."

    if any(k in title for k in ["petrol", "emtia", "altın"]):
        return "Emtia fiyatlarındaki hareketler, hem enflasyon beklentilerini hem de ilgili sektör hisselerini etkiler."

    return "Bu gelişme, piyasa beklentileri ve yatırımcı algısı açısından yakından takip ediliyor."

# -----------------------------
# SECTOR IMPACT TAGGING
# -----------------------------

def sector_impact(news):
    text = (news["title"] + " " + news["summary"]).lower()

    sectors = []

    if any(k in text for k in ["faiz", "tcmb", "banka", "kredi", "mevduat"]):
        sectors.append("Banking")

    if any(k in text for k in ["sanayi", "üretim", "ihracat", "fabrika"]):
        sectors.append("Industrial")

    if any(k in text for k in ["enerji", "petrol", "doğalgaz", "elektrik"]):
        sectors.append("Energy")

    if not sectors:
        sectors.append("Broad Market")

    return sectors

# -----------------------------
# SECTOR HEAT INDICATOR
# -----------------------------

def sector_heat(top_news):
    heat = {
        "Banking": 0,
        "Industrial": 0,
        "Energy": 0
    }

    positive_words = ["artış", "yükseliş", "güçlü", "rekor", "olumlu"]
    negative_words = ["düşüş", "gerileme", "zayıf", "baskı", "risk"]

    for news in top_news:
        text = (news["title"] + " " + news["summary"]).lower()
        sectors = sector_impact(news)

        sentiment = 0
        if any(w in text for w in positive_words):
            sentiment += 1
        if any(w in text for w in negative_words):
            sentiment -= 1

        for s in sectors:
            if s in heat:
                heat[s] += sentiment

    heat_label = {}
    for sector, score in heat.items():
        if score > 0:
            heat_label[sector] = "🔥 Positive"
        elif score < 0:
            heat_label[sector] = "❄️ Negative"
        else:
            heat_label[sector] = "➖ Neutral"

    return heat_label

# -----------------------------
# STREAMLIT UI
# -----------------------------

st.set_page_config(page_title="Turkish Market Newsletter", layout="wide")

st.title("📈 Turkish Market Daily Newsletter Dashboard")
st.caption("Noise-free automated market intelligence")

if st.button("🔄 Fetch Today's Data"):
    with st.spinner("Collecting news and market data..."):
        news = fetch_news()
        top_news = select_top_news(news)
        market = get_market_data()
        summary = generate_market_summary(market)

        st.success("Data loaded")

        st.subheader("📊 Market Snapshot")
        col1, col2, col3 = st.columns(3)
        col1.metric("BIST 100", market["bist_close"], f"{market['bist_change']}%")
        col2.metric("USD/TRY", market["usdtry"])
        col3.metric("Market Mood", "Positive" if market["bist_change"] > 0 else "Negative")

        st.subheader("📰 Top 3 News")
        for i, n in enumerate(top_news, 1):
            with st.expander(f"{i}. {n['title']}"):
                st.write(n["summary"])
                st.caption(f"Source: {n['source']} | Score: {round(n['score'],2)}")

        st.subheader("🧠 Auto Market Summary")
        st.info(summary)

        st.subheader("📄 Export")
        if st.button("Generate Word & PDF"):
            doc = Document()
            doc.add_heading("Günlük Piyasa Bülteni", level=1)
            for i, n in enumerate(top_news, 1):
                doc.add_paragraph(f"{i}. {n['title']}")
                doc.add_paragraph(n['summary'])
            doc.add_paragraph(summary)
            doc_path = f"{OUTPUT_DIR}/newsletter.docx"
            doc.save(doc_path)

            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.multi_cell(0, 8, summary)
            pdf_path = f"{OUTPUT_DIR}/newsletter.pdf"
            pdf.output(pdf_path)

            st.success("Files generated")
            st.download_button("⬇️ Download DOCX", open(doc_path, "rb"), file_name="newsletter.docx")
            st.download_button("⬇️ Download PDF", open(pdf_path, "rb"), file_name="newsletter.pdf")
