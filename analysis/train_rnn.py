"""플랫폼용 RNN 경기력 예측 모델 학습 (D4, D26). 실데이터를 다루므로 레포 안에서는 실행 결과를 남기지 않는다.

    <torch 가상환경>/bin/python analysis/train_rnn.py \\
        --workflow <저자 코드 폴더>/AI-driven_APP_workflow.py \\
        --raw <인계본>/data/male/male_weightlifting_raw.csv --sex M --out <레포 밖 경로>

연구진 코드(원고의 RNN)를 **실행 시 경로로 import**해서 같은 전처리·모델·학습 함수를 쓴다. 저자 코드는
라이선스가 없으므로 레포에 복사하지 않는다.

원고 파이프라인(run_all)과 다른 점 — 플랫폼 목적(경기력 예측만, 인계 메모)에 맞춘 것:
  1. doping 열을 읽지 않는다. 저자 함수가 label 열을 필수로 요구하므로, 입력 사본에서 그 열을 상수 0으로
     바꿔 넘긴다. reference_population = "all", 분할은 선수 단위 KFold(층화 없음).
  2. 최종 모델은 전 연도로 학습한다(원고 final은 cutoff 이전 fitting 분할만 → 이후 연도가 vocab에 없음).
  3. 분류·XGBoost·SHAP·calibration은 하지 않는다.
예측 구간용 편향(평균 잔차)과 σ는 선수 단위 OOF(out-of-fold) 잔차로, 최종 대회 계체 체중의 2018 IWF 체급별로
구한다(1998–2022 자료이므로 체급은 '체중 구간'으로 쓰는 것이며 당시 실제 체급이 아니다. 원고는 고정 구간 7개
≤61…>109를 썼다). 최종 대회가 예측보다 계통적으로 높게 나오므로 z = (잔차 − 편향) / σ로 쓴다.
직전 대비 계체 체중 변화가 rules.yaml의 weight_jump_kg를 넘는 선수는 플랫폼에서 z를 쓰지 않으므로(weight_change)
편향·σ 계산에서도 뺀다 — 규칙이 적용되는 모집단과 σ를 잰 모집단을 맞추기 위해서다.

산출물(--out/export): rnn_<sex>.npz(가중치), rnn_<sex>.json(vocab·표준화·σ·지표·출처). **선수 key(국적|생년월일)
목록은 넣지 않는다.** 중간 파일(정제 기록, fold 모델 메타 등 개인정보 포함)은 --keep-intermediate가 없으면 지운다.
내보내기 전에 backend/app/rnn_infer.py(numpy)와 torch 출력이 1e-4 kg 안에서 같은지 검증한다.
"""

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from sklearn.model_selection import KFold

REPO = Path(__file__).resolve().parents[1]
TOLERANCE_KG = 1e-4
MIN_PER_CLASS = 30  # 체급별 σ를 따로 쓰려면 필요한 OOF 선수 수. 모자라면 성별 전체 σ로 대체(표시함)


def weight_jump_kg() -> float:
    """rules.yaml의 값을 그대로 쓴다(학습 가상환경에 pyyaml이 없어 한 줄만 읽는다)."""
    text = (REPO / "knowledge/rules.yaml").read_text(encoding="utf-8")
    return float(re.search(r"^\s*weight_jump_kg:\s*([0-9.]+)", text, re.M).group(1))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weight_class(classes: list[int], bw: float) -> int:
    """profiling.weight_class와 같은 규칙(학습 가상환경에서는 backend를 import하지 않으므로 표만 공유)."""
    return next((c for c in classes if c != 999 and bw <= c), 999)


def guard_outside_repo(out: Path) -> None:
    if out.resolve().is_relative_to(REPO):
        raise SystemExit(f"--out은 레포 밖이어야 합니다(실데이터 산출물): {out}")


def label_free_copy(raw: Path, label_col: str, dest: Path) -> tuple[Path, int]:
    """doping 값을 읽지 않도록 상수 0으로 덮은 사본. 저자 함수의 필수 열 검사만 통과시킨다.
    원래 값이 0/1이 아니던 행 수만 센다(원고 코호트에서는 그 행이 빠졌으므로 코호트 차이의 설명용)."""
    df = pd.read_csv(raw, dtype=str, encoding="utf-8-sig")
    if label_col not in df:
        raise SystemExit(f"label 열 없음: {label_col}")
    nonbinary = int((~df[label_col].str.strip().isin(["0", "1", "0.0", "1.0"])).sum())
    df[label_col] = "0"
    df.to_csv(dest, index=False, encoding="utf-8-sig")
    return dest, nonbinary


def metrics(y: np.ndarray, p: np.ndarray) -> dict:
    r = y - p
    return dict(n=int(len(y)), rmse_kg=float(np.sqrt(np.mean(r ** 2))), mae_kg=float(np.mean(np.abs(r))),
                r2=float(1 - np.sum(r ** 2) / np.sum((y - y.mean()) ** 2)))


def to_numpy(model) -> dict[str, np.ndarray]:
    return {k: v.detach().cpu().numpy() for k, v in model.state_dict().items()}


def verify(wf, rnn_infer, model, meta, samples, ids, cfg) -> float:
    """torch(저자 predict_rnn)와 numpy(rnn_infer) 출력의 최대 차이(kg). 호출 쪽이 미지 토큰 사본도 넘긴다."""
    torch_pred = wf.predict_rnn(model, samples, ids, meta, cfg)
    w = {k: v.astype(np.float64) for k, v in to_numpy(model).items()}
    worst = 0.0
    for i, expected in zip(ids, torch_pred):
        s = samples[int(i)]
        ec, age, year = (rnn_infer.encode(m, list(vals)) for vals, m in
                         zip([s.event_categories, s.ages, s.years], meta["vocab"]))
        got = rnn_infer.predict(w, meta["center"], meta["scale"], list(s.totals), ec, age, year)
        worst = max(worst, abs(got - float(expected)))
    return worst


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--workflow", type=Path, required=True, help="저자 코드 AI-driven_APP_workflow.py 경로")
    ap.add_argument("--raw", type=Path, required=True)
    ap.add_argument("--sex", choices=["M", "F"], required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--columns", type=json.loads, default=None, help='Config.columns 덮어쓰기(JSON), 여성 자료용')
    ap.add_argument("--folds", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--epochs", type=int, default=None, help="max_epochs(기본: 저자 Config)")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--keep-intermediate", action="store_true", help="개인정보가 든 중간 파일을 지우지 않음")
    args = ap.parse_args()

    guard_outside_repo(args.out)
    work = args.out / f"work_{args.sex}"
    export = args.out / "export"
    shutil.rmtree(work, ignore_errors=True)  # 이전 실행이 강제 종료돼 남은 개인정보 중간 파일
    work.mkdir(parents=True, exist_ok=True)
    print(f"중간 파일: {work} (끝나면 삭제)", flush=True)
    export.mkdir(parents=True, exist_ok=True)

    wf = load_module("app_workflow", args.workflow)
    rnn_infer = load_module("rnn_infer", REPO / "backend/app/rnn_infer.py")
    classes = json.loads((REPO / "data/model_params.json").read_text(encoding="utf-8"))["classes"][args.sex]

    cfg = wf.Config()
    if args.columns:
        cfg.columns.update(args.columns)
    cfg.output_dir = str(work)  # 저자 함수가 output_dir에 쓰더라도 레포(cwd)가 아니라 work에
    cfg.reference_population = "all"
    cfg.resume = False
    cfg.device = args.device
    cfg.seed = args.seed
    if args.epochs:
        cfg.max_epochs = args.epochs
    label_free, nonbinary_labels = label_free_copy(args.raw, cfg.columns["label"], work / "input_label_free.csv")
    cfg.raw_csv = str(label_free)
    jump_k = weight_jump_kg()
    wf.set_seed(cfg.seed, cfg.n_jobs)

    try:
        records, audit = wf.read_and_audit(cfg, work)
        a, samples = wf.build_cohort(records, cfg, cfg.min_records)
        ids = np.arange(len(samples))
        targets = np.array([s.target for s in samples])
        target_class = np.array([weight_class(classes, float(bw)) for bw in a.bweight])

        # 1) 선수 단위 OOF 잔차 (층화 없음 — doping 라벨을 쓰지 않는다)
        oof = np.full(len(samples), np.nan)
        kfold = KFold(args.folds, shuffle=True, random_state=cfg.seed)
        for k, (tr, va) in enumerate(kfold.split(ids), start=1):
            model, meta = wf.fit_rnn(samples, ids[tr], cfg, cfg.seed + 1000 + k, work / "folds", f"fold{k}")
            oof[va] = wf.predict_rnn(model, samples, ids[va], meta, cfg)
        residual = targets - oof
        last_two = records.groupby("key", sort=False).bweight.agg(lambda s: float(s.iloc[-1] - s.iloc[-2]) if len(s) > 1 else 0.0)
        jumped = np.abs(a.key.map(last_two).to_numpy(float)) > jump_k
        residual_all = residual
        residual = residual[~jumped]
        target_class = target_class[~jumped]
        pooled = float(np.std(residual))
        pooled_bias = float(np.mean(residual))
        sigma, bias, sigma_n, pooled_classes = {}, {}, {}, []
        for c in classes:
            r = residual[target_class == c]
            key = f"{args.sex}{c}"
            sigma_n[key] = int(len(r))
            enough = len(r) >= MIN_PER_CLASS
            sigma[key] = round(float(np.std(r)) if enough else pooled, 3)
            bias[key] = round(float(np.mean(r)) if enough else pooled_bias, 3)
            if not enough:
                pooled_classes.append(c)

        # 2) 최종 모델: 전 선수·전 연도
        model, meta = wf.fit_rnn(samples, ids, cfg, cfg.seed + 2000, work / "final", "final")
        check_ids = np.random.default_rng(cfg.seed).choice(ids, size=min(300, len(ids)), replace=False)
        worst = verify(wf, rnn_infer, model, meta, samples, check_ids, cfg)
        # 플랫폼은 학습 이후 연도(미지 토큰 → padding 영벡터)를 늘 쓰므로 그 경로도 검증한다
        unseen = [dataclasses.replace(samples[int(i)], years=["UNSEEN"] * len(samples[int(i)].years))
                  for i in check_ids]
        worst = max(worst, verify(wf, rnn_infer, model, meta, unseen, np.arange(len(unseen)), cfg))
        if worst >= TOLERANCE_KG:
            raise SystemExit(f"numpy 추론이 torch와 다름: 최대 {worst:.2e} kg (허용 {TOLERANCE_KG})")

        years = sorted(int(y) for y in meta["vocab"][2])
        np.savez(export / f"rnn_{args.sex}.npz", **to_numpy(model))
        out_meta = dict(
            source="real", sex=args.sex, model="rnn", weight_class_system="IWF-2018",
            weight_class_note="체중 구간으로 사용(1998–2022 기록의 당시 실제 체급 아님). 원고는 고정 구간 7개(≤61…>109)",
            vocab=meta["vocab"], center=meta["center"], scale=meta["scale"], params=meta["params"],
            best_epoch=meta["best_epoch"], z95=1.96, min_history=2,
            sigma=sigma, bias=bias, sigma_n=sigma_n, sigma_pooled_classes=pooled_classes,
            sigma_pooled=round(pooled, 3), bias_pooled=round(pooled_bias, 3),
            weight_jump_kg=jump_k, sigma_excluded_weight_jump_n=int(jumped.sum()),
            oof_residual_sd_weight_jump=round(float(np.std(residual_all[jumped])), 3) if jumped.any() else None,
            oof_metrics_all_athletes=metrics(targets, oof),
            n_athletes=int(len(samples)), n_records=int(len(records)), label_nonbinary_rows_in_raw=nonbinary_labels,
            vocab_age_outside_10_60=sorted(int(x) for x in meta["vocab"][1] if not 10 <= int(x) <= 60),
            year_range=[years[0], years[-1]],
            event_category_counts={k: int(v) for k, v in records.event_category.value_counts().items()},
            reference_population="all", doping_column_read=False, split="athlete KFold, unstratified",
            numpy_torch_max_abs_diff_kg=worst,
            raw_sha256=sha256(args.raw), workflow_sha256=sha256(args.workflow),
            workflow_version=getattr(wf, "VERSION", None), torch=torch.__version__,
            created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            identity_status=audit.get("identity_status"),
        )
        (export / f"rnn_{args.sex}.json").write_text(json.dumps(out_meta, ensure_ascii=False, indent=2) + "\n",
                                                    encoding="utf-8")
        print(json.dumps({k: out_meta[k] for k in ("n_athletes", "n_records", "year_range", "oof_metrics_all_athletes",
                                                    "sigma_pooled", "bias_pooled", "sigma_pooled_classes",
                                                    "sigma_excluded_weight_jump_n", "label_nonbinary_rows_in_raw",
                                                    "numpy_torch_max_abs_diff_kg")}, ensure_ascii=False, indent=2))
    finally:
        if not args.keep_intermediate:
            shutil.rmtree(work, ignore_errors=True)
            print(f"중간 파일 삭제: {work}", flush=True)


if __name__ == "__main__":
    main()
