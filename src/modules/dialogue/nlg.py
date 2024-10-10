import re
from datetime import time as dt_time
from src.dialogue.utils.constants import TimeSegment

from src.utils import setup_custom_logger
logger = setup_custom_logger(__name__)

def convert_date_format(date_str):
    match = re.match(r'(\d{1,2})/(\d{1,2})', date_str)
    if match:
        month, day = match.groups()
        return f"{int(month)}月{int(day)}日"
    return date_str

def convert_time_format(time_str):
    match = re.match(r'(\d{1,2}):(\d{2})', time_str)
    if match:
        hour = match.group(1)
        return f"{int(hour)}時"
    return time_str


    
def extract_hour_and_minute(slot_value):
    """時間はHH:MMで与えられる"""
    hour, minute = None, None
    match = re.match(r'(\d{1,2}):(\d{2})', slot_value)
    if match:
        hour, minute = match.groups()
        hour, minute = int(hour), int(minute)
    return hour, minute

def invalidate_time(hour: int, minute: int, segments: list[TimeSegment]) -> bool:
    """時間が営業時間内にあるかどうかをチェックする
    Args:
        hour (int): 時の部分
        minute (int): 分の部分
        segments (List[TimeSegment]): 営業時間のセグメント
    Returns:
        bool: 営業時間内でなければTrue, そうでなければFalse
    """
    if minute is None:
        minute = 0

    if hour is None:
        return False

    time_to_check = dt_time(hour, minute)

    for segment in segments:
        if segment.start <= time_to_check <= segment.end:
            return False  # 営業時間内なので、Falseを返す

    return True  # どのセグメントにも該当しない場合、営業時間外としてTrueを返す
                
    

class TemplateNLG:
    
    def __init__(self, templates):
        self.templates = templates

    def get_response(self, state_info):
        action_type, state = state_info
        # logger.info(f"action_type: {action_type} state: {state}")
        template = self.templates["action_type"].get(action_type, {})
        
        # 未入力スロットチェックと質問生成
        for slot, question in template.get("slot", {}).items():
            if not state.get(slot):
                return question
        
        # すべてのスロットが埋まっている場合の応答生成
        response_template = template.get("function", {}).get("response", {}).get("COMPLETE", "")
        response = response_template.format(**state)
        
        return response

    def get_confirmation_response(self, state_info, prev_state):
        
        action_type, current_state = state_info
        implicit_confirmation_template = self.templates["action_type"][action_type].get("function", "").get("implicit_confirmation", {})
        
        new_slots = {}
        for slot_key, slot_value in current_state.items():
            if slot_value and slot_value != prev_state.get(slot_key):
                new_slots[slot_key] = slot_value
            # TODO: validationの実装(validationはdstでやるべきかも)
            # hour, minute = extract_hour_and_minute(slot_value)
            # is_invalid_time = invalidate_time(hour, minute, BUSINESS_HOURS)
            # logger.info(f"slot_key: {slot_key} slot_value: {slot_value} is_invalid_time: {is_invalid_time}")
            
            # business_hours_str = "、".join([f"{segment.start.strftime('%H:%M')}~{segment.end.strftime('%H:%M')}" for segment in BUSINESS_HOURS])
            # if is_invalid_time:
            #     return f"申し訳ございません。{hour}時代は営業時間外です。営業時間は{business_hours_str}です。"
        
        # new_slots = {k: v for k, v in current_state.items() if v and current_state[k] != prev_state.get(k)}
        new_slots_keys = frozenset(new_slots.keys())
        
        if new_slots_keys and new_slots_keys in implicit_confirmation_template:
            message_template = implicit_confirmation_template[new_slots_keys]
        elif len(new_slots) == 1:
            message_template = implicit_confirmation_template.get(list(new_slots.keys())[0], "")
        else:
            message_template = ""
        # logger.info(f"new_slots: {new_slots} message_template: {message_template} implicit_confirmation_template: {implicit_confirmation_template}")

        implicit_confirmation_message = message_template.format(**new_slots)
        
        return implicit_confirmation_message

    def get_confirm_response(self, action_type, user_response):
        template = self.templates["action_type"].get(action_type, {})
        confirm_responses = template.get("function", {}).get("confirm", {})
        
        if user_response in confirm_responses:
            return confirm_responses[user_response]
        
        return ""