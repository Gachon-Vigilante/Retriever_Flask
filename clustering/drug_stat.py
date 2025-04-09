from pymongo import MongoClient
import pandas as pd

client = MongoClient("mongodb://admin:sherlocked@34.64.57.207:27017/")
db = client['retriever-woohyuk']
drug_collection = db['drugs']

def drug_type():
    pipeline = [
        {
            "$group": {
                "_id": "$drugName",
                "total_count": {"$sum": "$count"}
            }
        },
        {
            "$sort": {"total_count": -1}
        }
    ]
    result = list(drug_collection.aggregate(pipeline))
    return [{"drug": r["_id"], "count": r["total_count"]} for r in result]

def drug_time(period='monthly'):
    cursor = drug_collection.find({}, {"count": 1, "updatedAt": 1})
    data = []

    for doc in cursor:
        timestamp = doc.get("updatedAt")
        if not timestamp:
            continue

        if period == 'monthly':
            key = timestamp.strftime("%Y-%m")
        else:
            key = timestamp.strftime("%Y-%W")  # 주차 기준

        data.append({
            "period": key,
            "count": doc.get("count", 0)
        })

    df = pd.DataFrame(data)
    grouped = df.groupby("period").sum().reset_index()
    return grouped.to_dict(orient="records")
