import gradio as gr
from src.utils import get_custom_logger
from src.modules.dialogue.dialogue_system import DialogueSystem

logger = get_custom_logger(__name__)


def format_state_display(state: dict, prev_state: dict = None) -> str:
    """現在の状態と前回の状態を表示用に整形"""
    lines = ["# 現在の状態:"]
    lines.extend([
        f"意図: {state['intent'] or '未特定'}",
        f"対話状態: {state['dialogue_state']}",
        "\nスロット値:"
    ])
    for slot, value in state['state'].items():
        lines.append(f"  {slot}: {value or '未入力'}")
    
    if state['missing_slots']:
        lines.append("\n未入力のスロット:")
        for slot in state['missing_slots']:
            lines.append(f"  - {slot}")
    
    if state['updated_slots']:
        lines.append("\n更新されたスロット:")
        for slot in state['updated_slots']:
            lines.append(f"  - {slot}")
    
    # 前回の状態がある場合は表示
    if prev_state:
        lines.extend([
            "\n# 前回の状態:",
            f"意図: {prev_state['intent'] or '未特定'}",
            f"対話状態: {prev_state['dialogue_state']}",
            "\nスロット値:"
        ])
        for slot, value in prev_state['state'].items():
            lines.append(f"  {slot}: {value or '未入力'}")
        
        if prev_state['missing_slots']:
            lines.append("\n未入力のスロット:")
            for slot in prev_state['missing_slots']:
                lines.append(f"  - {slot}")
        
        if prev_state['updated_slots']:
            lines.append("\n更新されたスロット:")
            for slot in prev_state['updated_slots']:
                lines.append(f"  - {slot}")
    
    return "\n".join(lines)    

def create_interface():
    dialogue_system = DialogueSystem()
    was_complete = False  # 対話完了フラグを追加
    prev_state = None  # 前回の状態を保持する変数を追加

    def process_message(message: str, history: list[tuple[str, str]]):
        nonlocal was_complete, prev_state
        
        # 前回の対話が完了していた場合はリセット
        if was_complete:
            was_complete = False
            dialogue_system.reset_dialogue()
            initial_state = dialogue_system.dst.get_current_state()
            prev_state = None
            return "", [("", dialogue_system.initial_message)], format_state_display(initial_state)
        
        # 現在の状態を前回の状態として保存
        prev_state = dialogue_system.dst.get_current_state()
        
        responses = dialogue_system.process_message(message)
        response = "\n".join(responses)
        history.append((message, response))
        updated_state = dialogue_system.dst.get_current_state()
        state_display = format_state_display(updated_state, prev_state)
        
        # 今回の対話が完了した場合はフラグを立てる
        if dialogue_system.is_complete():
            was_complete = True
        
        return "", history, state_display

    def reset_chat():
        nonlocal prev_state
        dialogue_system.reset_dialogue()
        initial_state = dialogue_system.dst.get_current_state()
        prev_state = None
        return [("", dialogue_system.initial_message)], format_state_display(initial_state)

    with gr.Blocks() as demo:
        gr.Markdown("# レストラン予約対話システム")
        
        with gr.Row():
            with gr.Column(scale=3):
                chatbot = gr.Chatbot(value=[("", dialogue_system.initial_message)])
                msg = gr.Textbox(
                    show_label=False,
                    placeholder="メッセージを入力してください"
                )
                
            with gr.Column(scale=1):
                state_display = gr.Markdown()

        with gr.Row():
            clear = gr.Button("対話をリセット")

        msg.submit(process_message, [msg, chatbot], [msg, chatbot, state_display])
        clear.click(reset_chat, None, [chatbot, state_display])

    return demo

if __name__ == "__main__":
    demo = create_interface()
    demo.launch()