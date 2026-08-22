import json
import logging
import threading
import queue as _queue
import uuid
from workflow import (
    create_initial_state, generate_clarify_questions, process_answers,
    finalize_clarification, ScoutState, DEBATE_AGENTS, CHIEF_SCOUT,
    AGENT_NAMES_CN,
    _build_agent_messages, _build_chief_eliminate_messages,
    _parse_chief_decision, generate_candidates_stream,
)
from llm_client import chat_stream
from langgraph.checkpoint.memory import MemorySaver

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("agent")

sessions = {}


def _is_content_filter_error(err: Exception) -> bool:
    """检测是否为百炼/通义内容安全拦截类错误。"""
    msg = str(err).lower()
    keys = ("inappropriate content", "content filter", "content_filter",
            "data may contain", "safety", "risk", "敏感内容", "内容审核")
    return any(k in msg for k in keys)


def _stream_worker(role, messages_provider, temperature, q, msg_id,
                   hide_chunks: bool = False, on_done_text=None):
    """在独立线程中构建消息(可能含联网搜索)并调用LLM流式接口。

    hide_chunks=True: 不向队列推送 chunk 事件（用于 chief_scout 的 JSON 阶段，避免把
    原始 JSON 串流式打到前端）；最终通过 on_done_text(content) 回调或 done 事件返回。
    """
    started = False
    try:
        messages = messages_provider() if callable(messages_provider) else messages_provider
        q.put(("start", role, msg_id, None))
        started = True
        parts = []
        for delta in chat_stream(messages, temperature=temperature):
            parts.append(delta)
            if not hide_chunks:
                q.put(("chunk", role, msg_id, delta))
        full = "".join(parts)
        q.put(("done", role, msg_id, full))
    except Exception as e:
        logger.error(f"Stream failed for {role}: {e}")
        if _is_content_filter_error(e):
            err = (f"（{AGENT_NAMES_CN.get(role, role)}本轮发言被内容安全策略拦截，"
                   f"请稍后重试或调整问题表述。）")
        else:
            err = f"（{AGENT_NAMES_CN.get(role, role)}暂时无法完成分析，请稍后重试。）"
        if not started:
            q.put(("start", role, msg_id, None))
        if not hide_chunks:
            q.put(("chunk", role, msg_id, err))
        q.put(("done", role, msg_id, err if on_done_text is None else on_done_text(err)))


def _run_parallel_stream(roles, build_fn, state, temperature=0.7, key_prefix=""):
    """并行启动多个 agent 流式输出。build_fn(role, state) 在每个工作线程中执行（含联网搜索）。"""
    q = _queue.Queue()
    msg_ids = {role: f"{key_prefix}{role}_{uuid.uuid4().hex[:6]}" for role in roles}
    threads = []
    for role in roles:
        provider = (lambda r=role: build_fn(r, state))
        t = threading.Thread(
            target=_stream_worker,
            args=(role, provider, temperature, q, msg_ids[role]),
            daemon=True,
        )
        t.start()
        threads.append(t)
    return q, threads, msg_ids


def _drain_stream_queue(q, threads, roles, round_num, msg_type="discussion"):
    """生成器：实时弹出每个 token 的 SSE 事件，全部完成后再返回 (completion_order, contents)。"""
    done_count = 0
    n = len(roles)
    completion_order = []
    contents = {}
    while done_count < n:
        kind, role, msg_id, payload = q.get()
        if kind == "start":
            yield ("debate_start", {
                "type": msg_type,
                "speaker": AGENT_NAMES_CN.get(role, role),
                "speaker_key": role,
                "msg_id": msg_id,
                "round": round_num,
                "content": "",
            })
        elif kind == "chunk":
            yield ("debate_chunk", {
                "msg_id": msg_id,
                "speaker_key": role,
                "delta": payload,
            })
        elif kind == "done":
            contents[role] = payload
            completion_order.append(role)
            done_count += 1
            yield ("debate_done", {
                "type": msg_type,
                "speaker": AGENT_NAMES_CN.get(role, role),
                "speaker_key": role,
                "msg_id": msg_id,
                "round": round_num,
                "content": payload,
            })
    for t in threads:
        t.join()
    yield ("__result__", (completion_order, contents))


def create_session(query: str, candidate_count: int = 3) -> dict:
    state = create_initial_state(query, candidate_count)
    sessions[state["session_id"]] = state
    state = generate_clarify_questions(state)
    sessions[state["session_id"]] = state
    return {
        "session_id": state["session_id"],
        "questions": state["questions"],
        "clarification_done": state["clarification_done"],
    }


def submit_answers(session_id: str, answers: dict, candidate_count: int = 3) -> dict:
    state = sessions.get(session_id)
    if not state:
        return {"error": "session not found"}
    state = process_answers(state, answers)
    state = generate_clarify_questions(state)
    state["candidate_count"] = max(2, min(candidate_count, 5))
    sessions[session_id] = state
    return {
        "session_id": state["session_id"],
        "questions": state["questions"],
        "clarification_done": state["clarification_done"],
        "answers": state["answers"],
    }


def run_full_analysis(session_id: str, preferences_memory: str = None):
    state = sessions.get(session_id)
    if not state:
        yield {"event": "error", "data": {"message": "session not found"}}
        return
    if preferences_memory:
        state["preferences_memory"] = preferences_memory

    state = finalize_clarification(state)
    sessions[session_id] = state

    yield {"event": "progress", "data": {"step": "rag", "message": "正在检索足球知识库...", "progress": 8}}

    from workflow import retrieve_knowledge, generate_candidates, generate_final_report
    state = retrieve_knowledge(state)
    sessions[session_id] = state
    yield {
        "event": "progress",
        "data": {"step": "rag", "message": f"知识库检索完成，已获取 {state['retrieved_count']} 条相关信息", "progress": 20},
    }

    yield {"event": "progress", "data": {"step": "candidates", "message": "正在联网搜索，逐个生成候选球员...", "progress": 30}}
    candidates_acc: list = []
    total_expected = state.get("candidate_count", 3)
    for event in generate_candidates_stream(state):
        if "final_state" in event:
            state = event["final_state"]
            sessions[session_id] = state
            yield {
                "event": "candidates",
                "data": {
                    "candidates": event["final_state"]["candidates"],
                    "complete": True,
                },
            }
        else:
            candidates_acc = event.get("candidates_so_far", candidates_acc)
            sessions[session_id] = {**state, "candidates": list(candidates_acc)}
            yield {
                "event": "candidate",
                "data": {
                    "candidate": event["candidate"],
                    "index": event["index"],
                    "total": event["total"],
                    "candidates_so_far": event["candidates_so_far"],
                    "complete": False,
                },
            }
            yield {
                "event": "progress",
                "data": {
                    "step": "candidates",
                    "message": f"已筛选出 {event['index'] + 1}/{event['total']} 名候选球员（{event['candidate']['name']}），继续搜索中...",
                    "progress": 30 + int((event["index"] + 1) / event["total"] * 12),
                },
            }
    yield {"event": "progress", "data": {"step": "debate", "message": f"已确定{len(state['candidates'])}名候选球员，即将开始多专家群聊辩论...", "progress": 45}}

    max_rounds = 10
    for round_idx in range(max_rounds):
        round_num = round_idx + 1
        state["debate_round"] = round_num
        sessions[session_id] = state

        yield {
            "event": "round_start",
            "data": {"round": round_num, "message": f"第 {round_num} 轮专家讨论开始"},
        }

        active = [c for c in state["candidates"] if c["name"] not in state["eliminated"]]
        if len(active) <= 1:
            state["debate_done"] = True
            state["final_candidate"] = active[0] if active else None
            sessions[session_id] = state
            yield {
                "event": "progress",
                "data": {"step": "debate", "message": "辩论环节结束，已确定最终推荐球员", "progress": 92},
            }
            break

        yield {
            "event": "progress",
            "data": {"step": "debate", "message": f"第 {round_num} 轮 - 4位专家正在并行联网搜索 + 流式分析中...", "progress": min(45 + round_idx * 5, 85)},
        }

        # 4 位专家并行流式输出，每个 agent 完成搜索后立即开始流式推送 token
        q, threads, msg_ids = _run_parallel_stream(
            DEBATE_AGENTS, _build_agent_messages, state, temperature=0.7,
            key_prefix=f"r{round_num}_",
        )

        completion_order = None
        contents = None
        for etype, data in _drain_stream_queue(q, threads, DEBATE_AGENTS, round_num, "discussion"):
            if etype == "__result__":
                completion_order, contents = data
            else:
                yield {"event": etype, "data": data}

        # 按完成顺序写入状态（用于下一轮上下文）
        for role in completion_order:
            state["debate_messages"].append({
                "speaker": role,
                "role": AGENT_NAMES_CN.get(role, role),
                "content": contents[role],
                "round": round_num,
                "type": "discussion",
                "msg_id": msg_ids[role],
            })
        sessions[session_id] = state

        yield {
            "event": "progress",
            "data": {"step": "debate", "message": f"第 {round_num} 轮 - 总球探正在综合各专家意见，流式生成本轮淘汰决定...", "progress": min(48 + round_idx * 5, 88)},
        }

        # 总球探流式输出淘汰决定。LLM 返回 JSON，我们不在前端流式渲染 JSON 串，
        # 而是 hide_chunks=True 隐藏 chunk，等拿到 JSON 完整内容后解析成自然语言
        # 淘汰决定一次性显示给用户。
        chief_messages, active_names = _build_chief_eliminate_messages(state)
        chief_msg_id = f"r{round_num}_chief_{uuid.uuid4().hex[:6]}"
        chief_q = _queue.Queue()
        chief_t = threading.Thread(
            target=_stream_worker,
            args=(CHIEF_SCOUT, chief_messages, 0.5, chief_q, chief_msg_id),
            kwargs={"hide_chunks": True},
            daemon=True,
        )
        chief_t.start()

        done = False
        while not done:
            kind, role, msg_id, payload = chief_q.get()
            if kind == "start":
                yield {
                    "event": "debate_start",
                    "data": {
                        "type": "elimination",
                        "speaker": AGENT_NAMES_CN.get(CHIEF_SCOUT, "总球探"),
                        "speaker_key": CHIEF_SCOUT,
                        "msg_id": chief_msg_id,
                        "round": round_num,
                        "content": "",
                        "pending": True,
                    },
                }
            elif kind == "chunk":
                # hide_chunks=True 下不会出现，保险起见忽略
                pass
            elif kind == "done":
                done = True
                decision = _parse_chief_decision(payload, active_names)
                target = decision.get("eliminate_candidate", "")
                if target and target not in state["eliminated"]:
                    state["eliminated"].append(target)
                elimination_text = (
                    f"【本轮淘汰决定】淘汰 {target}。\n\n"
                    f"理由：{decision.get('eliminate_reason', '综合评估后决定')}\n\n"
                    f"本轮小结：{decision.get('round_summary', '')}"
                )
                state["debate_messages"].append({
                    "speaker": CHIEF_SCOUT,
                    "role": AGENT_NAMES_CN.get(CHIEF_SCOUT, "总球探"),
                    "content": elimination_text,
                    "round": round_num,
                    "type": "elimination",
                    "msg_id": chief_msg_id,
                })
                sessions[session_id] = state
                logger.info(f"Round {round_num} eliminated: {target}")
                yield {
                    "event": "debate_done",
                    "data": {
                        "type": "elimination",
                        "speaker": AGENT_NAMES_CN.get(CHIEF_SCOUT, "总球探"),
                        "speaker_key": CHIEF_SCOUT,
                        "msg_id": chief_msg_id,
                        "round": round_num,
                        "content": elimination_text,
                        "eliminated": state["eliminated"],
                        "active_count": len([c for c in state["candidates"] if c["name"] not in state["eliminated"]]),
                    },
                }
        chief_t.join()

        active_after = [c for c in state["candidates"] if c["name"] not in state["eliminated"]]
        if len(active_after) <= 1:
            state["debate_done"] = True
            state["final_candidate"] = active_after[0] if active_after else None
            sessions[session_id] = state
            yield {
                "event": "progress",
                "data": {"step": "debate", "message": "辩论环节结束，已确定最终推荐球员", "progress": 92},
            }
            break

    yield {"event": "progress", "data": {"step": "report", "message": "正在生成最终球探报告...", "progress": 95}}
    state = generate_final_report(state)
    sessions[session_id] = state
    yield {
        "event": "result",
        "data": {
            "report": state["final_report"],
            "final_candidate": state["final_candidate"],
            "candidates": state["candidates"],
            "eliminated": state["eliminated"],
            "retrieved_count": state["retrieved_count"],
            "debate_messages": state["debate_messages"],
        },
    }
    yield {"event": "progress", "data": {"step": "done", "message": "分析完成", "progress": 100}}


def get_session(session_id: str) -> ScoutState | None:
    return sessions.get(session_id)
