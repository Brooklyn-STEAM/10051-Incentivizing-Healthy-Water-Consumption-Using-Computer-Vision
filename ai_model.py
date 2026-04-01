import json
import torch
import os
from torch import nn
from torch.utils.data import Dataset, DataLoader
from PIL import Image, ImageFile
from transformers import AutoImageProcessor, AutoModelForImageClassification
from torchvision import transforms

train_transform = transforms.Compose([
    transforms.RandomRotation(15),
    transforms.RandomHorizontalFlip(),
])

ImageFile.LOAD_TRUNCATED_IMAGES = True

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ----------------------------
# Model
# ----------------------------
processor = AutoImageProcessor.from_pretrained(
    "microsoft/resnet-152",
    use_fast=False
)

model = AutoModelForImageClassification.from_pretrained(
    "microsoft/resnet-152"
)

in_features = model.classifier[1].in_features

model.classifier[1] = nn.Sequential(
    nn.Linear(in_features, 2),
    nn.Sigmoid()
)

model.to(device)

# ----------------------------
# Dataset
# ----------------------------
class MultiTaskDataset(Dataset):
    def __init__(self, volume_json, fill_json, images_folder, processor, transform=None):
        print("📦 Loading JSON files...")

        with open(volume_json) as f:
            volume_data = {d["image_id"]: d for d in json.load(f)}

        with open(fill_json) as f:
            fill_data = {d["image_id"]: d for d in json.load(f)}

        self.keys = list(set(volume_data.keys()) & set(fill_data.keys()))
        print(f"✅ Overlapping samples: {len(self.keys)}")

        self.volume_data = volume_data
        self.fill_data = fill_data
        self.images_folder = images_folder
        self.processor = processor
        self.transform = transform

        self.max_volume = max(d["volume_continuous"] for d in volume_data.values())

    def __len__(self):
        return len(self.keys)

    def __getitem__(self, idx):
        key = self.keys[idx]

        vol_entry = self.volume_data[key]
        fill_entry = self.fill_data[key]

        img_path = os.path.join(self.images_folder, key)

        if not os.path.exists(img_path):
            print("❌ Missing image:", img_path)
            return self.__getitem__((idx + 1) % len(self))

        image = Image.open(img_path).convert("RGB")

        if self.transform:
            image = self.transform(image)

        inputs = self.processor(images=image, return_tensors="pt")
        pixel_values = inputs["pixel_values"].squeeze(0)

        capacity = vol_entry["volume_continuous"] / self.max_volume
        fill = fill_entry.get("source_fill", 0.0)

        return {
            "pixel_values": pixel_values,
            "capacity": torch.tensor(capacity, dtype=torch.float),
            "fill": torch.tensor(fill, dtype=torch.float)
        }
    
# Automatically get max volume from dataset
# ----------------------------
dataset_for_max = MultiTaskDataset(
    "static/COQE_dataset/train.json",
    "static/COQE_dataset/train_pour_prediction.json",
    "static/COQE_dataset/images",
    processor
)

# ----------------------------
# DataLoader
# ----------------------------
def get_loader(vol_json, fill_json, batch_size=8, shuffle=True):
    dataset = MultiTaskDataset(
        vol_json,
        fill_json,
        "static/COQE_dataset/images",
        processor,
        transform=train_transform if shuffle else None
    )

    return DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=0
    )

# ----------------------------
# Training (WITH CHECKPOINTING)
# ----------------------------
def train_model(epochs=16):
    print("🚀 Training started...")

    train_loader = get_loader(
        "static/COQE_dataset/train.json",
        "static/COQE_dataset/train_pour_prediction.json"
    )

    val_loader = get_loader(
        "static/COQE_dataset/val.json",
        "static/COQE_dataset/val_pour_prediction.json",
        shuffle=False
    )

    optimizer = torch.optim.Adam(model.parameters(), lr=3e-5)
    loss_fn = nn.MSELoss()

    best_loss = float("inf")

    checkpoint_path = "checkpoint.pth"
    start_epoch = 0

    # 🔄 RESUME IF CHECKPOINT EXISTS
    if os.path.exists(checkpoint_path):
        print("🔁 Resuming from checkpoint...")
        checkpoint = torch.load(checkpoint_path, map_location=device)

        model.load_state_dict(checkpoint['model_state'])
        optimizer.load_state_dict(checkpoint['optimizer_state'])
        start_epoch = checkpoint['epoch'] + 1
        best_loss = checkpoint['best_loss']

        print(f"➡️ Starting from epoch {start_epoch+1}")
        print(f"📊 Previous best loss: {best_loss:.4f}")

    for epoch in range(start_epoch, epochs):
        model.train()
        total_loss = 0

        print(f"\n🔥 Epoch {epoch+1} starting...")

        for i, batch in enumerate(train_loader):
            inputs = batch["pixel_values"].to(device)

            cap = batch["capacity"].unsqueeze(1).to(device)
            fill = batch["fill"].unsqueeze(1).to(device)

            outputs = model(pixel_values=inputs).logits

            pred_cap = outputs[:, 0:1]
            pred_fill = outputs[:, 1:2]

            loss = loss_fn(pred_cap, cap) + loss_fn(pred_fill, fill)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

            if i % 50 == 0:
                print(f"Batch {i}/{len(train_loader)} Loss: {loss.item():.4f}")

        avg_train = total_loss / len(train_loader)
        val_loss = evaluate(val_loader, loss_fn)

        print(f"✅ Epoch {epoch+1} | Train: {avg_train:.4f} | Val: {val_loss:.4f}")

        # 🏆 SAVE BEST MODEL
        if val_loss < best_loss:
            best_loss = val_loss
            torch.save(model.state_dict(), "best_model.pth")
            print("💾 Saved best model")

        # 💾 SAVE CHECKPOINT EVERY EPOCH
        torch.save({
            'epoch': epoch,
            'model_state': model.state_dict(),
            'optimizer_state': optimizer.state_dict(),
            'best_loss': best_loss
        }, checkpoint_path)

        print("💾 Checkpoint saved")

    print("🎉 Training complete!")

# ----------------------------
# Evaluation
# ----------------------------
def evaluate(loader, loss_fn):
    model.eval()
    total = 0

    with torch.no_grad():
        for batch in loader:
            inputs = batch["pixel_values"].to(device)

            cap = batch["capacity"].unsqueeze(1).to(device)
            fill = batch["fill"].unsqueeze(1).to(device)

            outputs = model(pixel_values=inputs).logits

            pred_cap = outputs[:, 0:1]
            pred_fill = outputs[:, 1:2]

            loss = loss_fn(pred_cap, cap) + loss_fn(pred_fill, fill)
            total += loss.item()

    return total / len(loader)

# ----------------------------
# Load model (Flask)
# ----------------------------
def load_model():
    if os.path.exists("best_model.pth"):
        model.load_state_dict(torch.load("best_model.pth", map_location=device))
        print("✅ Model loaded")
    else:
        print("⚠️ No trained model found")

    model.eval()
    return model

# ----------------------------
# Prediction
# ----------------------------
# ----------------------------
# Prediction
# ----------------------------
def predict_capacity(image_path):
    """
    Predicts the container capacity (mL) from an image.
    Returns only mL and fl oz as floats.
    """
    global model, processor, device, GLOBAL_MAX_VOLUME

    GLOBAL_MAX_VOLUME = 50000
    model.eval()

    # Open and process image
    image = Image.open(image_path).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}

    # Run model
    with torch.no_grad():
        outputs = model(**inputs)

    # ----------------------------
    # Extract scalar prediction safely
    # ----------------------------
    pred = outputs.logits  # could be tensor, tuple, list

    if isinstance(pred, torch.Tensor):
        # Convert any tensor shape to a scalar
        capacity_norm = float(pred.detach().cpu().numpy().flatten()[0])
    elif isinstance(pred, (tuple, list)):
        # If tuple/list, pick first element
        capacity_norm = float(pred[0])
    else:
        # Already a number
        capacity_norm = float(pred)

    # Clamp normalized value between 0 and 1
    capacity_norm = max(0, min(capacity_norm, 1))

    # ----------------------------
    # Convert to mL
    # ----------------------------
    capacity_ml = capacity_norm * GLOBAL_MAX_VOLUME
    capacity_ml = max(50, min(capacity_ml, GLOBAL_MAX_VOLUME))  # clamp

    # ----------------------------
    # Convert to fl oz
    # ----------------------------
    capacity_oz = capacity_ml / 29.5735

    # ----------------------------
    # Print and return
    # ----------------------------
    print(f"Predicted capacity: {capacity_ml:.1f} mL / {capacity_oz:.2f} fl oz")

    return float(capacity_ml), float(capacity_oz)