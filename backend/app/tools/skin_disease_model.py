import torch
import torchvision.models as models
import torch.nn as nn
import torch.nn.functional as F

# Load disease names
with open("app/models/classes.txt") as f:
    classes = [c.strip() for c in f.readlines()]

NUM_CLASSES = len(classes)

# Load model architecture
model = models.efficientnet_b4(pretrained=False)

model.classifier[1] = nn.Linear(
    model.classifier[1].in_features,
    NUM_CLASSES
)

# Load trained weights with safe weights_only=True
_ckpt = torch.load("app/models/skin_disease_model.pth", map_location="cpu", weights_only=True)
_state_dict = _ckpt.get("model_state_dict", _ckpt) if isinstance(_ckpt, dict) else _ckpt
model.load_state_dict(_state_dict)

model.eval()


def predict_skin_disease(img):

    with torch.no_grad():

        output = model(img)

        probs = F.softmax(output, dim=1)

        values, indices = torch.topk(probs, 3)

        results = []

        for i in range(3):

            results.append({
                "disease": classes[indices[0][i]],
                "confidence": float(values[0][i])
            })

        return results
