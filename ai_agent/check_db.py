import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from rag.vector_store import get_client, COLLECTION_NAME

client = get_client()
client.load_collection(COLLECTION_NAME)

info = client.describe_collection(COLLECTION_NAME)
print("=== 集合描述 ===")
print(f"  名称: {info['collection_name']}")
print(f"  动态字段: {info.get('enable_dynamic_field', 'N/A')}")
print(f"  正式字段数: {len(info.get('fields', []))}")
for f in info.get('fields', []):
    print(f"    - {f}")

print()
print("=== 实际数据（含动态字段） ===")
res = client.query(
    collection_name=COLLECTION_NAME,
    filter="id >= 0",
    output_fields=["id", "name", "team", "position", "text"],
    limit=2,
)
for r in res:
    print(f"  id={r['id']}, name={r['name']}, team={r['team']}, pos={r['position']}")
    print(f"  text={r['text'][:60]}...")
    print()

print("=== 结论 ===")
print("schema 只定义了 id + vector 两个正式字段")
print("name/team/position/text 作为动态字段存储（enable_dynamic_field=true）")
print("动态字段不用预定义 schema，可随 insert 自动写入，查询时可直接读取")
