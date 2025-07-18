from openai import OpenAI

def generate_ai_report(prompt):
    client = OpenAI(
        api_key="sk-02a22ee8128e4bfea64f675407370009",
        base_url="https://api.deepseek.com"
    )
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": "你是一个专业的监控平台日报生成助手，请用简洁、正式的语言生成日报。"},
            {"role": "user", "content": prompt}
        ],
        max_tokens=1024,
        temperature=0.7,
        stream=False
    )
    return response.choices[0].message.content
