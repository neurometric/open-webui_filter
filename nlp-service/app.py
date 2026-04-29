from fastapi import FastAPI
from pydantic import BaseModel
import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification, pipeline

MODEL_ID = "Gherman/bert-base-NER-Russian"

app = FastAPI(title="Russian NER (Gherman/bert-base-NER-Russian)")

class Req(BaseModel):
    text: str

device = 0 if torch.cuda.is_available() else -1
dtype = torch.float16 if torch.cuda.is_available() else torch.float32

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForTokenClassification.from_pretrained(MODEL_ID, torch_dtype=dtype)
if torch.cuda.is_available():
    model = model.to("cuda")

ner = pipeline(
    "token-classification",
    model=model,
    tokenizer=tokenizer,
    aggregation_strategy="simple",
    device=device,
)

@app.get("/health")
def health():
    return {
        "ok": True,
        "cuda": torch.cuda.is_available(),
        "device": "cuda" if torch.cuda.is_available() else "cpu",
        "model_id": MODEL_ID,
    }

@app.post("/ner")
def do_ner(req: Req):
    ents = ner(req.text)

    # normalize to JSON-safe types
    norm = []
    for e in ents:
        norm.append({
            "entity_group": str(e.get("entity_group") or e.get("entity") or ""),
            "word": str(e.get("word") or ""),
            "start": int(e.get("start")) if e.get("start") is not None else None,
            "end": int(e.get("end")) if e.get("end") is not None else None,
            "score": float(e.get("score")) if e.get("score") is not None else None,
        })

    return {
        "model_id": MODEL_ID,
        "entities": norm,
    }