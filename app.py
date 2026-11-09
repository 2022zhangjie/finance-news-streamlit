import time
from datetime import datetime, timezone

import feedparser
import pandas as pd
import streamlit as st

st.set_page_config(page_title="财经新闻速览", page_icon="📈", layout="wide")

FEEDS = {
    "CNBC 头条": "https://www.cnbc.com/id/100003114/device/rss/rss.html",
    "CNBC 市场": "https://www.cnbc.com/id/20910258/device/rss/rss.html",
    "WSJ 市场": "https://feeds.content.dowjones.io/public/rss/RSSMarketsMain",
    "MarketWatch": "https://feeds.content.dowjones.io/public/rss/mw_topstories",
    "BBC 商业": "https://feeds.bbci.co.uk/news/business/rss.xml",
}

TICKERS = {"标普500": "^GSPC", "纳斯达克": "^IXIC", "道琼斯": "^DJI", "恒生指数": "^HSI", "黄金": "GC=F", "比特币": "BTC-USD"}


@st.cache_data(ttl=600, show_spinner=False)
def load_feed(url: str) -> list[dict]:
    d = feedparser.parse(url, agent="Mozilla/5.0 (finnews-streamlit)")
    items = []
    for e in d.entries[:30]:
        ts = e.get("published_parsed") or e.get("updated_parsed")
        dt = datetime.fromtimestamp(time.mktime(ts), tz=timezone.utc) if ts else None
        items.append({
            "title": e.get("title", "").strip(),
            "link": e.get("link", ""),
            "summary": (e.get("summary", "") or "").split("<")[0].strip(),
            "time": dt,
        })
    return items


@st.cache_data(ttl=900, show_spinner=False)
def load_quotes() -> pd.DataFrame:
    try:
        import yfinance as yf
        rows = []
        for name, sym in TICKERS.items():
            h = yf.Ticker(sym).history(period="5d")["Close"].dropna()
            if len(h) >= 2:
                last, prev = h.iloc[-1], h.iloc[-2]
                rows.append({"名称": name, "最新": round(last, 2), "涨跌幅%": round((last / prev - 1) * 100, 2)})
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


st.title("📈 财经新闻速览")
st.caption("汇总多家财经媒体 RSS，每 10 分钟自动刷新缓存。")

with st.sidebar:
    st.header("设置")
    sources = st.multiselect("新闻来源", list(FEEDS), default=list(FEEDS)[:3])
    keyword = st.text_input("关键词过滤（标题/摘要）", "")
    limit = st.slider("每个来源显示条数", 5, 30, 10)
    if st.button("🔄 立即刷新"):
        st.cache_data.clear()
        st.rerun()

quotes = load_quotes()
if not quotes.empty:
    cols = st.columns(len(quotes))
    for c, (_, r) in zip(cols, quotes.iterrows()):
        c.metric(r["名称"], f'{r["最新"]:,}', f'{r["涨跌幅%"]}%')
    st.divider()

if not sources:
    st.info("请在左侧选择至少一个新闻来源。")

all_items = []
for src in sources:
    for it in load_feed(FEEDS[src])[:limit]:
        if keyword and keyword.lower() not in (it["title"] + it["summary"]).lower():
            continue
        all_items.append({**it, "source": src})

all_items.sort(key=lambda x: x["time"] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

tab_list, tab_stats = st.tabs(["📰 新闻列表", "📊 来源统计"])
with tab_list:
    st.write(f"共 {len(all_items)} 条")
    for it in all_items:
        t = it["time"].strftime("%Y-%m-%d %H:%M UTC") if it["time"] else ""
        st.markdown(f"**[{it['title']}]({it['link']})**  \n`{it['source']}` · {t}")
        if it["summary"]:
            st.caption(it["summary"][:240])
with tab_stats:
    if all_items:
        df = pd.DataFrame(all_items)
        st.bar_chart(df["source"].value_counts())
    else:
        st.write("暂无数据")

st.caption("数据来源：各媒体公开 RSS 与 Yahoo Finance，仅供参考，不构成投资建议。")
