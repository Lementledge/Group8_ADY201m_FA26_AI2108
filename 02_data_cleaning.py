"""
================================================================================
ADY201m - Step 2: Data Cleaning & UAS Segregation (Làm sạch & Tách nhãn)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Chuẩn hóa tên cột và kiểu dữ liệu.
  - Lọc phạm vi tai nạn hợp lệ (ev_type = 'ACC', ev_year từ 1990 đến 2024).
  - Tách cờ phương tiện không người lái is_uas (UAS / drone).
  - Xử lý nhãn tử vong y = (inj_tot_f > 0): quy đổi NULL thành 0 theo cẩm nang codman.pdf.
  - Xử lý missing values có căn cứ (UNK cho categorical, conditional median cho numerical).
  - Xuất bảng nhật ký làm sạch: report/table_cleaning_log.csv.
  - Lưu bảng dữ liệu sạch vào data/processed/clean_events.parquet.
================================================================================
"""

import os
import sys
import duckdb
import pandas as pd
import numpy as np

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def clean_data():
    db_path = 'data/processed/ntsb.duckdb'
    con = duckdb.connect(db_path)
    print(" [1/4] Kết nối cơ sở dữ liệu DuckDB:", db_path)
    
    cleaning_log = []
    
    # 1. Bảng events: Lọc loại tai nạn và năm
    n_raw_events = con.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    
    con.execute("""
        CREATE OR REPLACE TABLE clean_events AS
        SELECT 
            ev_id,
            ev_date,
            ev_year,
            ev_state,
            COALESCE(wx_cond_basic, 'UNK') AS wx,
            COALESCE(light_cond, 'UNK') AS light_cond,
            -- Áp dụng Human Delta: NULL ở inj_tot_f trong NTSB tương ứng với 0 thương vong
            COALESCE(inj_tot_f, 0) AS inj_tot_f,
            (COALESCE(inj_tot_f, 0) > 0)::INT AS y,
            COALESCE(on_ground_collision, 'N') AS on_ground_collision
        FROM events
        WHERE ev_year BETWEEN 1990 AND 2024 AND ev_type = 'ACC'
    """)
    n_clean_events = con.execute("SELECT COUNT(*) FROM clean_events").fetchone()[0]
    
    cleaning_log.append({
        'step': '1. Filter events',
        'table': 'events',
        'rows_before': n_raw_events,
        'rows_dropped': n_raw_events - n_clean_events,
        'reason': 'Chỉ giữ các vụ tai nạn chính thức (ev_type=ACC) trong giai đoạn 1990-2024',
        'rows_after': n_clean_events
    })
    print(f" [2/4] Đã làm sạch bảng events: {n_clean_events:,} dòng (loại {n_raw_events - n_clean_events} dòng)")

    # 2. Bảng aircraft: Gắn cờ is_uas và chuẩn hóa pha bay
    n_raw_ac = con.execute("SELECT COUNT(*) FROM aircraft").fetchone()[0]
    
    con.execute("""
        CREATE OR REPLACE TABLE clean_aircraft AS
        SELECT 
            Aircraft_Key,
            ev_id,
            acft_category,
            COALESCE(far_part, 'UNK') AS far_part,
            COALESCE(type_fly, 'UNK') AS type_fly,
            COALESCE(flt_phase, 'UNK') AS flt_phase,
            COALESCE(num_eng, 1) AS num_eng,
            -- Gắn cờ drone theo danh mục UAS hoặc hãng chế tạo drone
            (acft_category = 'UAS' OR far_part = '107')::INT AS is_uas
        FROM aircraft
        WHERE ev_id IN (SELECT ev_id FROM clean_events)
    """)
    n_clean_ac = con.execute("SELECT COUNT(*) FROM clean_aircraft").fetchone()[0]
    
    cleaning_log.append({
        'step': '2. Clean aircraft & flag UAS',
        'table': 'aircraft',
        'rows_before': n_raw_ac,
        'rows_dropped': n_raw_ac - n_clean_ac,
        'reason': 'Liên kết với clean_events, loại bỏ bản ghi máy bay không thuộc tai nạn phân tích',
        'rows_after': n_clean_ac
    })
    print(f"       Đã làm sạch bảng aircraft: {n_clean_ac:,} dòng")

    # 3. Bảng flight_crew: Nội suy median có điều kiện
    n_raw_crew = con.execute("SELECT COUNT(*) FROM flight_crew").fetchone()[0]
    
    con.execute("""
        CREATE OR REPLACE TABLE clean_crew AS
        WITH crew_filtered AS (
            SELECT 
                ev_id,
                -- Lọc tuổi hợp lý sinh học 16 - 90
                CASE WHEN crew_age BETWEEN 16 AND 90 THEN crew_age ELSE NULL END AS crew_age,
                -- Lọc giờ bay hợp lý < 50,000h
                CASE WHEN pilot_tot_hrs BETWEEN 0 AND 50000 THEN pilot_tot_hrs ELSE NULL END AS pilot_tot_hrs
            FROM flight_crew
            WHERE ev_id IN (SELECT ev_id FROM clean_events)
        ),
        medians AS (
            SELECT 
                MEDIAN(crew_age) AS med_age,
                MEDIAN(pilot_tot_hrs) AS med_hrs
            FROM crew_filtered
        )
        SELECT 
            c.ev_id,
            COALESCE(c.crew_age, m.med_age, 48) AS crew_age,
            COALESCE(c.pilot_tot_hrs, m.med_hrs, 1500) AS pilot_tot_hrs
        FROM crew_filtered c, medians m
    """)
    n_clean_crew = con.execute("SELECT COUNT(*) FROM clean_crew").fetchone()[0]
    
    cleaning_log.append({
        'step': '3. Clean crew & conditional median impute',
        'table': 'flight_crew',
        'rows_before': n_raw_crew,
        'rows_dropped': n_raw_crew - n_clean_crew,
        'reason': 'Lọc giá trị phi lý (age <16 or >90, hours >50k) và điền khuyết bằng median',
        'rows_after': n_clean_crew
    })
    print(f"       Đã làm sạch bảng flight_crew: {n_clean_crew:,} dòng")

    # 4. Xuất nhật ký làm sạch và lưu file parquet
    df_log = pd.DataFrame(cleaning_log)
    df_log.to_csv('report/table_cleaning_log.csv', index=False)
    print(" [3/4] Đã xuất nhật ký làm sạch ra report/table_cleaning_log.csv")
    
    con.execute("COPY clean_events TO 'data/processed/clean_events.parquet' (FORMAT PARQUET)")
    print(" [4/4] Đã lưu bảng clean_events ra data/processed/clean_events.parquet")
    
    # Báo cáo tỷ lệ khớp (Match Rate)
    manned_count = con.execute("SELECT COUNT(DISTINCT ev_id) FROM clean_aircraft WHERE is_uas = 0").fetchone()[0]
    uas_count = con.execute("SELECT COUNT(DISTINCT ev_id) FROM clean_aircraft WHERE is_uas = 1").fetchone()[0]
    print(f"\n   • Manned Aviation events: {manned_count:,}")
    print(f"   • UAS (Drone) events: {uas_count:,}")
    
    con.close()
    print("\n================================================================================")
    print(" BƯỚC 2 (DATA CLEANING) HOÀN TẤT THÀNH CÔNG!")
    print(" Sẵn sàng bàn giao dữ liệu cho Bước 3: Phân tích bằng SQL (03_sql_analysis.py)")
    print("================================================================================")

if __name__ == '__main__':
    clean_data()
