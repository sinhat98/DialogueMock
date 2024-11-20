import gradio as gr
from copy import deepcopy
from src.utils import get_custom_logger
from src.modules.dialogue.dst import RuleDST
from src.modules.dialogue.nlg import TemplateNLG
from src.modules.dialogue.utils.template import templates
from src.modules.nlu.streaming_nlu import StreamingNLUModule, EntityLabel
from src.modules.nlu.prompt import get_base_system_prompt
from src.bridge.llm_bridge import LLMBridge

logger = get_custom_logger(__name__)

# 初期設定
DefinedEntities = [e.value[1] for e in EntityLabel.__members__.values()]

# pdb.set_trace()
# モジュールの初期化
default_state = templates["initial_state"]
dst = RuleDST(templates, default_state)

rule_based_nlu = StreamingNLUModule(slot_keys=list(dst.initial_state.keys()))
llm_nlu = LLMBridge(get_base_system_prompt(default_state), json_format=True)
nlg = TemplateNLG(templates)

# フラグを追加
waiting_for_confirmation = False
awaiting_final_confirmation = False


def respond(message, chat_history):
    global waiting_for_confirmation, awaiting_final_confirmation

    # ユーザーの最終確認応答をチェック
    if awaiting_final_confirmation and message.lower() == "はい":
        response = nlg.get_confirm_response(
            dst.state_stack[-1][0], "はい"
        )  # 最終確認応答を生成
        awaiting_final_confirmation = False
        waiting_for_confirmation = False
    else:
        # NLU処理
        if not dst.state_stack:
            # json形式で返されるものをdictに変換
            _out = eval(llm_nlu.call_llm(message))
            action_type = _out.pop("用件", "")
            out = {"action_type": action_type, "slot": _out}
            # action_type
        else:
            rule_based_nlu.process(message)
            _out = rule_based_nlu.slot_states
            out = {"action_type": "", "slot": _out}

        logger.info(f"NLU output: {out}")

        # DST状態更新
        prev_state = (
            deepcopy(dst.state_stack[-1][1]) if dst.state_stack else dst.initial_state
        )
        dst.update_state(out)

        # 暗黙確認応答生成
        implicit_confirmation = nlg.get_confirmation_response(
            dst.state_stack[-1], prev_state
        )
        if implicit_confirmation:
            response = implicit_confirmation
            waiting_for_confirmation = True
        else:
            response = nlg.get_response(dst.state_stack[-1])
            waiting_for_confirmation = False

        # 状態確認して全てのスロットが埋まっているかチェック
        if dst.is_complete() and not waiting_for_confirmation:
            response += "ご予約を確定してもよろしいでしょうか？"
            awaiting_final_confirmation = True

    # 対話履歴にユーザー入力とシステム応答を追加
    chat_history.append((message, response))

    # 現在のslot状態を取得して表示用に整形
    current_state = dst.state_stack[-1]
    logger.info(f"Current state: {current_state}")
    current_state_str = "\n".join([f"{k}: {v}" for k, v in current_state[1].items()])

    return "", chat_history, current_state_str


# Gradioインターフェースの設定
with gr.Blocks() as demo:
    gr.Markdown("# 対話システムデモ")

    with gr.Row():
        with gr.Column(scale=3):
            chatbot = gr.Chatbot()
            msg = gr.Textbox(
                show_label=False,
                placeholder="メッセージを入力してEnterを押してください",
            )
            current_state_display = gr.Markdown()
            msg.submit(respond, [msg, chatbot], [msg, chatbot, current_state_display])

        with gr.Column(scale=1):
            current_state_display

    clear = gr.Button("クリア")
    clear.click(lambda: None, None, [chatbot, current_state_display], queue=False)

# アプリケーションの起動
if __name__ == "__main__":
    demo.launch()
