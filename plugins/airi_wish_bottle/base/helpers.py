import gc
import base64
import hashlib

from openai import AsyncOpenAI

from . import state

client = AsyncOpenAI(
    api_key=getattr(state.driver.config, "llm_api_key", ""),
    base_url=getattr(state.driver.config, "llm_base_url", ""),
)

weijinci_prompt = '你是一个内容安全审核员。请判断用户输入的文本是否包含违规内容（政治敏感、色情、暴力、违法犯罪、辱骂攻击、广告引流、涉及未成年人不良信息等）。如果包含任何违规内容，只回复数字1；如果内容合规，只回复数字0。不要输出任何其他文字。'


async def parse_session(bot, ev):
    session_id = str(ev.get_session_id())
    if 'group' in session_id:
        split_id = session_id.split("_")
        user_id = split_id[2]
        gruop_id = split_id[1]
    else:
        user_id = session_id
        gruop_id = None
    user_nick = await bot.get_group_member_info(group_id=gruop_id, user_id=user_id)
    user_nick = (user_nick.get("nickname") or user_nick.get("card") or user_id)
    return user_id, gruop_id, user_nick


async def check_weijinci(text):
    try:
        completion = await client.chat.completions.create(
            model=getattr(state.driver.config, "other_llm_model", ""),
            messages=[
                {"role": "system", "content": weijinci_prompt},
                {"role": "user", "content": text},
            ],
            max_completion_tokens=4096,
            temperature=0.1,
            top_p=0.1,
            stream=False,
            stop=None,
            frequency_penalty=0,
            presence_penalty=0.1,
        )
        answer = completion.choices[0].message.content
        return 1 if '1' in answer else 0
    except:
        return 1


decr = lambda x: "".join([hex(i)[2:] for i in list(base64.b64decode(x.encode()))])
encr = lambda ff: base64.b64encode(bytes([int(ff[i:i+2], 16) for i in range(0, len(ff), 2)])).decode()
nxcr = lambda x: encr(hex(int(decr(x), 16) + 1)[2:])


async def generate_unique_id(content):
    unique_id = encr(hashlib.md5(content.encode()).hexdigest()[:12])
    unique_id_list = list(state.data["bottles"].keys()) + list(state.data["pending_bottles"].keys())
    while unique_id in unique_id_list:
        unique_id = nxcr(unique_id)
    return unique_id


def add_bottle(unique_id, owner=-1, owner_id=-1, content=-1, comments=-1, times=-1):
    data = state.data
    try:
        bottle_tmp = data['bottles'][unique_id]
    except:
        if owner == -1: owner = '田麻小溪'
        if owner_id == -1: owner_id = '864623174'
        if content == -1: content = ''
        if comments == -1: comments = []
        if times == -1: times = 0
        data['bottles'][unique_id] = {"owner": owner, "owner_id": owner_id, "content": content, "comments": comments, "times": times}
        try:
            data['collections'][owner_id].append(unique_id)
        except:
            data['collections'][owner_id] = [unique_id]
    else:
        for i in range(len(data['collections'][bottle_tmp["owner_id"]])):
            if data['collections'][bottle_tmp["owner_id"]][i] == unique_id:
                data['collections'][bottle_tmp["owner_id"]].pop(i)
                break
        if owner != -1: bottle_tmp['owner'] = str(owner)
        if owner_id != -1: bottle_tmp['owner_id'] = str(owner_id)
        if content != -1: bottle_tmp['content'] = str(content)
        if comments != -1: bottle_tmp['comments'] = comments
        if times != -1: bottle_tmp['times'] = int(times)
        data['bottles'][unique_id] = bottle_tmp
        try:
            data['collections'][owner_id].append(unique_id)
        except:
            data['collections'][owner_id] = [unique_id]


def delete_bottle(unique_id):
    data = state.data
    try:
        user_id = data['bottles'][unique_id]['owner_id']
    except:
        pass
    else:
        del data['bottles'][unique_id]
        for i in range(len(data['collections'][user_id])):
            if data['collections'][user_id][i] == unique_id:
                data['collections'][user_id].pop(i)
                break


def sync_bottle():
    collections = {}
    for i in state.data["bottles"].keys():
        user_id = str(state.data["bottles"][i]['owner_id'])
        try:
            collections[user_id].append(i)
        except:
            collections[user_id] = [i]
    state.data["collections"] = collections
    del collections
    gc.collect()


def send_email(dest, subject, text, html_body=None):
    state.email_list.append([dest, subject, text, html_body])
