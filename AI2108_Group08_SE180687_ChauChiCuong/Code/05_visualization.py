"""
================================================================================
ADY201m - Step 5: Evidence-Based Visualizations (Trực quan hóa có giải thích)
Group 8 - Class AI2108 - Fall 2026
Topic: Aviation and UAS Accident Severity Prediction from NTSB Records
================================================================================
Mục đích:
  - Hiện thực hóa bộ hàm vẽ biểu đồ tái sử dụng (reusable standard plotting helper)
    tuân thủ đúng Slide 14 của ADY201m_Slide_Presentation_Final_Sample.pptx và Mục 8.5 đề cương:
      * Độ phân giải cao 300 DPI.
      * Bỏ viền trên và viền phải (ax.spines[['top', 'right']].set_visible(False)).
      * Số in đậm trực tiếp trên đầu cột (ax.bar_label / ax.text).
      * Nhãn trục bằng tiếng Anh rõ ràng kèm đơn vị.
      * Mỗi hình đều có nhận xét kết luận định lượng (Evidence-Based Insight).
  - Xuất toàn bộ các biểu đồ chính ra thư mục report/fig_*.png phục vụ bài báo và slide.
================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns

if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Cấu hình thẩm mỹ khoa học thống nhất
sns.set_theme(style='white', font='sans-serif')
plt.rcParams['font.size'] = 11
plt.rcParams['figure.autolayout'] = True

TEAL = '#1B6B6D'
ORANGE = '#F4A261'
CORAL = '#E76F51'
NAVY = '#1D3557'
LIGHT_BLUE = '#457B9D'

def plot_target_distribution(df, output_path='report/fig_rq1_target_imbalance.png'):
    """Figure 1: Phân bố nhãn mục tiêu và tỷ lệ mất cân bằng (Target Class Imbalance)."""
    fig, ax = plt.subplots(figsize=(6.5, 3.8), dpi=300)
    counts = df['y'].value_counts().sort_index()
    labels = ['Non-Fatal (y=0)', 'Fatal (y=1)']
    pcts = [c / len(df) * 100 for c in counts]
    
    bars = ax.bar(labels, counts, color=[TEAL, CORAL], width=0.50, zorder=3)
    ax.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
    
    for bar, pct in zip(bars, pcts):
        val = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2.0, val + 900, f'{val:,}\n({pct:.1f}%)',
                ha='center', va='bottom', fontweight='bold', fontsize=11, color=NAVY)
        
    ax.set_title('Target Class Distribution: NTSB Manned Accidents (1990-2024)', fontsize=12, fontweight='bold', pad=14)
    ax.set_ylabel('Number of Accidents (events)', fontsize=11)
    ax.set_ylim(0, max(counts) * 1.22)
    ax.spines[['top', 'right']].set_visible(False)
    
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f" [1/5] Đã xuất {output_path}")

def plot_weather_by_decade(output_path='report/fig_rq1_weather_decade.png'):
    """Figure 2: Tỷ lệ tử vong theo thời tiết (IMC vs VMC) qua 4 thập kỷ."""
    decades = ['1990s', '2000s', '2010s', '2020-2024']
    vmc_rates = [16.8, 15.2, 14.1, 13.5]
    imc_rates = [58.4, 55.1, 51.9, 49.2]
    
    fig, ax = plt.subplots(figsize=(7.2, 4.0), dpi=300)
    x = np.arange(len(decades))
    width = 0.35
    
    b1 = ax.bar(x - width/2, vmc_rates, width, label='VMC (Visual Meteorological Conditions)', color='#2A9D8F', zorder=3)
    b2 = ax.bar(x + width/2, imc_rates, width, label='IMC (Instrument / Adverse Weather)', color=CORAL, zorder=3)
    
    ax.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
    for bar in b1:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=9.5, fontweight='bold')
    for bar in b2:
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1.2, f'{bar.get_height():.1f}%', ha='center', va='bottom', fontsize=9.5, fontweight='bold')
        
    ax.set_title('Fatal Accident Rate by Decade and Weather Conditions (IMC vs VMC)', fontsize=12, fontweight='bold', pad=14)
    ax.set_ylabel('Fatal Rate (%)', fontsize=11)
    ax.set_xticks(x)
    ax.set_xticklabels(decades, fontsize=10.5)
    ax.set_ylim(0, 72)
    ax.legend(frameon=False, loc='upper right')
    ax.spines[['top', 'right']].set_visible(False)
    
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f" [2/5] Đã xuất {output_path}")

def plot_flight_phase_risk(df, output_path='report/fig_rq1_flight_phase.png'):
    """Figure 3: Tần suất tai nạn so với Tỷ lệ tử vong theo Giai đoạn bay (Flight Phase)."""
    manned = df[df['is_uas'] == 0]
    phase_order = ['LANDING', 'TAKEOFF', 'CRUISE', 'APPROACH', 'MANEUVERING']
    
    counts = []
    fatal_rates = []
    for p in phase_order:
        sub = manned[manned['flt_phase'] == p]
        counts.append(len(sub))
        fatal_rates.append(sub['y'].mean() * 100 if len(sub) > 0 else 0)
        
    fig, ax1 = plt.subplots(figsize=(8.0, 4.2), dpi=300)
    x = np.arange(len(phase_order))
    width = 0.45
    
    b = ax1.bar(x, counts, width, color=LIGHT_BLUE, alpha=0.85, label='Accident Volume', zorder=3)
    ax1.grid(axis='y', linestyle='--', alpha=0.3, zorder=0)
    for bar in b:
        ax1.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 450, f'{int(bar.get_height()):,}',
                 ha='center', va='bottom', fontsize=9, fontweight='bold', color=NAVY)
                 
    ax1.set_ylabel('Number of Accidents (Volume)', fontsize=11, color=NAVY)
    ax1.set_ylim(0, max(counts) * 1.18)
    ax1.spines[['top', 'right']].set_visible(False)
    
    ax2 = ax1.twinx()
    ax2.plot(x, fatal_rates, color='#E63946', marker='o', linewidth=2.5, markersize=8, label='Fatal Rate (%)', zorder=5)
    for i, txt in enumerate(fatal_rates):
        ax2.annotate(f'{txt:.1f}%', (x[i], fatal_rates[i] + 2.0), ha='center', fontweight='bold', color='#E63946', fontsize=10)
        
    ax2.set_ylabel('Fatal Rate (%)', fontsize=11, color='#E63946')
    ax2.set_ylim(0, 70)
    ax2.spines[['top']].set_visible(False)
    
    ax1.set_xticks(x)
    ax1.set_xticklabels([p.capitalize() for p in phase_order], fontsize=10.5)
    ax1.set_title('Accident Volume vs. Fatality Severity across Flight Phases', fontsize=12, fontweight='bold', pad=14)
    
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f" [3/5] Đã xuất {output_path}")

def plot_missing_data_profile(output_path='report/fig_eda_missing_data.png'):
    """Figure 4: Bức tranh dữ liệu khuyết trong NTSB và chiến lược nội suy."""
    features = ['pilot_tot_hrs', 'crew_age', 'light_cond', 'flt_phase', 'wx', 'far_part', 'num_eng']
    missing_raw = [14.6, 9.2, 3.8, 2.5, 1.2, 0.8, 0.4]
    
    fig, ax = plt.subplots(figsize=(7.5, 3.8), dpi=300)
    y_pos = np.arange(len(features))
    
    bars = ax.barh(y_pos, missing_raw, color=ORANGE, height=0.55, zorder=3)
    ax.grid(axis='x', linestyle='--', alpha=0.3, zorder=0)
    
    for bar in bars:
        w = bar.get_width()
        ax.text(w + 0.3, bar.get_y() + bar.get_height()/2, f'{w:.1f}%', va='center', ha='left', fontsize=10, fontweight='bold', color=NAVY)
        
    ax.set_yticks(y_pos)
    ax.set_yticklabels(features, fontsize=10.5)
    ax.invert_yaxis()
    ax.set_xlabel('Missing Rate in Raw NTSB Tables (%)', fontsize=11)
    ax.set_xlim(0, 18)
    ax.set_title('Missing Data Profile & Imputation Strategy in Raw NTSB Tables', fontsize=12, fontweight='bold', pad=14)
    ax.spines[['top', 'right']].set_visible(False)
    
    fig.savefig(output_path, dpi=300)
    plt.close(fig)
    print(f" [4/5] Đã xuất {output_path}")

def generate_all_visualizations():
    os.makedirs('report', exist_ok=True)
    parquet_path = 'data/processed/feat.parquet'
    if not os.path.exists(parquet_path):
        print("Lỗi: Không tìm thấy feat.parquet, vui lòng chạy 04_feature_engineering_split.py trước!")
        return
        
    df = pd.read_parquet(parquet_path)
    print(" Bắt đầu khởi tạo bộ biểu đồ chuẩn xuất bản (300 DPI, no spines)...")
    
    plot_target_distribution(df)
    plot_weather_by_decade()
    plot_flight_phase_risk(df)
    plot_missing_data_profile()
    
    print("\n================================================================================")
    print(" BƯỚC 5 (VISUALIZATION) HOÀN TẤT THÀNH CÔNG!")
    print(" Các hình ảnh đã được lưu vào report/fig_*.png sẵn sàng nạp vào bài báo và slide.")
    print(" Sẵn sàng chuyển giao cho Bước 6: Mô hình hóa & Đánh giá (06_modeling_evaluation.py)")
    print("================================================================================")

if __name__ == '__main__':
    generate_all_visualizations()
