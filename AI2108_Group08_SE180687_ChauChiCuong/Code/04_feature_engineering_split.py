"""
================================================================================
ADY201m - Step 4: Feature Engineering & Temporal Split (Đặc trưng & Chia tập)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Nạp bảng feat từ DuckDB và hoàn thiện kỹ thuật đặc trưng (Feature Engineering).
  - Mã hóa biến phân loại (Categorical Dtypes / Label Encoding cho cây, One-Hot cho tuyến tính).
  - Phân chia dữ liệu theo thời gian (Temporal Split) tránh rò rỉ tương lai (Data Leakage):
      * Tập Train (Manned Aviation): 1990 - 2018 (huấn luyện 5 mô hình)
      * Tập Test (Manned Aviation): 2019 - 2024 (đánh giá kiểm thử RQ2)
      * Tập UAS Holdout: 2018 - 2024 (kiểm thử đổi miền RQ3)
  - Cài đặt hàm tính Expected Calibration Error (ECE) theo Guo et al. (2017).
  - Xuất bảng mô tả đặc trưng: report/table_features.csv.
  - Tạo tệp tin bàn giao duy nhất: data/processed/feat.parquet và manifest.json
    đảm bảo việc cộng tác độc lập giữa Sinh viên A và Sinh viên B theo đề cương.
================================================================================
"""

import os
import sys
import json
import hashlib
import duckdb
import numpy as np
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def ece_score(y_true, y_prob, bins=10):
    """
    Tính Expected Calibration Error (ECE) chia 10 bin xác suất
    theo Guo et al. (ICML 2017).
    """
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

def run_feature_engineering_and_split():
    db_path = 'data/processed/ntsb.duckdb'
    con = duckdb.connect(db_path)
    print(" [1/5] Nạp bảng feat từ DuckDB...")
    
    df = con.execute("SELECT * FROM feat").df()
    con.close()
    
    # 1. Danh sách đặc trưng độc lập và biến mục tiêu
    cat_cols = ['ev_state', 'wx', 'light_cond', 'far_part', 'type_fly', 'flt_phase']
    num_cols = ['num_eng', 'n_aircraft', 'age_max', 'hours_max']
    X_cols = cat_cols + num_cols
    
    print(f"       Tổng số bản ghi ban đầu: {len(df):,} dòng × {len(df.columns)} cột")
    print(f"       Đặc trưng độc lập ({len(X_cols)}): {X_cols}")
    
    # Chuẩn hóa kiểu category
    for c in cat_cols:
        df[c] = df[c].astype(str).fillna('UNK').astype('category')
    for c in num_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(df[c].median())
        
    df['y'] = df['y'].astype(int)
    df['is_uas'] = df['is_uas'].astype(int)
    
    # 2. Phân chia tập dữ liệu: Manned train, Manned test, UAS test
    print("\n [2/5] Phân chia dữ liệu theo thời gian (Temporal Split) & miền (UAS Holdout)...")
    manned_mask = (df['is_uas'] == 0)
    uas_mask = (df['is_uas'] == 1)
    
    train_df = df[manned_mask & (df['ev_year'] <= 2018)].copy()
    test_df = df[manned_mask & (df['ev_year'] >= 2019)].copy()
    uas_df = df[uas_mask].copy()
    
    print(f"   • Train set (Manned 1990-2018): {len(train_df):,} dòng (Tử vong: {train_df['y'].mean()*100:.2f}%)")
    print(f"   • Test set  (Manned 2019-2024): {len(test_df):,} dòng (Tử vong: {test_df['y'].mean()*100:.2f}%)")
    print(f"   • UAS set   (Drone 2018-2024) : {len(uas_df):,} dòng (Tử vong: {uas_df['y'].mean()*100:.2f}%)")
    
    # 3. Bộ kiểm thử bảo đảm tính toàn vẹn (Test Cases & Assertions)
    print("\n [3/5] Thực thi các kiểm thử kiểm soát rò rỉ dữ liệu (No Target Leakage)...")
    assert 'y' not in X_cols, "Lỗi nghiêm trọng: Cột mục tiêu y nằm trong tập đặc trưng X!"
    assert train_df['ev_year'].max() <= 2018, "Lỗi: Tập train chứa dữ liệu sau năm 2018!"
    assert test_df['ev_year'].min() >= 2019, "Lỗi: Tập test chứa dữ liệu trước năm 2019!"
    assert len(train_df) > 30000, "Lỗi: Số lượng dòng tập train không đủ lớn cho 5 mô hình!"
    assert not train_df[X_cols].isnull().any().any(), "Lỗi: Tập train vẫn còn giá trị NULL!"
    print("    -> Tất cả 5 kiểm thử bảo đảm (Assertions) đã vượt qua thành công!")
    
    # 4. Xuất bảng mô tả đặc trưng
    feat_desc = []
    for c in X_cols:
        feat_desc.append({
            'feature_name': c,
            'feature_type': 'Categorical' if c in cat_cols else 'Numerical',
            'source_table': 'events' if c in ['ev_state', 'wx', 'light_cond'] else ('crew' if 'max' in c else 'aircraft'),
            'n_unique': df[c].nunique(),
            'missing_rate': 0.0,
            'role_in_rq': 'RQ1 & RQ2'
        })
    df_feat_desc = pd.DataFrame(feat_desc)
    df_feat_desc.to_csv('report/table_features.csv', index=False)
    print(" [4/5] Đã xuất bảng đặc trưng ra report/table_features.csv")

    # 5. Lưu trữ tập tin bàn giao feat.parquet & manifest.json
    parquet_path = 'data/processed/feat.parquet'
    df.to_parquet(parquet_path, index=False)
    
    # Tính mã băm SHA256 để đối soát bàn giao
    hasher = hashlib.sha256()
    with open(parquet_path, 'rb') as f:
        hasher.update(f.read())
    sha256_hash = hasher.hexdigest()
    
    manifest = {
        'dataset_name': 'NTSB Clean Aviation & UAS Feature Dataset',
        'file_name': 'feat.parquet',
        'sha256': sha256_hash,
        'total_rows': len(df),
        'total_columns': len(df.columns),
        'features': X_cols,
        'target': 'y',
        'temporal_split': {
            'train_manned_years': '1990-2018',
            'train_manned_count': len(train_df),
            'test_manned_years': '2019-2024',
            'test_manned_count': len(test_df),
            'uas_holdout_years': '2018-2024',
            'uas_holdout_count': len(uas_df)
        }
    }
    
    with open('manifest.json', 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)
    print(" [5/5] Đã xuất tệp bàn giao manifest.json và data/processed/feat.parquet thành công.")

    print("\n================================================================================")
    print(" BƯỚC 4 (FEATURE ENGINEERING & SPLIT) HOÀN TẤT THÀNH CÔNG!")
    print(" Sẵn sàng bàn giao cho Bước 5: Trực quan hóa (05_visualization.py)")
    print(" và Bước 6: Mô hình hóa & Đánh giá (06_modeling_evaluation.py)")
    print("================================================================================")

if __name__ == '__main__':
    run_feature_engineering_and_split()
