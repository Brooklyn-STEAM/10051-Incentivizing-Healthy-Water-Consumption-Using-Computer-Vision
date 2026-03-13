# ai_model.py
from transformers import AutoImageProcessor, AutoModelForImageClassification
from PIL import Image
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader
import os
import json

# ----------------------------
# 1️⃣ Initialize AI model
# ----------------------------
processor = AutoImageProcessor.from_pretrained("microsoft/resnet-152")
model = AutoModelForImageClassification.from_pretrained("microsoft/resnet-152")

# Replace classifier with regression head for volume prediction
model.classifier[1] = nn.Linear(model.classifier[1].in_features, 1)
model.eval()  # evaluation mode

# ----------------------------
# 2️⃣ Dataset class for COQE_dataset
# ----------------------------
class VolumeDataset(Dataset):
    """
    Dataset class that reads COQE_dataset JSON labels and images
    """
    def __init__(self, json_file, images_folder, processor):
        """
        json_file: path to train.json, test.json, etc.
        images_folder: path to COQE_dataset/images/
        processor: Hugging Face image processor
        """
        with open(json_file, "r") as f:
            self.data = json.load(f)
        self.images_folder = images_folder
        self.processor = processor

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        # Each entry in JSON should have "image_filename" and "volume" keys
        entry = self.data[idx]
        img_path = os.path.join(self.images_folder, entry["image_filename"])
        volume = entry["volume"]

        image = Image.open(img_path).convert("RGB")
        inputs = self.processor(images=image, return_tensors="pt")
        pixel_values = inputs['pixel_values'].squeeze(0)

        return {
            "pixel_values": pixel_values,
            "volume": torch.tensor(volume, dtype=torch.float)
        }

# ----------------------------
# 3️⃣ DataLoader helper function
# ----------------------------
def get_dataloader(json_file, images_folder, processor, batch_size=8, shuffle=True):
    dataset = VolumeDataset(json_file, images_folder, processor)
    return DataLoader(dataset, batch_size=batch_size, shuffle=shuffle)

# ----------------------------
# 4️⃣ Predict function for user-uploaded images
# ----------------------------
def predict_volume(image_file):
    """
    Takes a file-like object (uploaded by user) and returns predicted volume.
    Example in Flask: predict_volume(request.files['file'])
    """
    image = Image.open(image_file).convert("RGB")
    inputs = processor(images=image, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    return outputs.logits.item()  # numeric volume prediction

print("AI model loaded successfully")