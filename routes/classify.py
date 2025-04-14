import shap
import torch
from transformers import BertTokenizer, BertForSequenceClassification
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from models import PoemRequest
from fastapi.encoders import jsonable_encoder  # for safe JSON conversion
from database import db
from datetime import datetime
from bson import ObjectId
from fastapi.responses import JSONResponse

collection = db['poems']
# Setup device and model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_name = "Tashuu/bert-finetuned-6classes-best-model-2"
tokenizer = BertTokenizer.from_pretrained(model_name)
model = BertForSequenceClassification.from_pretrained(model_name).to(device)
model.eval()

class_names = ["Anger", "Fear", "Hate", "Joy", "Love", "Sad"]

# Prediction function
def predict(texts):
    encodings = tokenizer(list(texts), return_tensors="pt", padding=True, truncation=True).to(device)
    with torch.no_grad():
        outputs = model(**encodings)
    return torch.nn.functional.softmax(outputs.logits, dim=1).cpu().numpy()

classify_router = APIRouter()

@classify_router.post("/classify/")
async def classify_and_save_poem(request: PoemRequest):
    input_text = request.text
    user_id = request.user_id
    favourite = request.favourite or False

    # Get prediction probabilities
    probs = predict([input_text])[0]
    pred_class_idx = int(torch.argmax(torch.tensor(probs)).item())
    pred_class = class_names[pred_class_idx]
    confidence = float(probs[pred_class_idx])

    # Prepare data to store (without SHAP tokens)
    data_to_save = {
        "user_id": ObjectId(user_id),
        "input_text": input_text,
        "predicted_emotion": pred_class,
        "confidence": confidence,
        "favourite": favourite,
        "timestamp": datetime.now()
    }

    insert_result = collection.insert_one(data_to_save)
    return jsonable_encoder({
        "poem_id": str(insert_result.inserted_id),
        "predicted_emotion": pred_class,
        "confidence": confidence
    })


# 2. Endpoint to calculate SHAP tokens using poem ID and update DB
@classify_router.post("/calculate_shap/")
async def calculate_shap(poem_id: str):
    try:
        poem_doc = collection.find_one({"_id": ObjectId(poem_id)})
        if not poem_doc:
            raise HTTPException(status_code=404, detail="Poem not found")

        input_text = poem_doc["input_text"]
        pred_class = poem_doc["predicted_emotion"]
        pred_class_idx = class_names.index(pred_class)

        # SHAP explainer
        explainer = shap.Explainer(predict, tokenizer)
        shap_values = explainer([input_text])

        shap_expl = shap.Explanation(
            values=shap_values.values[:, :, pred_class_idx],
            base_values=shap_values.base_values[:, pred_class_idx],
            data=shap_values.data,
            feature_names=shap_values.feature_names
        )

        tokens = tokenizer.tokenize(input_text)
        contributions = shap_expl[0].values
        token_contributions = [
            {"token": token, "contribution": float(contribution)}
            for token, contribution in zip(tokens, contributions)
        ]
        sorted_top_10 = sorted(token_contributions, key=lambda x: x["contribution"], reverse=True)[:10]

        # Update DB with SHAP tokens
        collection.update_one(
            {"_id": ObjectId(poem_id)},
            {"$set": {"top_10_tokens_with_contributions": sorted_top_10}}
        )

        return jsonable_encoder({
            "poem_id": poem_id,
            "top_10_tokens_with_contributions": sorted_top_10
        })

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@classify_router.get("/history/")
async def get_user_history(user_id: str):
    try:
        history = list(
            db["poems"]
            .find({"user_id": ObjectId(user_id)}, {"_id": 1, "input_text": 1, "predicted_emotion": 1, "confidence": 1, "top_10_tokens_with_contributions": 1, "timestamp": 1})
            .sort("timestamp", -1)
        )

        for item in history:
            item["_id"] = str(item["_id"])
            item["confidence"] = float(item["confidence"])
            for token in item.get("top_10_tokens_with_contributions", []):
                token["contribution"] = float(token["contribution"])

        return JSONResponse(content=jsonable_encoder(history))

    except Exception as e:
        return {"error": str(e)}
    
class FavouriteUpdate(BaseModel):
    favourite: bool

@classify_router.put("/classify/update_favourite/")
async def update_favourite(poem_id: str, update: FavouriteUpdate):
    try:
        result = collection.update_one(
            {"_id": ObjectId(poem_id)},
            {"$set": {"favourite": update.favourite}}
        )

        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Poem not found")

        return {"message": "Favourite status updated successfully"}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@classify_router.get("/favourites/")
async def get_favourites(user_id: str):
    try:
        favourites = list(db["poems"].find(
            {"user_id": ObjectId(user_id), "favourite": True},
            {"_id": 0, "input_text": 1, "predicted_emotion": 1}
        ).sort("timestamp", -1))

        # Rename for clarity in frontend response
        result = [
            {"poem": item["input_text"], "emotion": item["predicted_emotion"]}
            for item in favourites
        ]

        return JSONResponse(content=jsonable_encoder(result))
    except Exception as e:
        return {"error": str(e)}
