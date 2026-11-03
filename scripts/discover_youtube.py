#!/usr/bin/env python3
"""Discover candidate Chinese-city food videos through official YouTube Data API.
No comment bodies or personal user details are published or persisted.
"""
import argparse
import datetime as dt
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request

CITIES = {"Shanghai":"上海","Beijing":"北京","Guangzhou":"广州","Shenzhen":"深圳",
"Chengdu":"成都","Chongqing":"重庆","Hangzhou":"杭州","Suzhou":"苏州",
"Nanjing":"南京","Xian":"西安","Wuhan":"武汉","Xiamen":"厦门",
"Changsha":"长沙","Qingdao":"青岛","Kunming":"昆明","Tianjin":"天津"}
KEYWORDS = ["美食探店","苍蝇馆子","本地美食","food tour"]
SPAM = re.compile(r"(https?://|wa\.me/|whatsapp|telegram|加微|加V|私信领取|代购|返佣|推广链接)",re.I)
CLUES = re.compile(r"(店名|地址|在哪|在哪里|几号|路|街|巷|推荐|好吃|人均|元|面馆|饭店|餐厅|小吃|烧烤|火锅|粉店|馄饨|生煎|老店)")
def call(endpoint, params, key):
    params = dict(params, key=key)
    url = "https://www.googleapis.com/youtube/v3/"+endpoint+"?"+urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent":"ShanghaiMapDiscovery/0.1"}),timeout=25) as response:
        return json.load(response)
def normalize(s):
    return re.sub(r"\s+"," ",s or "").strip()
def collect_comments(video_id,key,limit=100):
    """Return aggregate public comment clues, not comment texts or user information."""
    found=0; examples=[]; token=None; pages=0
    while found<limit and pages<2:
        q={"part":"snippet","videoId":video_id,"maxResults":min(100,limit-found),"textFormat":"plainText","order":"relevance"}
        if token:q["pageToken"]=token
        try: payload=call("commentThreads",q,key)
        except urllib.error.HTTPError as e:
            if e.code in (403,404):break
            raise
        for item in payload.get("items",[]):
            comment=item.get("snippet",{}).get("topLevelComment",{}).get("snippet",{})
            txt=normalize(comment.get("textDisplay",""))
            if not txt or SPAM.search(txt) or len(txt)>600:continue
            if CLUES.search(txt):
                found+=1
                # Store only the source link as evidence; do not persist raw comments.
                if len(examples)<3:
                    examples.append("https://www.youtube.com/watch?v="+video_id+"&lc="+item["id"])
        token=payload.get("nextPageToken");pages+=1
        if not token:break
    return {"relevant_comment_count_sampled":found,"comment_evidence_urls":examples}
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--cities",nargs="*",default=list(CITIES))
    parser.add_argument("--max-searches",type=int,default=8)
    parser.add_argument("--comments-per-video",type=int,default=50)
    parser.add_argument("--output",default="data/youtube_candidates.json")
    args=parser.parse_args()
    key=os.getenv("YOUTUBE_API_KEY")
    if not key:raise SystemExit("YOUTUBE_API_KEY secret is required")
    today=dt.datetime.now(dt.timezone.utc)
    stop=min(today,dt.datetime(2027,1,1,tzinfo=dt.timezone.utc))
    start="2026-01-01T00:00:00Z"
    after=stop.strftime("%Y-%m-%dT%H:%M:%SZ")
    if stop.year<2026:raise SystemExit("2026 discovery window has not started")
    out=[];seen=set();searches=0
    for city in args.cities:
        if city not in CITIES:raise SystemExit("Unknown city: "+city)
        for keyword in KEYWORDS:
            if searches>=args.max_searches:break
            q={"part":"snippet","type":"video","q":CITIES[city]+" "+keyword,"maxResults":15,
               "publishedAfter":start,"publishedBefore":after,"order":"relevance","regionCode":"HK"}
            payload=call("search",q,key);searches+=1
            ids=[v["id"]["videoId"] for v in payload.get("items",[]) if v.get("id",{}).get("videoId")]
            if not ids:continue
            meta=call("videos",{"part":"snippet,statistics","id":",".join(ids)},key)
            for v in meta.get("items",[]):
                vid=v["id"]
                if vid in seen:continue
                seen.add(vid)
                sn=v["snippet"]
                published=sn.get("publishedAt","")
                if not published.startswith("2026"):continue
                title=normalize(sn.get("title",""))
                descr=normalize(sn.get("description",""))
                if not (CITIES[city] in title+" "+descr or city.lower() in (title+" "+descr).lower()):continue
                comments=collect_comments(vid,key,args.comments_per_video) if args.comments_per_video else {}
                out.append({"id":vid,"city_candidate":city,"title":title,"description_excerpt":descr[:400],
                  "published_at":published,"channel_title":sn.get("channelTitle",""),
                  "video_url":"https://www.youtube.com/watch?v="+vid,
                  "view_count":int(v.get("statistics",{}).get("viewCount",0)),
                  "comments":comments,"restaurant_name":None,"address":None,
                  "status":"needs_human_review","discovered_at":today.isoformat()})
        if searches>=args.max_searches:break
    path=pathlib.Path(args.output);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps({"schema_version":1,"generated_at":today.isoformat(),
      "note":"Video candidates, NOT verified restaurant pins; no raw comments saved",
      "cities":list(args.cities),"searches_run":searches,"candidates":out},
      ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(f"Saved {len(out)} video candidates from {searches} searches to {path}")
if __name__=="__main__":main()
