import pandas as pd
import streamlit as st
from collections import defaultdict

class PenjadwalanAdaptif:
    def __init__(self):
        self.wahana_df = None
        self.peserta_df = None
        self.penempatan_awal = None
        self.penempatan_akhir = None
        
    def input_data_manual(self, data_wahana, data_peserta):
        """Menerima input data langsung dari antarmuka"""
        self.wahana_df = pd.DataFrame(data_wahana)
        self.peserta_df = pd.DataFrame(data_peserta)
        
    def hitung_skor_kecocokan(self, peserta, wahana):
        """Reasoning: Menghitung skor kecocokan berdasarkan aturan"""
        skor = 0
        
        # Kesesuaian preferensi pekerjaan
        if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
            skor += 50
            
        # Kesesuaian beban kerja
        pasien_per_peserta = wahana['Pasien Normal'] / wahana['Kapasitas Optimal']
        if 5 <= pasien_per_peserta <= 20:
            skor += 30
        elif pasien_per_peserta < 5:
            skor += 10
        else:
            skor += 5
            
        # Ketersediaan kapasitas
        if wahana['Kapasitas Optimal'] > 0:
            skor += 20
            
        return skor
        
    def penjadwalan_awal(self):
        """Planning: Membuat rencana penempatan awal"""
        if self.wahana_df is None or self.peserta_df is None:
            raise ValueError("Data belum dimuat")
            
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Hanya pertimbangkan wahana stabil untuk penjadwalan awal
        wahana_stabil = self.wahana_df[self.wahana_df['Status Gangguan'] == 'Stabil']
        
        # Searching: Untuk setiap peserta, cari wahana terbaik
        for _, peserta in self.peserta_df.iterrows():
            skor_wahana = []
            
            for _, wahana in wahana_stabil.iterrows():
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    skor = self.hitung_skor_kecocokan(peserta, wahana)
                    skor_wahana.append((wahana['Nama Wahana'], skor))
            
            # Urutkan berdasarkan skor tertinggi
            skor_wahana.sort(key=lambda x: x[1], reverse=True)
            
            # Tempatkan peserta di wahana terbaik yang tersedia
            for wahana, _ in skor_wahana:
                if kapasitas_tersedia[wahana] > 0:
                    penempatan[peserta['ID Peserta']] = wahana
                    kapasitas_tersedia[wahana] -= 1
                    break
        
        self.penempatan_awal = penempatan
        return penempatan
    
    def simulasikan_gangguan(self):
        """Reasoning: Menentukan status wahana berdasarkan kondisi"""
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
    
    def redistribusi_adaptif(self, prioritas="stabilitas"):
        """Planning: Membuat rencana penempatan ulang setelah gangguan"""
        if self.penempatan_awal is None:
            raise ValueError("Penjadwalan awal belum dilakukan")
                
        penempatan_baru = self.penempatan_awal.copy()
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Hitung ulang kapasitas tersedia
        for wahana in kapasitas_tersedia:
            jumlah_peserta = sum(1 for w in penempatan_baru.values() if w == wahana)
            kapasitas_tersedia[wahana] = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Kapasitas Optimal'].values[0] - jumlah_peserta
        
        # Identifikasi peserta di wahana bermasalah
        peserta_dipindahkan = []
        for peserta_id, wahana in penempatan_baru.items():
            status_wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Status Gangguan'].values[0]
            if status_wahana in ['Overload', 'Tutup']:
                peserta_dipindahkan.append(peserta_id)
        
        # Searching: Cari wahana baru untuk peserta yang perlu dipindahkan
        for peserta_id in peserta_dipindahkan:
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana_asal = penempatan_baru[peserta_id]
            
            # Cari wahana yang underutilized atau stabil
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
            
            # Pindahkan peserta jika ada wahana cocok
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
        
        # Gabungkan dengan data peserta dan wahana
        hasil_df = hasil_df.merge(self.peserta_df, on='ID Peserta')
        hasil_df = hasil_df.merge(
            self.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Status Gangguan']], 
            left_on='Nama Wahana Akhir', 
            right_on='Nama Wahana',
            suffixes=('', '_wahana')
        )
        
        return hasil_df