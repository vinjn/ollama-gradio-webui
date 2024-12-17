import gradio as gr
import ollama
import json
import base64
import copy

model_list = ollama.list()
model_names = [model["model"] for model in model_list["models"]]
PROMPT_LIST = []
VL_CHAT_LIST = []
# 解析 prompt
with open("prompt.json", "r", encoding="utf-8") as f:
    PROMPT_DICT = json.load(f)
    for key in PROMPT_DICT:
        PROMPT_LIST.append(key)


# 初始化函数
def init():
    VL_CHAT_LIST.clear()


# 是否包含中文
def contains_chinese(string):
    for char in string:
        if "\u4e00" <= char <= "\u9fa5":
            return True
    return False


def ollama_chat(message, history, model_name, history_flag):
    messages = []
    chat_message = {"role": "user", "content": message}
    if history_flag and len(history) > 0:
        for element in history:
            history_user_message = {"role": "user", "content": element[0]}
            history_assistant_message = {"role": "assistant", "content": element[1]}
            messages.append(history_user_message)
            messages.append(history_assistant_message)
    messages.append(chat_message)
    stream = ollama.chat(model=model_name, messages=messages, stream=True)
    partial_message = ""
    for chunk in stream:
        if len(chunk["message"]["content"]) != 0:
            partial_message = partial_message + chunk["message"]["content"]
            yield partial_message


# 智能体生成
def ollama_prompt(message, history, model_name, prompt_info):
    messages = []
    system_message = {"role": "system", "content": PROMPT_DICT[prompt_info]}
    user_message = {"role": "user", "content": message}
    messages.append(system_message)
    messages.append(user_message)
    stream = ollama.chat(model=model_name, messages=messages, stream=True)
    partial_message = ""
    for chunk in stream:
        if len(chunk["message"]["content"]) != 0:
            partial_message = partial_message + chunk["message"]["content"]
            yield partial_message


# 图片上传
def vl_image_upload(image_path, chat_history):
    messsage = {"type": "image", "content": image_path}
    chat_history.append(((image_path,), None))
    VL_CHAT_LIST.append(messsage)
    return None, chat_history


# Submit问题
def vl_submit_message(message, chat_history):
    messsage = {"type": "user", "content": message}
    chat_history.append((message, None))
    VL_CHAT_LIST.append(messsage)
    return "", chat_history


# Redo
def vl_retry(chat_history):
    if len(VL_CHAT_LIST) > 1:
        if VL_CHAT_LIST[len(VL_CHAT_LIST) - 1]["type"] == "assistant":
            VL_CHAT_LIST.pop()
            chat_history.pop()
    return chat_history


# 撤销
def vl_undo(chat_history):
    message = ""
    chat_list = copy.deepcopy(VL_CHAT_LIST)
    if len(chat_list) > 1:
        if chat_list[len(chat_list) - 1]["type"] == "assistant":
            message = chat_list[len(chat_list) - 2]["content"]
            VL_CHAT_LIST.pop()
            VL_CHAT_LIST.pop()
            chat_history.pop()
            chat_history.pop()
        elif chat_list[len(chat_list) - 1]["type"] == "user":
            message = chat_list[len(chat_list) - 1]["content"]
            VL_CHAT_LIST.pop()
            chat_history.pop()
    return message, chat_history


# Clear
def vl_clear():
    VL_CHAT_LIST.clear()
    return None, "", []


# 返回问题答案
def vl_submit(history_flag, chinese_flag, chat_history):
    if len(VL_CHAT_LIST) > 1:
        messages = get_vl_message(history_flag, chinese_flag)
        response = ollama.chat(model="llava:latest", messages=messages)
        result = response["message"]["content"]
        output = {"type": "assistant", "content": result}
        chat_history.append((None, result))
        VL_CHAT_LIST.append(output)
    else:
        gr.Warning("Result Exception")
    return chat_history


def get_vl_message(history_flag, chinese_flag):
    messages = []
    if history_flag:
        i = 0
        while i < len(VL_CHAT_LIST):
            if (
                VL_CHAT_LIST[i]["type"] == "image"
                and VL_CHAT_LIST[i + 1]["type"] == "user"
            ):
                image_path = VL_CHAT_LIST[i]["content"]
                # 读取图像文件的二进制数据
                with open(image_path, "rb") as image_file:
                    image_data = image_file.read()
                # 将二进制数据转换为 base64 编码的字符串
                base64_string = base64.b64encode(image_data).decode("utf-8")
                content = VL_CHAT_LIST[i + 1]["content"]
                chat_message = {
                    "role": "user",
                    "content": content,
                    "images": [base64_string],
                }
                messages.append(chat_message)
                i += 2
            elif VL_CHAT_LIST[i]["type"] == "assistant":
                assistant_message = {
                    "role": "assistant",
                    "content": VL_CHAT_LIST[i]["content"],
                }
                messages.append(assistant_message)
                i += 1
            elif VL_CHAT_LIST[i]["type"] == "user":
                user_message = {"role": "user", "content": VL_CHAT_LIST[i]["content"]}
                messages.append(user_message)
                i += 1
            else:
                i += 1
    else:
        if VL_CHAT_LIST[0]["type"] == "image" and VL_CHAT_LIST[-1]["type"] == "user":
            image_path = VL_CHAT_LIST[0]["content"]
            # 读取图像文件的二进制数据
            with open(image_path, "rb") as image_file:
                image_data = image_file.read()
            # 将二进制数据转换为 base64 编码的字符串
            base64_string = base64.b64encode(image_data).decode("utf-8")
            content = VL_CHAT_LIST[-1]["content"]
            chat_message = {
                "role": "user",
                "content": content,
                "images": [base64_string],
            }
            messages.append(chat_message)
    if chinese_flag:
        system_message = {
            "role": "system",
            "content": "You are a Helpal Assistant.Please answer the question in Chinese.请用中文回答",
        }
        messages.insert(0, system_message)
    return messages


with gr.Blocks(title="Ollama WebUI", fill_height=True) as demo:
    with gr.Tab("Chat", default=False):
        with gr.Row():
            with gr.Column(scale=1):
                model_info = gr.Dropdown(
                    model_names, value="", allow_custom_value=True, label="Select Model"
                )
                history_flag = gr.Checkbox(label="Enable Context")
            with gr.Column(scale=4):
                chat_bot = gr.Chatbot(height=600, render=False)
                text_box = gr.Textbox(scale=4, render=False)
                gr.ChatInterface(
                    fn=ollama_chat,
                    chatbot=chat_bot,
                    textbox=text_box,
                    additional_inputs=[model_info, history_flag],
                    submit_btn="Submit",
                    retry_btn="🔄 Redo",
                    undo_btn="↩️ Undo",
                    clear_btn="🗑️ Clear",
                    fill_height=True,
                )
    with gr.Tab("AI Agent", default=False):
        with gr.Row():
            with gr.Column(scale=1):
                prompt_model_info = gr.Dropdown(
                    model_names, value="", allow_custom_value=True, label="Select Model"
                )
                prompt_info = gr.Dropdown(
                    choices=PROMPT_LIST,
                    value=PROMPT_LIST[0],
                    label="Select Agent",
                    interactive=True,
                )
            with gr.Column(scale=4):
                prompt_chat_bot = gr.Chatbot(height=600, render=False)
                prompt_text_box = gr.Textbox(scale=4, render=False)
                gr.ChatInterface(
                    fn=ollama_prompt,
                    chatbot=prompt_chat_bot,
                    textbox=prompt_text_box,
                    additional_inputs=[prompt_model_info, prompt_info],
                    submit_btn="Submit",
                    retry_btn="🔄 Redo",
                    undo_btn="↩️ Undo",
                    clear_btn="🗑️ Clear",
                    fill_height=True,
                )
    with gr.Tab("Visual Agent"):
        with gr.Row():
            with gr.Column(scale=2):
                history_flag = gr.Checkbox(label="Enable Context")
                chinese_flag = gr.Checkbox(value=False, label="Force Chinese")
                image = gr.Image(type="filepath")
            with gr.Column(scale=4):
                chat_bot = gr.Chatbot(height=600)
                with gr.Row():
                    retry_btn = gr.Button("🔄 Redo")
                    undo_btn = gr.Button("↩️ Undo")
                    clear_btn = gr.Button("🗑️ Clear")
                with gr.Row():
                    message = gr.Textbox(show_label=False, container=False, scale=5)
                    message.submit(
                        fn=vl_submit_message,
                        inputs=[message, chat_bot],
                        outputs=[message, chat_bot],
                    ).then(
                        fn=vl_submit,
                        inputs=[history_flag, chinese_flag, chat_bot],
                        outputs=[chat_bot],
                    )
                    submit_btn = gr.Button("Submit", variant="primary", scale=1)
        image.upload(
            fn=vl_image_upload, inputs=[image, chat_bot], outputs=[image, chat_bot]
        )
        submit_btn.click(
            fn=vl_submit_message,
            inputs=[message, chat_bot],
            outputs=[message, chat_bot],
        ).then(
            fn=vl_submit,
            inputs=[history_flag, chinese_flag, chat_bot],
            outputs=[chat_bot],
        )
        retry_btn.click(fn=vl_retry, inputs=[chat_bot], outputs=[chat_bot]).then(
            fn=vl_submit,
            inputs=[history_flag, chinese_flag, chat_bot],
            outputs=[chat_bot],
        )
        undo_btn.click(fn=vl_undo, inputs=[chat_bot], outputs=[message, chat_bot])
        clear_btn.click(fn=vl_clear, inputs=[], outputs=[image, message, chat_bot])
    demo.load(fn=init)
if __name__ == "__main__":
    demo.launch(share=False)
