from openai import OpenAI
from config import API_KEY, BASE_URL_CHAT, LLM_MODEL

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL_CHAT,
    timeout=300.0,
    max_retries=2,
)


def chat(messages, stream=False, temperature=0.7, extra_body=None, timeout=None):
    kwargs = dict(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
    )
    if stream:
        kwargs["stream"] = True
    if extra_body:
        kwargs["extra_body"] = extra_body
    if timeout:
        kwargs["timeout"] = timeout
    return client.chat.completions.create(**kwargs)


def chat_with_search(messages, temperature=0.7):
    return client.chat.completions.create(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
        extra_body={"enable_search": True},
        timeout=300.0,
    )


def chat_stream(messages, temperature=0.7, extra_body=None, timeout=None):
    kwargs = dict(
        model=LLM_MODEL,
        messages=messages,
        temperature=temperature,
        stream=True,
    )
    if extra_body:
        kwargs["extra_body"] = extra_body
    if timeout:
        kwargs["timeout"] = timeout
    stream = client.chat.completions.create(**kwargs)
    for chunk in stream:
        if not getattr(chunk, "choices", None):
            continue
        delta = chunk.choices[0].delta
        content = getattr(delta, "content", None)
        if content:
            yield content