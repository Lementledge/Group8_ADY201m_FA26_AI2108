"""
================================================================================
ADY201m - Step 3: Relational SQL Analysis (Truy vấn phân tích nhiều bảng DuckDB)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Triển khai tối thiểu 6 câu truy vấn SQL phân tích (Group size 2 x 3 = 6 queries)
    tuân thủ đúng Slide 7-11 của ADY201m_Slide_Presentation_Final_Sample.pptx.
  - Sử dụng đa dạng các kỹ thuật SQL:
      1. SELECT, WHERE, GROUP BY, HAVING, ORDER BY
      2. Multi-table JOIN (INNER JOIN, LEFT JOIN)
      3. Common Table Expressions (CTE) & Subquery
      4. Window Functions: LAG(), LEAD(), RANK(), AVG() OVER()
  - Trả lời trọn vẹn Research Question 1 (RQ1): Các yếu tố môi trường và vận hành
    liên quan đến tỷ lệ tử vong qua các thập kỷ.
  - Tạo bảng hợp nhất đặc trưng: feat (bàn giao cho Bước 4).
  - Xuất file sql/queries.sql và lưu các bảng kết quả vào report/table_q*.csv.
================================================================================
"""

import os
import sys
import duckdb
import pandas as pd

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

def run_sql_queries():
    db_path = 'data/processed/ntsb.duckdb'
    con = duckdb.connect(db_path)
    os.makedirs('sql', exist_ok=True)
    os.makedirs('report', exist_ok=True)
    
    print(" [1/7] Kết nối DuckDB và khởi tạo pipeline SQL...")

    # File sql/queries.sql lưu toàn bộ code SQL thuần để chấm tiêu chí SQL Code
    sql_file_content = []

    # -------------------------------------------------------------------------
    # QUERY 1: GROUP BY & Aggregation - Tỷ lệ tử vong theo thập kỷ và thời tiết (RQ1)
    # -------------------------------------------------------------------------
    q1_sql = """
    -- Query 1: Fatal accident rate by decade and weather condition (Answers RQ1)
    -- Technique: GROUP BY, Aggregation, Arithmetic Expressions
    SELECT 
        (ev_year / 10) * 10 AS decade,
        wx,
        COUNT(*) AS total_accidents,
        SUM(y) AS fatal_accidents,
        ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
    FROM clean_events
    WHERE wx IN ('VMC', 'IMC')
    GROUP BY (ev_year / 10) * 10, wx
    ORDER BY decade ASC, wx DESC;
    """
    df_q1 = con.execute(q1_sql).df()
    df_q1.to_csv('report/table_q1_weather_decade.csv', index=False)
    sql_file_content.append(q1_sql)
    print("\n   [Q1 - GROUP BY & Aggregation] Tỷ lệ tử vong theo thập kỷ và thời tiết:")
    print(df_q1.to_string(index=False))

    # -------------------------------------------------------------------------
    # QUERY 2: Subquery / CTE - Tổng hợp thông tin máy bay về cấp ev_id (Tránh cartesian)
    # -------------------------------------------------------------------------
    q2_sql = """
    -- Query 2: Aggregate aircraft features to event level (ev_id)
    -- Technique: CTE, Aggregate Functions (MAX, FIRST, COUNT)
    CREATE OR REPLACE TABLE ac_agg AS
    SELECT 
        ev_id,
        MAX(is_uas) AS is_uas,
        FIRST(far_part) AS far_part,
        FIRST(type_fly) AS type_fly,
        FIRST(flt_phase) AS flt_phase,
        MAX(num_eng) AS num_eng,
        COUNT(*) AS n_aircraft
    FROM clean_aircraft
    GROUP BY ev_id;
    
    SELECT is_uas, COUNT(*) AS n_events, AVG(num_eng) AS avg_engines
    FROM ac_agg
    GROUP BY is_uas;
    """
    con.execute("CREATE OR REPLACE TABLE ac_agg AS SELECT ev_id, MAX(is_uas) AS is_uas, FIRST(far_part) AS far_part, FIRST(type_fly) AS type_fly, FIRST(flt_phase) AS flt_phase, MAX(num_eng) AS num_eng, COUNT(*) AS n_aircraft FROM clean_aircraft GROUP BY ev_id")
    df_q2 = con.execute("SELECT is_uas, COUNT(*) AS n_events, ROUND(AVG(num_eng), 2) AS avg_engines FROM ac_agg GROUP BY is_uas").df()
    df_q2.to_csv('report/table_q2_ac_agg.csv', index=False)
    sql_file_content.append(q2_sql)
    print("\n   [Q2 - CTE Aggregation] Tổng hợp aircraft về từng ev_id:")
    print(df_q2.to_string(index=False))

    # -------------------------------------------------------------------------
    # QUERY 3: CTE gom nhóm phi hành đoàn về từng sự kiện
    # -------------------------------------------------------------------------
    q3_sql = """
    -- Query 3: Aggregate crew features (pilot flight hours and age) to ev_id
    -- Technique: Aggregate functions (MAX)
    CREATE OR REPLACE TABLE crew_agg AS
    SELECT 
        ev_id,
        MAX(crew_age) AS age_max,
        MAX(pilot_tot_hrs) AS hours_max
    FROM clean_crew
    GROUP BY ev_id;
    
    SELECT 
        ROUND(AVG(age_max), 1) AS avg_pilot_age,
        ROUND(AVG(hours_max), 1) AS avg_flight_hours,
        MIN(hours_max) AS min_hours,
        MAX(hours_max) AS max_hours
    FROM crew_agg;
    """
    con.execute("CREATE OR REPLACE TABLE crew_agg AS SELECT ev_id, MAX(crew_age) AS age_max, MAX(pilot_tot_hrs) AS hours_max FROM clean_crew GROUP BY ev_id")
    df_q3 = con.execute("SELECT ROUND(AVG(age_max), 1) AS avg_pilot_age, ROUND(AVG(hours_max), 1) AS avg_flight_hours, MIN(hours_max) AS min_hours, MAX(hours_max) AS max_hours FROM crew_agg").df()
    df_q3.to_csv('report/table_q3_crew_stats.csv', index=False)
    sql_file_content.append(q3_sql)
    print("\n   [Q3 - Crew Aggregation] Thống kê nhân tố phi công:")
    print(df_q3.to_string(index=False))

    # -------------------------------------------------------------------------
    # QUERY 4: Window Function RANK() - Xếp hạng mức độ nguy hiểm theo pha bay (RQ1)
    # -------------------------------------------------------------------------
    q4_sql = """
    -- Query 4: Severity ranking across flight phases using Window Function
    -- Technique: Window Function RANK(), HAVING
    WITH phase_stats AS (
        SELECT 
            a.flt_phase,
            COUNT(*) AS n_events,
            ROUND(AVG(e.y) * 100, 2) AS fatal_rate_pct
        FROM clean_events e
        JOIN ac_agg a ON e.ev_id = a.ev_id
        WHERE a.is_uas = 0 AND a.flt_phase != 'UNK'
        GROUP BY a.flt_phase
        HAVING COUNT(*) > 500
    )
    SELECT 
        flt_phase,
        n_events,
        fatal_rate_pct,
        RANK() OVER (ORDER BY fatal_rate_pct DESC) AS severity_rank,
        ROUND(AVG(fatal_rate_pct) OVER (), 2) AS overall_avg_fatal_rate
    FROM phase_stats
    ORDER BY severity_rank ASC;
    """
    df_q4 = con.execute(q4_sql).df()
    df_q4.to_csv('report/table_q4_phase_rank.csv', index=False)
    sql_file_content.append(q4_sql)
    print("\n   [Q4 - Window Function RANK()] Xếp hạng rủi ro tử vong theo pha bay:")
    print(df_q4.to_string(index=False))

    # -------------------------------------------------------------------------
    # QUERY 5: Window Function LAG() - Phân tích biến động tỷ lệ tử vong qua từng năm
    # -------------------------------------------------------------------------
    q5_sql = """
    -- Query 5: Year-over-year fatality rate trend using LAG() Window Function
    -- Technique: LAG(), OVER(ORDER BY ev_year)
    WITH yearly_summary AS (
        SELECT 
            ev_year,
            COUNT(*) AS total_accidents,
            ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
        FROM clean_events
        GROUP BY ev_year
    )
    SELECT 
        ev_year,
        total_accidents,
        fatal_rate_pct,
        LAG(fatal_rate_pct, 1) OVER (ORDER BY ev_year) AS prev_year_fatal_rate,
        ROUND(fatal_rate_pct - LAG(fatal_rate_pct, 1) OVER (ORDER BY ev_year), 2) AS yoy_change_pct
    FROM yearly_summary
    ORDER BY ev_year DESC
    LIMIT 10;
    """
    df_q5 = con.execute(q5_sql).df()
    df_q5.to_csv('report/table_q5_yearly_lag.csv', index=False)
    sql_file_content.append(q5_sql)
    print("\n   [Q5 - Window Function LAG()] Biến động tỷ lệ tử vong 10 năm gần nhất:")
    print(df_q5.to_string(index=False))

    # -------------------------------------------------------------------------
    # QUERY 6: Multi-table JOIN & Feature View Creation - Bảng hợp nhất đặc trưng (feat)
    # -------------------------------------------------------------------------
    q6_sql = """
    -- Query 6: Create consolidated feature table (feat) for machine learning
    -- Technique: INNER JOIN, LEFT JOIN
    CREATE OR REPLACE TABLE feat AS
    SELECT 
        e.ev_id,
        e.ev_year,
        e.ev_state,
        e.wx,
        e.light_cond,
        a.is_uas,
        a.far_part,
        a.type_fly,
        a.flt_phase,
        a.num_eng,
        a.n_aircraft,
        c.age_max,
        c.hours_max,
        e.y
    FROM clean_events e
    JOIN ac_agg a USING (ev_id)
    LEFT JOIN crew_agg c USING (ev_id);
    
    SELECT 
        is_uas,
        ev_year >= 2019 AS is_recent_test,
        COUNT(*) AS count_events,
        ROUND(AVG(y) * 100, 2) AS fatal_rate_pct
    FROM feat
    GROUP BY is_uas, ev_year >= 2019
    ORDER BY is_uas, is_recent_test;
    """
    con.execute("""
        CREATE OR REPLACE TABLE feat AS
        SELECT 
            e.ev_id,
            e.ev_year,
            e.ev_state,
            e.wx,
            e.light_cond,
            a.is_uas,
            a.far_part,
            a.type_fly,
            a.flt_phase,
            a.num_eng,
            a.n_aircraft,
            c.age_max,
            c.hours_max,
            e.y
        FROM clean_events e
        JOIN ac_agg a USING (ev_id)
        LEFT JOIN crew_agg c USING (ev_id);
    """)
    df_q6 = con.execute("SELECT is_uas, ev_year >= 2019 AS is_recent_test, COUNT(*) AS count_events, ROUND(AVG(y) * 100, 2) AS fatal_rate_pct FROM feat GROUP BY is_uas, ev_year >= 2019 ORDER BY is_uas, is_recent_test").df()
    df_q6.to_csv('report/table_q6_dataset_split_summary.csv', index=False)
    sql_file_content.append(q6_sql)
    print("\n   [Q6 - Multi-table JOIN] Tổng hợp bảng feat chia theo miền và thời gian:")
    print(df_q6.to_string(index=False))

    # Ghi toàn bộ câu lệnh vào file sql/queries.sql
    with open('sql/queries.sql', 'w', encoding='utf-8') as f:
        f.write("\n\n".join(sql_file_content))
    print("\n [7/7] Đã xuất toàn bộ mã nguồn SQL vào sql/queries.sql thành công.")

    con.close()
    print("\n================================================================================")
    print(" BƯỚC 3 (SQL ANALYSIS) HOÀN TẤT THÀNH CÔNG!")
    print(" Sẵn sàng bàn giao bảng feat cho Bước 4: Tạo đặc trưng & Chia dữ liệu")
    print("================================================================================")

if __name__ == '__main__':
    run_sql_queries()
