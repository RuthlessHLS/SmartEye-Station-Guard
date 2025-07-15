from openai import OpenAI

client = OpenAI(
    api_key="sk-02a22ee8128e4bfea64f675407370009",
    base_url="https://api.deepseek.com"
)

response = client.chat.completions.create(
    model="deepseek-chat",
    messages=[
        {"role": "system", "content": "你是一个专业的监控平台日报生成助手，请用简洁、正式的语言生成日报。"},
        {"role": "user", "content": "请根据以下监控数据生成一份简明扼要的监控日报：告警数5，正常数100，异常类型：烟雾、闯入"}
    ],
    max_tokens=1024,
    temperature=0.7,
    stream=False
)

print("AI日报内容：\n", response.choices[0].message.content) 