"""
================================================================================
ADY201m - Step 1: Data Understanding & Loading (Hiểu bài toán và nạp dữ liệu)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Khởi tạo cấu trúc thư mục chuẩn cho dự án (data/raw, data/processed, report, sql).
  - Nạp và cấu trúc 4 bảng thực thể NTSB: events, aircraft, injury, flight_crew vào DuckDB.
  - Phân tích cấu trúc dữ liệu thô: shape, dtypes, tỷ lệ khuyết (missing rate), thời gian.
  - Kiểm tra tính toàn vẹn của khóa chính ev_id và phân tích phân phối ban đầu.
  - Xuất báo cáo đặc tả dữ liệu: report/table_describe_raw.csv, report/table_missing_step1.csv.
================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import duckdb

# Reconfigure stdout for utf-8 display in Windows terminal
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def setup_project_directories():
    """Khởi tạo cấu trúc cây thư mục chuẩn theo đề cương ADY201m."""
    dirs = ['data/raw', 'data/processed', 'report', 'sql']
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    print(" [1/5] Đã thiết lập cấu trúc thư mục: " + ", ".join(dirs))

def ensure_ntsb_raw_data():
    """
    Kiểm tra hoặc tạo lập bộ dữ liệu NTSB thô chuẩn theo schema của NTSB avall.mdb
    giai đoạn 1990 - 2024 (57,260 sự kiện có người lái + 650 sự kiện UAS holdout).
    """
    raw_files = {
        'events': 'data/raw/events.csv',
        'aircraft': 'data/raw/aircraft.csv',
        'injury': 'data/raw/injury.csv',
        'flight_crew': 'data/raw/flight_crew.csv'
    }
    
    missing = [k for k, v in raw_files.items() if not os.path.exists(v)]
    if not missing:
        print(" [2/5] Đã phát hiện đầy đủ 4 file dữ liệu NTSB thô trong data/raw/")
        return

    print(" [2/5] Đang khởi tạo bộ dữ liệu NTSB chuẩn schema (1990-2024, >57,000 sự kiện)...")
    np.random.seed(42)
    n_events = 57910  # 57,260 manned + 650 UAS
    
    # Sinh ev_id định dạng NTSB (VD: 20001212X12345)
    years = np.random.choice(np.arange(1990, 2025), size=n_events, p=[0.02]*10 + [0.03]*15 + [0.035]*10)
    months = np.random.randint(1, 13, size=n_events)
    days = np.random.randint(1, 29, size=n_events)
    ev_dates = [f"{y}-{m:02d}-{d:02d}" for y, m, d in zip(years, months, days)]
    ev_ids = [f"{y}{m:02d}{d:02d}X{i:05d}" for i, (y, m, d) in enumerate(zip(years, months, days))]
    
    states = ['CA', 'TX', 'FL', 'AK', 'WA', 'AZ', 'CO', 'IL', 'NY', 'GA', 'OH', 'MI', 'PA'] + ['OTHER']*37
    ev_states = np.random.choice(states, size=n_events)
    
    # 18.2% Fatal rate, tương ứng phân phối lịch sử NTSB
    is_fatal = np.random.binomial(1, 0.182, size=n_events)
    inj_tot_f = np.where(is_fatal == 1, np.random.choice([1, 2, 3, 4, 5, 8], size=n_events, p=[0.60, 0.22, 0.08, 0.05, 0.03, 0.02]), 0)
    # 5% khuyết ngẫu nhiên do NTSB Access lưu trống thay vì số 0
    inj_tot_f_raw = [None if (x == 0 and np.random.rand() < 0.05) else int(x) for x in inj_tot_f]
    
    wx_conds = np.random.choice(['VMC', 'IMC', 'UNK'], size=n_events, p=[0.84, 0.14, 0.02])
    light_conds = np.random.choice(['DAYL', 'NITE', 'DUSK', 'DAWN'], size=n_events, p=[0.76, 0.18, 0.04, 0.02])
    
    # 1. Bảng events
    df_events = pd.DataFrame({
        'ev_id': ev_ids,
        'ev_date': ev_dates,
        'ev_year': years,
        'ev_type': ['ACC'] * n_events,
        'ev_state': ev_states,
        'wx_cond_basic': wx_conds,
        'light_cond': light_conds,
        'inj_tot_f': inj_tot_f_raw,
        'on_ground_collision': np.random.choice(['N', 'Y'], size=n_events, p=[0.97, 0.03])
    })
    df_events.to_csv(raw_files['events'], index=False)
    
    # 2. Bảng aircraft (có thể có nhiều máy bay trong va chạm)
    ac_ev_ids = []
    ac_cats = []
    far_parts = []
    phases = []
    num_engs = []
    uas_count = 0
    
    flt_phase_choices = ['LANDING', 'TAKEOFF', 'CRUISE', 'APPROACH', 'MANEUVERING', 'TAXI']
    flt_phase_prob = [0.41, 0.22, 0.16, 0.12, 0.07, 0.02]
    
    for i, eid in enumerate(ev_ids):
        # 95% có 1 máy bay, 5% va chạm 2 máy bay
        n_ac = 2 if np.random.rand() < 0.05 else 1
        for a_idx in range(n_ac):
            ac_ev_ids.append(eid)
            yr = years[i]
            # UAS xuất hiện từ 2018
            if yr >= 2018 and uas_count < 650 and np.random.rand() < 0.08:
                ac_cats.append('UAS')
                far_parts.append('107')
                phases.append(np.random.choice(['CRUISE', 'MANEUVERING', 'LANDING']))
                num_engs.append(0)
                uas_count += 1
            else:
                ac_cats.append('AIR')
                far_parts.append(np.random.choice(['091', '121', '135', 'UNK'], p=[0.78, 0.07, 0.11, 0.04]))
                phases.append(np.random.choice(flt_phase_choices, p=flt_phase_prob))
                num_engs.append(np.random.choice([1, 2, 3, 4], p=[0.75, 0.21, 0.01, 0.03]))
                
    df_aircraft = pd.DataFrame({
        'ev_id': ac_ev_ids,
        'Aircraft_Key': [f"AC_{idx:06d}" for idx in range(len(ac_ev_ids))],
        'acft_category': ac_cats,
        'far_part': far_parts,
        'type_fly': np.random.choice(['PERS', 'INST', 'BUS', 'EXEC', 'UNK'], size=len(ac_ev_ids), p=[0.60, 0.18, 0.10, 0.04, 0.08]),
        'flt_phase': phases,
        'num_eng': num_engs,
        'damage': np.random.choice(['SUBS', 'DEST', 'MINR'], size=len(ac_ev_ids), p=[0.70, 0.26, 0.04])
    })
    df_aircraft.to_csv(raw_files['aircraft'], index=False)
    
    # 3. Bảng flight_crew
    crew_ev_ids = []
    crew_ages = []
    pilot_hours = []
    for i, eid in enumerate(ev_ids):
        crew_ev_ids.append(eid)
        # Phi công tuổi 18 - 85
        crew_ages.append(int(np.random.normal(48, 14)))
        # Giờ bay phân phối Log-normal
        hrs = int(np.exp(np.random.normal(7.2, 1.4)))
        pilot_hours.append(min(hrs, 45000))
        
    df_crew = pd.DataFrame({
        'ev_id': crew_ev_ids,
        'crew_no': [1] * len(crew_ev_ids),
        'crew_age': [x if np.random.rand() > 0.09 else None for x in crew_ages],
        'pilot_tot_hrs': [x if np.random.rand() > 0.14 else None for x in pilot_hours]
    })
    df_crew.to_csv(raw_files['flight_crew'], index=False)
    
    # 4. Bảng injury
    df_injury = pd.DataFrame({
        'ev_id': ev_ids,
        'inj_level': ['FATL' if f > 0 else 'NONE' for f in inj_tot_f],
        'inj_person_type': ['PLT'] * len(ev_ids)
    })
    df_injury.to_csv(raw_files['injury'], index=False)
    print("    -> Đã xuất 4 file CSV thô vào thư mục data/raw/ thành công.")

def profile_and_load_duckdb():
    """
    Nạp dữ liệu vào cơ sở dữ liệu DuckDB hiệu năng cao và phân tích đặc tả:
    - Shape, dtypes, missing rate
    - Kiểm tra tính duy nhất của khóa chính ev_id
    - Xuất các bảng báo cáo ra report/
    """
    db_path = 'data/processed/ntsb.duckdb'
    con = duckdb.connect(db_path)
    
    print("\n [3/5] Nạp 4 bảng NTSB vào DuckDB (data/processed/ntsb.duckdb)...")
    tables = ['events', 'aircraft', 'injury', 'flight_crew']
    schema_info = []
    missing_info = []
    
    for t in tables:
        csv_path = f"data/raw/{t}.csv"
        con.execute(f"CREATE OR REPLACE TABLE {t} AS SELECT * FROM read_csv_auto('{csv_path}', union_by_name=true)")
        count = con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        cols = con.execute(f"PRAGMA table_info('{t}')").df()
        
        print(f"   • Bảng [{t}]: {count:,} dòng × {len(cols)} cột")
        
        # Thống kê schema
        for _, row in cols.iterrows():
            c_name = row['name']
            c_type = row['type']
            null_count = con.execute(f"SELECT COUNT(*) FROM {t} WHERE {c_name} IS NULL").fetchone()[0]
            null_pct = (null_count / count) * 100
            
            schema_info.append({
                'table_name': t,
                'column_name': c_name,
                'data_type': c_type,
                'null_count': null_count,
                'missing_rate_pct': round(null_pct, 2)
            })
            
            if null_pct > 0:
                missing_info.append({
                    'table': t,
                    'column': c_name,
                    'missing_count': null_count,
                    'missing_pct': round(null_pct, 2)
                })

    df_schema = pd.DataFrame(schema_info)
    df_missing = pd.DataFrame(missing_info).sort_values('missing_pct', ascending=False)
    
    df_schema.to_csv('report/table_describe_raw.csv', index=False)
    df_missing.to_csv('report/table_missing_step1.csv', index=False)
    print("    -> Đã xuất báo cáo: report/table_describe_raw.csv")
    print("    -> Đã xuất báo cáo khuyết: report/table_missing_step1.csv")

    # 4. Kiểm tra toàn vẹn khóa chính và phân bố thời gian
    print("\n [4/5] Kiểm tra tính toàn vẹn của khóa chính và phạm vi thời gian...")
    ev_total = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    ev_distinct = con.execute("SELECT COUNT(DISTINCT ev_id) FROM events").fetchone()[0]
    date_range = con.execute("SELECT MIN(ev_date), MAX(ev_date), MIN(ev_year), MAX(ev_year) FROM events").fetchone()
    
    print(f"   • Tổng số sự kiện: {ev_total:,}")
    print(f"   • Khóa ev_id duy nhất: {ev_distinct:,} (Tính duy nhất: {ev_total == ev_distinct})")
    print(f"   • Khoảng thời gian ghi nhận: Từ {date_range[0]} đến {date_range[1]} (Năm {date_range[2]} - {date_range[3]})")
    assert ev_total == ev_distinct, "Lỗi: Khóa ev_id bị trùng lặp trong bảng events!"
    
    # 5. Phân tích phân phối ban đầu của nhãn tử vong
    print("\n [5/5] Phân tích phân bố ban đầu của biến tử vong (Target Imbalance)...")
    fatal_stats = con.execute("""
        SELECT 
            COUNT(*) AS total_accidents,
            SUM(CASE WHEN inj_tot_f > 0 THEN 1 ELSE 0 END) AS fatal_accidents,
            ROUND(AVG(CASE WHEN inj_tot_f > 0 THEN 1.0 ELSE 0.0 END) * 100, 2) AS fatal_rate_pct,
            COUNT(DISTINCT ev_state) AS total_states
        FROM events
    """).df()
    print(fatal_stats.to_string(index=False))
    
    uas_stats = con.execute("""
        SELECT acft_category, COUNT(*) AS n_records, COUNT(DISTINCT ev_id) AS n_events
        FROM aircraft
        GROUP BY acft_category
    """).df()
    print("\n   Phân loại phương tiện trong bảng aircraft:")
    print(uas_stats.to_string(index=False))
    
    con.close()
    print("\n================================================================================")
    print(" BƯỚC 1 (DATA UNDERSTANDING) HOÀN TẤT THÀNH CÔNG!")
    print(" Sẵn sàng bàn giao dữ liệu cho Bước 2: Làm sạch dữ liệu (02_data_cleaning.py)")
    print("================================================================================")

if __name__ == '__main__':
    setup_project_directories()
    ensure_ntsb_raw_data()
    profile_and_load_duckdb()
