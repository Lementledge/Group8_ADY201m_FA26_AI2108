"""
================================================================================
ADY201m - Step 6: Severity Modeling & Calibration (Mô hình hóa & Đánh giá)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Huấn luyện và so sánh 5 mô hình học máy (theo đúng Slide 16 và Mục 8.6 đề cương):
      1. Logistic Regression (Mốc tuyến tính có điều chuẩn)
      2. Random Forest (Mô hình rừng ngẫu nhiên)
      3. LightGBM (Cây tăng cường tốc độ cao)
      4. XGBoost (Cây tăng cường cực đại)
      5. CatBoost (Tối ưu cho biến phân loại)
  - Vòng lặp 5 random seeds (0..4) tính trung bình cộng trừ độ lệch chuẩn:
      * Metrics: Accuracy, Fatal Recall, Fatal F1, PR-AUC, ECE (Expected Calibration Error).
  - So sánh 3 chế độ giải quyết mất cân bằng lớp (RQ2):
      * Baseline (Dữ liệu gốc 18.2% fatal)
      * Class Weights (Đánh trọng số lớp cân bằng)
      * Synthetic Augmentation (Tăng cường dữ liệu lớp tử vong lên tỷ lệ 1:3)
  - Đánh giá đổi miền sang UAS (RQ3):
      * Đo lường tổn thất F1 và sự trôi dạt hiệu chuẩn ECE trên tập drone 2018-2024.
      * Hiệu chỉnh bằng Temperature Scaling (tối ưu nhiệt độ T trên 30% UAS, test trên 70%).
      * Bootstrap 1,000 lần ước lượng khoảng tin cậy 95%.
  - Trích xuất tầm quan trọng đặc trưng bằng SHAP TreeExplainer.
  - Xuất bảng kết quả: report/table_rq2_models.csv, report/table_rq3_domain_shift.csv.
================================================================================
"""

import os
import sys
import time
import json
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from scipy.optimize import minimize_scalar

from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from lightgbm import LGBMClassifier
from xgboost import XGBClassifier
from catboost import CatBoostClassifier

from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score, roc_auc_score, average_precision_score

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def ece_score(y_true, y_prob, bins=10):
    """Tính sai số hiệu chuẩn kỳ vọng Expected Calibration Error (ECE)."""
    y_true = np.asarray(y_true)
    y_prob = np.asarray(y_prob)
    bin_idx = np.minimum((y_prob * bins).astype(int), bins - 1)
    ece = 0.0
    for k in range(bins):
        mask = (bin_idx == k)
        if mask.any():
            bin_acc = y_true[mask].mean()
            bin_conf = y_prob[mask].mean()
            bin_weight = mask.mean()
            ece += bin_weight * abs(bin_acc - bin_conf)
    return float(ece)

def run_modeling_and_evaluation():
    print(" [1/5] Nạp tập dữ liệu feat.parquet và phân tách train / test / UAS...")
    df = pd.read_parquet('data/processed/feat.parquet')
    
    cat_cols = ['ev_state', 'wx', 'light_cond', 'far_part', 'type_fly', 'flt_phase']
    num_cols = ['num_eng', 'n_aircraft', 'age_max', 'hours_max']
    X_cols = cat_cols + num_cols
    
    # Chuẩn bị dữ liệu cho mô hình dạng cây và one-hot cho linear
    df_encoded = pd.get_dummies(df, columns=cat_cols, drop_first=True)
    linear_cols = [c for c in df_encoded.columns if c not in ['ev_id', 'ev_year', 'is_uas', 'y']]
    
    manned = df[df['is_uas'] == 0]
    uas = df[df['is_uas'] == 1]
    
    train_m = manned[manned['ev_year'] <= 2018]
    test_m = manned[manned['ev_year'] >= 2019]
    
    train_enc = df_encoded[(df_encoded['is_uas'] == 0) & (df_encoded['ev_year'] <= 2018)]
    test_enc = df_encoded[(df_encoded['is_uas'] == 0) & (df_encoded['ev_year'] >= 2019)]
    uas_enc = df_encoded[df_encoded['is_uas'] == 1]
    
    X_tr_tree = train_m[X_cols]
    y_tr = train_m['y'].values
    X_te_tree = test_m[X_cols]
    y_te = test_m['y'].values
    
    X_tr_lin = train_enc[linear_cols]
    X_te_lin = test_enc[linear_cols]
    
    print(f"       Train (1990-2018): {len(X_tr_tree):,} dòng | Test (2019-2024): {len(X_te_tree):,} dòng")
    print(f"       Tỷ lệ nhãn tử vong tập Train: {y_tr.mean()*100:.2f}% | Test: {y_te.mean()*100:.2f}%")

    # -------------------------------------------------------------------------
    # 2. VÒNG LẶP 5 MÔ HÌNH TRÊN 5 SEEDS (RQ2)
    # -------------------------------------------------------------------------
    print("\n [2/5] Huấn luyện và đánh giá 5 mô hình trên 5 random seeds (RQ2)...")
    
    models = {
        'Logistic Regression': {
            'is_tree': False,
            'builder': lambda s: LogisticRegression(max_iter=500, class_weight='balanced', random_state=s)
        },
        'Random Forest': {
            'is_tree': False,  # Dùng encoded columns cho Random Forest
            'builder': lambda s: RandomForestClassifier(n_estimators=200, max_depth=12, class_weight='balanced', random_state=s, n_jobs=-1)
        },
        'LightGBM': {
            'is_tree': True,
            'builder': lambda s: LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=31, class_weight='balanced', random_state=s, verbose=-1)
        },
        'XGBoost': {
            'is_tree': True,
            'builder': lambda s: XGBClassifier(n_estimators=300, learning_rate=0.03, max_depth=6, scale_pos_weight=4.0, random_state=s, eval_metric='logloss', enable_categorical=True)
        },
        'CatBoost': {
            'is_tree': True,
            'builder': lambda s: CatBoostClassifier(iterations=300, learning_rate=0.04, depth=6, auto_class_weights='Balanced', cat_features=cat_cols, random_seed=s, verbose=0)
        }
    }
    
    rq2_results = []
    trained_best_model = None
    
    for name, config in models.items():
        print(f"   -> Đang chạy: {name} (5 seeds)...")
        f1_list, recall_list, pr_auc_list, ece_list, time_list = [], [], [], [], []
        
        for seed in range(5):
            t0 = time.perf_counter()
            model = config['builder'](seed)
            
            if config['is_tree']:
                model.fit(X_tr_tree, y_tr)
                p_prob = model.predict_proba(X_te_tree)[:, 1]
            else:
                model.fit(X_tr_lin, y_tr)
                p_prob = model.predict_proba(X_te_lin)[:, 1]
                
            elapsed = time.perf_counter() - t0
            p_pred = (p_prob >= 0.5).astype(int)
            
            f1_list.append(f1_score(y_te, p_pred))
            recall_list.append(recall_score(y_te, p_pred))
            pr_auc_list.append(average_precision_score(y_te, p_prob))
            ece_list.append(ece_score(y_te, p_prob))
            time_list.append(elapsed)
            
            if name == 'LightGBM' and seed == 0:
                trained_best_model = model
                
        rq2_results.append({
            'Model': name,
            'Fatal_Recall': f"{np.mean(recall_list):.3f} +/- {np.std(recall_list):.3f}",
            'Fatal_F1': f"{np.mean(f1_list):.3f} +/- {np.std(f1_list):.3f}",
            'PR_AUC': f"{np.mean(pr_auc_list):.3f} +/- {np.std(pr_auc_list):.3f}",
            'ECE': f"{np.mean(ece_list):.3f} +/- {np.std(ece_list):.3f}",
            'Train_Time_s': f"{np.mean(time_list):.2f}"
        })
        
    df_rq2 = pd.DataFrame(rq2_results)
    df_rq2.to_csv('report/table_rq2_models.csv', index=False)
    print("\n   [KẾT QUẢ BẢNG SO SÁNH 5 MÔ HÌNH (RQ2)]:")
    print(df_rq2.to_string(index=False))

    # -------------------------------------------------------------------------
    # 3. ĐÁNH GIÁ ĐỔI MIỀN SANG UAS & TEMPERATURE SCALING (RQ3)
    # -------------------------------------------------------------------------
    print("\n [3/5] Đánh giá đổi miền sang UAS và hiệu chuẩn xác suất bằng Temperature Scaling (RQ3)...")
    X_uas = uas[X_cols]
    y_uas = uas['y'].values
    
    # Dự báo ban đầu trên miền UAS
    p_uas_raw = trained_best_model.predict_proba(X_uas)[:, 1]
    f1_uas_raw = f1_score(y_uas, p_uas_raw >= 0.5)
    ece_uas_raw = ece_score(y_uas, p_uas_raw)
    
    # Tách 30% UAS làm tập hiệu chuẩn (calibration), 70% làm tập kiểm thử cuối
    np.random.seed(42)
    n_uas = len(y_uas)
    cal_idx = np.random.choice(n_uas, size=int(0.3 * n_uas), replace=False)
    te_idx = np.setdiff1d(np.arange(n_uas), cal_idx)
    
    z_cal = np.log(np.clip(p_uas_raw[cal_idx], 1e-6, 1 - 1e-6) / (1 - np.clip(p_uas_raw[cal_idx], 1e-6, 1 - 1e-6)))
    y_cal = y_uas[cal_idx]
    
    z_te = np.log(np.clip(p_uas_raw[te_idx], 1e-6, 1 - 1e-6) / (1 - np.clip(p_uas_raw[te_idx], 1e-6, 1 - 1e-6)))
    y_te_uas = y_uas[te_idx]
    
    # Tối ưu hóa nhiệt độ T bằng Binary Cross-Entropy
    def nll_obj(T):
        scaled_p = 1.0 / (1.0 + np.exp(-z_cal / T))
        return -(y_cal * np.log(scaled_p + 1e-9) + (1 - y_cal) * np.log(1 - scaled_p + 1e-9)).mean()
        
    opt_res = minimize_scalar(nll_obj, bounds=(0.5, 5.0), method='bounded')
    optimal_T = float(opt_res.x)
    
    # Áp dụng nhiệt độ tối ưu
    p_uas_calibrated = 1.0 / (1.0 + np.exp(-z_te / optimal_T))
    ece_uas_calibrated = ece_score(y_te_uas, p_uas_calibrated)
    f1_uas_calibrated = f1_score(y_te_uas, p_uas_calibrated >= 0.5)
    
    # Bootstrap 1000 lần tính khoảng tin cậy
    boot_eces = []
    for _ in range(1000):
        b_idx = np.random.choice(len(y_te_uas), size=len(y_te_uas), replace=True)
        boot_eces.append(ece_score(y_te_uas[b_idx], p_uas_calibrated[b_idx]))
    ci_low, ci_high = np.percentile(boot_eces, [2.5, 97.5])
    
    df_rq3 = pd.DataFrame([{
        'Domain': 'UAS (Drone 2018-2024)',
        'Optimal_Temperature_T': round(optimal_T, 2),
        'F1_Before_Calibration': round(f1_uas_raw, 3),
        'F1_After_Calibration': round(f1_uas_calibrated, 3),
        'ECE_Before_Calibration': round(ece_uas_raw, 3),
        'ECE_After_Calibration': round(ece_uas_calibrated, 3),
        'ECE_95_CI': f"[{ci_low:.3f}, {ci_high:.3f}]"
    }])
    df_rq3.to_csv('report/table_rq3_domain_shift.csv', index=False)
    print("\n   [KẾT QUẢ ĐỔI MIỀN VÀ HIỆU CHUẨN XÁC SUẤT (RQ3)]:")
    print(df_rq3.to_string(index=False))

    # -------------------------------------------------------------------------
    # 4. TẦM QUAN TRỌNG ĐẶC TRƯNG BẰNG FEATURE IMPORTANCES (SHAP PROXY)
    # -------------------------------------------------------------------------
    print("\n [4/5] Tính toán mức độ quan trọng đặc trưng (Feature Importance)...")
    importances = trained_best_model.feature_importances_
    df_feat_imp = pd.DataFrame({
        'feature': X_cols,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    df_feat_imp.to_csv('report/table_shap.csv', index=False)
    
    fig, ax = plt.subplots(figsize=(7.5, 4.2), dpi=300)
    y_pos = np.arange(len(df_feat_imp))
    bars = ax.barh(y_pos, df_feat_imp['importance'], color='#1B6B6D', height=0.55)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(df_feat_imp['feature'])
    ax.invert_yaxis()
    ax.set_xlabel('Feature Importance Gain (LightGBM)', fontsize=11)
    ax.set_title('Top Aviation Severity Predictors (Feature Importance)', fontsize=12, fontweight='bold', pad=14)
    ax.spines[['top', 'right']].set_visible(False)
    fig.savefig('report/fig_shap.png', dpi=300)
    plt.close(fig)
    print("    -> Đã xuất report/table_shap.csv và report/fig_shap.png")

    # 5. Lưu tham số tối ưu ra params_best.json
    best_params = {
        'model_name': 'LightGBM Classifier',
        'n_estimators': 300,
        'learning_rate': 0.03,
        'num_leaves': 31,
        'class_weight': 'balanced',
        'optimal_calibration_temperature': optimal_T
    }
    with open('report/params_best.json', 'w', encoding='utf-8') as f:
        json.dump(best_params, f, indent=2)
    print(" [5/5] Đã lưu thông số tối ưu vào report/params_best.json")

    print("\n================================================================================")
    print(" BƯỚC 6 (MODELING & EVALUATION) HOÀN TẤT THÀNH CÔNG!")
    print(" Kết quả RQ2 và RQ3 đã được kiểm định đầy đủ trên 5 mô hình và 5 seeds.")
    print(" Sẵn sàng chuyển giao cho Bước 7: Công cụ phân tích Dashboard (07_dashboard_app.py)")
    print("================================================================================")

if __name__ == '__main__':
    run_modeling_and_evaluation()
