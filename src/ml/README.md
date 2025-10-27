# SOCIALIZER ML Service

This directory contains the machine learning components for the Live Thread Sentiment Radar project. The current implementation ships a deterministic bag-of-words checkpoint so the backend can exercise the full inference contract while the transformer-based model is being fine-tuned.

## Layout

```
src/ml/
├── README.md                # This file
├── requirements.txt         # Extra dependencies for ML work
└── ltsr_ml/                 # Python package
    ├── __init__.py
    ├── config.py            # Shared configuration via environment variables
    ├── schemas.py           # Pydantic models for inference inputs/outputs
    ├── utils/               # Shared helpers (logging, paths)
    ├── models/              # Model definitions and wrappers
    ├── training/            # Training dataset and pipeline scaffolding
    ├── evaluation/          # Metrics helpers
    └── inference/           # FastAPI inference service
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r src/ml/requirements.txt
python -m spacy download en_core_web_lg
uvicorn ltsr_ml.inference.server:app --reload
```

`POST /predict` accepts a list of comment texts and returns sentiment, sarcasm, and toxicity scores derived from the packaged checkpoint in `ltsr_ml/assets/bow_checkpoint.json`. Swap the checkpoint path (or export a new one via the training pipeline) once a transformer model is ready.

## Environment Variables

All ML-specific environment variables are prefixed with `ML_`. See `ltsr_ml/config.py` for defaults such as:

| Variable | Description | Default |
|----------|-------------|---------|
| `ML_MODEL_NAME` | Hugging Face model identifier | `roberta-base` |
| `ML_MODEL_VERSION` | Semantic version of the deployed model | `v0` |
| `ML_DEVICE` | Compute device (`cpu`, `cuda`) | `cpu` |
| `ML_MAX_LENGTH` | Maximum token length during inference | `256` |
| `ML_CHECKPOINT_DIR` | Directory that stores trained weights | `data/models` |
| `ML_WANDB_PROJECT` | Optional Weights & Biases project | `None` |
| `ML_WANDB_ENTITY` | Optional Weights & Biases entity/team | `None` |

## Next Steps

- Replace the bag-of-words baseline with a fine-tuned transformer checkpoint and update the inference service configuration.
- Plug the dataset builder into real annotated Reddit comment exports (or migrate to Hugging Face `datasets`) before running longer training jobs.
- Expand training/evaluation logging (W&B charts, confusion matrices) and add automated regression tests around exported checkpoints.
