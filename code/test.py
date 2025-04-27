import pandas as pd
import streamlit as st
from collections import defaultdict
import tempfile
import os
import plotly.express as px

class PenjadwalanAdaptif:
    def __init__(self):
        self.wahana_df = None
        self.peserta_df = None
        self.penempatan_awal = None
        self.penempatan_akhir = None
        
    def load_data_excel(self, file_path):
        """Memuat data dari file Excel dengan 2 sheet"""
        try:
            self.wahana_df = pd.read_excel(file_path, sheet_name='Data Wahana')
            self.peserta_df = pd.read_excel(file_path, sheet_name='Data Peserta')
            
            # Set default status gangguan
            if 'Status Gangguan' not in self.wahana_df.columns:
                self.wahana_df['Status Gangguan'] = 'Stabil'
                
            return True
        except Exception as e:
            st.error(f"Error loading Excel file: {str(e)}")
            return False
            
    def input_data_manual(self, data_wahana, data_peserta):
        """Menerima input data langsung dari antarmuka"""
        try:
            self.wahana_df = pd.DataFrame(data_wahana)
            self.peserta_df = pd.DataFrame(data_peserta)
            
            # Set default status gangguan
            if 'Status Gangguan' not in self.wahana_df.columns:
                self.wahana_df['Status Gangguan'] = 'Stabil'
                
            return True
        except Exception as e:
            st.error(f"Error processing manual input: {str(e)}")
            return False
        
    def hitung_skor_kecocokan(self, peserta, wahana):
        """Menghitung skor kecocokan antara peserta dan wahana"""
        skor = 0
        
        # Kesesuaian preferensi pekerjaan (50% bobot)
        if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
            skor += 50
            
        # Kesesuaian beban kerja (30% bobot)
        pasien_per_peserta = wahana['Pasien Normal'] / wahana['Kapasitas Optimal']
        if 5 <= pasien_per_peserta <= 20:  # Range ideal
            skor += 30
        elif pasien_per_peserta < 5:  # Underutilized
            skor += 10
        else:  # Overload
            skor += 5
            
        # Ketersediaan kapasitas (20% bobot)
        if wahana['Kapasitas Optimal'] > 0:
            skor += 20
            
        return skor
        
    # Fix the penjadwalan_awal() method in the PenjadwalanAdaptif class
    def penjadwalan_awal(self):
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Urutkan: Stabil -> Underutilized, kapasitas besar -> kecil
        wahana_prioritas = self.wahana_df[
            (self.wahana_df['Status Gangguan'].isin(['Stabil', 'Underutilized'])) &
            (self.wahana_df['Pasien Gangguan'] > 0)
        ].sort_values(by=['Status Gangguan', 'Kapasitas Optimal'], 
                    ascending=[True, False])  # True=Stabil di awal
        
        peserta_tidak_tertempatkan = []
        
        for _, peserta in self.peserta_df.iterrows():
            ditempatkan = False
            
            for _, wahana in wahana_prioritas.iterrows():
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    penempatan[peserta['ID Peserta']] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    ditempatkan = True
                    break
                    
            if not ditempatkan:
                peserta_tidak_tertempatkan.append(peserta['ID Peserta'])
        
        # Store the results directly in the class instance
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = peserta_tidak_tertempatkan
        
        return penempatan
    
    def simulasikan_gangguan(self):
        """Mensimulasikan gangguan pada wahana"""
        if self.wahana_df is None:
            raise ValueError("Data wahana belum dimuat")
            
        for idx, wahana in self.wahana_df.iterrows():
            if wahana['Pasien Gangguan'] == 0:
                self.wahana_df.at[idx, 'Status Gangguan'] = 'Tutup'
            else:
                pasien_per_peserta = wahana['Pasien Gangguan'] / wahana['Kapasitas Optimal']
                if pasien_per_peserta > 20:
                    self.wahana_df.at[idx, 'Status Gangguan'] = 'Overload'
                elif pasien_per_peserta < 5:
                    self.wahana_df.at[idx, 'Status Gangguan'] = 'Underutilized'
                else:
                    self.wahana_df.at[idx, 'Status Gangguan'] = 'Stabil'
    
    def redistribusi_adaptif(self):
        """Melakukan penyesuaian penempatan setelah gangguan"""
        if self.penempatan_awal is None:
            raise ValueError("Penjadwalan awal belum dilakukan")
            
        penempatan_baru = self.penempatan_awal.copy()
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Hitung ulang kapasitas tersedia berdasarkan penempatan awal
        for wahana in kapasitas_tersedia:
            jumlah_peserta = sum(1 for w in penempatan_baru.values() if w == wahana)
            kapasitas_tersedia[wahana] = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Kapasitas Optimal'].values[0] - jumlah_peserta
        
        # Identifikasi peserta di wahana bermasalah
        peserta_dipindahkan = []
        for peserta_id, wahana in penempatan_baru.items():
            status_wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Status Gangguan'].values[0]
            if status_wahana in ['Overload', 'Tutup']:
                peserta_dipindahkan.append(peserta_id)
        
        # Untuk setiap peserta yang perlu dipindahkan, cari wahana baru
        for peserta_id in peserta_dipindahkan:
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana_asal = penempatan_baru[peserta_id]
            
            # Hitung skor untuk wahana yang underutilized atau stabil
            wahana_cocok = self.wahana_df[
                (self.wahana_df['Status Gangguan'].isin(['Underutilized', 'Stabil'])) & 
                (self.wahana_df['Nama Wahana'] != wahana_asal)
            ]
            
            skor_wahana = []
            for _, wahana in wahana_cocok.iterrows():
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    skor = self.hitung_skor_kecocokan(peserta, wahana)
                    skor_wahana.append((wahana['Nama Wahana'], skor))
            
            # Urutkan berdasarkan skor tertinggi
            skor_wahana.sort(key=lambda x: x[1], reverse=True)
            
            # Pindahkan peserta ke wahana baru jika ada yang cocok
            if skor_wahana:
                wahana_baru = skor_wahana[0][0]
                penempatan_baru[peserta_id] = wahana_baru
                kapasitas_tersedia[wahana_baru] -= 1
                kapasitas_tersedia[wahana_asal] += 1
        
        self.penempatan_akhir = penempatan_baru
        return penempatan_baru
    
    def visualisasi_hasil(self):
        """Menampilkan hasil penjadwalan"""
        if self.penempatan_awal is None or self.penempatan_akhir is None:
            raise ValueError("Penjadwalan belum selesai")
            
        # Buat DataFrame untuk hasil penempatan
        hasil_df = pd.DataFrame({
            'ID Peserta': list(self.penempatan_akhir.keys()),
            'Nama Wahana Awal': [self.penempatan_awal.get(pid, 'Belum ditempatkan') for pid in self.penempatan_akhir.keys()],
            'Nama Wahana Akhir': list(self.penempatan_akhir.values())
        })
        
        # Gabungkan dengan data peserta dan wahana untuk informasi lengkap
        hasil_df = hasil_df.merge(self.peserta_df, on='ID Peserta')
        hasil_df = hasil_df.merge(
            self.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Status Gangguan']], 
            left_on='Nama Wahana Akhir', 
            right_on='Nama Wahana',
            suffixes=('', '_wahana')
        )
        
        return hasil_df
    
    def hitung_statistik_awal(self):
        """Menghitung statistik untuk penjadwalan awal"""
        if self.penempatan_awal is None:
            raise ValueError("Penjadwalan awal belum dilakukan")
            
        statistik = {
            'total_peserta': len(self.penempatan_awal),
            'wahana_terisi': defaultdict(int),
            'kategori_match': 0,
            'distribusi_status': defaultdict(int)
        }
        
        # Hitung distribusi peserta per wahana
        for wahana in self.penempatan_awal.values():
            statistik['wahana_terisi'][wahana] += 1
        
        # Hitung match preferensi
        for peserta_id, wahana in self.penempatan_awal.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana].iloc[0]
            if peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan']:
                statistik['kategori_match'] += 1
        
        # Hitung distribusi status awal wahana
        for status in self.wahana_df['Status Gangguan']:
            statistik['distribusi_status'][status] += 1
            
        return statistik
    
    def bandingkan_penempatan(self):
        """Membandingkan penempatan awal dan akhir dengan penanganan error yang lebih baik"""
        if self.penempatan_awal is None or self.penempatan_akhir is None:
            raise ValueError("Penjadwalan belum selesai")
            
        komparasi = {
            'total_pindah': 0,
            'wahana_asal': defaultdict(int),
            'wahana_tujuan': defaultdict(int),
            'peningkatan_match': 0,
            'detail_pemindahan': []
        }
        
        for peserta_id in self.penempatan_awal:
            try:
                wahana_awal = self.penempatan_awal[peserta_id]
                wahana_akhir = self.penempatan_akhir.get(peserta_id, None)
                
                if wahana_akhir is None or wahana_awal == wahana_akhir:
                    continue
                    
                # Dapatkan data peserta dan wahana
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                wahana_awal_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_awal].iloc[0]
                wahana_akhir_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_akhir].iloc[0]
                
                # Hitung match preferensi
                match_awal = 1 if peserta['Preferensi Pekerjaan'] == wahana_awal_data['Kategori Pekerjaan'] else 0
                match_akhir = 1 if peserta['Preferensi Pekerjaan'] == wahana_akhir_data['Kategori Pekerjaan'] else 0
                
                komparasi['total_pindah'] += 1
                komparasi['wahana_asal'][wahana_awal] += 1
                komparasi['wahana_tujuan'][wahana_akhir] += 1
                komparasi['peningkatan_match'] += (match_akhir - match_awal)
                
                komparasi['detail_pemindahan'].append({
                    'ID Peserta': peserta_id,
                    'Nama Peserta': peserta['Nama Peserta'],
                    'Preferensi': peserta['Preferensi Pekerjaan'],
                    'Wahana Awal': wahana_awal,
                    'Kategori Awal': wahana_awal_data['Kategori Pekerjaan'],
                    'Status Awal': wahana_awal_data['Status Gangguan'],
                    'Wahana Akhir': wahana_akhir,
                    'Kategori Akhir': wahana_akhir_data['Kategori Pekerjaan'],
                    'Status Akhir': wahana_akhir_data['Status Gangguan'],
                    'Match Awal': match_awal,
                    'Match Akhir': match_akhir
                })
                
            except Exception as e:
                print(f"Error processing peserta {peserta_id}: {str(e)}")
                continue
                
        return komparasi


def main():
    st.set_page_config(layout="wide")
    st.title("Sistem Penjadwalan Adaptif untuk Penempatan Peserta Didik Profesi Dokter")
    
    # Inisialisasi sistem dan session state
    if 'sistem' not in st.session_state:
        st.session_state.sistem = PenjadwalanAdaptif()
        st.session_state.data_loaded = False
        st.session_state.penjadwalan_done = False
        st.session_state.gangguan_done = False
        st.session_state.penyesuaian_done = False
    
    # Tab navigasi
    tab1, tab2, tab3, tab4 = st.tabs(["Input Data", "Penjadwalan Awal", "Simulasi Gangguan", "Hasil Akhir"])
    
    # Modifikasi untuk tab1 (Input Data) dengan informasi yang lebih lengkap
    with tab1:
        st.header("Input Data")
        
        # Pilihan metode input
        input_method = st.radio("Pilih metode input:", ("Upload File Excel", "Input Manual"))
        
        if input_method == "Upload File Excel":
            st.subheader("Upload File Excel")
            uploaded_file = st.file_uploader("Upload file Excel dengan 2 sheet (Data Wahana dan Data Peserta)", 
                                        type=["xlsx", "xls"])
            
            if uploaded_file is not None:
                # Simpan file sementara
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    tmp_file.write(uploaded_file.getvalue())
                    tmp_file_path = tmp_file.name
                
                # Load data dari file
                if st.session_state.sistem.load_data_excel(tmp_file_path):
                    st.session_state.data_loaded = True
                    st.success("Data berhasil dimuat dari file Excel!")
                    
                    # Data Wahana
                    st.subheader("Data Wahana")
                    
                    # Menampilkan statistik umum wahana
                    col1, col2, col3, col4 = st.columns(4)
                    total_wahana = len(st.session_state.sistem.wahana_df)
                    total_kapasitas = st.session_state.sistem.wahana_df['Kapasitas Optimal'].sum()
                    total_pasien_normal = st.session_state.sistem.wahana_df['Pasien Normal'].sum()
                    total_pasien_gangguan = st.session_state.sistem.wahana_df['Pasien Gangguan'].sum()
                    
                    col1.metric("Total Wahana", total_wahana)
                    col2.metric("Total Kapasitas", total_kapasitas)
                    col3.metric("Total Pasien Normal", total_pasien_normal)
                    col4.metric("Total Pasien Gangguan", total_pasien_gangguan)
                    
                    # Distribusi kategori wahana
                    st.subheader("Distribusi Kategori Wahana")
                    kategori_counts = st.session_state.sistem.wahana_df['Kategori Pekerjaan'].value_counts()
                    fig_kategori = px.pie(names=kategori_counts.index, values=kategori_counts.values, 
                                        title="Distribusi Kategori Pekerjaan Wahana")
                    st.plotly_chart(fig_kategori)
                    
                    # Tampilkan data wahana lengkap dengan toggle
                    with st.expander("Lihat Data Wahana Lengkap"):
                        st.dataframe(st.session_state.sistem.wahana_df, use_container_width=True)
                    
                    # Data Peserta
                    st.subheader("Data Peserta")
                    
                    # Menampilkan statistik umum peserta
                    col1, col2 = st.columns(2)
                    total_peserta = len(st.session_state.sistem.peserta_df)
                    
                    col1.metric("Total Peserta", total_peserta)
                    col2.metric("Rasio Peserta:Kapasitas", f"{total_peserta}/{total_kapasitas} ({total_peserta/total_kapasitas:.2f})")
                    
                    # Distribusi preferensi peserta
                    st.subheader("Distribusi Preferensi Peserta")
                    preferensi_counts = st.session_state.sistem.peserta_df['Preferensi Pekerjaan'].value_counts()
                    fig_preferensi = px.pie(names=preferensi_counts.index, values=preferensi_counts.values, 
                                            title="Distribusi Preferensi Pekerjaan Peserta")
                    st.plotly_chart(fig_preferensi)
                    
                    # Tampilkan data peserta lengkap dengan toggle
                    with st.expander("Lihat Data Peserta Lengkap"):
                        st.dataframe(st.session_state.sistem.peserta_df, use_container_width=True)
                    
                    # Analisis Potensi Match
                    st.subheader("Analisis Potensi Kecocokan")
                    
                    # Hitung potensi kecocokan preferensi
                    umum_preferensi = preferensi_counts.get("Umum", 0)
                    bedah_preferensi = preferensi_counts.get("Bedah", 0)
                    
                    umum_kapasitas = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Kategori Pekerjaan'] == "Umum"]['Kapasitas Optimal'].sum()
                    bedah_kapasitas = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Kategori Pekerjaan'] == "Bedah"]['Kapasitas Optimal'].sum()
                    
                    col1, col2 = st.columns(2)
                    
                    col1.metric("Preferensi Umum vs Kapasitas Umum", f"{umum_preferensi}/{umum_kapasitas}", 
                            f"{umum_preferensi-umum_kapasitas:+d}" if umum_preferensi != umum_kapasitas else "0")
                    
                    col2.metric("Preferensi Bedah vs Kapasitas Bedah", f"{bedah_preferensi}/{bedah_kapasitas}", 
                            f"{bedah_preferensi-bedah_kapasitas:+d}" if bedah_preferensi != bedah_kapasitas else "0")
                    
                    # Hapus file sementara
                    os.unlink(tmp_file_path)
        
        else:  # Input Manual
            st.subheader("Input Data Wahana")
            jumlah_wahana = st.number_input("Jumlah Wahana", min_value=1, max_value=50, value=5, key='num_wahana')
            
            data_wahana = []
            cols_wahana = st.columns(5)
            for i in range(jumlah_wahana):
                with cols_wahana[i % 5]:
                    st.subheader(f"Wahana {i+1}")
                    nama = st.text_input(f"Nama Wahana {i+1}", value=f"RS_{i+1:02d}", key=f"wahana_nama_{i}")
                    kapasitas = st.number_input(f"Kapasitas {i+1}", min_value=1, value=5, key=f"wahana_kap_{i}")
                    pasien_normal = st.number_input(f"Pasien Normal {i+1}", min_value=0, value=30, key=f"wahana_normal_{i}")
                    pasien_gangguan = st.number_input(f"Pasien Gangguan {i+1}", min_value=0, value=30, key=f"wahana_gangguan_{i}")
                    kategori = st.selectbox(f"Kategori {i+1}", ["Umum", "Bedah"], key=f"wahana_kategori_{i}")
                    
                    data_wahana.append({
                        'Nama Wahana': nama,
                        'Kapasitas Optimal': kapasitas,
                        'Pasien Normal': pasien_normal,
                        'Pasien Gangguan': pasien_gangguan,
                        'Kategori Pekerjaan': kategori
                    })
            
            st.subheader("Input Data Peserta")
            jumlah_peserta = st.number_input("Jumlah Peserta", min_value=1, max_value=200, value=10, key='num_peserta')
            
            data_peserta = []
            cols_peserta = st.columns(5)
            for i in range(jumlah_peserta):
                with cols_peserta[i % 5]:
                    st.subheader(f"Peserta {i+1}")
                    id_peserta = st.text_input(f"ID Peserta {i+1}", value=f"P{i+1:03d}", key=f"peserta_id_{i}")
                    nama = st.text_input(f"Nama Peserta {i+1}", value=f"Peserta {i+1}", key=f"peserta_nama_{i}")
                    preferensi = st.selectbox(f"Preferensi {i+1}", ["Umum", "Bedah"], key=f"peserta_pref_{i}")
                    
                    data_peserta.append({
                        'ID Peserta': id_peserta,
                        'Nama Peserta': nama,
                        'Preferensi Pekerjaan': preferensi
                    })
            
            # Tampilkan ringkasan data yang akan disimpan
            if data_wahana and data_peserta:
                with st.expander("Ringkasan Data Input Manual"):
                    # Statistik wahana
                    total_kapasitas = sum(w['Kapasitas Optimal'] for w in data_wahana)
                    total_pasien_normal = sum(w['Pasien Normal'] for w in data_wahana)
                    total_pasien_gangguan = sum(w['Pasien Gangguan'] for w in data_wahana)
                    
                    st.write("**Statistik Wahana:**")
                    col1, col2, col3, col4 = st.columns(4)
                    col1.metric("Total Wahana", len(data_wahana))
                    col2.metric("Total Kapasitas", total_kapasitas)
                    col3.metric("Total Pasien Normal", total_pasien_normal)
                    col4.metric("Total Pasien Gangguan", total_pasien_gangguan)
                    
                    # Distribusi kategori
                    kategori_counts = {}
                    for w in data_wahana:
                        kategori_counts[w['Kategori Pekerjaan']] = kategori_counts.get(w['Kategori Pekerjaan'], 0) + 1
                    
                    st.write("**Distribusi Kategori:**")
                    st.write(f"- Umum: {kategori_counts.get('Umum', 0)}")
                    st.write(f"- Bedah: {kategori_counts.get('Bedah', 0)}")
                    
                    # Statistik peserta
                    preferensi_counts = {}
                    for p in data_peserta:
                        preferensi_counts[p['Preferensi Pekerjaan']] = preferensi_counts.get(p['Preferensi Pekerjaan'], 0) + 1
                    
                    st.write("**Statistik Peserta:**")
                    col1, col2 = st.columns(2)
                    col1.metric("Total Peserta", len(data_peserta))
                    col2.metric("Rasio Peserta:Kapasitas", f"{len(data_peserta)}/{total_kapasitas}")
                    
                    st.write("**Distribusi Preferensi:**")
                    st.write(f"- Umum: {preferensi_counts.get('Umum', 0)}")
                    st.write(f"- Bedah: {preferensi_counts.get('Bedah', 0)}")
                    
                    # Analisis potensi match
                    umum_preferensi = preferensi_counts.get("Umum", 0)
                    bedah_preferensi = preferensi_counts.get("Bedah", 0)
                    
                    umum_kapasitas = sum(w['Kapasitas Optimal'] for w in data_wahana if w['Kategori Pekerjaan'] == "Umum")
                    bedah_kapasitas = sum(w['Kapasitas Optimal'] for w in data_wahana if w['Kategori Pekerjaan'] == "Bedah")
                    
                    st.write("**Potensi Kecocokan:**")
                    st.write(f"- Preferensi Umum vs Kapasitas Umum: {umum_preferensi}/{umum_kapasitas} ({umum_preferensi-umum_kapasitas:+d})")
                    st.write(f"- Preferensi Bedah vs Kapasitas Bedah: {bedah_preferensi}/{bedah_kapasitas} ({bedah_preferensi-bedah_kapasitas:+d})")
                    
                    # Tampilkan tabel data wahana dan peserta
                    st.write("**Data Wahana:**")
                    st.dataframe(pd.DataFrame(data_wahana))
                    
                    st.write("**Data Peserta:**")
                    st.dataframe(pd.DataFrame(data_peserta))
            
            if st.button("Simpan Data Manual"):
                if data_wahana and data_peserta:
                    if st.session_state.sistem.input_data_manual(data_wahana, data_peserta):
                        st.session_state.data_loaded = True
                        st.success("Data manual berhasil disimpan!")
                else:
                    st.error("Data wahana atau peserta kosong. Mohon lengkapi data terlebih dahulu.")
    
    with tab2:
        st.header("Penjadwalan Awal")
        
        if not st.session_state.data_loaded:
            st.warning("Silakan input data terlebih dahulu di tab Input Data")
        else:
            if st.button("Lakukan Penjadwalan Awal"):
                with st.spinner('Sedang melakukan penjadwalan awal...'):
                    try:
                        penempatan_hasil = st.session_state.sistem.penjadwalan_awal()
                        st.session_state.penjadwalan_done = True
                        
                        st.success("Penjadwalan awal berhasil dilakukan!")
                        
                        # Tampilkan hasil
                        st.subheader("Distribusi Peserta per Wahana (Awal)")
                        distribusi = pd.Series(penempatan_hasil).value_counts().reset_index()
                        distribusi.columns = ['Nama Wahana', 'Jumlah Peserta']
                        st.bar_chart(distribusi.set_index('Nama Wahana'))
                        
                        # Simpan hasil di session state
                        st.session_state.distribusi_awal = distribusi
                        
                        if hasattr(st.session_state.sistem, 'peserta_tidak_tertempatkan') and st.session_state.sistem.peserta_tidak_tertempatkan:
                            st.warning(f"{len(st.session_state.sistem.peserta_tidak_tertempatkan)} peserta tidak dapat ditempatkan karena kapasitas tidak mencukupi.")
                    except Exception as e:
                        st.error(f"Gagal melakukan penjadwalan: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())
            
            if st.session_state.penjadwalan_done:
                st.subheader("Detail Penempatan Awal")
                
                # Buat DataFrame untuk penempatan awal
                hasil_awal = pd.DataFrame({
                    'ID Peserta': list(st.session_state.sistem.penempatan_awal.keys()),
                    'Nama Wahana': list(st.session_state.sistem.penempatan_awal.values())
                })
                
                # Gabungkan dengan data peserta
                hasil_awal = hasil_awal.merge(
                    st.session_state.sistem.peserta_df,
                    on='ID Peserta'
                )
                
                # Tambahkan informasi wahana (kategori pekerjaan)
                hasil_awal = hasil_awal.merge(
                    st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan']],
                    on='Nama Wahana',
                    how='left'
                )
                
                # Tambahkan kolom match
                hasil_awal['Match'] = hasil_awal['Preferensi Pekerjaan'] == hasil_awal['Kategori Pekerjaan']
                hasil_awal['Match'] = hasil_awal['Match'].map({True: '✅ Match', False: '❌ Tidak Match'})
                
                # Tampilkan tabel dengan informasi lengkap
                st.dataframe(
                    hasil_awal.style.apply(
                        lambda x: ['background-color: #e6ffe6' if x['Match'] == '✅ Match' else 
                                'background-color: #ffe6e6' for _ in x],
                        axis=1
                    ),
                    use_container_width=True
                )
                
                # Tampilkan statistik match
                match_count = hasil_awal['Match'].value_counts()
                match_percent = match_count / len(hasil_awal) * 100
                
                col1, col2 = st.columns(2)
                col1.metric("Total Peserta", len(hasil_awal))
                col2.metric("Total Match", f"{match_count.get('✅ Match', 0)} ({match_percent.get('✅ Match', 0):.1f}%)")
                
                # Tambahkan statistik per wahana
                st.subheader("Statistik Penempatan per Wahana")
                
                # Grup berdasarkan wahana
                wahana_stats = hasil_awal.groupby(['Nama Wahana', 'Kategori Pekerjaan']).agg(
                    Total_Peserta=('ID Peserta', 'count'),
                    Match=('Match', lambda x: (x == '✅ Match').sum()),
                    Tidak_Match=('Match', lambda x: (x == '❌ Tidak Match').sum())
                ).reset_index()
                
                # Hitung persentase match
                wahana_stats['Persentase_Match'] = (wahana_stats['Match'] / wahana_stats['Total_Peserta'] * 100).round(1)
                wahana_stats['Persentase_Match'] = wahana_stats['Persentase_Match'].map('{:.1f}%'.format)
                
                # Tampilkan tabel statistik
                st.dataframe(
                    wahana_stats.style.background_gradient(subset=['Match'], cmap='Greens'),
                    use_container_width=True
                )
                
                # Tambahkan download button untuk hasil penjadwalan
                csv = hasil_awal.to_csv(index=False)
                st.download_button(
                    label="📥 Download Hasil Penjadwalan",
                    data=csv,
                    file_name="hasil_penjadwalan_awal.csv",
                    mime="text/csv",
                )
    
    with tab3:
        st.header("Simulasi Gangguan dan Penyesuaian")
        
        if not st.session_state.penjadwalan_done:
            st.warning("Silakan lakukan penjadwalan awal terlebih dahulu di tab Penjadwalan Awal")
        else:
            if st.button("Simulasikan Gangguan"):
                with st.spinner('Sedang mensimulasikan gangguan...'):
                    try:
                        st.session_state.sistem.simulasikan_gangguan()
                        st.session_state.gangguan_done = True
                        
                        st.success("Simulasi gangguan berhasil dilakukan!")
                        
                        # Tampilkan status wahana setelah gangguan
                        st.subheader("Status Wahana Setelah Gangguan")
                        status_wahana = st.session_state.sistem.wahana_df[['Nama Wahana', 'Status Gangguan']]
                        st.dataframe(status_wahana)
                        
                        # Visualisasi status
                        st.subheader("Distribusi Status Wahana")
                        status_counts = status_wahana['Status Gangguan'].value_counts()
                        st.bar_chart(status_counts)
                    except Exception as e:
                        st.error(f"Gagal mensimulasikan gangguan: {str(e)}")
            
            if st.session_state.gangguan_done:
                if st.button("Lakukan Penyesuaian Penempatan"):
                    with st.spinner('Sedang menyesuaikan penempatan...'):
                        try:
                            penempatan_akhir = st.session_state.sistem.redistribusi_adaptif()
                            st.session_state.penyesuaian_done = True
                            
                            st.success("Penyesuaian penempatan berhasil dilakukan!")
                            
                            # Tampilkan hasil
                            st.subheader("Distribusi Peserta per Wahana (Setelah Penyesuaian)")
                            distribusi_akhir = pd.Series(penempatan_akhir.values()).value_counts().reset_index()
                            distribusi_akhir.columns = ['Nama Wahana', 'Jumlah Peserta']
                            st.bar_chart(distribusi_akhir.set_index('Nama Wahana'))
                            
                            # Simpan hasil di session state
                            st.session_state.distribusi_akhir = distribusi_akhir
                        except Exception as e:
                            st.error(f"Gagal melakukan penyesuaian: {str(e)}")
    
    with tab4:
        st.header("Hasil Akhir")
        
        if not st.session_state.penyesuaian_done:
            st.warning("Silakan selesaikan proses penjadwalan dan penyesuaian terlebih dahulu")
        else:
            try:
                # Tampilkan statistik penjadwalan awal
                st.subheader("📊 Statistik Penjadwalan Awal")
                statistik_awal = st.session_state.sistem.hitung_statistik_awal()
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Total Peserta", statistik_awal['total_peserta'])
                col2.metric("Match Preferensi", 
                        f"{statistik_awal['kategori_match']} ({statistik_awal['kategori_match']/statistik_awal['total_peserta']:.1%})")
                
                # Tampilkan distribusi status awal wahana
                st.write("### Distribusi Status Wahana Awal")
                df_status_awal = pd.DataFrame.from_dict(statistik_awal['distribusi_status'], orient='index', columns=['Jumlah'])
                st.bar_chart(df_status_awal)
                
                # Komparasi penempatan
                st.subheader("🔄 Komparasi Penempatan Awal vs Akhir")
                komparasi = st.session_state.sistem.bandingkan_penempatan()
                
                st.write(f"**Total Peserta Dipindahkan:** {komparasi['total_pindah']}")
                st.write(f"**Peningkatan Match Preferensi:** {komparasi['peningkatan_match']}")
                
                # Initialize df_pemindahan outside the conditional blocks
                df_pemindahan = pd.DataFrame()
                
                # Grafik komparasi
                st.write("### Aliran Pemindahan Peserta")
                if komparasi['total_pindah'] > 0:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("**Wahana Asal**")
                        df_asal = pd.DataFrame.from_dict(komparasi['wahana_asal'], orient='index', columns=['Jumlah'])
                        st.bar_chart(df_asal)
                    
                    with col2:
                        st.write("**Wahana Tujuan**")
                        df_tujuan = pd.DataFrame.from_dict(komparasi['wahana_tujuan'], orient='index', columns=['Jumlah'])
                        st.bar_chart(df_tujuan)
                    
                    # Tampilkan detail pemindahan
                    st.subheader("📝 Detail Pemindahan Peserta")
                    if komparasi['detail_pemindahan']:
                        df_pemindahan = pd.DataFrame(komparasi['detail_pemindahan'])
                        
                        # Format tampilan
                        df_pemindahan['Match Awal'] = df_pemindahan['Match Awal'].map({1: '✅', 0: '❌'})
                        df_pemindahan['Match Akhir'] = df_pemindahan['Match Akhir'].map({1: '✅', 0: '❌'})
                        
                        # Urutkan berdasarkan peningkatan match
                        df_pemindahan = df_pemindahan.sort_values(by=['Match Akhir', 'Match Awal'], ascending=[False, True])
                        
                        st.dataframe(
                            df_pemindahan.style.apply(
                                lambda x: ['background-color: #e6ffe6' if x['Match Akhir'] == '✅' else 
                                        'background-color: #ffe6e6' for _ in x],
                                axis=1
                            )
                        )
                    else:
                        st.info("Tidak ada peserta yang dipindahkan")
                else:
                    st.info("Tidak ada peserta yang dipindahkan setelah penyesuaian")
                
                # Perbandingan distribusi
                st.subheader("📈 Perbandingan Distribusi Peserta")
                
                # Gabungkan data distribusi awal dan akhir
                distribusi_awal = pd.Series(st.session_state.sistem.penempatan_awal.values()).value_counts().reset_index()
                distribusi_awal.columns = ['Nama Wahana', 'Jumlah Awal']
                
                distribusi_akhir = pd.Series(st.session_state.sistem.penempatan_akhir.values()).value_counts().reset_index()
                distribusi_akhir.columns = ['Nama Wahana', 'Jumlah Akhir']
                
                distribusi_gabung = distribusi_awal.merge(distribusi_akhir, on='Nama Wahana', how='outer').fillna(0)
                distribusi_gabung['Perubahan'] = distribusi_gabung['Jumlah Akhir'] - distribusi_gabung['Jumlah Awal']
                
                # Tampilkan tabel dan grafik
                st.dataframe(distribusi_gabung)
                
                fig = px.bar(distribusi_gabung, 
                            x='Nama Wahana', 
                            y=['Jumlah Awal', 'Jumlah Akhir'],
                            barmode='group',
                            title='Perbandingan Distribusi Peserta',
                            labels={'value': 'Jumlah Peserta', 'variable': 'Tahap'})
                st.plotly_chart(fig)
                
                # Download hasil - only show if we have data to download
                if not df_pemindahan.empty:
                    st.download_button(
                        label="📥 Download Hasil Lengkap",
                        data=df_pemindahan.to_csv(index=False),
                        file_name='komparasi_penempatan.csv',
                        mime='text/csv'
                    )
                else:
                    st.info("Tidak ada data pemindahan untuk diunduh")
                
            except Exception as e:
                st.error(f"Gagal menampilkan hasil akhir: {str(e)}")
                import traceback
                st.code(traceback.format_exc())

if __name__ == "__main__":
    main()