import os
import re
from datetime import datetime

def apply_prompt_template(prompt_name: str, prompt_context={}) -> str:
    
    prompt_path = os.path.join(os.path.dirname(__file__), f"{prompt_name}.md")
    # UTF-8 인코딩으로 명시적으로 읽기 (Windows cp949 문제 해결)
    with open(prompt_path, encoding="utf-8") as f:
        system_prompts = f.read()
    
    context = {"CURRENT_TIME": datetime.now().strftime("%a %b %d %Y %H:%M:%S %z")}
    context.update(prompt_context)
    
    # .format() 대신 정규식으로 특정 변수만 치환 (JSON 예시의 중괄호 보호)
    # {CURRENT_TIME}, {USER_REQUEST} 같은 변수만 치환
    for key, value in context.items():
        # {KEY} 형식만 치환 (줄바꿈이나 공백이 있어도 처리)
        pattern = r'\{\s*' + re.escape(key) + r'\s*\}'
        system_prompts = re.sub(pattern, str(value), system_prompts)
        
    return system_prompts