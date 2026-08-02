# Chat 246 SpaceNet Building Shadow Candidate

This directory contains a blocked evaluation candidate for background shadow comparison only.

## Evidence

- Dataset: SpaceNet 2 Buildings sample
- Source: https://spacenet.ai/spacenet-buildings-dataset-v2/
- Attribution: SpaceNet Partners
- Dataset license: CC BY-SA 4.0
- Images: 40 across Vegas, Paris, Shanghai, and Khartoum
- Split: 28 train, 4 validation, 8 independently held-out test images
- Held-out objects: 124 buildings
- Held-out precision: 0.4615
- Held-out recall: 0.2419
- Held-out F1: 0.3175
- Held-out mean matched bounding-box IoU: 0.6700

The model failed Civora's precision, recall, F1, geography, season, and imagery-quality coverage gates. Its manifest is
therefore `candidate_blocked`, and no approver is recorded.

## Operating Boundary

The artifact may be loaded only with `require_promoted=False` inside Civora's bounded background shadow path. Shadow
inference is sampled, asynchronous, aggregate-only, and cannot replace or add a user-visible detection. Do not set this
artifact as `CIVORA_GATEWAY_MODEL_MANIFEST` for the primary detector.

No source imagery or SpaceNet annotation files are stored in this repository. The ONNX weights are a derived evaluation
artifact; preserve the SpaceNet attribution and CC BY-SA 4.0 notice when redistributing them. Torchvision's LRASPP
MobileNetV3 backbone code and pretrained weights are provided under the PyTorch BSD-style license.
