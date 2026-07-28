from nonebot import get_driver

driver = get_driver()

bot_nick = "Momoi Airi"
max_group_turtle_perday = 5
max_player_query_trial = 15
max_player_truth_trial = 3
max_group_trial = 90
min_turtle_minutes = 30
difficulty = {
    "简单": [20, 10],
    "普通": [15, 7],
    "困难": [10, 5],
    "大师": [5, 3]
}
_2fa_key = getattr(driver.config, "_2fa_key", "")
llm_api_key = getattr(driver.config, "llm_api_key", "")
llm_base_url = getattr(driver.config, "llm_base_url", "")
