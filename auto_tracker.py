import os
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests

# 1. 增加 "ru_keys" 字段，用于匹配俄语新闻标题中的地名
GEO_DATABASE = {
    "chapayevsk": {"ru_keys": ["чапаевск", "самара"], "name": "Ozon 萨马拉/恰帕耶夫斯克仓", "platform": "Ozon", "lat": 52.9833, "lng": 49.7167, "area": "135,000 m²"},
    "orenburg": {"ru_keys": ["оренбург"], "name": "Ozon 奥伦堡特区仓", "platform": "Ozon", "lat": 51.7667, "lng": 55.1000, "area": "40,000 m²"},
    "krasnodar": {"ru_keys": ["краснодар"], "name": "克拉斯诺达尔仓", "platform": "Ozon/WB", "lat": 45.0355, "lng": 38.9753, "area": "150,000 m²"},
    "makhachkala": {"ru_keys": ["махачкала", "дагестан"], "name": "Ozon 马哈奇卡拉仓", "platform": "Ozon", "lat": 42.9849, "lng": 47.5046, "area": "分拨仓"},
    "adygea": {"ru_keys": ["адыгея", "адыгейск"], "name": "Ozon 阿迪格仓", "platform": "Ozon", "lat": 44.8833, "lng": 39.1833, "area": "未知"},
    "stavropol": {"ru_keys": ["ставропол", "невинномысск"], "name": "Ozon 斯塔夫罗波尔仓", "platform": "Ozon", "lat": 44.6333, "lng": 41.9333, "area": "未知"},
    "ufa": {"ru_keys": ["уфа", "башкортостан"], "name": "Ozon 乌法仓", "platform": "Ozon", "lat": 54.7388, "lng": 55.9721, "area": "未知"},
    "rostov": {"ru_keys": ["ростов"], "name": "Ozon 罗斯托夫仓", "platform": "Ozon", "lat": 47.2333, "lng": 39.7000, "area": "未知"}
}

def fetch_rss_news(query):
    """从 Google News RSS 抓取新闻"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ru&gl=RU&ceid=RU:ru"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            return []
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item")[:20]: # 扩大获取数量
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            items.append({"title": title, "link": link, "date": pub_date})
        return items
    except Exception as e:
        print(f"Error fetching news: {e}")
        return []

def analyze_and_extract():
    """检索并结构化提取受损信息"""
    # 优化了俄语查询词，使其更精准
    queries = [
        "Ozon склад беспилотник OR дрон OR пожар OR атака",
        "Озон склад горит OR атакован"
    ]
    
    all_news = []
    for q in queries:
        all_news.extend(fetch_rss_news(q))
        time.sleep(1)

    data_file = "data.json"
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    existing_titles = {r.get("news_title", "") for r in records}
    new_records_count = 0

    for news in all_news:
        title = news["title"]
        if title in existing_titles:
            continue

        title_lower = title.lower()
        matched_platform = None
        
        # 匹配平台 (增加俄文 озон 匹配)
        if "ozon" in title_lower or "озон" in title_lower:
            matched_platform = "Ozon"
        elif "wildberries" in title_lower or "вайлдберриз" in title_lower:
            matched_platform = "Wildberries"

        # 匹配事件类型 (仓库, 燃烧, 无人机, 攻击)
        is_incident = any(word in title_lower for word in ["склад", "пожар", "дрон", "беспилотник", "атака", "горит"])

        if matched_platform and is_incident:
            matched_geo = None
            
            # 使用俄文关键词遍历匹配地名
            for key, geo in GEO_DATABASE.items():
                if any(ru_key in title_lower for ru_key in geo.get("ru_keys", [])):
                    matched_geo = geo
                    break

            if matched_geo:
                records.append({
                    "id": f"auto-{int(time.time())}-{len(records)}",
                    "platform": matched_platform,
                    "name": matched_geo["name"],
                    "type": "ozon-damaged" if matched_platform == "Ozon" else "wb-damaged",
                    "lat": matched_geo["lat"],
                    "lng": matched_geo["lng"],
                    "area": matched_geo["area"],
                    "date": news["date"][:16],
                    "status": "监测到火灾/遭袭警报",
                    "details": title,
                    "news_title": title,
                    "source_url": news["link"]
                })
                existing_titles.add(title)
                new_records_count += 1

    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Update complete. Added {new_records_count} new records. Total tracked records: {len(records)}")

if __name__ == "__main__":
    analyze_and_extract()
