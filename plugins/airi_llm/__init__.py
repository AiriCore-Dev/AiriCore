import os
import re
import json
import time
import httpx
import random
import base64
import asyncio
import logging
import datetime
import traceback
from utils.totp_2fa import totp_verify
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
from nonebot import (
    get_driver,
    on_message,
    require,
    on_startswith,
    logger as nonebot_logger
)
from nonebot.rule import to_me
from nonebot.permission import SUPERUSER
from nonebot.adapters.onebot.v11 import (
    Bot,
    MessageSegment,
    MessageEvent,
    GroupMessageEvent
)

# ===================== 配置常量 =====================
# 日志配置
driver = get_driver()
logger = logging.getLogger("airi_llm")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)

# 白名单配置
WHITELIST_GROUP = {"657965723", "740774974", "466470972", "823217376", "808085026", "1030569383", "609034568"}
WHITELIST_BOT = {"1330248395", "535071478", "2745762139", "1264177306","3357763830"}
SUPERUSERS = {"864623174", "3630532026"}

# 内存/发言配置
MEMORY_MAX_CAPACITY_GROUP = 200  # 群记忆最大存储数量
PASSIVE_SPEAK_DELAY_RANGE = (301, 7200)  # 被动发言延迟范围（秒）
NEGATIVE_SPEAK_TOKENS_INIT = 50  # 发言令牌初始值
NEGATIVE_SPEAK_TOKENS_DEDUCT = 3  # 每次消息扣除令牌数
RANDOM_SPEAK_PROBABILITY = 1 / 150  # 随机发言概率
PASSIVE_SPEAK_TRIGGER_PROB = 1 / 150  # 被动发言触发概率
EMOJI_RANDOM_PROB = 1 / 10  # 发送表情概率
FINAL_EMOJI_PROB = 1 / 5  # 结尾发送表情概率

# LLM调用配置
LLM_MODEL = getattr(driver.config, "chat_llm_model", "")
LLM_MAX_TOKENS = 8000
LLM_TEMPERATURE = 1.0
LLM_TOP_P = 0.9
LLM_FREQ_PENALTY = 0.3
LLM_PRESENCE_PENALTY = 0.2
_2fa_key = getattr(driver.config, "_2fa_key", "")

# 路径配置
PROJECT_DIR = os.path.dirname(__file__)
ROLE_SETUP_FILE = os.path.join(PROJECT_DIR, "airi_prompt_v2.md")
EMOJI_DIR = os.path.join(PROJECT_DIR, "emoji")

# ===================== 状态管理（替代全局变量，更可控） =====================
class AiriState:
    def __init__(self):
        self.role_setup: str = ""
        self.group_is_tamed: Dict[str, int] = {}
        self.passive_speaking_group_tamed: Dict[str, int] = {}  # 修复命名：is_tamed → tamed
        self.last_speak_time_group: Dict[str, float] = {}
        self.negative_speaking_tokens: Dict[str, int] = {}
        self.memory_group: Dict[str, List[str]] = {}
        self.emoji_list: List[str] = []

    def flush_prompt(self) -> str:
        """刷新角色提示词（从文件读取）"""
        try:
            with open(ROLE_SETUP_FILE, "r", encoding="utf-8") as f:
                self.role_setup = f.read().strip()
            logger.info("角色提示词已刷新")
            return "提示词已刷新"
        except Exception as e:
            logger.error(f"刷新提示词失败: {e}")
            raise

    def init_emoji_list(self) -> None:
        """初始化表情列表"""
        if not os.path.exists(EMOJI_DIR):
            logger.warning(f"表情目录不存在: {EMOJI_DIR}")
            self.emoji_list = []
            return
        self.emoji_list = [
            os.path.join(EMOJI_DIR, fname)
            for fname in os.listdir(EMOJI_DIR)
            if os.path.isfile(os.path.join(EMOJI_DIR, fname))
        ]
        logger.info(f"加载表情数量: {len(self.emoji_list)}")

# 初始化状态实例
airi_state = AiriState()
airi_state.flush_prompt()
airi_state.init_emoji_list()

# ===================== LLM客户端初始化 =====================

client = AsyncOpenAI(
    api_key = getattr(driver.config, "llm_api_key", ""),
    base_url = getattr(driver.config, "llm_base_url", "")
)

# ===================== 工具函数（单一职责） =====================
async def get_image_base64_list(message: Any) -> List[str]:
    """
    提取消息中的图片并转换为Base64编码列表
    :param message: 消息对象
    :return: Base64编码列表
    """
    base64_results = []
    async with httpx.AsyncClient() as http_client:
        for seg in message:
            if seg.type != "image":
                continue
            file_str: str = seg.data.get("url", "")
            try:
                # 1. Base64格式
                if file_str.startswith("base64://"):
                    b64_data = file_str[len("base64://"):]
                    base64_results.append(b64_data)
                # 2. 网络URL
                elif file_str.startswith(("http://", "https://")):
                    resp = await http_client.get(file_str)
                    resp.raise_for_status()
                    b64_data = base64.b64encode(resp.content).decode("utf-8")
                    base64_results.append(b64_data)
                # 3. 本地文件
                elif file_str.startswith("file://"):
                    file_path = file_str[len("file://"):]
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            b64_data = base64.b64encode(f.read()).decode("utf-8")
                            base64_results.append(b64_data)
            except Exception as e:
                logger.warning(f"处理图片失败: {str(e)}")
    return base64_results

async def call_llm(
    system_prompt: str,
    user_input: str,
    group_id: str,
    img_b64_list: List[str]
) -> str:
    """
    调用LLM接口获取回复
    :param system_prompt: 系统提示词
    :param user_input: 用户输入
    :param group_id: 群ID
    :param img_b64_list: 图片Base64列表
    :return: LLM回复内容（空字符串表示失败）
    """
    # 构造消息内容
    content = [{"type": "text", "text": user_input}]
    
    for img_b64 in img_b64_list:
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        })
    
    try:
        completion = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": content}
            ],
            max_completion_tokens=LLM_MAX_TOKENS,
            temperature=LLM_TEMPERATURE,
            top_p=LLM_TOP_P,
            stream=False,
            stop=None,
            frequency_penalty=LLM_FREQ_PENALTY,
            presence_penalty=LLM_PRESENCE_PENALTY,
#            extra_body={"thinking": {"type": "disabled"}}
#            tools=[
#                {
#                    "type": "web_search",
#                    "max_keyword": 3,
#                    "force_search": False,
#                    "limit": 1
#                }
#            ],
#            tool_choice="auto"
        )
        # 解析回复
        reply = json.loads(completion.model_dump_json())
        return reply["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.error(f"调用LLM失败: {e}")
        # 内存超限则截断
        if airi_state.memory_group.get(group_id):
            airi_state.memory_group[group_id] = airi_state.memory_group[group_id][:-10]
        return ""

async def generate_random_emoji() -> MessageSegment:
    """生成随机表情消息段"""
    if not airi_state.emoji_list:
        return MessageSegment.text("😜")  # 兜底表情
    emoji_path = random.choice(airi_state.emoji_list)
    with open(emoji_path, "rb") as f:
        b64_data = base64.b64encode(f.read()).decode("utf-8")
    return MessageSegment.image(f"base64://{b64_data}")

async def save_group_memory(group_id: str, speaker: str, content: str) -> None:
    """
    保存群聊记忆
    :param group_id: 群ID
    :param speaker: 发言者
    :param content: 发言内容
    """
    if group_id not in airi_state.memory_group:
        airi_state.memory_group[group_id] = []
    # 添加记忆并限制最大长度
    airi_state.memory_group[group_id].append(f"{speaker}：{content}")
    if len(airi_state.memory_group[group_id]) > MEMORY_MAX_CAPACITY_GROUP:
        airi_state.memory_group[group_id].pop(0)

def get_user_nickname(bot: Bot, ev: MessageEvent) -> str:
    """获取用户昵称（优先群名片，其次昵称）"""
    return ev.sender.card or ev.sender.nickname or str(ev.user_id)

async def replace_at_nickname(bot: Bot, group_id: str, input_text: str) -> str:
    """
    替换消息中的@CQ码为实际昵称
    :param bot: Bot实例
    :param group_id: 群ID
    :param input_text: 原始文本
    :return: 替换后的文本
    """
    at_pattern = re.compile(r'\[CQ:at,qq=(\d+)\]')
    replace_map = {}
    for match in at_pattern.finditer(input_text):
        cq_at = match.group(0)
        qq_num = match.group(1)
        try:
            member_info = await bot.get_group_member_info(group_id=group_id, user_id=qq_num)
            nick = member_info.get("nickname") or member_info.get("card") or qq_num
            replace_map[cq_at] = f" @{nick} "
        except Exception as e:
            logger.warning(f"获取@用户信息失败: {e}")
            replace_map[cq_at] = f" @{qq_num} "
    # 执行替换
    for old, new in replace_map.items():
        input_text = input_text.replace(old, new)
    # 清理剩余CQ码
    input_text = re.sub(r"\[CQ:.*?\]", "", input_text)
    return input_text.strip()

async def should_speak(bot: Bot, ev: MessageEvent, group_id: str, user_id: str) -> bool:
    """
    判断是否需要回复消息
    :param bot: Bot实例
    :param ev: 消息事件
    :param group_id: 群ID
    :param user_id: 用户ID
    :return: 是否需要回复
    """
    # 超级用户前缀指令强制回复
    if user_id in SUPERUSERS and str(ev.message).startswith('.'):
        return True
    # 触发关键词/@机器人/回复机器人
    tokens = airi_state.negative_speaking_tokens.get(group_id, 0)
    if tokens > 0:
        msg_text = str(ev.message).lower()
        trigger_conditions = [
            'airi' in msg_text,
            '爱莉' in str(ev.message),
            bot.self_id in str(ev),
            str(ev.message).startswith('.'),
            (hasattr(ev, 'reply') and ev.reply and str(ev.reply.sender.user_id) == bot.self_id)
        ]
        if any(trigger_conditions):
            airi_state.negative_speaking_tokens[group_id] = tokens + 2
            return True
    # 随机触发
    if random.random() < RANDOM_SPEAK_PROBABILITY:
        return True
    return False

async def send_llm_reply(msg_content: str, need_reply: int) -> int:
    """
    发送LLM回复（分段发送+随机表情）
    :param msg_content: 回复内容
    :param need_reply: 是否需要回复消息
    :return: 最终的need_reply状态
    """
    # 处理标点符号分割
    punct_pattern = re.compile(r"[，。！？；：～]+")
    if random.randint(1, 8) > 1:
        msg_segments = punct_pattern.split(msg_content)
    else:
        msg_segments = [msg_content]
    
    # 过滤空内容
    msg_segments = [seg.strip() for seg in msg_segments if seg.strip()]
    if not msg_segments:
        return 0

    # 处理多段消息格式
    if len(msg_segments) > 2:
        is_single = 1
        for idx in range(len(msg_segments)):
            seg = msg_segments[idx]
            if seg.endswith(("，", "。")):
                msg_segments[idx] = seg[:-1]
    
            if idx != len(msg_segments) - 1 and len(seg) > 1:
                is_single = 0
        if is_single:
            msg_segments = ["！".join(msg_segments) + "！"]
    for idx in range(len(msg_segments)):
        seg = msg_segments[idx]
        if seg.endswith(("，", "。")):
            msg_segments[idx] = seg[:-1]

    # 随机发送表情
    if random.random() < EMOJI_RANDOM_PROB:
        emoji_seg = await generate_random_emoji()
        await asyncio.sleep(random.randint(3, 8))
        await airi_llm.send(emoji_seg)

    # 开局延迟
    await asyncio.sleep(random.randint(3, 8))

    # 分段发送消息
    for idx, seg in enumerate(msg_segments):
        if seg:
            await airi_llm.send(seg, reply_message=bool(need_reply))
            need_reply = 0  # 仅第一段回复
            # 分段间隔
            sleep_time = random.randint(4, 8) if idx != len(msg_segments)-1 else random.randint(1, 2)
            await asyncio.sleep(sleep_time)

    # 结尾随机表情
    if random.random() < FINAL_EMOJI_PROB:
        emoji_seg = await generate_random_emoji()
        await airi_llm.send(emoji_seg)

    return need_reply

async def passive_speaking(bot: Bot, group_id: str, mode: int = 1) -> None:
    """
    被动发言逻辑（主动插话）
    :param group_id: 群ID
    :param mode: 模式（1=带延迟，0=立即）
    """
    # 检查是否被驯服（避免重复发言）
    if mode and airi_state.passive_speaking_group_tamed.get(group_id, 0):
        return
   
    if mode:
        airi_state.passive_speaking_group_tamed[group_id] = 1
   
    # 模式1添加随机延迟
    if mode:
        await asyncio.sleep(random.randint(*PASSIVE_SPEAK_DELAY_RANGE))

    # 检查最近发言时间（5分钟内跳过）
    last_speak = airi_state.last_speak_time_group.get(group_id, 0)
    if mode and (time.time() - last_speak) < 300:
        airi_state.passive_speaking_group_tamed[group_id] = 0
        return

    # 更新最后发言时间
    airi_state.last_speak_time_group[group_id] = time.time()
    # 初始化发言令牌
    if airi_state.negative_speaking_tokens.get(group_id, 0) == 0:
        airi_state.negative_speaking_tokens[group_id] = NEGATIVE_SPEAK_TOKENS_INIT

    # 调用LLM生成主动发言内容
    memory_context = "\n".join(airi_state.memory_group.get(group_id, []))
    prompt = (
        f"【以下是上下文，供参考，格式为 发言人(账号ID): 发言内容】\n{memory_context}\n\n"
        f"当前时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        "现在轮到你主动发言。"
    )
    reply = await call_llm(airi_state.role_setup, prompt, group_id, [])
    if not reply:
        return

    # 清理回复内容
    reply = re.sub(r"[(（].+?[)）]", "", reply)
    # 保存记忆
    await save_group_memory(group_id, f"(你)({bot.self_id})", reply)
    # 发送消息
    try:
        await send_llm_reply(reply, 0)
    except:
        pass

    # 解除驯服
    if mode:
        airi_state.passive_speaking_group_tamed[group_id] = 0

# ===================== 事件处理器 =====================
# 主消息处理器
airi_llm = on_message(priority=50, block=False)
# 超级用户调试指令
superuser_debug = on_startswith('ldebug ', priority=5, block=True, rule=to_me(), permission=SUPERUSER)

@airi_llm.handle()
async def handle_airi_llm(bot: Bot, ev: MessageEvent):
    """处理群聊/私聊消息，调用LLM生成回复"""
    try:
        # 解析会话ID（区分群聊/私聊）
        session_id = str(ev.get_session_id())
        user_id: str = ""
        group_id: Optional[str] = None
        
        if 'group' in session_id:
            _, group_id, user_id = session_id.split("_")
            # 白名单校验（注释保留，可按需启用）
            # if group_id not in WHITELIST_GROUP:
            #     return
        else:
            user_id = session_id

        # 校验机器人白名单
        if bot.self_id not in WHITELIST_BOT:
            return

        # 初始化发言令牌
        airi_state.negative_speaking_tokens.setdefault(group_id, 0)
        airi_state.negative_speaking_tokens[group_id] -= NEGATIVE_SPEAK_TOKENS_DEDUCT
        if airi_state.negative_speaking_tokens[group_id] < 0:
            airi_state.negative_speaking_tokens[group_id] = 0

        # 获取用户昵称
        user_nick = get_user_nickname(bot, ev)
        # 处理消息内容（替换@、清理CQ码）
        input_text = str(ev.message).strip()
        if group_id:
            input_text = await replace_at_nickname(bot, group_id, input_text)

        # 保存用户发言到记忆
        if input_text:
            await save_group_memory(group_id, user_nick+f"({ev.user_id})", input_text)
        # 更新最后发言时间
        if group_id:
            airi_state.last_speak_time_group[group_id] = time.time()

        # 随机触发被动发言
        if group_id and random.random() < PASSIVE_SPEAK_TRIGGER_PROB:
            asyncio.create_task(passive_speaking(bot, group_id, 1))

        # 判断是否需要回复
        need_speak = await should_speak(bot, ev, group_id, user_id)
        if not need_speak:
            return

        # 提取图片Base64
        img_b64_list = await get_image_base64_list(ev.get_message())

        # 处理前缀指令（.开头去掉前缀）
        if input_text.startswith('.'):
            input_text = input_text[1:]

        # 初始化群驯服状态
        airi_state.group_is_tamed.setdefault(group_id, 0)
        # 等待驯服状态解除
        need_reply = 1 if random.randint(0, 10) >= 10 else 0
        while airi_state.group_is_tamed[group_id]:
            need_reply = 1
            await asyncio.sleep(5)
            '''
            if random.randint(1, 20) == 1:
                airi_state.group_is_tamed[group_id] = 0
            '''

        # 初始化发言令牌
        if airi_state.negative_speaking_tokens.get(group_id, 0) == 0:
            airi_state.negative_speaking_tokens[group_id] = NEGATIVE_SPEAK_TOKENS_INIT

        # 构造LLM输入
        memory_context = "\n".join(airi_state.memory_group.get(group_id, []))
        llm_input = (
            f"【以下是上下文，供参考，格式为时间: 发言人(账号ID): 发言内容】\n{memory_context}\n\n"
            f"当前时间：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            f"现在轮到你发言。"
        )
        # 调用LLM
        llm_reply = await call_llm(airi_state.role_setup, llm_input, group_id, img_b64_list)
        if not llm_reply:
            return

        # 清理回复内容
        llm_reply = re.sub(r"[(（].+?[)）]", "", llm_reply)
        # 保存机器人回复到记忆
        await save_group_memory(group_id, f"(你)({bot.self_id})", llm_reply)

        # 已被占用
        if group_id:
            airi_state.group_is_tamed[group_id] = 1
            
        # 发送回复
        try:
            await send_llm_reply(llm_reply, need_reply)
        except:
            pass

        # 解除群驯服状态
        if group_id:
            airi_state.group_is_tamed[group_id] = 0

    except Exception as err:
        logger.error(f"消息处理失败: {err}\n{traceback.format_exc()}")
        return

@superuser_debug.handle()
async def handle_superuser_debug(bot: Bot, ev: MessageEvent):
    """超级用户调试指令处理器"""
    try:
        # 解析会话ID
        session_id = str(ev.get_session_id())
        if 'group' in session_id:
            _, group_id, user_id = session_id.split("_")
        else:
            user_id = session_id
            group_id = None

        # 提取调试指令
        src = ev.get_plaintext()[6:].strip()
        while (tmpa := src.replace("  "," ")) != src:
            src = tmpa
        user_2fa_digit = src[:6]
        if not totp_verify(_2fa_key, user_2fa_digit):
            await superuser_debug.send('2fa verification failed')
            return
        cmd = src[6:].strip()
        # 执行指令（支持await）
        if cmd.startswith('await '):
            try:
                result = await eval(cmd[6:].lstrip())
            except:
                result = await exec(cmd[6:].lstrip())
        else:
            try:
                result = eval(cmd)
            except:
                result = exec(cmd)

        # 格式化返回结果
        if result is None:
            reply = "命令执行成功"
        else:
            reply = str(result)
        await superuser_debug.send(reply, reply_message=True)

    except Exception as err:
        reply = traceback.format_exc()
        await superuser_debug.finish(reply, reply_message=True)
