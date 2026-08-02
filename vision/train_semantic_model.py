from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
from PIL import Image, ImageDraw


COCO_PACKAGE_VERSION = "civora_vision_coco_package_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="Train Civora's semantic aerial imagery model from a rights-cleared COCO package.")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--image-root", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--learning-rate", type=float, default=0.0003)
    parser.add_argument("--image-size", type=int, default=512)
    parser.add_argument("--base-channels", type=int, default=32)
    parser.add_argument("--seed", type=int, default=41)
    parser.add_argument("--device", default="auto")
    args = parser.parse_args()

    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, Dataset
    except Exception as exc:
        raise SystemExit(
            "PyTorch training dependencies are missing. Install requirements_vision_training.txt before training."
        ) from exc

    dataset_payload = json.loads(Path(args.dataset).expanduser().read_text(encoding="utf-8"))
    if dataset_payload.get("version") != COCO_PACKAGE_VERSION:
        raise SystemExit(f"Expected {COCO_PACKAGE_VERSION}.")
    if dataset_payload.get("contains_image_bytes") is not False:
        raise SystemExit("Training package must preserve the no-embedded-image contract.")
    if not dataset_payload.get("dataset_fingerprint"):
        raise SystemExit("Training package is missing its deterministic dataset fingerprint.")
    image_root = Path(args.image_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    categories = sorted(dataset_payload.get("categories") or [], key=lambda item: int(item["id"]))
    class_ids = [int(item["id"]) for item in categories]
    if class_ids != list(range(1, len(categories) + 1)):
        raise SystemExit("COCO category IDs must be contiguous and start at 1; class 0 is reserved for background.")
    class_count = len(categories) + 1
    annotations_by_image: Dict[int, List[Dict[str, Any]]] = {}
    for item in dataset_payload.get("annotations") or []:
        annotations_by_image.setdefault(int(item["image_id"]), []).append(dict(item))
    images_by_split = {
        split: [dict(item) for item in dataset_payload.get("images") or [] if item.get("split") == split]
        for split in ("train", "validation", "test")
    }
    if not images_by_split["train"]:
        raise SystemExit("Training split contains no rights-cleared images.")
    if not images_by_split["validation"]:
        raise SystemExit("Validation split contains no images; add more frames or choose a different deterministic split seed.")

    class CocoSemanticDataset(Dataset):
        def __init__(self, images: List[Dict[str, Any]], *, augment: bool) -> None:
            self.images = images
            self.augment = augment

        def __len__(self) -> int:
            return len(self.images)

        def __getitem__(self, index: int) -> Tuple[Any, Any]:
            rec = self.images[index]
            path = (image_root / str(rec["file_name"])).resolve()
            if image_root not in path.parents and path != image_root:
                raise RuntimeError("Image path escaped the configured image root.")
            if not path.is_file():
                raise FileNotFoundError(f"Registered training image is missing: {path}")
            image = Image.open(path).convert("RGB")
            source_width, source_height = image.size
            image = image.resize((args.image_size, args.image_size), Image.Resampling.BILINEAR)
            mask = Image.new("I", (args.image_size, args.image_size), 0)
            draw = ImageDraw.Draw(mask)
            scale_x = args.image_size / max(source_width, 1)
            scale_y = args.image_size / max(source_height, 1)
            for annotation in annotations_by_image.get(int(rec["id"]), []):
                class_id = int(annotation["category_id"])
                for polygon in annotation.get("segmentation") or []:
                    points = [
                        (float(polygon[offset]) * scale_x, float(polygon[offset + 1]) * scale_y)
                        for offset in range(0, len(polygon) - 1, 2)
                    ]
                    if len(points) >= 3:
                        draw.polygon(points, fill=class_id)
            image_array = np.asarray(image, dtype=np.float32) / 255.0
            mask_array = np.asarray(mask, dtype=np.int64)
            if self.augment and random.random() < 0.5:
                image_array = np.flip(image_array, axis=1).copy()
                mask_array = np.flip(mask_array, axis=1).copy()
            if self.augment and random.random() < 0.25:
                image_array = np.flip(image_array, axis=0).copy()
                mask_array = np.flip(mask_array, axis=0).copy()
            return (
                torch.from_numpy(np.transpose(image_array, (2, 0, 1))).float(),
                torch.from_numpy(mask_array).long(),
            )

    class ConvBlock(nn.Module):
        def __init__(self, input_channels: int, output_channels: int) -> None:
            super().__init__()
            self.block = nn.Sequential(
                nn.Conv2d(input_channels, output_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(output_channels),
                nn.ReLU(inplace=True),
                nn.Conv2d(output_channels, output_channels, 3, padding=1, bias=False),
                nn.BatchNorm2d(output_channels),
                nn.ReLU(inplace=True),
            )

        def forward(self, value: Any) -> Any:
            return self.block(value)

    class CivoraUNet(nn.Module):
        def __init__(self, classes: int, base: int) -> None:
            super().__init__()
            self.enc1 = ConvBlock(3, base)
            self.enc2 = ConvBlock(base, base * 2)
            self.enc3 = ConvBlock(base * 2, base * 4)
            self.bridge = ConvBlock(base * 4, base * 8)
            self.pool = nn.MaxPool2d(2)
            self.up3 = nn.ConvTranspose2d(base * 8, base * 4, 2, stride=2)
            self.dec3 = ConvBlock(base * 8, base * 4)
            self.up2 = nn.ConvTranspose2d(base * 4, base * 2, 2, stride=2)
            self.dec2 = ConvBlock(base * 4, base * 2)
            self.up1 = nn.ConvTranspose2d(base * 2, base, 2, stride=2)
            self.dec1 = ConvBlock(base * 2, base)
            self.head = nn.Conv2d(base, classes, 1)

        def forward(self, value: Any) -> Any:
            enc1 = self.enc1(value)
            enc2 = self.enc2(self.pool(enc1))
            enc3 = self.enc3(self.pool(enc2))
            bridge = self.bridge(self.pool(enc3))
            dec3 = self.dec3(torch.cat([self.up3(bridge), enc3], dim=1))
            dec2 = self.dec2(torch.cat([self.up2(dec3), enc2], dim=1))
            dec1 = self.dec1(torch.cat([self.up1(dec2), enc1], dim=1))
            return self.head(dec1)

    device_name = args.device
    if device_name == "auto":
        device_name = "cuda" if torch.cuda.is_available() else "mps" if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available() else "cpu"
    device = torch.device(device_name)
    train_loader = DataLoader(
        CocoSemanticDataset(images_by_split["train"], augment=True),
        batch_size=max(1, args.batch_size),
        shuffle=True,
        num_workers=0,
    )
    validation_loader = DataLoader(
        CocoSemanticDataset(images_by_split["validation"], augment=False),
        batch_size=max(1, args.batch_size),
        shuffle=False,
        num_workers=0,
    )
    model = CivoraUNet(class_count, max(8, args.base_channels)).to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=args.learning_rate)
    criterion = nn.CrossEntropyLoss()
    history: List[Dict[str, float]] = []
    best_validation_loss = float("inf")
    checkpoint_path = output_dir / "best_state_dict.pt"
    for epoch in range(max(1, args.epochs)):
        model.train()
        training_loss = 0.0
        for images, masks in train_loader:
            images, masks = images.to(device), masks.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = criterion(model(images), masks)
            loss.backward()
            optimizer.step()
            training_loss += float(loss.detach().cpu())
        validation = _validate(model, validation_loader, criterion, device, class_count, torch)
        record = {
            "epoch": epoch + 1,
            "training_loss": round(training_loss / max(len(train_loader), 1), 6),
            **validation,
        }
        history.append(record)
        print(json.dumps(record))
        if validation["validation_loss"] < best_validation_loss:
            best_validation_loss = validation["validation_loss"]
            torch.save(model.state_dict(), checkpoint_path)
    model.load_state_dict(torch.load(checkpoint_path, map_location=device, weights_only=True))
    model.eval()
    onnx_path = output_dir / "civora_semantic.onnx"
    dummy = torch.zeros((1, 3, args.image_size, args.image_size), dtype=torch.float32, device=device)
    torch.onnx.export(
        model,
        dummy,
        str(onnx_path),
        input_names=["images"],
        output_names=["logits"],
        dynamic_axes={"images": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=18,
        dynamo=False,
    )
    run_report = {
        "version": "civora_vision_training_run_v1",
        "dataset_fingerprint": dataset_payload["dataset_fingerprint"],
        "training_image_count": len(images_by_split["train"]),
        "validation_image_count": len(images_by_split["validation"]),
        "test_image_count": len(images_by_split["test"]),
        "categories": [{"id": 0, "name": "background"}] + categories,
        "hyperparameters": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "learning_rate": args.learning_rate,
            "image_size": args.image_size,
            "base_channels": args.base_channels,
            "seed": args.seed,
            "device": device_name,
        },
        "history": history,
        "best_validation": min(history, key=lambda item: item["validation_loss"]),
        "onnx_path": onnx_path.name,
        "checkpoint_path": checkpoint_path.name,
        "promotion_ready": False,
        "promotion_blocker": "Run object-level ground-truth evaluation and the promotion gate before deployment.",
        "truth_label": (
            "Training/validation loss and pixel IoU describe this run only. They are not deployment quality, survey/control, "
            "or engineering evidence."
        ),
    }
    class_map = {"0": "background", **{str(int(item["id"])): str(item["name"]) for item in categories}}
    (output_dir / "classes.json").write_text(json.dumps(class_map, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output_dir / "training_run.json").write_text(json.dumps(run_report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "onnx_model": str(onnx_path),
                "class_map": str(output_dir / "classes.json"),
                "training_report": str(output_dir / "training_run.json"),
            },
            indent=2,
        )
    )
    return 0


def _validate(model: Any, loader: Any, criterion: Any, device: Any, class_count: int, torch: Any) -> Dict[str, float]:
    model.eval()
    loss_total = 0.0
    intersections = np.zeros(class_count, dtype=np.float64)
    unions = np.zeros(class_count, dtype=np.float64)
    correct = 0
    pixels = 0
    with torch.no_grad():
        for images, masks in loader:
            images, masks = images.to(device), masks.to(device)
            logits = model(images)
            loss_total += float(criterion(logits, masks).detach().cpu())
            predicted = torch.argmax(logits, dim=1)
            correct += int((predicted == masks).sum().detach().cpu())
            pixels += int(masks.numel())
            pred_np = predicted.detach().cpu().numpy()
            truth_np = masks.detach().cpu().numpy()
            for class_id in range(class_count):
                pred_mask = pred_np == class_id
                truth_mask = truth_np == class_id
                intersections[class_id] += np.logical_and(pred_mask, truth_mask).sum()
                unions[class_id] += np.logical_or(pred_mask, truth_mask).sum()
    class_ious = [intersections[index] / unions[index] for index in range(1, class_count) if unions[index] > 0]
    return {
        "validation_loss": round(loss_total / max(len(loader), 1), 6),
        "validation_pixel_accuracy": round(correct / max(pixels, 1), 6),
        "validation_mean_foreground_iou": round(float(np.mean(class_ious)) if class_ious else 0.0, 6),
    }


if __name__ == "__main__":
    raise SystemExit(main())
