from groq import Groq
import os
from .utils import is_image_path

def run_groq_interleaved(messages: list, system: str, model_name: str, api_key: str, max_tokens=256, temperature=0.6):
    """
    Run a chat completion through Groq's API, ignoring any images in the messages.
    """
    api_key = api_key or os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError("GROQ_API_KEY is not set")
    
    client = Groq(api_key=api_key)
    final_messages = [{"role": "system", "content": system}]

    if isinstance(messages, list):
        for item in messages:
            if isinstance(item, dict):
                role = item.get("role", "user")
                text_contents = []
                for cnt in item.get("content", []):
                    if isinstance(cnt, str):
                        if not is_image_path(cnt) and not cnt.endswith(".png"):
                            text_contents.append(cnt)
                    elif hasattr(cnt, "text") and getattr(cnt, "text", None):
                        text_contents.append(str(cnt.text))
                    elif hasattr(cnt, "input") and getattr(cnt, "input", None):
                        text_contents.append(f"Action: {cnt.input}")
                    else:
                        text_contents.append(str(cnt))
                
                if text_contents:
                    content_str = "\n".join(text_contents)
                    if final_messages and final_messages[-1]["role"] == role:
                        final_messages[-1]["content"] += "\n" + content_str
                    else:
                        final_messages.append({"role": role, "content": content_str})
            else:  # str
                final_messages.append({"role": "user", "content": str(item)})
    
    elif isinstance(messages, str):
        final_messages.append({"role": "user", "content": messages})

    # Ensure the user prompt ends with clear instruction to determine next action
    prompt_suffix = "\nPlease determine the next action for the current screen based on the detected bounding boxes to complete the task."
    if final_messages and final_messages[-1]["role"] == "user":
        final_messages[-1]["content"] += prompt_suffix
    else:
        final_messages.append({"role": "user", "content": prompt_suffix.strip()})

    try:
        target_model = model_name or "deepseek-r1-distill-llama-70b"
        if "qwen" in target_model:
            target_model = "deepseek-r1-distill-llama-70b"

        completion = client.chat.completions.create(
            model=target_model,
            messages=final_messages,
            temperature=temperature,
            max_completion_tokens=max_tokens,
            top_p=0.95,
            stream=False,
        )
        
        msg_obj = completion.choices[0].message
        response = msg_obj.content or getattr(msg_obj, "reasoning", None) or ""
        if "</think>" in response:
            after_think = response.split("</think>")[-1].strip()
            final_answer = after_think if after_think else response
        else:
            final_answer = response

        final_answer = final_answer.replace("<output>", "").replace("</output>", "").strip()
        token_usage = completion.usage.total_tokens if completion.usage else 0
        if not final_answer:
            print(f"[DEBUG GROQ] Empty answer! Choice: {completion.choices[0]}")
        
        return final_answer, token_usage
    except Exception as e:
        print(f"Error in interleaved Groq: {e}")

        return str(e), 0