import sys
import json
from agent import create_session, submit_answers, run_full_analysis


def main():
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
    else:
        query = input("请输入球探查询需求: ")

    print("\n[1/5] 正在明确需求...")
    result = create_session(query)

    while not result["clarification_done"]:
        print(f"\n已明确的需求：{json.dumps(result.get('answers', {}), ensure_ascii=False, indent=2)}")
        print("\n请回答以下问题：")
        for q in result["questions"]:
            print(f"\n{q['question']}")
            for i, opt in enumerate(q["options"]):
                print(f"  {i + 1}. {opt['label']}")
            choice = int(input("请选择 (输入编号): ")) - 1
            selected = q["options"][choice] if 0 <= choice < len(q["options"]) else q["options"][0]
            result = submit_answers(result["session_id"], {q["id"]: selected["value"]})
            if result.get("error"):
                print(f"错误: {result['error']}")
                return

    print("\n[2/5] 需求已明确，开始检索足球知识库...")
    print("[3/5] 生成候选球员推荐...")
    print("[4/5] 多专家辩论中...")

    for event in run_full_analysis(result["session_id"]):
        etype = event["event"]
        data = event.get("data", {})
        if etype == "progress":
            print(f"  进度: {data.get('message', '')} ({data.get('progress', 0)}%)")
        elif etype == "candidates":
            print("\n候选球员：")
            for i, c in enumerate(data.get("candidates", [])):
                print(f"  {i+1}. {c['name']} ({c['position']}, {c['team']})")
        elif etype == "debate":
            speaker = data.get("speaker", "")
            if data.get("type") == "elimination":
                print(f"\n  ❌ 淘汰: {', '.join(data.get('eliminated', []))}")
            else:
                content = data.get("content", "")
                print(f"\n  [{speaker}]: {content[:100]}...")
        elif etype == "result":
            print("\n" + "=" * 60)
            print("最终球探报告")
            print("=" * 60)
            print(data.get("report", ""))
        elif etype == "error":
            print(f"\n错误: {data.get('message', '')}")

    print("\n分析完成。")


if __name__ == "__main__":
    main()
