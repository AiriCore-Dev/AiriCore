import json
import time
from openai import OpenAI
 
client = OpenAI(
    api_key="sk-c8hddt5pd43l14mp5gfpsjdjkw5q5d2btuk7vwxaycwznqsd",
    base_url="https://api.xiaomimimo.com/v1"
)

with open('generate_tips.txt', 'r', encoding='utf-8') as f:
    generate_tips = f.read()
    
with open('turtle_soup.json', 'r', encoding='utf-8') as f:
    turtle_soup = json.load(f)    
 
def call_llm(prompt, input, deepseek):
    completion = client.chat.completions.create(
        model="mimo-v2-flash",
        messages=[
            {
                "role": "system",
                "content": prompt
            },
            {
                "role": "user",
                "content": input
            }
        ],
        max_completion_tokens=1024,
        temperature=0.3,
        top_p=0.95,
        stream=False,
        stop=None,
        frequency_penalty=0,
        presence_penalty=0,
        extra_body={
            "thinking": {"type": "enabled" if deepseek else "disabled"}
        }
    )
    return json.loads(completion.model_dump_json())["choices"][0]["message"]["content"]
 
def outine():
     with open('turtle_soup.json', 'w', encoding='utf-8') as f:
        json.dump(turtle_soup, f, ensure_ascii=False)
     moder = []
     for i in range(len(turtle_soup)):
         try:
             turtle_soup[i]["tips"]
         except:
             while 1:
                 print(i)
                 print(turtle_soup[i])
                 try:
                     tips = call_llm(generate_tips, str(turtle_soup[i]), 0)
                     if tips.endswith('```'):
                         tips = tips[7:-3]
                     print(tips)
                     tips = json.loads(tips)
                     turtle_soup[i]["tips"] = tips['tips']
                     with open('turtle_soup.json', 'w', encoding='utf-8') as f:
                        json.dump(turtle_soup, f, ensure_ascii=False)
                     break
                 except Exception as err:
                     print(err)
                     if 'Moderation Block' in str(err):
                         turtle_soup[i]["tips"] = []
                         moder.append(i)
                         with open('moder.txt', 'w') as f:
                             w = f.write(str(moder))
                         break
                     if 'request' in str(err):
                        time.sleep(60)

def check():
    for i in turtle_soup:
        try:
            i['tips']
        except:
            print(i)
                
if __name__ == "__main__":                 
    check()
    