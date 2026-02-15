"""
Train a GradientBoostingRegressor for flight time prediction.

Reads the synthetic training data CSV, trains the model, and saves the
model artifact (model + scaler + encoder) as a single .joblib file.

Usage:
    python ml_models/training/train_model.py
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler
import joblib

# ── Paths ───────────────────────────────────────────────────────────────────

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "training_data" / "flight_times.csv"
MODEL_FILE = BASE_DIR / "flight_time_model.joblib"

# ── Main ────────────────────────────────────────────────────────────────────

def main():
    if not DATA_FILE.exists():
        print(f"ERROR: Training data not found at {DATA_FILE}")
        print("Run generate_training_data.py first.")
        sys.exit(1)

    print(f"Loading training data from {DATA_FILE}...")
    df = pd.read_csv(DATA_FILE)
    print(f"Loaded {len(df)} samples")

    # Drop rows with missing or invalid values
    df = df.dropna()
    df = df[(df["distance_nm"] > 0) & (df["flight_time_minutes"] > 0)]
    print(f"After cleaning: {len(df)} samples")

    if len(df) < 100:
        print("ERROR: Not enough valid samples for training")
        sys.exit(1)

    # ── Feature engineering ─────────────────────────────────────────────

    # Encode aircraft type
    le = LabelEncoder()
    df["aircraft_encoded"] = le.fit_transform(df["aircraft_type"])

    # Fill missing route_deviation_factor with 1.0 (direct routing)
    if "route_deviation_factor" not in df.columns:
        df["route_deviation_factor"] = 1.0
    df["route_deviation_factor"] = df["route_deviation_factor"].fillna(1.0)

    feature_cols = ["distance_nm", "aircraft_encoded", "cruise_speed_kts", "cruise_altitude_ft", "route_deviation_factor"]
    X = df[feature_cols].values
    y = df["flight_time_minutes"].values

    # ── Train/test split ────────────────────────────────────────────────

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    # ── Train model ─────────────────────────────────────────────────────

    print("\nTraining GradientBoostingRegressor...")
    model = GradientBoostingRegressor(
        n_estimators=200,
        max_depth=5,
        learning_rate=0.1,
        random_state=42,
    )
    model.fit(X_train_scaled, y_train)

    # ── Evaluate ────────────────────────────────────────────────────────

    y_pred = model.predict(X_test_scaled)

    mae = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2 = r2_score(y_test, y_pred)

    print(f"\n{'='*40}")
    print(f"  MAE:  {mae:.2f} minutes")
    print(f"  RMSE: {rmse:.2f} minutes")
    print(f"  R²:   {r2:.4f}")
    print(f"{'='*40}")

    # Feature importance
    print("\nFeature importance:")
    for name, imp in zip(feature_cols, model.feature_importances_):
        print(f"  {name:25s} {imp:.4f}")

    # ── Save artifact ───────────────────────────────────────────────────

    artifact = {
        "model": model,
        "scaler": scaler,
        "label_encoder": le,
        "feature_cols": feature_cols,
        "aircraft_classes": list(le.classes_),
        "version": "1.0.0",
        "metrics": {"mae": mae, "rmse": rmse, "r2": r2},
    }

    joblib.dump(artifact, MODEL_FILE)
    print(f"\nModel saved to {MODEL_FILE}")
    print(f"Known aircraft types: {list(le.classes_)}")


if __name__ == "__main__":
    main()
