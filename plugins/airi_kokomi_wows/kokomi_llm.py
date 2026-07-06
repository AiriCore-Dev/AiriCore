import os
import json
import nonebot
from openai import AsyncOpenAI

driver = nonebot.get_driver()

client = AsyncOpenAI(
    api_key = getattr(driver.config, "llm_api_key", ""),
    base_url = getattr(driver.config, "llm_base_url", "")
)

with open(os.path.join(os.path.dirname(__file__), 'kokomi_NL2C.md'),'r',encoding='utf-8') as f:
    role_setup = f.read()

async def kokomi_llm(input_words):
    try:
        completion = await client.chat.completions.create(
            model = getattr(driver.config, "other_llm_model", ""),
            messages=[
                {
                    "role": "system",
                    "content": role_setup
                },
                {
                    "role": "user",
                    "content": input_words
                }
            ],
            max_completion_tokens=1024,
            temperature=0,
            top_p=1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0,
        )

        msg_list = json.loads(completion.model_dump_json())["choices"][0]["message"]["content"].split(':')
        if len(msg_list) == 2:
            msg_list = [int(msg_list[0]),msg_list[1]]
            return msg_list
        else:
            raise ValueError("服务器繁忙，请稍后再试")
    except Exception as err:
        return [0,str(err)]
