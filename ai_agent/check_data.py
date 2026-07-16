import sys
sys.path.insert(0, ".")
from rag.vector_store import get_client, ensure_collection

client = get_client()
ensure_collection()
client.load_collection("football_theory")

stats = client.describe_collection(collection_name="football_theory")
print("=" * 60)
print("集合信息")
print("=" * 60)
print(f"  名称:      {stats.get('collection_name')}")
print(f"  向量维度:   {stats.get('dimension')}")
print(f"  向量数量:   {stats.get('num_of_entities', 'N/A')}")
print()

results = client.query(
    collection_name="football_theory",
    output_fields=["id", "text", "section"],
    limit=200
)

print("=" * 60)
print(f"标量数据预览（共 {len(results)} 条）")
print("=" * 60)
for r in results:
    text_preview = r.get("text", "")[:100].replace("\n", " ")
    print(f"  id={r['id']:<4}  section={r.get('section',''):<16}  text={text_preview}...")
print()

print("向量数据预览（取第1条前10维）")
print("-" * 60)
vec_data = client.get(
    collection_name="football_theory",
    ids=[0],
    output_fields=["vector"]
)
if vec_data:
    v = vec_data[0].get("vector", [])
    vec_str = ", ".join(f"{x:+.6f}" for x in v[:10])
    print(f"  id=0  vector[:10] = [{vec_str}, ...]  (共 {len(v)} 维)")
print()

print("=" * 60)
print("向量搜索测试（使用第一条文本的向量查询自身）")
print("=" * 60)
if vec_data:
    q_vec = vec_data[0]["vector"]
    search_results = client.search(
        collection_name="football_theory",
        data=[q_vec],
        limit=5,
        output_fields=["text", "section"],
    )
    for i, hit in enumerate(search_results[0]):
        entity = hit.get("entity") or {}
        text_preview = entity.get("text", "")[:80].replace("\n", " ")
        print(f"  rank={i+1}  distance={hit['distance']:.4f}  "
              f"section={entity.get('section','')}  text={text_preview}...")
