import os
import json
import time
import urllib.parse
import xml.etree.ElementTree as ET
import requests

# 1. 优化 ru_keys：使用“词根”或枚举变格，解决俄语语法变格匹配不到的问题！
GEO_DATABASE = {
    "chapayevsk": {"ru_keys": ["чапаевск", "самар"], "name": "Ozon 萨马拉仓", "platform": "Ozon", "lat": 52.9833, "lng": 49.7167, "area": "135,000 m²"},
    "orenburg": {"ru_keys": ["оренбург"], "name": "Ozon 奥伦堡仓", "platform": "Ozon", "lat": 51.7667, "lng": 55.1000, "area": "40,000 m²"},
    "krasnodar": {"ru_keys": ["краснодар"], "name": "Ozon 克拉斯诺达尔仓", "platform": "Ozon/WB", "lat": 45.0355, "lng": 38.9753, "area": "150,000 m²"},
    "makhachkala": {"ru_keys": ["махачкал", "дагестан"], "name": "Ozon 马哈奇卡拉仓", "platform": "Ozon", "lat": 42.9849, "lng": 47.5046, "area": "分拨仓"},
    "adygea": {"ru_keys": ["адыге"], "name": "Ozon 阿迪格仓", "platform": "Ozon", "lat": 44.8833, "lng": 39.1833, "area": "未知"},
    "stavropol": {"ru_keys": ["ставропол", "невинномысс"], "name": "Ozon 斯塔夫罗波尔仓", "platform": "Ozon", "lat": 44.6333, "lng": 41.9333, "area": "未知"},
    "ufa": {"ru_keys": ["уфа", "уфе", "уфу", "башкир"], "name": "Ozon 乌法仓", "platform": "Ozon", "lat": 54.7388, "lng": 55.9721, "area": "未知"},
    "rostov": {"ru_keys": ["ростов"], "name": "Ozon 罗斯托夫仓", "platform": "Ozon", "lat": 47.2333, "lng": 39.7000, "area": "未知"}
}

def fetch_rss_news(query):
    """从 Google News 抓取新闻"""
    encoded_query = urllib.parse.quote(query)
    # 取消复杂的 OR，加上 when:1y (获取过去1年的新闻)，提高命中率
    url = f"https://news.google.com/rss/search?q={encoded_query}+when:1y&hl=ru&gl=RU&ceid=RU:ru"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code != 200:
            print(f"[错误] RSS 请求失败，状态码: {resp.status_code}")
            return []
        
        root = ET.fromstring(resp.content)
        items = []
        for item in root.findall(".//item")[:30]: # 每次拿30条
            title = item.find("title").text if item.find("title") is not None else ""
            link = item.find("link").text if item.find("link") is not None else ""
            pub_date = item.find("pubDate").text if item.find("pubDate") is not None else ""
            items.append({"title": title, "link": link, "date": pub_date})
        return items
    except Exception as e:
        print(f"[错误] 抓取异常: {e}")
        return []

def analyze_and_extract():
    # 简化查询词，把复杂的逻辑交给 Python 脚本判断，避免 RSS 接口罢工
    queries = [
        "Ozon склад", 
        "Озон склад",
        "Wildberries склад"
    ]
    
    all_news = []
    print("开始从 Google News 获取数据...")
    for q in queries:
        news_items = fetch_rss_news(q)
        print(f"关键词 '{q}' 抓取到 {len(news_items)} 条新闻")
        all_news.extend(news_items)
        time.sleep(1.5)

    if not all_news:
        print("未抓取到任何新闻，请检查网络是否能访问 Google (需科学上网)！")
        return

    data_file = "data.json"
    if os.path.exists(data_file):
        with open(data_file, "r", encoding="utf-8") as f:
            records = json.load(f)
    else:
        records = []

    existing_titles = {r.get("news_title", "") for r in records}
    new_records_count = 0

    print("\n--- 开始分析新闻内容 ---")
    for news in all_news:
        title = news["title"]
        if title in existing_titles:
            continue

        title_lower = title.lower()
        matched_platform = None
        
        if "ozon" in title_lower or "озон" in title_lower:
            matched_platform = "Ozon"
        elif "wildberries" in title_lower or "вайлдберриз" in title_lower or " wb " in title_lower:
            matched_platform = "Wildberries"

        # 判断是否是灾害/遇袭相关新闻
        incident_keywords = ["пожар", "дрон", "беспилотник", "атака", "горит", "возгорание", "эвакуац"]
        is_incident = any(word in title_lower for word in incident_keywords)

        if matched_platform and is_incident:
            matched_geo = None
            for key, geo in GEO_DATABASE.items():
                if any(ru_key in title_lower for ru_key in geo.get("ru_keys", [])):
                    matched_geo = geo
                    break

            if matched_geo:
                print(f"[命中!] 发现匹配: {matched_geo['name']} -> {title}")
                records.append({
                    "id": f"auto-{int(time.time())}-{new_records_count}",
                    "platform": matched_platform,
                    "name": matched_geo["name"],
                    "type": "ozon-damaged" if matched_platform == "Ozon" else "wb-damaged",
                    "lat": matched_geo["lat"],
                    "lng": matched_geo["lng"],
                    "area": matched_geo["area"],
                    "date": news["date"][:16],
                    "status": "监测到异常(火灾/袭击)",
                    "details": title,
                    "news_title": title,
                    "source_url": news["link"]
                })
                existing_titles.add(title)
                new_records_count += 1
            else:
                # 抓到了事故新闻，但没匹配上已有的城市库
                print(f"[未知城市/需新增] 平台:{matched_platform} 发生事故，但在词库未匹配到城市: {title}")

    # 写回文件
    if new_records_count > 0:
        with open(data_file, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 更新成功！向 data.json 写入了 {new_records_count} 条新记录。目前总计追踪记录数: {len(records)}")
    else:
        print(f"\n未发现新的遇袭/火灾新闻。目前总追踪记录数依然为: {len(records)}")

if __name__ == "__main__":
    analyze_and_extract()
