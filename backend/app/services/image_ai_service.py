from transformers import BlipProcessor, BlipForConditionalGeneration
from PIL import Image
import torch

device = "cuda" if torch.cuda.is_available() else "cpu"

processor = BlipProcessor.from_pretrained(
    "Salesforce/blip-image-captioning-base"
)

model = BlipForConditionalGeneration.from_pretrained(
    "Salesforce/blip-image-captioning-base"
).to(device)


def describe_medical_image(image_path):

    image = Image.open(image_path).convert("RGB")

    inputs = processor(image, return_tensors="pt").to(device)

    output = model.generate(**inputs)

    caption = processor.decode(output[0], skip_special_tokens=True)

    return caption
