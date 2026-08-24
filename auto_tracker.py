import os
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests

# 1. 基础基础已知全量仓网坐标库（用于模糊匹配地名获取精确坐标）
GEO_DATABASE = {
    "chapayevsk": {"name": "Ozon 恰帕耶夫斯克仓", "platform": "Ozon", "lat": 52.9833, "lng": 49.7167, "area": "135,000 m²"},
    "orenburg": {"name": "Ozon 奥伦堡特区仓", "platform": "Ozon", "lat": 51.7667, "lng": 55.1000, "area": "40,000 m²"},
    "krasnodar": {"name": "克拉斯诺达尔仓", "platform": "Ozon/WB", "lat": 45.0355, "lng": 38.9753, "area": "150,000 m²"},
    "makhachkala": {"name": "Ozon 马哈奇卡拉仓", "platform": "Ozon", "lat": 42.9849, "lng": 47.5046, "area": "分拨仓"},
    "elektrostal": {"name": "WB 埃莱克特罗斯塔尔仓", "platform": "Wildberries", "lat": 55.7936, "lng": 38.4414, "area": "230,000 m²"},
    "koledino": {"name": "WB 波多利斯克/科列季诺仓", "platform": "Wildberries", "lat": 55.3725, "lng": 37.5817, "area": "200,000 m²"},
    "aleksin": {"name": "WB 阿列克辛仓", "platform": "Wildberries", "lat": 54.5083, "lng": 37.0786, "area": "194,500 m²"},
    "shushary": {"name": "WB/Ozon 圣彼得堡舒沙雷仓", "platform": "WB/Ozon", "lat": 59.8117, "lng": 30.3853, "area": "170,000 m²"},
    "novousmansky": {"name": "WB 沃罗涅日新乌斯曼仓", "platform": "Wildberries", "lat": 51.6433, "lng": 39.4103, "area": "152,900 m²"},
    "samara": {"name": "萨马拉仓", "platform": "Ozon/WB", "lat": 53.3667, "lng": 50.3500, "area": "85,000 m²"}
}

def fetch_rss_news(query):
    """从 Google News RSS 抓取关于 Ozon / Wildberries 仓库的最新俄语及英语新闻"""
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ru&gl=RU&ceid=RU:ru"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    resp = requests.get(url, headers=headers, timeout=10)
    if resp.status_code != 200:
        return []

    root = ET.fromstring(resp.content)
    items = []
    for item in root.findall(".//item")[:15]:
        title = item.find("title").text if item.find("title") is not None else ""
        link = item.find("link").text if item.find("link") is not None else ""
        pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
        items.append({"title": title, "link": link, "date": pub_date})
    return items

def geocode_city_osm(city_name):
    """利用 OpenStreetMap Nominatim 自动查询未收录城市的经纬度"""
    try:
        url = f"https://nominatim.openstreetmap.org/search?q={urllib.parse.quote(city_name)}&format=json&limit=1"
        res = requests.get(url, headers={"User-Agent": "AutoWarehouseTracker/1.0"}, timeout=5).json()
        if res:
            return float(res[0]["lat"]), float(res[0]["lon"])
    except Exception as e:
        print(f"Geocoding failed for {city_name}: {e}")
    return None, None

def analyze_and_extract():
    """检索并结构化提取受损信息"""
    queries = [
        "Ozon склад дрон OR пожар OR атака",
        "Wildberries склад дрон OR пожар OR атака",
        "Ozon warehouse drone strike fire"
    ]
    
    all_news = []
    for q in queries:
        all_news.extend(fetch_rss_news(q))
        time.sleep(1)

    # 读取已有数据或初始化
    data_file = "data.json"
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    existing_titles = {r.get("news_title", "") for r in records}

    # 简易关键词匹配与实体提取逻辑（生产环境可对接免费大模型 API 如 Gemini API 提取）
    for news in all_news:
        title = news["title"]
        if title in existing_titles:
            continue

        title_lower = title.lower()
        matched_platform = None
        if "ozon" in title_lower or "озон" in title_lower:
            matched_platform = "Ozon"
        elif "wildberries" in title_lower or "вайлдберриз" in title_lower:
            matched_platform = "Wildberries"

        if matched_platform and ("склад" in title_lower or "warehouse" in title_lower or "пожар" in title_lower):
            # 扫描地理库
            matched_geo = None
            for key, geo in GEO_DATABASE.items():
                if key in title_lower or geo["name"].lower() in title_lower:
                    matched_geo = geo
                    break

            if matched_geo:
                records.append({
                    "id": f"auto-{int(time.time())}-{len(records)}",
                    "platform": matched_platform,
                    "name": f"[{matched_platform}] {matched_geo['name']}",
                    "type": "ozon-damaged" if matched_platform == "Ozon" else "wb-damaged",
                    "lat": matched_geo["lat"],
                    "lng": matched_geo["lng"],
                    "area": matched_geo["area"],
                    "date": news["date"][:16],
                    "status": "新闻监测到火灾/遭袭警报",
                    "details": title,
                    "news_title": title,
                    "source_url": news["link"]
                })
                existing_titles.add(title)

    # 写回 data.json
    with open(data_file, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)
    print(f"Update complete. Total tracked records: {len(records)}")

if __name__ == "__main__":
    analyze_and_extract()