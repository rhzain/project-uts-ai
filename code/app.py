import streamlit as st
import pandas as pd
import plotly.express as px
from penjadwalan_adaptif import PenjadwalanAdaptif

def main():
    st.set_page_config(layout="wide")
    st.title("Sistem Penjadwalan Adaptif untuk Penempatan Peserta Didik Profesi Dokter")
    
    # Inisialisasi session state
    if 'sistem' not in st.session_state:
        st.session_state.sistem = None
    if 'penjadwalan_awal' not in st.session_state:
        st.session_state.penjadwalan_awal = None
    if 'gangguan' not in st.session_state:
        st.session_state.gangguan = None
    if 'hasil_perbandingan' not in st.session_state:
        st.session_state.hasil_perbandingan = None
    
    # Sidebar untuk upload file
    with st.sidebar:
        st.header("Unggah Data")
        uploaded_file = st.file_uploader("Upload file Excel data dummy", type=["xlsx"])
        
        if uploaded_file is not None:
            with open("temp_data.xlsx", "wb") as f:
                f.write(uploaded_file.getbuffer())
            
            if st.session_state.sistem is None:
                st.session_state.sistem = PenjadwalanAdaptif("temp_data.xlsx", "temp_data.xlsx")
                st.success("Data berhasil diunggah!")
        
        # Tambahan di sidebar: perbandingan strategi
        # Di app.py, modifikasi bagian perbandingan strategi di sidebar
        # Di app.py, modifikasi bagian perbandingan strategi di sidebar
        if st.session_state.sistem is not None:
            st.divider()
            st.header("Perbandingan Strategi")
            
            # Pilihan optimasi untuk perbandingan
            st.subheader("Pengaturan Perbandingan")
            col1, col2 = st.columns(2)
            
            with col1:
                reduce_params = st.checkbox("Gunakan Parameter Lebih Ringan", value=True, 
                                        help="Mengurangi jumlah iterasi untuk mempercepat eksekusi")
                exclude_slow = st.checkbox("Lewati Algoritma Lambat", value=True,
                                        help="Melewati algoritma ILP untuk dataset besar")
            
            with col2:
                max_time = st.number_input("Batas Waktu per Strategi (detik)", 
                                        min_value=10, max_value=600, value=60)
                skenario = st.radio("Skenario:", ["Normal", "Gangguan"], horizontal=True)
            
            # Tambahkan opsi thread/proses
            use_threading = st.checkbox("Gunakan Threading", value=False, 
                                    help="Gunakan threading untuk menjalankan algoritma secara paralel (eksperimental)")
            
            if st.button("Bandingkan Semua Strategi"):
                with st.spinner("Membandingkan strategi optimasi..."):
                    try:
                        skenario_param = "normal" if skenario == "Normal" else "gangguan"
                        st.session_state.hasil_perbandingan = st.session_state.sistem.bandingkan_strategi(
                            skenario=skenario_param,
                            max_time_per_strategy=max_time,
                            reduce_parameters=reduce_params,
                            exclude_slow=exclude_slow
                        )
                        st.success("Perbandingan selesai!")
                    except Exception as e:
                        st.error(f"Terjadi kesalahan saat membandingkan strategi: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
    
    # Tab utama
    if st.session_state.sistem is not None:
        tab1, tab2, tab3, tab4 = st.tabs([
            "🗓 Penjadwalan Awal", 
            "⚠️ Simulasi Gangguan", 
            "🔄 Redistribusi Adaptif",
            "📊 Analisis Perbandingan"
        ])
        
        # Tab 1: Penjadwalan Awal
        with tab1:
            st.header("Penjadwalan Awal")
            
            # Tambahkan pilihan strategi optimasi
            strategi = st.selectbox(
                "Pilih algoritma penjadwalan:",
                ["Greedy (Default)", "ILP (Optimal Global)", "Algoritma Genetik", "Simulated Annealing", "Two-Phase"]
            )
            
            # Mapping nilai selectbox ke parameter method
            strategi_map = {
                "Greedy (Default)": "greedy",
                "ILP (Optimal Global)": "ilp",
                "Algoritma Genetik": "genetik",
                "Simulated Annealing": "simulated_annealing",
                "Two-Phase": "two-phase"
            }
            
            if st.button("Buat Penjadwalan Awal", type="primary"):
                with st.spinner(f"Membuat penjadwalan dengan algoritma {strategi}..."):
                    try:
                        st.session_state.penjadwalan_awal = st.session_state.sistem.penjadwalan_adaptif_optimal(
                            strategi=strategi_map[strategi]
                        )
                        st.success("Jadwal awal berhasil dibuat!")
                    except Exception as e:
                        st.error(f"Terjadi kesalahan: {e}")
                        # Fallback ke greedy jika algoritma pilihan gagal
                        st.warning("Menggunakan algoritma greedy sebagai fallback...")
                        st.session_state.penjadwalan_awal = st.session_state.sistem.penjadwalan_awal()
                
                # Tampilkan hasil
                st.subheader("Hasil Penjadwalan")
                wahana_list = list(st.session_state.penjadwalan_awal.keys())
                selected_wahana = st.selectbox("Pilih wahana untuk detail:", wahana_list)
                
                with st.expander(f"Detail Penempatan di {selected_wahana}"):
                    peserta_list = st.session_state.penjadwalan_awal[selected_wahana]
                    for peserta in peserta_list:
                        st.write(f"**{peserta['ID Peserta']}**: {peserta['Nama']} (Skor: {peserta['Skor Kecocokan']})")
                
                # Evaluasi
                eval_awal = st.session_state.sistem.evaluasi_penjadwalan(st.session_state.penjadwalan_awal)
                st.subheader("Evaluasi Kualitas")
                col1, col2, col3 = st.columns(3)
                col1.metric("Rata-rata Skor", f"{eval_awal['rata_rata_skor']:.2f}")
                col2.metric("Match Sempurna", f"{eval_awal['persentase_match_sempurna']:.2f}%")
                col3.metric("Peserta Terjadwal", eval_awal['total_peserta_terjadwal'])
        
        # Tab 2: Simulasi Gangguan
        with tab2:
            st.header("Simulasi Gangguan")
            if st.session_state.penjadwalan_awal is not None:
                skenario = st.radio("Pilih skenario:", ["Normal", "Gangguan"], horizontal=True)
                
                if st.button("Identifikasi Gangguan", type="primary"):
                    with st.spinner("Menganalisis gangguan..."):
                        st.session_state.gangguan = st.session_state.sistem.identifikasi_gangguan(
                            skenario='gangguan' if skenario == "Gangguan" else 'normal'
                        )
                    
                    # Visualisasi gangguan
                    st.subheader("Hasil Identifikasi")
                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown("**🔥 Wahana Overload**")
                        for item in st.session_state.gangguan['overload']:
                            st.error(f"""
                            **{item['wahana']}**  
                            Rasio: {item['rasio']:.1f} pasien/peserta  
                            Pasien: {item['pasien']} | Peserta: {item['peserta']}
                            """)
                    
                    with col2:
                        st.markdown("**❄️ Wahana Underutilized**")
                        for item in st.session_state.gangguan['underutilized']:
                            st.success(f"""
                            **{item['wahana']}**  
                            Rasio: {item['rasio']:.1f} pasien/peserta  
                            Pasien: {item['pasien']} | Peserta: {item['peserta']}
                            """)
            else:
                st.warning("Silakan buat penjadwalan awal terlebih dahulu di tab Penjadwalan Awal")
        
        # Tab 3: Redistribusi Adaptif
        with tab3:
            st.header("Redistribusi Adaptif")
            if st.session_state.penjadwalan_awal is not None and st.session_state.gangguan is not None:
                # Pilihan metode redistribusi
                redistribusi_method = st.radio(
                    "Pilih metode redistribusi:",
                    ["Adaptif (Default)", "Global (Optimasi)"],
                    horizontal=True
                )
                
                if st.button("Lakukan Redistribusi", type="primary"):
                    with st.spinner("Menyesuaikan penjadwalan..."):
                        if redistribusi_method == "Adaptif (Default)":
                            penjadwalan_baru = st.session_state.sistem.redistribusi_adaptif(st.session_state.gangguan)
                        else:
                            # Gunakan metode redistribusi global
                            penjadwalan_baru = st.session_state.sistem.redistribusi_global(st.session_state.gangguan)
                    
                    # Cek perubahan
                    perubahan_terjadi = False
                    for wahana in st.session_state.penjadwalan_awal:
                        if len(st.session_state.penjadwalan_awal[wahana]) != len(penjadwalan_baru[wahana]):
                            perubahan_terjadi = True
                            break
                    
                    if not perubahan_terjadi:
                        # Kasus tidak ada perubahan
                        st.success("""
                        ✅ **Sistem Sudah Optimal**  
                        Tidak ditemukan redistribusi yang dapat meningkatkan kualitas penjadwalan
                        """)
                        
                        # Analisis penyebab
                        st.subheader("🔍 Diagnosa Sistem")
                        with st.expander("Detail Analisis", expanded=True):
                            st.markdown("""
                            **Kemungkinan penyebab:**
                            - Tidak ada wahana underutilized yang cocok dengan minat peserta dari wahana overload
                            - Kapasitas underutilized tidak cukup untuk menampung peserta tambahan
                            - Skor kecocokan peserta di wahana asal sudah optimal
                            """)
                            
                            st.markdown("""
                            **Rekomendasi:**
                            1. Tambahkan wahana pendidikan baru
                            2. Sesuaikan kriteria overload/underutilized
                            3. Tinjau ulang data kecocokan peserta-wahana
                            """)
                    else:
                        # Tampilkan perubahan
                        st.subheader("📊 Perubahan Penjadwalan")
                        
                        # Data untuk visualisasi
                        data = []
                        for wahana in st.session_state.penjadwalan_awal:
                            perubahan = len(penjadwalan_baru[wahana]) - len(st.session_state.penjadwalan_awal[wahana])
                            if perubahan != 0:
                                data.append({
                                    'Wahana': wahana,
                                    'Perubahan': perubahan,
                                    'Tipe': 'Ditambahkan' if perubahan > 0 else 'Dikurangi'
                                })
                        
                        # Visualisasi perubahan
                        if data:
                            fig = px.bar(
                                pd.DataFrame(data),
                                x='Wahana',
                                y='Perubahan',
                                color='Tipe',
                                color_discrete_map={
                                    'Ditambahkan': '#4CAF50',
                                    'Dikurangi': '#F44336'
                                },
                                title='Perubahan Jumlah Peserta per Wahana'
                            )
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Detail perubahan
                            st.subheader("🔎 Detail Redistribusi")
                            for item in data:
                                st.write(f"**{item['Wahana']}**: {abs(item['Perubahan'])} peserta {item['Tipe'].lower()}")
                        else:
                            st.info("Tidak ada perubahan signifikan dalam distribusi peserta")
                        
                        # Evaluasi hasil
                        st.subheader("📈 Evaluasi Hasil")
                        eval_awal = st.session_state.sistem.evaluasi_penjadwalan(st.session_state.penjadwalan_awal)
                        eval_baru = st.session_state.sistem.evaluasi_penjadwalan(penjadwalan_baru)
                        
                        col1, col2, col3 = st.columns(3)
                        col1.metric(
                            "Rata-rata Skor",
                            f"{eval_baru['rata_rata_skor']:.2f}",
                            delta=f"{eval_baru['rata_rata_skor'] - eval_awal['rata_rata_skor']:.2f}"
                        )
                        col2.metric(
                            "Match Sempurna",
                            f"{eval_baru['persentase_match_sempurna']:.2f}%",
                            delta=f"{eval_baru['persentase_match_sempurna'] - eval_awal['persentase_match_sempurna']:.2f}%"
                        )
                        col3.metric(
                            "Peserta Terjadwal",
                            eval_baru['total_peserta_terjadwal'],
                            delta=eval_baru['total_peserta_terjadwal'] - eval_awal['total_peserta_terjadwal']
                        )
            else:
                st.warning("Silakan identifikasi gangguan terlebih dahulu di tab Simulasi Gangguan")
        
        # Tab 4: Analisis Perbandingan
        with tab4:
            st.header("Analisis Perbandingan Algoritma")
            if st.session_state.hasil_perbandingan is not None:
                # Tampilkan hasil perbandingan dalam bentuk tabel
                st.subheader("Tabel Perbandingan")
                
                # Buat DataFrame untuk hasil perbandingan
                data_perbandingan = []
                
                for strategi, data in st.session_state.hasil_perbandingan.items():
                    if 'error' in data:
                        row = {
                            'Strategi': strategi,
                            'Rata-rata Skor': 'ERROR',
                            'Match Sempurna (%)': 'ERROR',
                            'Peserta Terjadwal': 'ERROR',
                            'Waktu Eksekusi (s)': 'ERROR'
                        }
                    else:
                        row = {
                            'Strategi': strategi,
                            'Rata-rata Skor': f"{data['evaluasi']['rata_rata_skor']:.2f}",
                            'Match Sempurna (%)': f"{data['evaluasi']['persentase_match_sempurna']:.2f}",
                            'Peserta Terjadwal': data['evaluasi']['total_peserta_terjadwal'],
                            'Waktu Eksekusi (s)': f"{data['waktu']:.2f}"
                        }
                    data_perbandingan.append(row)
                
                # Tampilkan tabel
                df_perbandingan = pd.DataFrame(data_perbandingan)
                st.table(df_perbandingan)
                
                # Visualisasi grafik perbandingan
                st.subheader("Visualisasi Grafik")
                
                # Buat pilihan untuk tampilan grafik
                grafik_option = st.selectbox(
                    "Pilih grafik:",
                    ["Rata-rata Skor", "Match Sempurna (%)", "Peserta Terjadwal", "Waktu Eksekusi (s)"]
                )
                
                # Filter data yang tidak error
                data_valid = {k: v for k, v in st.session_state.hasil_perbandingan.items() if 'error' not in v}
                strategi_valid = list(data_valid.keys())
                
                if strategi_valid:
                    if grafik_option == "Rata-rata Skor":
                        values = [data_valid[s]['evaluasi']['rata_rata_skor'] for s in strategi_valid]
                        y_title = "Skor"
                    elif grafik_option == "Match Sempurna (%)":
                        values = [data_valid[s]['evaluasi']['persentase_match_sempurna'] for s in strategi_valid]
                        y_title = "%"
                    elif grafik_option == "Peserta Terjadwal":
                        values = [data_valid[s]['evaluasi']['total_peserta_terjadwal'] for s in strategi_valid]
                        y_title = "Jumlah"
                    else:  # Waktu Eksekusi
                        values = [data_valid[s]['waktu'] for s in strategi_valid]
                        y_title = "Detik"
                    
                    # Buat grafik bar
                    fig = px.bar(
                        x=strategi_valid,
                        y=values,
                        labels={'x': 'Strategi', 'y': y_title},
                        title=f"Perbandingan {grafik_option} antar Strategi",
                        text=[f"{v:.2f}" if isinstance(v, float) else str(v) for v in values]
                    )
                    
                    # Custom format untuk waktu
                    if grafik_option == "Waktu Eksekusi (s)":
                        fig.update_layout(yaxis_type="log")
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Tampilkan interpretasi hasil
                    st.subheader("Interpretasi Hasil")
                    
                    best_skor_idx = values.index(max(values)) if grafik_option != "Waktu Eksekusi (s)" else values.index(min(values))
                    best_strategi = strategi_valid[best_skor_idx]
                    
                    if grafik_option == "Waktu Eksekusi (s)":
                        st.info(f"**Strategi tercepat**: {best_strategi} ({values[best_skor_idx]:.2f} detik)")
                        
                        # Trade-off analisis
                        tradeoff_data = []
                        for s in strategi_valid:
                            tradeoff_data.append({
                                'Strategi': s,
                                'Skor': data_valid[s]['evaluasi']['rata_rata_skor'],
                                'Waktu': data_valid[s]['waktu']
                            })
                        
                        df_tradeoff = pd.DataFrame(tradeoff_data)
                        fig = px.scatter(
                            df_tradeoff, 
                            x='Waktu', 
                            y='Skor', 
                            text='Strategi',
                            title="Trade-off: Waktu vs Skor",
                            labels={'Waktu': 'Waktu Eksekusi (s)', 'Skor': 'Rata-rata Skor'}
                        )
                        fig.update_traces(textposition='top center')
                        fig.update_layout(xaxis_type="log")
                        st.plotly_chart(fig, use_container_width=True)
                        
                        st.markdown("""
                        **Analisis Trade-off:**
                        - **Greedy**: Solusi cepat namun sub-optimal
                        - **ILP**: Solusi optimal global namun lebih lambat
                        - **Algoritma Genetik**: Balance antara waktu dan kualitas solusi
                        - **Two-Phase**: Kombinasi optimasi global dan penyesuaian lokal
                        """)
                    else:
                        st.info(f"**Strategi terbaik untuk {grafik_option}**: {best_strategi} ({values[best_skor_idx]:.2f})")
                        
                        st.markdown(f"""
                        **Insight:**
                        - Strategi **{best_strategi}** memberikan hasil terbaik untuk metrik {grafik_option.lower()}
                        - Untuk kasus dengan jumlah data besar, pertimbangkan trade-off antara kualitas solusi dan waktu eksekusi
                        """)
                else:
                    st.warning("Tidak ada data valid untuk divisualisasikan")
            else:
                st.info("Silakan jalankan perbandingan strategi terlebih dahulu menggunakan tombol di sidebar")
    else:
        st.info("Silakan unggah file data terlebih dahulu di sidebar")

if __name__ == "__main__":
    main()