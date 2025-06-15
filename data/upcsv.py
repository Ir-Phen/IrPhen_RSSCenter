import pandas as pd
from io import StringIO

# ===== 原始srt字符串 =====
srt = """name,Tag,Tip,pixiv_id,twitter_id,weibo_id,Bilibili/UID,米画师
,,,,,,,
あずーる,,,5838770,azure_0608_sub,,,
,,,,,,,
隔夜瓜瓜,,,,,5259086782,10074425,
,,,,,,,
廿罗,,,,,,8571162,
,,,,,,,
牡蛎不是努力,,,,,5073476986,,
,,,,,,,
,,,,,,,
饼饼冫,,,,,3383156732,3185813,
Laylakkkk杏,,,,,,301621,
,,,,,,,
什阿纺,,,,,7744308001,,
,,,,,,,
,,,,,,,
民◆joeManyODw,,,1568891,,,,
きのにく,,,92261662,,,,"""

# ===== 解析成 DataFrame =====
df = pd.read_csv(StringIO(srt), dtype=str)  # 强制所有列为字符串
df = df[df['name'].notna()].copy()  # 去除空行

# ===== 填充并生成 URL 字段 =====
def generate_urls(row):
    def make_url(base, ids):
        if pd.isna(ids): return ""
        return ";".join([f"{base}{i.strip()}" for i in str(ids).split(";") if i.strip()])

    row["pixiv_url"] = make_url("https://www.pixiv.net/users/", row.get("pixiv_id"))
    row["twitter_url"] = make_url("https://x.com/", row.get("twitter_id"))
    row["weibo_url"] = make_url("https://weibo.com/u/", row.get("weibo_id"))
    row["bili_url"] = make_url("https://space.bilibili.com/", row.get("Bilibili/UID"))
    return row

df = df.apply(generate_urls, axis=1)

# ===== 重命名列以匹配 Artist.csv 的结构 =====
df.rename(columns={
    "Tag": "tags",
    "Tip": "tips",
    "pixiv_id": "pixiv_id",
    "twitter_id": "twitter_id",
    "weibo_id": "weibo_id",
    "Bilibili/UID": "bili_id",
    "pixiv_url": "pixiv_url",
    "twitter_url": "twitter_url",
    "weibo_url": "weibo_url",
    "bili_url": "bili_url"
}, inplace=True)

# 补充空列以符合结构
df["name_used"] = ""
df["uni_id"] = ""
df["pixiv_name"] = ""
df["pixiv_user_comment"] = ""
df["twitter_name"] = ""
df["weibo_name"] = ""
df["bili_name"] = ""

# 按目标列顺序重排
columns = [
    "name", "name_used", "uni_id",
    "pixiv_name", "pixiv_id", "pixiv_user_comment", "pixiv_url",
    "twitter_name", "twitter_id", "twitter_url",
    "weibo_name", "weibo_id", "weibo_url",
    "bili_name", "bili_id", "bili_url",
    "tags", "tips"
]
df = df[columns]

# ===== 读取原始 Artist.csv 并合并 =====
artist_df = pd.read_csv("data/Artist.csv", dtype=str)  # 强制为字符串，防止数字变浮点

# 按 name 字段进行外连接（可修改为 inner/left/right 根据需求）
merged_df = pd.concat([artist_df, df], ignore_index=True)

# 去重（可选，根据 name 去重）
merged_df.drop_duplicates(subset=["name"], keep="first", inplace=True)

# ===== 写入新文件 =====
merged_df.to_csv("data/Artist_updata.csv", index=False, encoding="utf-8-sig")
