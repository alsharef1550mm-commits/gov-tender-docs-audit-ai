"""ضبط LoRA لـQwen3.5-9B على صفحات train المُفسَدة (make_lora_data.py)، على الـPod بعد إيقاف vLLM (الذاكرة لا تتسع لهما).

الهدف: تثبيت قراءة الأرقام والأعمدة (مجموع القيمة بخانتي الريال والهللة، إجمالي الفاتورة الأخير، رموز الأصناف، أرقام السند) لا نسخ حاصل الضرب.
يستعمل الموجّه والمخطط نفسيهما اللذين تستعملهما vlm_reader.call_vlm حتى لا يختلف التدريب عن الاستعمال.
المخرجات: ADAPTER_OUT (أوزان LoRA صغيرة، تُحفظ دورياً) و MERGED_OUT (أوزان مدمجة تُخدَّم بـvLLM).
تقسيم: train فقط؛ لا val ولا test ولا 730 ولا مجموعة الصفحات الـ49.
"""
import json
import os
import random
import sys
import time

import torch
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import vlm_reader as V  # noqa: E402

DATA = os.environ.get("LORA_DATA", "/workspace/lora_data")
MODEL = os.environ.get("QWEN_MODEL", "Qwen/Qwen3.5-9B")
ADAPTER_OUT = os.environ.get("ADAPTER_OUT", "/workspace/out/lora_adapter")
MERGED_OUT = os.environ.get("MERGED_OUT", "/root/merged")
EPOCHS = int(os.environ.get("EPOCHS", "1"))
LR = float(os.environ.get("LR", "1e-4"))
ACCUM = int(os.environ.get("ACCUM", "8"))
MAXPIX = int(os.environ.get("MAXPIX", str(2_800_000)))
LIMIT = int(os.environ.get("LIMIT", "0"))
TARGETS = (r".*(language_model\.layers\.\d+\.(linear_attn\.(in_proj_qkv|in_proj_z|out_proj)|mlp\.(gate_proj|up_proj|down_proj)|self_attn\.(q_proj|k_proj|v_proj|o_proj))"
           r"|visual\.blocks\.\d+\.(attn\.(qkv|proj)|mlp\.(linear_fc1|linear_fc2)))")

PROMPT = open(V.PROMPT_PATH, encoding="utf-8").read()
USER_TEXT = PROMPT + "\nReturn exactly this JSON shape (one item object per table row; null where not visible):\n" + V.SKELETON


def main():
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForImageTextToText, AutoProcessor
    rows = [json.loads(l) for l in open(os.path.join(DATA, "train.jsonl"), encoding="utf-8")]
    if LIMIT:
        rows = rows[:LIMIT]
    print("train pages", len(rows), flush=True)
    proc = AutoProcessor.from_pretrained(MODEL)
    try:
        proc.image_processor.max_pixels = MAXPIX
    except Exception as e:  # noqa: BLE001
        print("max_pixels not set:", e, flush=True)
    model = AutoModelForImageTextToText.from_pretrained(MODEL, dtype=torch.bfloat16, device_map={"": 0})
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(r=32, lora_alpha=64, lora_dropout=0.05, target_modules=TARGETS))
    model.print_trainable_parameters()
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=LR, weight_decay=0.0)
    total = EPOCHS * len(rows)
    sched = torch.optim.lr_scheduler.LambdaLR(opt, lambda s: min(1.0, (s + 1) / 5) * max(0.05, 1 - s * ACCUM / max(1, total)))
    model.train()
    msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": USER_TEXT}]}]
    prompt = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False, enable_thinking=False)
    print("PROMPT TAIL:", repr(prompt[-80:]), flush=True)
    t0, step, run_loss = time.time(), 0, []
    for ep in range(EPOCHS):
        random.Random(ep).shuffle(rows)
        for r in rows:
            img = Image.open(os.path.join(DATA, "images", r["image"])).convert("RGB")
            tgt = json.dumps(r["target"], ensure_ascii=False, indent=1)
            enc = proc(text=[prompt + tgt + "<|im_end|>"], images=[img], return_tensors="pt")
            plen = proc(text=[prompt], images=[img], return_tensors="pt")["input_ids"].shape[1]
            labels = enc["input_ids"].clone()
            labels[:, :plen] = -100
            enc = enc.to(model.device)
            out = model(**enc, labels=labels.to(model.device))
            (out.loss / ACCUM).backward()
            run_loss.append(out.loss.item())
            step += 1
            if step % ACCUM == 0:
                torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
            if step % 16 == 0:
                print(f"ep {ep} sample {step}/{total} loss {sum(run_loss[-16:]) / 16:.4f} tokens {enc['input_ids'].shape[1]} "
                      f"elapsed {time.time() - t0:.0f}s mem {torch.cuda.max_memory_allocated() / 1e9:.1f}GB", flush=True)
            if step % 200 == 0:
                model.save_pretrained(ADAPTER_OUT)
    model.save_pretrained(ADAPTER_OUT)
    print("adapter saved", ADAPTER_OUT, flush=True)
    model = model.merge_and_unload()
    model.save_pretrained(MERGED_OUT, safe_serialization=True)
    proc.save_pretrained(MERGED_OUT)
    print("merged saved", MERGED_OUT, flush=True)


if __name__ == "__main__":
    main()
