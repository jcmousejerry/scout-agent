import sys
sys.path.insert(0, ".")
from rag.vector_store import get_client, ensure_collection

client = get_client()
ensure_collection()
client.load_collection("football_theory")

stats = client.describe_collection(collection_name="football_theory")
print("集合名称:", stats.get("collection_name"))
print("向量维度:", stats.get("dimension"))
print("向量数量:", stats.get("num_of_entities", "N/A"))
print()

results = client.query(
    collection_name="football_theory",
    output_fields=["id", "text", "section"],
    limit=200
)
for r in results[:30]:
    text_preview = r.get("text", "")[:80].replace("\n", " ")
    print("  id={}  section={}  text={}...".format(
        r.get("id"), r.get("section", ""), text_preview
    ))

print("\n共 {} 条向量记录".format(len(results)))
