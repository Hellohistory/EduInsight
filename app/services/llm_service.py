# app/services/llm_service.py

from openai import OpenAI, APIStatusError, APIError
from tenacity import retry, stop_after_attempt, wait_random_exponential

from app.core.config import settings

try:
    client = OpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url=settings.DEEPSEEK_BASE_URL
    )
except Exception as e:
    print(f"初始化 OpenAI 客户端失败: {e}")
    client = None


@retry(wait=wait_random_exponential(min=1, max=30), stop=stop_after_attempt(3))
def get_completion(prompt: str) -> str | None:

    if not client:
        raise RuntimeError("LLM 服务客户端未成功初始化，请检查配置。")

    try:

        response = client.chat.completions.create(
            model=settings.DEEPSEEK_MODEL,
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=4096,
            stream=False,
        )


        content = response.choices[0].message.content
        return content.strip() if content else None

    except APIStatusError as e:
        print(f"调用 DeepSeek API 时发生 HTTP 状态错误: Status={e.status_code}, Response={e.response}")
        raise
    except APIError as e:
        print(f"调用 DeepSeek API 时发生 API 错误: {e}")
        raise
    except Exception as e:

        print(f"调用 DeepSeek API 时发生未知错误: {e}")
        raise