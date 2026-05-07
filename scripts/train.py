from __future__ import annotations

import argparse
import inspect
import json
from pathlib import Path

import numpy as np
import torch
import yaml
from datasets import load_dataset
from rouge_score import rouge_scorer, scoring
from transformers import (
    AutoModelForSeq2SeqLM,
    AutoTokenizer,
    DataCollatorForSeq2Seq,
    Seq2SeqTrainer,
    Seq2SeqTrainingArguments,
    set_seed,
)


def load_config(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def maybe_apply_lora(model, config: dict):
    lora = config.get("lora", {})
    if not lora.get("enabled", False):
        return model

    from peft import LoraConfig, TaskType, get_peft_model

    peft_config = LoraConfig(
        task_type=TaskType.SEQ_2_SEQ_LM,
        inference_mode=False,
        r=int(lora.get("r", 16)),
        lora_alpha=int(lora.get("alpha", 32)),
        lora_dropout=float(lora.get("dropout", 0.05)),
        target_modules=lora.get("target_modules"),
    )
    model = get_peft_model(model, peft_config)
    model.print_trainable_parameters()
    return model


def maybe_enable_gradient_checkpointing(model, config: dict):
    train_cfg = config.get("training", {})
    if not train_cfg.get("gradient_checkpointing", False):
        return model

    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()
    if hasattr(model, "config"):
        model.config.use_cache = False
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--data-dir", default="data/processed")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--hub-model-id", default="")
    parser.add_argument("--push-to-hub", action="store_true")
    args = parser.parse_args()

    set_seed(args.seed)
    config = load_config(args.config)
    data_files = {
        "train": str(Path(args.data_dir) / "train.jsonl"),
        "validation": str(Path(args.data_dir) / "val.jsonl"),
    }
    dataset = load_dataset("json", data_files=data_files)

    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForSeq2SeqLM.from_pretrained(config["model_name"])
    model = maybe_apply_lora(model, config)
    model = maybe_enable_gradient_checkpointing(model, config)

    prefix = config.get("prefix", "")
    max_source_length = int(config.get("max_source_length", 1024))
    max_target_length = int(config.get("max_target_length", 256))

    def preprocess(batch: dict) -> dict:
        inputs = [prefix + item for item in batch["source"]]
        model_inputs = tokenizer(
            inputs,
            max_length=max_source_length,
            truncation=True,
        )
        labels = tokenizer(
            text_target=batch["summary"],
            max_length=max_target_length,
            truncation=True,
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    tokenized = dataset.map(
        preprocess,
        batched=True,
        remove_columns=dataset["train"].column_names,
    )

    rouge = rouge_scorer.RougeScorer(["rouge1", "rouge2", "rougeL"], use_stemmer=False)

    def compute_metrics(eval_pred):
        preds, labels = eval_pred
        if isinstance(preds, tuple):
            preds = preds[0]
        preds = np.where(preds >= 0, preds, tokenizer.pad_token_id)
        decoded_preds = tokenizer.batch_decode(preds, skip_special_tokens=True)
        labels = np.where(labels != -100, labels, tokenizer.pad_token_id)
        decoded_labels = tokenizer.batch_decode(labels, skip_special_tokens=True)
        decoded_preds = [pred.strip() for pred in decoded_preds]
        decoded_labels = [label.strip() for label in decoded_labels]
        aggregator = scoring.BootstrapAggregator()
        for pred, label in zip(decoded_preds, decoded_labels):
            aggregator.add_scores(rouge.score(label, pred))
        result = {
            key: round(value.mid.fmeasure * 100, 4)
            for key, value in aggregator.aggregate().items()
        }
        result["gen_len"] = float(np.mean([np.count_nonzero(pred != tokenizer.pad_token_id) for pred in preds]))
        return result

    train_cfg = config.get("training", {})
    generation_cfg = config.get("generation", {})
    training_kwargs = {
        "output_dir": config["output_dir"],
        "run_name": config.get("run_name", Path(config["output_dir"]).name),
        "learning_rate": float(train_cfg.get("learning_rate", 3e-5)),
        "num_train_epochs": float(train_cfg.get("num_train_epochs", 5)),
        "weight_decay": float(train_cfg.get("weight_decay", 0.01)),
        "per_device_train_batch_size": int(train_cfg.get("per_device_train_batch_size", 2)),
        "per_device_eval_batch_size": int(train_cfg.get("per_device_eval_batch_size", 2)),
        "gradient_accumulation_steps": int(train_cfg.get("gradient_accumulation_steps", 8)),
        "warmup_ratio": float(train_cfg.get("warmup_ratio", 0.06)),
        "save_strategy": train_cfg.get("save_strategy", "epoch"),
        "logging_steps": int(train_cfg.get("logging_steps", 50)),
        "predict_with_generate": bool(train_cfg.get("predict_with_generate", True)),
        "generation_max_length": max_target_length,
        "generation_num_beams": int(generation_cfg.get("num_beams", 4)),
        "fp16": bool(train_cfg.get("fp16", True)) and torch.cuda.is_available(),
        "save_total_limit": 2,
        "load_best_model_at_end": True,
        "metric_for_best_model": "rougeL",
        "greater_is_better": True,
        "push_to_hub": args.push_to_hub,
        "hub_model_id": args.hub_model_id or None,
        "report_to": train_cfg.get("report_to", "none"),
    }
    signature = inspect.signature(Seq2SeqTrainingArguments.__init__)
    if "eval_strategy" in signature.parameters:
        training_kwargs["eval_strategy"] = train_cfg.get("eval_strategy", "epoch")
    else:
        training_kwargs["evaluation_strategy"] = train_cfg.get("eval_strategy", "epoch")
    if "gradient_checkpointing" in signature.parameters:
        training_kwargs["gradient_checkpointing"] = bool(train_cfg.get("gradient_checkpointing", False))
    if "eval_accumulation_steps" in signature.parameters and train_cfg.get("eval_accumulation_steps"):
        training_kwargs["eval_accumulation_steps"] = int(train_cfg["eval_accumulation_steps"])
    if train_cfg.get("max_steps"):
        training_kwargs["max_steps"] = int(train_cfg["max_steps"])

    training_args = Seq2SeqTrainingArguments(**training_kwargs)

    data_collator = DataCollatorForSeq2Seq(tokenizer=tokenizer, model=model)
    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"],
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    trainer.train()
    trainer.save_model(config["output_dir"])
    tokenizer.save_pretrained(config["output_dir"])
    with open(Path(config["output_dir"]) / "training_config.json", "w", encoding="utf-8") as file:
        json.dump(config, file, ensure_ascii=False, indent=2)

    if args.push_to_hub:
        trainer.push_to_hub()


if __name__ == "__main__":
    main()
