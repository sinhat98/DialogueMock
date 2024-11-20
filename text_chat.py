import gradio as gr
from src.utils import get_custom_logger
from src.modules.dialogue.dialogue_system import DialogueSystem

logger = get_custom_logger(__name__)


def format_state_display(state: dict) -> str:
    """現在の状態を表示用に整形"""
    lines = [
        "現在の状態:",
        f"意図: {state['intent'] or '未特定'}",
        f"対話状態: {state['dialogue_state']}",
        "\nスロット値:"
    ]
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
    
    return "\n".join(lines)    

def create_interface():
    dialogue_system = DialogueSystem()

    def process_message(message: str, history: list[tuple[str, str]]):
        response = dialogue_system.process_message(message)
        history.append((message, response))
        updated_state = dialogue_system.dst.get_current_state()
        state_display = format_state_display(updated_state)
        return "", history, state_display

    def reset_chat():
        dialogue_system.reset_dialogue()
        return [("", dialogue_system.initial_message)], ""

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