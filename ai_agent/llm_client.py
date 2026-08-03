from openai import OpenAI
from config import API_KEY, BASE_URL_CHAT, LLM_MODEL

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL_CHAT,
    timeout=300.0,
    max_retries=2,
)


def _chat_kwargs(messages, temperature, extra_body=None, timeout=None):
    extra_body = dict(extra_body or {})
    if extra_body.get("enable_search"):
        search_options = dict(extra_body.get("search_options") or {})
        search_options.setdefault("forced_search", True)
        extra_body["search_options"] = search_options

    kwargs = {
        "model": LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
    }
    if extra_body:
        kwargs["extra_body"] = extra_body
    if timeout:
        kwargs["timeout"] = timeout
    return kwargs


def chat(messages, stream=False, temperature=0.7, extra_body=None, timeout=None):
    kwargs = _chat_kwargs(messages, temperature, extra_body, timeout)
    if stream:
        kwargs["stream"] = True
    return client.chat.completions.create(**kwargs)


def chat_with_search(messages, temperature=0.7):
    return chat(
        messages,
        temperature=temperature,
        extra_body={"enable_search": True},
        timeout=300.0,
    )


def chat_stream(messages, temperature=0.7, extra_body=None, timeout=None):
    kwargs = _chat_kwargs(messages, temperature, extra_body, timeout)
    kwargs["stream"] = True
    for chunk in client.chat.completions.create(**kwargs):
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content
