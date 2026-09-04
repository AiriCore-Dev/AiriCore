import os
from utils import llm

with open(os.path.join(os.path.dirname(__file__), 'kokomi_NL2C.md'),'r',encoding='utf-8') as f:
    role_setup = f.read()

def _parse_nl2c(text):
    msg_list = text.split(':')
    if len(msg_list) != 2:
        raise ValueError("服务器繁忙，请稍后再试")
    return [int(msg_list[0]), msg_list[1]]


async def kokomi_llm(input_words):
    try:
        return await llm.call_with_fallback(
            [
                {
                    "role": "system",
                    "content": role_setup
                },
                {
                    "role": "user",
                    "content": input_words
                }
            ],
            tag="kokomi_nl2c",
            usage_source="水表",
            validate=_parse_nl2c,
            max_completion_tokens=4096,
            temperature=0,
            top_p=1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0,
        )
    except Exception as err:
        return [0, str(err)]
