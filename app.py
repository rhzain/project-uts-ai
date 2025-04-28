import streamlit as st
from penjadwalan_adaptif import PenjadwalanAdaptif
import pandas as pd

def main():
    st.title("Sistem Penjadwalan Adaptif - Input Langsung")
    
    sistem = PenjadwalanAdaptif()
    
    # Tab untuk input data
    tab1, tab2, tab3 = st.tabs(["Input Data", "Penjadwalan", "Hasil"])
    
    with tab1:
        st.header("Input Data Wahana")
        jumlah_wahana = st.number_input("Jumlah Wahana", min_value=1, max_value=50, value=5)
        
        data_wahana = []
        cols_wahana = st.columns(5)
        for i in range(jumlah_wahana):
            with cols_wahana[i % 5]:
                st.subheader(f"Wahana {i+1}")
                nama = st.text_input(f"Nama Wahana {i+1}", value=f"RS_{i+1:02d}")
                kapasitas = st.number_input(f"Kapasitas {i+1}", min_value=1, value=5)
                pasien_normal = st.number_input(f"Pasien Normal {i+1}", min_value=0, value=30)
                pasien_gangguan = st.number_input(f"Pasien Gangguan {i+1}", min_value=0, value=30)
                kategori = st.selectbox(f"Kategori {i+1}", ["Umum", "Bedah"])
                
                data_wahana.append({
                    'Nama Wahana': nama,
                    'Kapasitas Optimal': kapasitas,
                    'Pasien Normal': pasien_normal,
                    'Pasien Gangguan': pasien_gangguan,
                    'Kategori Pekerjaan': kategori,
                    'Status Gangguan': 'Stabil'  # Default
                })
        
        st.header("Input Data Peserta")
        jumlah_peserta = st.number_input("Jumlah Peserta", min_value=1, max_value=200, value=10)
        
        data_peserta = []
        cols_peserta = st.columns(5)
        for i in range(jumlah_peserta):
            with cols_peserta[i % 5]:
                st.subheader(f"Peserta {i+1}")
                id_peserta = st.text_input(f"ID Peserta {i+1}", value=f"P{i+1:03d}")
                nama = st.text_input(f"Nama Peserta {i+1}", value=f"Peserta {i+1}")
                preferensi = st.selectbox(f"Preferensi {i+1}", ["Umum", "Bedah"])
                
                data_peserta.append({
                    'ID Peserta': id_peserta,
                    'Nama Peserta': nama,
                    'Preferensi Pekerjaan': preferensi
                })
        
        if st.button("Simpan Data"):
            sistem.input_data_manual(data_wahana, data_peserta)
            st.success("Data berhasil disimpan!")
    
    with tab2:
        st.header("Proses Penjadwalan")
        
        if st.button("Lakukan Penjadwalan Awal"):
            with st.spinner('Sedang melakukan penjadwalan awal...'):
                try:
                    penempatan_awal = sistem.penempatan_awal()
                    
                    st.subheader("Hasil Penjadwalan Awal")
                    st.write(f"Total peserta yang ditempatkan: {len(penempatan_awal)}")
                    
                    # Tampilkan distribusi
                    distribusi = pd.Series(penempatan_awal.values()).value_counts().reset_index()
                    distribusi.columns = ['Nama Wahana', 'Jumlah Peserta']
                    st.bar_chart(distribusi.set_index('Nama Wahana'))
                    
                    st.session_state.penempatan_awal = True
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        if st.button("Simulasikan Gangguan"):
            with st.spinner('Sedang mensimulasikan gangguan...'):
                try:
                    sistem.simulasikan_gangguan()
                    
                    st.subheader("Status Wahana Setelah Gangguan")
                    st.dataframe(sistem.wahana_df[['Nama Wahana', 'Status Gangguan']])
                    
                    # Visualisasi status
                    status_counts = sistem.wahana_df['Status Gangguan'].value_counts()
                    st.bar_chart(status_counts)
                    
                    st.session_state.gangguan = True
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        if st.button("Lakukan Penyesuaian"):
            with st.spinner('Sedang menyesuaikan penempatan...'):
                try:
                    penempatan_akhir = sistem.redistribusi_adaptif()
                    
                    st.subheader("Hasil Penempatan Setelah Penyesuaian")
                    st.write(f"Total peserta yang ditempatkan: {len(penempatan_akhir)}")
                    
                    # Tampilkan distribusi akhir
                    distribusi_akhir = pd.Series(penempatan_akhir.values()).value_counts().reset_index()
                    distribusi_akhir.columns = ['Nama Wahana', 'Jumlah Peserta']
                    st.bar_chart(distribusi_akhir.set_index('Nama Wahana'))
                    
                    st.session_state.penyesuaian = True
                except Exception as e:
                    st.error(f"Error: {str(e)}")
    
    with tab3:
        st.header("Hasil Akhir")
        
        if 'penyesuaian' in st.session_state:
            try:
                hasil_df = sistem.visualisasi_hasil()
                
                st.subheader("Detail Penempatan")
                st.dataframe(hasil_df)
                
                # Hitung statistik
                match_sempurna = sum(
                    1 for _, row in hasil_df.iterrows() 
                    if row['Preferensi Pekerjaan'] == row['Kategori Pekerjaan']
                )
                total_peserta = len(hasil_df)
                
                st.subheader("Statistik")
                col1, col2 = st.columns(2)
                col1.metric("Total Peserta", total_peserta)
                col2.metric("Match Sempurna", f"{match_sempurna} ({match_sempurna/total_peserta:.1%})")
                
                # Download hasil
                st.download_button(
                    label="Download Hasil Penempatan",
                    data=hasil_df.to_csv(index=False),
                    file_name='hasil_penempatan.csv',
                    mime='text/csv'
                )
            except Exception as e:
                st.error(f"Error: {str(e)}")
        else:
            st.warning("Silakan lakukan proses penjadwalan terlebih dahulu")

if __name__ == "__main__":
    main()