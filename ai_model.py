import torch
import torch.nn as nn
from PIL import Image
from transformers import AutoImageProcessor, AutoModelForImageClassification

# ----------------------------
# Device
# ----------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

GLOBAL_MAX_VOLUME = 50000  # same scaling you used in training

# ----------------------------
# Lazy Processor
# ----------------------------
processor = None

def get_processor():
    global processor
    if processor is None:
        print("⏳ Loading processor...")
        processor = AutoImageProcessor.from_pretrained(
            "microsoft/resnet-152",
            use_fast=False
        )
        print("✅ Processor loaded")
    return processor

# ----------------------------
# Model Architecture
# ----------------------------
def build_model():
    model = AutoModelForImageClassification.from_pretrained(
        "microsoft/resnet-152"
    )

    in_features = model.classifier[1].in_features

    model.classifier[1] = nn.Sequential(
        nn.Linear(in_features, 2),
        nn.Sigmoid()
    )

    return model

# ----------------------------
# Lazy Model
# ----------------------------
model = None

def get_model():
    global model
    if model is None:
        print("⏳ Loading model...")

        m = build_model()
        m.load_state_dict(torch.load("best_model.pth", map_location=device))
        m.to(device)
        m.eval()

        model = m
        print("✅ Model loaded")

    return model

# ----------------------------
# Prediction Function
# ----------------------------
def predict_capacity(image_path):
    """
    Returns:
        capacity_ml (float)
        capacity_oz (float)
        fill_norm (float)
    """

    image = Image.open(image_path).convert("RGB")

    processor = get_processor()
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    model = get_model()

    with torch.no_grad():
        outputs = model(**inputs)

    logits = outputs.logits  # shape: [batch, 2]

    # You trained 2 outputs: [capacity, fill]
    capacity_norm = logits[0, 0].item()
    fill_norm = logits[0, 1].item()

    # Clamp
    capacity_norm = max(0.0, min(capacity_norm, 1.0))
    fill_norm = max(0.0, min(fill_norm, 1.0))

    # Convert to real units
    capacity_ml = capacity_norm * GLOBAL_MAX_VOLUME
    capacity_oz = capacity_ml / 29.5735

    print(f"📦 Capacity: {capacity_ml:.1f} mL ({capacity_oz:.2f} fl oz)")
    print(f"🧪 Fill level: {fill_norm:.3f}")

    return float(capacity_ml), float(capacity_oz), float(fill_norm)