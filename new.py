import pandas as pd
import streamlit as st
from collections import defaultdict
import tempfile
import os
import plotly.express as px
import math
import plotly.graph_objects as go

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
    
    def redistribusi_adaptif(self, prioritas="stabilitas"):
        """
        Redistribusi adaptif dengan prioritas:
        1. Memastikan wahana yang overload menjadi stabil
        2. Mengoptimalkan penempatan untuk peningkatan kecocokan
        3. Menyeimbangkan distribusi skor antar wahana
        """
        if self.penempatan_awal is None:
            raise ValueError("Penjadwalan awal belum dilakukan")
                
        # Salin penempatan awal
        penempatan_baru = self.penempatan_awal.copy()
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Hitung ulang kapasitas tersedia
        for wahana in kapasitas_tersedia:
            jumlah_peserta = sum(1 for w in penempatan_baru.values() if w == wahana)
            kapasitas_tersedia[wahana] = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Kapasitas Optimal'].values[0] - jumlah_peserta
        
        # FASE 1: Identifikasi dan pindahkan peserta dari wahana overload
        peserta_dipindahkan = []
        for peserta_id, wahana in penempatan_baru.items():
            status_wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Status Gangguan'].values[0]
            if status_wahana == 'Overload':
                peserta_dipindahkan.append(peserta_id)
        
        # FASE 2: Cari penempatan baru untuk peserta dari wahana overload
        for peserta_id in peserta_dipindahkan:
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana_asal = penempatan_baru[peserta_id]
            
            # Cari wahana yang underutilized atau stabil
            wahana_cocok = self.wahana_df[
                (self.wahana_df['Status Gangguan'].isin(['Underutilized', 'Stabil'])) & 
                (self.wahana_df['Nama Wahana'] != wahana_asal)
            ]
            
            # Hitung skor kecocokan untuk setiap wahana potensial
            skor_wahana = []
            for _, wahana in wahana_cocok.iterrows():
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                    skor_wahana.append((wahana['Nama Wahana'], skor))
            
            # Pilih wahana dengan skor tertinggi
            if skor_wahana:
                skor_wahana.sort(key=lambda x: x[1], reverse=True)
                wahana_baru = skor_wahana[0][0]
                penempatan_baru[peserta_id] = wahana_baru
                kapasitas_tersedia[wahana_baru] -= 1
                kapasitas_tersedia[wahana_asal] += 1
        
        # FASE 3: Optimasi untuk meningkatkan skor kecocokan global
        # Hitung skor per wahana saat ini
        skor_per_wahana = defaultdict(list)
        for peserta_id, wahana_nama in penempatan_baru.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
            skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
            skor_per_wahana[wahana_nama].append(skor)
        
        # Hitung rata-rata per wahana
        rata_rata_per_wahana = {
            wahana: sum(skor_list) / len(skor_list) if skor_list else 0
            for wahana, skor_list in skor_per_wahana.items()
        }
        
        # Lakukan penyeimbangan skor dengan mempertimbangkan preferensi peserta
        if rata_rata_per_wahana:
            # Identifikasi wahana dengan skor rendah dan tinggi
            wahana_sorted = sorted(rata_rata_per_wahana.items(), key=lambda x: x[1])
            wahana_skor_rendah = [w[0] for w in wahana_sorted[:len(wahana_sorted)//3]]
            wahana_skor_tinggi = [w[0] for w in wahana_sorted[-len(wahana_sorted)//3:]]
            
            # Coba pindahkan peserta untuk menyeimbangkan skor
            for peserta_id, wahana_nama in list(penempatan_baru.items()):
                # Hanya pertimbangkan peserta di wahana dengan skor tinggi
                if wahana_nama not in wahana_skor_tinggi:
                    continue
                    
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                skor_asal = self.hitung_skor_kecocokan_baru(
                    peserta, 
                    self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0].to_dict()
                )
                
                # Cek wahana skor rendah yang masih punya kapasitas
                for wahana_target in wahana_skor_rendah:
                    if kapasitas_tersedia[wahana_target] <= 0:
                        continue
                        
                    wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_target].iloc[0]
                    if wahana_data['Status Gangguan'] == 'Overload':
                        continue
                        
                    # Hitung skor di wahana target
                    skor_target = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                    
                    # Pindahkan jika skor target minimal 80% dari skor asal
                    if skor_target >= skor_asal * 0.8:
                        # Simulasi perubahan skor
                        new_scores = rata_rata_per_wahana.copy()
                        
                        # Update skor wahana asal
                        asal_scores = skor_per_wahana[wahana_nama].copy()
                        asal_scores.remove(skor_asal)
                        new_scores[wahana_nama] = sum(asal_scores) / len(asal_scores) if asal_scores else 0
                        
                        # Update skor wahana target
                        target_scores = skor_per_wahana[wahana_target].copy()
                        target_scores.append(skor_target)
                        new_scores[wahana_target] = sum(target_scores) / len(target_scores)
                        
                        # Hitung deviasi saat ini vs setelah perubahan
                        current_values = list(rata_rata_per_wahana.values())
                        new_values = list(new_scores.values())
                        
                        mean_current = sum(current_values)/len(current_values)
                        mean_new = sum(new_values)/len(new_values)
                        
                        std_current = math.sqrt(sum((x - mean_current)**2 for x in current_values) / len(current_values))
                        std_new = math.sqrt(sum((x - mean_new)**2 for x in new_values) / len(new_values))
                        
                        # Jika deviasi berkurang, lakukan pemindahan
                        if std_new < std_current:
                            penempatan_baru[peserta_id] = wahana_target
                            kapasitas_tersedia[wahana_target] -= 1
                            kapasitas_tersedia[wahana_nama] += 1
                            
                            # Update tracking skor
                            rata_rata_per_wahana = new_scores
                            skor_per_wahana[wahana_nama] = asal_scores
                            skor_per_wahana[wahana_target] = target_scores
                            break
        
        # Simpan hasil redistribusi
        self.penempatan_akhir = penempatan_baru
        
        # Hitung kualitas penjadwalan akhir
        self.hitung_rata_rata_skor()
        
        return penempatan_baru
    
    def penjadwalan_stabil_kapasitas(self):
        """
        Algoritma penjadwalan awal dengan prioritas kestabilan dan memenuhi kapasitas.
        Fokus pada:
        1. Menjaga rasio pasien:peserta dalam rentang stabil (5-20)
        2. Memaksimalkan pengisian kapasitas wahana
        3. Mempertimbangkan preferensi peserta sebagai faktor tambahan
        """
        # Inisialisasi
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        peserta_belum_ditempatkan = list(self.peserta_df['ID Peserta'])
        
        # FASE 1: Stabilisasi wahana Underutilized dan Overload
        # Prioritaskan wahana berdasarkan urgensi stabilisasi
        wahana_prioritas = self.wahana_df.copy()
        
        # Tambahkan kolom skor prioritas
        wahana_prioritas['Skor_Prioritas'] = wahana_prioritas.apply(
            lambda x: 3 if x['Status Gangguan'] == 'Underutilized' else 
                    2 if x['Status Gangguan'] == 'Overload' else 
                    1 if x['Status Gangguan'] == 'Stabil' else 0, axis=1
        )
        
        # Urutkan berdasarkan prioritas dan pasien normal (untuk konsistensi)
        wahana_prioritas = wahana_prioritas.sort_values(
            by=['Skor_Prioritas', 'Pasien Normal'],
            ascending=[False, False]
        )
        
        # Untuk setiap wahana, hitung jumlah peserta yang dibutuhkan untuk mencapai stabilitas
        for _, wahana in wahana_prioritas.iterrows():
            # Skip wahana yang tutup
            if wahana['Status Gangguan'] == 'Tutup' or wahana['Pasien Normal'] == 0:
                continue
                
            # Hitung jumlah peserta ideal untuk stabilisasi
            pasien_count = wahana['Pasien Normal']
            
            # Target rasio berdasarkan status gangguan
            if wahana['Status Gangguan'] == 'Underutilized':
                # Untuk underutilized, targetkan rasio sekitar 5 (batas bawah stabil)
                target_ratio = 5
            elif wahana['Status Gangguan'] == 'Overload':
                # Untuk overload, targetkan rasio sekitar 20 (batas atas stabil)
                target_ratio = 20
            else:  # Stabil
                # Untuk stabil, pertahankan di tengah range (10)
                target_ratio = 10
                
            jumlah_ideal = max(1, round(pasien_count / target_ratio))
            
            # Batasi dengan kapasitas tersedia
            jumlah_ideal = min(jumlah_ideal, wahana['Kapasitas Optimal'])
            kebutuhan = jumlah_ideal
            
            # Cari peserta yang cocok berdasarkan preferensi terlebih dahulu
            peserta_cocok = []
            peserta_tidak_cocok = []
            
            for peserta_id in peserta_belum_ditempatkan:
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                
                # Hitung skor kecocokan
                skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                
                # Bagi berdasarkan preferensi
                if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
                    peserta_cocok.append((peserta_id, skor))
                else:
                    peserta_tidak_cocok.append((peserta_id, skor))
            
            # Urutkan berdasarkan skor kecocokan
            peserta_cocok.sort(key=lambda x: x[1], reverse=True)
            peserta_tidak_cocok.sort(key=lambda x: x[1], reverse=True)
            
            # Tempatkan peserta dengan preferensi cocok terlebih dahulu
            peserta_terpilih = 0
            for peserta_id, _ in peserta_cocok:
                if peserta_terpilih < kebutuhan and kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    penempatan[peserta_id] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    peserta_belum_ditempatkan.remove(peserta_id)
                    peserta_terpilih += 1
            
            # Jika masih perlu, tambahkan peserta dengan preferensi tidak cocok
            for peserta_id, _ in peserta_tidak_cocok:
                if peserta_terpilih < kebutuhan and kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    penempatan[peserta_id] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    peserta_belum_ditempatkan.remove(peserta_id)
                    peserta_terpilih += 1
        
        # FASE 2: Optimalkan sisa kapasitas untuk wahana yang masih memiliki ruang
        # Prioritaskan wahana stabil yang belum terisi kapasitasnya
        for _, wahana in self.wahana_df.iterrows():
            # Skip jika wahana penuh atau tidak ada pasien
            if kapasitas_tersedia[wahana['Nama Wahana']] <= 0 or wahana['Pasien Normal'] == 0:
                continue
                
            # Cari peserta dengan preferensi cocok terlebih dahulu
            peserta_cocok = []
            peserta_tidak_cocok = []
            
            for peserta_id in peserta_belum_ditempatkan:
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                
                if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
                    peserta_cocok.append((peserta_id, skor))
                else:
                    peserta_tidak_cocok.append((peserta_id, skor))
                    
            # Urutkan berdasarkan skor
            peserta_cocok.sort(key=lambda x: x[1], reverse=True)
            peserta_tidak_cocok.sort(key=lambda x: x[1], reverse=True)
            
            # Isi sampai kapasitas penuh atau semua peserta ditempatkan
            for peserta_id, _ in peserta_cocok + peserta_tidak_cocok:
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                    penempatan[peserta_id] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    peserta_belum_ditempatkan.remove(peserta_id)
                else:
                    break
        
        # Simpan hasil
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = peserta_belum_ditempatkan
        
        # Hitung kualitas penjadwalan
        self.hitung_rata_rata_skor()
        self.hitung_deviasi_kecocokan()
        
        return penempatan

    def redistribusi_preferensi_merata(self):
        """
        Redistribusi dengan fokus keseimbangan skor kecocokan antar wahana.
        Algoritma akan mencoba menyeimbangkan skor antar wahana dengan memindahkan
        peserta dari wahana dengan skor tinggi ke wahana dengan skor rendah,
        sambil tetap mempertahankan kestabilan dan mempertimbangkan preferensi.
        """
        if self.penempatan_awal is None:
            raise ValueError("Penjadwalan awal belum dilakukan")
                
        # Salin penempatan awal
        penempatan_baru = self.penempatan_awal.copy()
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Hitung ulang kapasitas tersedia
        for wahana in kapasitas_tersedia:
            jumlah_peserta = sum(1 for w in penempatan_baru.values() if w == wahana)
            kapasitas_tersedia[wahana] = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana]['Kapasitas Optimal'].values[0] - jumlah_peserta
        
        # FASE 1: Hitung skor kecocokan saat ini untuk setiap wahana
        skor_per_wahana = defaultdict(list)
        for peserta_id, wahana_nama in penempatan_baru.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
            skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
            skor_per_wahana[wahana_nama].append((peserta_id, skor))
        
        # Hitung rata-rata skor per wahana
        rata_rata_per_wahana = {}
        for wahana_nama, skor_list in skor_per_wahana.items():
            if skor_list:
                rata_rata_per_wahana[wahana_nama] = sum(s[1] for s in skor_list) / len(skor_list)
            else:
                rata_rata_per_wahana[wahana_nama] = 0
        
        # Urutkan wahana berdasarkan rata-rata skor
        wahana_sorted = sorted(rata_rata_per_wahana.items(), key=lambda x: x[1])
        
        # Identifikasi wahana dengan skor rendah dan tinggi (bagi menjadi 3 kelompok)
        wahana_skor_rendah = [w[0] for w in wahana_sorted[:len(wahana_sorted)//3]]
        wahana_skor_tinggi = [w[0] for w in wahana_sorted[-len(wahana_sorted)//3:]]
        
        # FASE 2: Iterasi untuk menyeimbangkan skor antar wahana
        max_iterasi = min(50, len(self.peserta_df) // 2)  # Batasi jumlah iterasi
        for iterasi in range(max_iterasi):
            perbaikan_dilakukan = False
            
            # Coba tukar peserta antara wahana skor tinggi dan rendah
            for wahana_tinggi in wahana_skor_tinggi:
                if not perbaikan_dilakukan:
                    # Dapatkan daftar peserta di wahana skor tinggi
                    peserta_di_wahana_tinggi = [p for p, w in penempatan_baru.items() if w == wahana_tinggi]
                    
                    # Urutkan berdasarkan kontribusi terhadap skor tinggi
                    peserta_scores = []
                    for peserta_id in peserta_di_wahana_tinggi:
                        peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                        wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_tinggi].iloc[0]
                        skor = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                        peserta_scores.append((peserta_id, skor))
                    
                    # Urutkan dari skor terendah (kandidat untuk dipindah)
                    peserta_scores.sort(key=lambda x: x[1])
                    
                    # Coba pindahkan peserta ke wahana skor rendah
                    for peserta_id, skor_asal in peserta_scores:
                        if perbaikan_dilakukan:
                            break
                            
                        peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                        
                        # Cek setiap wahana skor rendah yang masih punya kapasitas
                        for wahana_rendah in wahana_skor_rendah:
                            if kapasitas_tersedia[wahana_rendah] <= 0:
                                continue
                                
                            wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_rendah].iloc[0]
                            
                            # Skip jika status wahana tidak stabil atau underutilized
                            if wahana_data['Status Gangguan'] not in ['Stabil', 'Underutilized']:
                                continue
                                
                            # Hitung skor di wahana target
                            skor_target = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                            
                            # Simulasi perubahan rata-rata skor
                            # Untuk wahana asal
                            skor_list_asal = [s[1] for s in skor_per_wahana[wahana_tinggi] if s[0] != peserta_id]
                            new_avg_asal = sum(skor_list_asal) / len(skor_list_asal) if skor_list_asal else 0
                            
                            # Untuk wahana target
                            skor_list_target = [s[1] for s in skor_per_wahana[wahana_rendah]] + [skor_target]
                            new_avg_target = sum(skor_list_target) / len(skor_list_target)
                            
                            # Hitung standar deviasi sebelum perubahan
                            values_current = list(rata_rata_per_wahana.values())
                            mean_current = sum(values_current) / len(values_current)
                            std_current = (sum((v - mean_current) ** 2 for v in values_current) / len(values_current)) ** 0.5
                            
                            # Hitung standar deviasi setelah perubahan
                            new_values = rata_rata_per_wahana.copy()
                            new_values[wahana_tinggi] = new_avg_asal
                            new_values[wahana_rendah] = new_avg_target
                            values_new = list(new_values.values())
                            mean_new = sum(values_new) / len(values_new)
                            std_new = (sum((v - mean_new) ** 2 for v in values_new) / len(values_new)) ** 0.5
                            
                            # Kriteria untuk pemindahan:
                            # 1. Standar deviasi berkurang (lebih merata)
                            # 2. Skor di target minimal 75% dari skor asal atau preferensi cocok
                            preferensi_cocok = peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan']
                            
                            if std_new < std_current and (skor_target >= skor_asal * 0.75 or preferensi_cocok):
                                # Lakukan pemindahan
                                penempatan_baru[peserta_id] = wahana_rendah
                                kapasitas_tersedia[wahana_rendah] -= 1
                                kapasitas_tersedia[wahana_tinggi] += 1
                                
                                # Update tracking skor
                                skor_per_wahana[wahana_tinggi] = [(p, s) for p, s in skor_per_wahana[wahana_tinggi] if p != peserta_id]
                                skor_per_wahana[wahana_rendah].append((peserta_id, skor_target))
                                
                                # Update rata-rata
                                rata_rata_per_wahana[wahana_tinggi] = new_avg_asal
                                rata_rata_per_wahana[wahana_rendah] = new_avg_target
                                
                                perbaikan_dilakukan = True
                                break
                                
            # Jika tidak ada perbaikan yang bisa dilakukan, hentikan iterasi
            if not perbaikan_dilakukan:
                break
        
        # Simpan hasil redistribusi
        self.penempatan_akhir = penempatan_baru
        
        # Hitung kualitas penjadwalan akhir
        self.hitung_rata_rata_skor()
        
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
    
    def hitung_skor_kecocokan_baru(self, peserta, wahana):
        """Menghitung skor kecocokan dengan parameter yang lebih komprehensif"""
        skor = 0
        
        # Kesesuaian preferensi pekerjaan (40% bobot)
        if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
            skor += 40
            
        # Kesesuaian beban kerja (30% bobot)
        if wahana['Kapasitas Optimal'] > 0:
            pasien_per_peserta = wahana['Pasien Normal'] / wahana['Kapasitas Optimal']
            # Fungsi keanggotaan fuzzy untuk beban kerja ideal
            if 10 <= pasien_per_peserta <= 15:  # Range sangat ideal
                skor += 30
            elif 5 <= pasien_per_peserta < 10 or 15 < pasien_per_peserta <= 20:  # Range cukup ideal
                skor += 20
            elif pasien_per_peserta < 5:  # Underutilized
                skor += 10
            else:  # Overload
                skor += 0
                
        # Ketersediaan kapasitas (20% bobot)
        kapasitas_terisi = sum(1 for w in self.penempatan_awal.values() if w == wahana['Nama Wahana']) if self.penempatan_awal else 0
        kapasitas_sisa = wahana['Kapasitas Optimal'] - kapasitas_terisi
        kapasitas_ratio = kapasitas_sisa / wahana['Kapasitas Optimal'] if wahana['Kapasitas Optimal'] > 0 else 0
        skor += 20 * kapasitas_ratio  # Semakin banyak kapasitas tersisa, semakin tinggi skor
        
        # Prioritas stabilisasi (10% bobot)
        status = wahana['Status Gangguan']
        if status == 'Underutilized':
            skor += 10  # Prioritaskan wahana yang kekurangan peserta
        elif status == 'Stabil':
            skor += 5   # Wahana stabil tetap dapat prioritas menengah
        else:  # Overload atau Tutup
            skor += 0   # Tidak diprioritaskan
        
        return skor
    
    def penjadwalan_adaptif_dua_fase(self):
        """Algoritma penjadwalan dua fase: stabilisasi dan optimasi"""
        # Inisialisasi
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        peserta_belum_ditempatkan = list(self.peserta_df['ID Peserta'])
        
        # FASE 1: STABILISASI - Prioritaskan wahana Underutilized
        wahana_underutilized = self.wahana_df[
            (self.wahana_df['Status Gangguan'] == 'Underutilized') &
            (self.wahana_df['Pasien Gangguan'] > 0)
        ].sort_values(by='Kapasitas Optimal', ascending=False)
        
        # Stabilkan wahana Underutilized terlebih dahulu
        for _, wahana in wahana_underutilized.iterrows():
            # Hitung berapa peserta yang dibutuhkan untuk mencapai status stabil
            # Gunakan pasien gangguan untuk simulasi
            pasien_count = wahana['Pasien Gangguan']
            current_count = sum(1 for w in penempatan.values() if w == wahana['Nama Wahana'])
            
            target_ratio = 10  # Target rasio pasien:peserta = 10 (ditengah range stabil 5-20)
            needed_peserta = max(1, int(pasien_count / target_ratio)) - current_count
            
            # Batasi dengan kapasitas tersedia
            needed_peserta = min(needed_peserta, kapasitas_tersedia[wahana['Nama Wahana']])
            
            # Pilih peserta yang paling cocok
            for _ in range(needed_peserta):
                if not peserta_belum_ditempatkan:
                    break
                    
                skor_peserta = []
                for peserta_id in peserta_belum_ditempatkan:
                    peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                    skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                    skor_peserta.append((peserta_id, skor))
                
                # Pilih peserta dengan skor tertinggi
                skor_peserta.sort(key=lambda x: x[1], reverse=True)
                if skor_peserta:
                    best_peserta = skor_peserta[0][0]
                    penempatan[best_peserta] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    peserta_belum_ditempatkan.remove(best_peserta)
        
        # FASE 2: OPTIMASI - Tempatkan peserta yang tersisa
        wahana_stabil = self.wahana_df[
            (self.wahana_df['Status Gangguan'] == 'Stabil') &
            (self.wahana_df['Pasien Gangguan'] > 0)
        ].sort_values(by='Kapasitas Optimal', ascending=False)
        
        # Distribusi ke wahana stabil
        for _, wahana in wahana_stabil.iterrows():
            while kapasitas_tersedia[wahana['Nama Wahana']] > 0 and peserta_belum_ditempatkan:
                skor_peserta = []
                for peserta_id in peserta_belum_ditempatkan:
                    peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                    skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                    skor_peserta.append((peserta_id, skor))
                
                # Pilih peserta dengan skor tertinggi
                skor_peserta.sort(key=lambda x: x[1], reverse=True)
                if skor_peserta:
                    best_peserta = skor_peserta[0][0]
                    penempatan[best_peserta] = wahana['Nama Wahana']
                    kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    peserta_belum_ditempatkan.remove(best_peserta)
        
        # FASE 3: DISTRIBUSI LANJUTAN - Tempatkan sisa peserta di wahana apa pun
        for peserta_id in peserta_belum_ditempatkan.copy():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            
            # Cari wahana yang masih tersedia kapasitas
            skor_wahana = []
            for _, wahana in self.wahana_df.iterrows():
                if kapasitas_tersedia[wahana['Nama Wahana']] > 0 and wahana['Pasien Gangguan'] > 0:
                    skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                    skor_wahana.append((wahana['Nama Wahana'], skor))
            
            # Pilih wahana dengan skor tertinggi
            skor_wahana.sort(key=lambda x: x[1], reverse=True)
            if skor_wahana:
                best_wahana = skor_wahana[0][0]
                penempatan[peserta_id] = best_wahana
                kapasitas_tersedia[best_wahana] -= 1
                peserta_belum_ditempatkan.remove(peserta_id)
        
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = peserta_belum_ditempatkan
        
        # Hitung rata-rata skor kecocokan
        self.hitung_rata_rata_skor()
        
        return penempatan
    
    def hitung_rata_rata_skor(self):
        """Menghitung rata-rata skor kecocokan untuk evaluasi kualitas penjadwalan"""
        if not self.penempatan_awal:
            return {"total": 0, "per_wahana": {}}
        
        total_skor = 0
        skor_per_wahana = defaultdict(list)
        jumlah_penempatan = 0
        
        for peserta_id, wahana_nama in self.penempatan_awal.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
            
            skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
            total_skor += skor
            skor_per_wahana[wahana_nama].append(skor)
            jumlah_penempatan += 1
        
        # Hitung rata-rata keseluruhan
        rata_rata_skor = total_skor / jumlah_penempatan if jumlah_penempatan > 0 else 0
        
        # Hitung rata-rata per wahana
        rata_rata_per_wahana = {
            wahana: sum(skor_list) / len(skor_list) 
            for wahana, skor_list in skor_per_wahana.items()
        }
        
        self.kualitas_penjadwalan = {
            "rata_rata_skor": rata_rata_skor,
            "per_wahana": rata_rata_per_wahana,
            "interpretasi": self.interpretasi_skor(rata_rata_skor)
        }
        
        return self.kualitas_penjadwalan

    def interpretasi_skor(self, skor):
        """Memberikan interpretasi kualitas penjadwalan berdasarkan skor rata-rata"""
        if skor >= 80:
            return "Sangat Baik - Preferensi dan beban kerja terpenuhi dengan optimal"
        elif skor >= 70:
            return "Baik - Sebagian besar preferensi terpenuhi dengan beban kerja seimbang"
        elif skor >= 60:
            return "Cukup - Ada keseimbangan antara preferensi dan beban kerja"
        elif skor >= 50:
            return "Kurang Optimal - Beberapa preferensi tidak terpenuhi atau beban kerja tidak seimbang"
        else:
            return "Perlu Perbaikan - Banyak ketidaksesuaian preferensi dan beban kerja tidak merata"
        
    def penjadwalan_distribusi_merata(self):
        """Algoritma penjadwalan dengan distribusi kecocokan lebih merata antar wahana"""
        # Inisialisasi
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Tracking skor kecocokan per wahana untuk pemerataan
        skor_wahana = {wahana: [] for wahana in kapasitas_tersedia.keys()}
        
        # Hitung semua skor kecocokan untuk semua pasangan peserta-wahana
        skor_kecocokan_global = []
        
        for _, peserta in self.peserta_df.iterrows():
            for _, wahana in self.wahana_df.iterrows():
                skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                skor_kecocokan_global.append({
                    'ID Peserta': peserta['ID Peserta'],
                    'Nama Wahana': wahana['Nama Wahana'],
                    'Skor': skor,
                    'Preferensi Match': peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']
                })
        
        # Set untuk melacak peserta yang sudah ditempatkan
        peserta_ditempatkan = set()
        wahana_terisi = {wahana: 0 for wahana in kapasitas_tersedia.keys()}
        
        # Fase 1: Penempatan awal untuk memastikan semua wahana mendapat minimal 1 peserta
        # Ini mencegah wahana tetap kosong karena tidak mendapat giliran di algoritma utama
        wahana_belum_terisi = [w for w, count in wahana_terisi.items() if count == 0 and kapasitas_tersedia[w] > 0]
        
        for wahana_nama in wahana_belum_terisi:
            # Cari peserta terbaik untuk wahana ini
            skor_terbaik = []
            for _, peserta in self.peserta_df.iterrows():
                if peserta['ID Peserta'] not in peserta_ditempatkan:
                    wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
                    skor = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                    skor_terbaik.append((peserta['ID Peserta'], skor))
            
            if skor_terbaik:
                # Pilih peserta dengan skor terbaik
                skor_terbaik.sort(key=lambda x: x[1], reverse=True)
                peserta_id = skor_terbaik[0][0]
                skor = skor_terbaik[0][1]
                
                penempatan[peserta_id] = wahana_nama
                kapasitas_tersedia[wahana_nama] -= 1
                wahana_terisi[wahana_nama] += 1
                peserta_ditempatkan.add(peserta_id)
                skor_wahana[wahana_nama].append(skor)
        
        # Fase 2: Distribusi berdasarkan pemerataan skor
        deviasi_log = []
        # Lakukan iterasi sampai semua peserta ditempatkan atau kapasitas habis
        iterasi_max = len(self.peserta_df) * 2  # Batasi jumlah iterasi untuk menghindari infinite loop
        iterasi = 0
        
        peserta_tersisa = [p for p in self.peserta_df['ID Peserta'] if p not in peserta_ditempatkan]
        
        while peserta_tersisa and any(k > 0 for k in kapasitas_tersedia.values()) and iterasi < iterasi_max:
            iterasi += 1
            
            # Hitung rata-rata skor saat ini untuk setiap wahana
            avg_skor_wahana = {}
            for wahana, skor_list in skor_wahana.items():
                if skor_list:  # Jika ada skor
                    avg_skor_wahana[wahana] = sum(skor_list) / len(skor_list)
                else:  # Jika belum ada peserta
                    avg_skor_wahana[wahana] = 0
            
            # Hitung dan log deviasi setiap 10 iterasi
            if iterasi % 10 == 0 or iterasi == 1:
                # Hitung deviasi saat ini
                current_deviasi = 0
                if avg_skor_wahana:
                    values = [v for v in avg_skor_wahana.values() if v > 0]
                    if values:
                        mean = sum(values) / len(values)
                        current_deviasi = (sum((x - mean) ** 2 for x in values) / len(values)) ** 0.5 if len(values) > 1 else 0
                
                deviasi_log.append((iterasi, current_deviasi))
            
            # Hitung global mean dan standard deviation dari skor rata-rata wahana
            if avg_skor_wahana:
                values = [v for v in avg_skor_wahana.values() if v > 0]
                if values:
                    global_mean = sum(values) / len(values)
                    global_stddev = (sum((x - global_mean) ** 2 for x in values) / len(values)) ** 0.5 if len(values) > 1 else 0
                else:
                    global_mean = 0
                    global_stddev = 0
            else:
                global_mean = 0
                global_stddev = 0
            
            # Cari pasangan (peserta, wahana) berikutnya yang optimal untuk keseimbangan
            best_pair = None
            best_score = -float('inf')
            
            for peserta_id in peserta_tersisa[:min(len(peserta_tersisa), 30)]:  # Batasi pencarian untuk performa
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                
                for wahana_nama, kapasitas in kapasitas_tersedia.items():
                    if kapasitas <= 0:  # Skip wahana yang sudah penuh
                        continue
                    
                    wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
                    base_skor = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                    
                    # Faktor pengisian kapasitas - prioritaskan wahana yang masih kosong
                    kapasitas_faktor = 2.0 * (1 - (wahana_terisi[wahana_nama] / wahana_data['Kapasitas Optimal']))
                    
                    # Faktor keseimbangan skor - simulasikan penempatan ini
                    skor_simulasi = skor_wahana[wahana_nama] + [base_skor]
                    new_avg = sum(skor_simulasi) / len(skor_simulasi)
                    
                    # Hitung efek perubahan pada standar deviasi global
                    # Copy rata-rata skor untuk simulasi
                    simulated_avgs = avg_skor_wahana.copy()
                    simulated_avgs[wahana_nama] = new_avg
                    
                    # Hitung standar deviasi hasil simulasi
                    sim_values = [v for v in simulated_avgs.values() if v > 0]
                    if sim_values:
                        sim_mean = sum(sim_values) / len(sim_values)
                        sim_stddev = (sum((x - sim_mean) ** 2 for x in sim_values) / len(sim_values)) ** 0.5 if len(sim_values) > 1 else 0
                    else:
                        sim_stddev = 0
                    
                    # Faktor perbaikan standar deviasi (semakin berkurang deviasi, semakin baik)
                    stddev_improvement = global_stddev - sim_stddev if global_stddev > 0 else 0
                    
                    # Faktor keseimbangan: menghargai penempatan yang mendekatkan rata-rata wahana ke mean global
                    current_distance = abs(avg_skor_wahana.get(wahana_nama, 0) - global_mean) if avg_skor_wahana.get(wahana_nama, 0) > 0 else abs(0 - global_mean)
                    new_distance = abs(new_avg - global_mean)
                    balance_factor = current_distance - new_distance  # Positif jika semakin mendekati mean global
                    
                    # Faktor preferensi peserta tetap dipertimbangkan
                    preferensi_faktor = 1.5 if peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan'] else 1.0
                    
                    # Perhitungan skor akhir dengan prioritas lebih tinggi pada keseimbangan
                    final_score = (
                        base_skor * 0.4 +                 # Skor kecocokan dasar (40%)
                        kapasitas_faktor * 10 +           # Faktor pengisian kapasitas (10-20)
                        balance_factor * 15 +             # Faktor keseimbangan (dampak terhadap mean global) (0-15)
                        stddev_improvement * 25 +         # Faktor perbaikan standar deviasi (0-25)
                        preferensi_faktor * 10            # Faktor preferensi (10-15)
                    )
                    
                    if final_score > best_score:
                        best_score = final_score
                        best_pair = (peserta_id, wahana_nama, base_skor)
            
            # Jika menemukan pasangan optimal, tempatkan peserta
            if best_pair:
                peserta_id, wahana_nama, base_skor = best_pair
                penempatan[peserta_id] = wahana_nama
                kapasitas_tersedia[wahana_nama] -= 1
                wahana_terisi[wahana_nama] += 1
                skor_wahana[wahana_nama].append(base_skor)
                peserta_ditempatkan.add(peserta_id)
                peserta_tersisa.remove(peserta_id)
            else:
                # Jika tidak ada pasangan optimal, keluar dari loop untuk menghindari infinite
                break
        
        # Fase 3: Distribusi sisa peserta (jika masih ada)
        for peserta_id in peserta_tersisa:
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            
            # Cari wahana dengan kapasitas tersisa
            wahana_tersedia = [(w, k) for w, k in kapasitas_tersedia.items() if k > 0]
            if not wahana_tersedia:
                break  # Tidak ada kapasitas tersisa
                
            # Pilih wahana terbaik berdasarkan skor kecocokan tanpa mempertimbangkan keseimbangan
            best_wahana = None
            best_score = -1
            
            for wahana_nama, _ in wahana_tersedia:
                wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
                skor = self.hitung_skor_kecocokan_baru(peserta, wahana_data.to_dict())
                
                # Preferensi masih diutamakan untuk penempatan terakhir
                if peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan']:
                    skor += 20
                    
                if skor > best_score:
                    best_score = skor
                    best_wahana = wahana_nama
            
            if best_wahana:
                penempatan[peserta_id] = best_wahana
                kapasitas_tersedia[best_wahana] -= 1
                wahana_terisi[best_wahana] += 1
                skor_wahana[best_wahana].append(best_score)
                peserta_ditempatkan.add(peserta_id)
        
        # Simpan hasil penjadwalan
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = list(set(self.peserta_df['ID Peserta']) - peserta_ditempatkan)
        
        # Hitung metrik kualitas
        self.hitung_rata_rata_skor()
        self.hitung_deviasi_kecocokan()
        self.deviasi_iterasi_log = deviasi_log
        
        return penempatan
        
    def penjadwalan_prioritas_stabilitas(self):
        """
        Algoritma penjadwalan awal dengan prioritas stabilitas:
        1. Menghitung jumlah peserta optimal untuk setiap wahana agar stabil
        2. Mengassign peserta berdasarkan skor kecocokan tertinggi untuk setiap wahana
        3. Mendistribusikan sisa peserta ke wahana yang masih memiliki kapasitas
        """
        # Inisialisasi
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        peserta_belum_ditempatkan = list(self.peserta_df['ID Peserta'])
        
        # FASE 1: Stabilisasi - Hitung kebutuhan optimal setiap wahana
        kebutuhan_peserta = {}
        for _, wahana in self.wahana_df.iterrows():
            # Hitung jumlah peserta ideal untuk mencapai rasio stabil (antara 5-20)
            pasien_count = wahana['Pasien Normal']
            target_ratio = 10  # Target rasio pasien:peserta = 10 (di tengah range stabil 5-20)
            jumlah_ideal = max(1, round(pasien_count / target_ratio))
            
            # Batasi dengan kapasitas
            jumlah_ideal = min(jumlah_ideal, wahana['Kapasitas Optimal'])
            kebutuhan_peserta[wahana['Nama Wahana']] = jumlah_ideal
        
        # FASE 2: Prioritaskan penempatan untuk mencapai stabilitas
        for nama_wahana, kebutuhan in kebutuhan_peserta.items():
            # Jika wahana tidak butuh peserta (pasien = 0), skip
            if kebutuhan == 0:
                continue
                
            wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == nama_wahana].iloc[0]
            
            # Hitung skor kecocokan untuk semua peserta yang belum ditempatkan
            skor_peserta = []
            for peserta_id in peserta_belum_ditempatkan:
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                skor = self.hitung_skor_kecocokan(peserta, wahana_data)
                skor_peserta.append((peserta_id, skor))
            
            # Urutkan peserta berdasarkan skor tertinggi
            skor_peserta.sort(key=lambda x: x[1], reverse=True)
            
            # Tempatkan peserta sebanyak kebutuhan wahana
            peserta_ditempatkan = 0
            for peserta_id, _ in skor_peserta:
                if peserta_ditempatkan < kebutuhan and kapasitas_tersedia[nama_wahana] > 0:
                    penempatan[peserta_id] = nama_wahana
                    peserta_belum_ditempatkan.remove(peserta_id)
                    kapasitas_tersedia[nama_wahana] -= 1
                    peserta_ditempatkan += 1
                
                # Jika sudah mencapai kebutuhan, stop
                if peserta_ditempatkan >= kebutuhan:
                    break
        
        # FASE 3: Distribusi sisa peserta dengan tetap mempertimbangkan skor kecocokan
        for peserta_id in peserta_belum_ditempatkan.copy():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            
            # Cari wahana dengan kapasitas tersisa
            wahana_tersedia = [(nama, kapasitas) for nama, kapasitas in kapasitas_tersedia.items() if kapasitas > 0]
            
            # Jika tidak ada wahana tersedia, peserta tidak ditempatkan
            if not wahana_tersedia:
                continue
            
            # Hitung skor kecocokan untuk setiap wahana tersedia
            skor_wahana = []
            for nama_wahana, _ in wahana_tersedia:
                wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == nama_wahana].iloc[0]
                skor = self.hitung_skor_kecocokan(peserta, wahana_data)
                skor_wahana.append((nama_wahana, skor))
            
            # Tempatkan di wahana dengan skor tertinggi
            skor_wahana.sort(key=lambda x: x[1], reverse=True)
            if skor_wahana:
                wahana_terbaik = skor_wahana[0][0]
                penempatan[peserta_id] = wahana_terbaik
                kapasitas_tersedia[wahana_terbaik] -= 1
                peserta_belum_ditempatkan.remove(peserta_id)
        
        # Simpan hasil
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = peserta_belum_ditempatkan
        
        # Hitung kualitas penjadwalan
        self.hitung_kualitas_penjadwalan()
        
        return penempatan

    def hitung_kualitas_penjadwalan(self):
        """
        Menghitung kualitas penjadwalan berdasarkan:
        1. Rata-rata skor kecocokan keseluruhan
        2. Rata-rata skor kecocokan per wahana
        3. Deviasi standar skor kecocokan antar wahana
        4. Interpretasi kualitas
        """
        if not self.penempatan_awal:
            return {"total": 0, "per_wahana": {}}
        
        skor_per_wahana = defaultdict(list)
        total_skor = 0
        jumlah_penempatan = 0
        
        for peserta_id, wahana_nama in self.penempatan_awal.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
            
            skor = self.hitung_skor_kecocokan(peserta, wahana)
            total_skor += skor
            skor_per_wahana[wahana_nama].append(skor)
            jumlah_penempatan += 1
        
        # Hitung rata-rata keseluruhan
        rata_rata_skor = total_skor / jumlah_penempatan if jumlah_penempatan > 0 else 0
        
        # Hitung rata-rata per wahana
        rata_rata_per_wahana = {
            wahana: sum(skor_list) / len(skor_list) 
            for wahana, skor_list in skor_per_wahana.items()
        }
        
        # Hitung standar deviasi antar wahana
        nilai_rata_rata = list(rata_rata_per_wahana.values())
        if len(nilai_rata_rata) > 1:
            mean = sum(nilai_rata_rata) / len(nilai_rata_rata)
            standar_deviasi = math.sqrt(sum((x - mean) ** 2 for x in nilai_rata_rata) / len(nilai_rata_rata))
        else:
            standar_deviasi = 0
        
        # Interpretasi kualitas
        interpretasi = self.interpretasi_kualitas(rata_rata_skor, standar_deviasi)
        
        self.kualitas_penjadwalan = {
            "rata_rata_skor": rata_rata_skor,
            "per_wahana": rata_rata_per_wahana,
            "standar_deviasi": standar_deviasi,
            "interpretasi": interpretasi
        }
        
        return self.kualitas_penjadwalan

    def interpretasi_kualitas(self, rata_rata_skor, standar_deviasi):
        """Memberikan interpretasi kualitas penjadwalan berdasarkan skor rata-rata dan standar deviasi"""
        # Interpretasi berdasarkan rata-rata skor
        if rata_rata_skor >= 80:
            interpretasi_skor = "Sangat Baik"
        elif rata_rata_skor >= 70:
            interpretasi_skor = "Baik"
        elif rata_rata_skor >= 60:
            interpretasi_skor = "Cukup"
        elif rata_rata_skor >= 50:
            interpretasi_skor = "Kurang Optimal"
        else:
            interpretasi_skor = "Perlu Perbaikan"
        
        # Interpretasi berdasarkan standar deviasi
        if standar_deviasi <= 5:
            interpretasi_deviasi = "sangat merata"
        elif standar_deviasi <= 10:
            interpretasi_deviasi = "cukup merata"
        elif standar_deviasi <= 15:
            interpretasi_deviasi = "kurang merata"
        else:
            interpretasi_deviasi = "tidak merata"
        
        return f"{interpretasi_skor} dengan distribusi {interpretasi_deviasi} (σ={standar_deviasi:.2f})"
                
    def hitung_deviasi_kecocokan(self):
        """Menghitung deviasi skor kecocokan antar wahana untuk evaluasi keseimbangan"""
        if not self.penempatan_awal:
            return {"std_dev": 0, "min_skor": 0, "max_skor": 0, "range_skor": 0, "rata_rata_per_wahana": {}}
        
        # Ubah pendekatan: Hitung ulang skor untuk setiap penempatan
        skor_per_wahana = defaultdict(list)
        
        for peserta_id, wahana_nama in self.penempatan_awal.items():
            peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
            wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == wahana_nama].iloc[0]
            
            # Hitung skor untuk penempatan ini
            skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
            skor_per_wahana[wahana_nama].append(skor)
        
        # Hitung rata-rata per wahana
        rata_rata_per_wahana = {
            wahana: sum(skor_list) / len(skor_list) 
            for wahana, skor_list in skor_per_wahana.items() if skor_list
        }
        
        # Hitung deviasi standar antar rata-rata wahana
        if rata_rata_per_wahana:
            nilai_rata_rata = list(rata_rata_per_wahana.values())
            mean = sum(nilai_rata_rata) / len(nilai_rata_rata)
            deviasi = math.sqrt(sum((x - mean) ** 2 for x in nilai_rata_rata) / len(nilai_rata_rata))
            
            self.deviasi_kecocokan = {
                "std_dev": deviasi,
                "min_skor": min(nilai_rata_rata),
                "max_skor": max(nilai_rata_rata),
                "range_skor": max(nilai_rata_rata) - min(nilai_rata_rata),
                "rata_rata_per_wahana": rata_rata_per_wahana
            }
            
            return self.deviasi_kecocokan
        
        return {"std_dev": 0, "min_skor": 0, "max_skor": 0, "range_skor": 0, "rata_rata_per_wahana": {}}
        
    def penjadwalan_dengan_prioritas(self, prioritas="seimbang"):
        """
        Algoritma penjadwalan dengan dua tipe prioritas:
        - "kapasitas": Prioritaskan mengisi semua kapasitas wahana
        - "seimbang": Prioritaskan stabilitas meskipun mungkin ada peserta tidak ditempatkan
        """
        # Inisialisasi
        penempatan = {}
        kapasitas_tersedia = self.wahana_df.set_index('Nama Wahana')['Kapasitas Optimal'].to_dict()
        
        # Urutkan peserta berdasarkan preferensi (untuk konsistensi hasil)
        peserta_sorted = self.peserta_df.sort_values(['Preferensi Pekerjaan', 'ID Peserta'])
        
        # PENDEKATAN 1: PRIORITAS KAPASITAS
        if prioritas == "kapasitas":
            # Hitung kapasitas total dan jumlah peserta
            total_kapasitas = self.wahana_df['Kapasitas Optimal'].sum()
            total_peserta = len(self.peserta_df)
            
            # Fase 1: Distribusi peserta untuk memenuhi kapasitas minimum di setiap wahana
            for _, wahana in self.wahana_df.iterrows():
                # Hitung kapasitas minimum yang perlu diisi (persentase dari kapasitas optimal)
                # Gunakan rasio total peserta:total kapasitas sebagai acuan
                rasio_populasi = min(1.0, total_peserta / total_kapasitas)
                min_kapasitas = math.ceil(wahana['Kapasitas Optimal'] * rasio_populasi * 0.7)  # Minimal 70% dari proporsi
                
                # Cari peserta yang preferensinya cocok terlebih dahulu
                peserta_cocok = []
                peserta_tidak_cocok = []
                
                for _, peserta in peserta_sorted.iterrows():
                    if peserta['ID Peserta'] not in penempatan:
                        if peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']:
                            peserta_cocok.append(peserta['ID Peserta'])
                        else:
                            peserta_tidak_cocok.append(peserta['ID Peserta'])
                
                # Isi dengan peserta yang preferensinya cocok dulu
                peserta_terpilih = []
                while len(peserta_terpilih) < min_kapasitas and peserta_cocok:
                    peserta_terpilih.append(peserta_cocok.pop(0))
                
                # Jika masih kurang, tambahkan peserta yang tidak cocok preferensinya
                while len(peserta_terpilih) < min_kapasitas and peserta_tidak_cocok:
                    peserta_terpilih.append(peserta_tidak_cocok.pop(0))
                
                # Tempatkan peserta yang terpilih
                for peserta_id in peserta_terpilih:
                    if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                        penempatan[peserta_id] = wahana['Nama Wahana']
                        kapasitas_tersedia[wahana['Nama Wahana']] -= 1
            
            # Fase 2: Distribusi sisa peserta untuk mengoptimalkan preferensi
            peserta_tersisa = [p for p in peserta_sorted['ID Peserta'] if p not in penempatan]
            
            for peserta_id in peserta_tersisa:
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                
                # Cari wahana dengan preferensi yang cocok terlebih dahulu
                wahana_cocok = self.wahana_df[
                    (self.wahana_df['Kategori Pekerjaan'] == peserta['Preferensi Pekerjaan'])
                ]
                
                wahana_terpilih = None
                for _, wahana in wahana_cocok.iterrows():
                    if kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                        wahana_terpilih = wahana['Nama Wahana']
                        break
                
                # Jika tidak ada wahana cocok yang tersedia, cari wahana lain
                if not wahana_terpilih:
                    for nama_wahana, kapasitas in kapasitas_tersedia.items():
                        if kapasitas > 0:
                            wahana_terpilih = nama_wahana
                            break
                
                # Tempatkan peserta jika ada wahana yang tersedia
                if wahana_terpilih:
                    penempatan[peserta_id] = wahana_terpilih
                    kapasitas_tersedia[wahana_terpilih] -= 1
        
        # PENDEKATAN 2: PRIORITAS STABILITAS/KESEIMBANGAN
        else:  # prioritas == "seimbang"
            # Identifikasi wahana berdasarkan status pasien untuk distribusi awal
            wahana_stabil = self.wahana_df[self.wahana_df['Status Gangguan'] == 'Stabil']
            
            # Fase 1: Distribusi untuk wahana stabil, prioritas match preferensi
            for _, wahana in wahana_stabil.iterrows():
                # Tentukan jumlah optimal peserta untuk wahana ini
                pasien_count = wahana['Pasien Normal']
                target_ratio = 10  # Target rasio pasien:peserta = 10 (di tengah range stabil)
                optimal_peserta = max(1, int(pasien_count / target_ratio))
                optimal_peserta = min(optimal_peserta, wahana['Kapasitas Optimal'])
                
                # Cari peserta yang preferensinya cocok
                peserta_cocok = []
                for _, peserta in peserta_sorted.iterrows():
                    if (peserta['ID Peserta'] not in penempatan and 
                        peserta['Preferensi Pekerjaan'] == wahana['Kategori Pekerjaan']):
                        peserta_cocok.append(peserta['ID Peserta'])
                    
                    if len(peserta_cocok) >= optimal_peserta:
                        break
                
                # Tempatkan peserta yang cocok
                for i, peserta_id in enumerate(peserta_cocok):
                    if i < optimal_peserta and kapasitas_tersedia[wahana['Nama Wahana']] > 0:
                        penempatan[peserta_id] = wahana['Nama Wahana']
                        kapasitas_tersedia[wahana['Nama Wahana']] -= 1
            
            # Fase 2: Distribusi untuk underutilized
            wahana_underutilized = self.wahana_df[self.wahana_df['Status Gangguan'] == 'Underutilized']
            
            for _, wahana in wahana_underutilized.iterrows():
                # Tentukan jumlah minimal peserta untuk wahana ini
                pasien_count = wahana['Pasien Normal']
                target_ratio = 5  # Target rasio pasien:peserta = 5 (batas bawah stabil)
                min_peserta = max(1, int(pasien_count / target_ratio))
                current_count = sum(1 for w in penempatan.values() if w == wahana['Nama Wahana'])
                needed_peserta = max(0, min_peserta - current_count)
                
                # Batasi dengan kapasitas
                needed_peserta = min(needed_peserta, kapasitas_tersedia[wahana['Nama Wahana']])
                
                # Cari peserta yang belum ditempatkan
                peserta_tersedia = []
                for _, peserta in peserta_sorted.iterrows():
                    if peserta['ID Peserta'] not in penempatan:
                        # Hitung skor kecocokan
                        skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                        peserta_tersedia.append((peserta['ID Peserta'], skor))
                
                # Urutkan berdasarkan skor kecocokan
                peserta_tersedia.sort(key=lambda x: x[1], reverse=True)
                
                # Tempatkan peserta berdasarkan skor
                for i, (peserta_id, _) in enumerate(peserta_tersedia):
                    if i < needed_peserta:
                        penempatan[peserta_id] = wahana['Nama Wahana']
                        kapasitas_tersedia[wahana['Nama Wahana']] -= 1
                    else:
                        break
            
            # Fase 3: Distribusi sisa peserta (jika masih ada kapasitas)
            peserta_tersisa = [p for p in peserta_sorted['ID Peserta'] if p not in penempatan]
            
            # Hitung skor kecocokan untuk semua pasangan tersisa
            skor_kecocokan = []
            
            for peserta_id in peserta_tersisa:
                peserta = self.peserta_df[self.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                
                for nama_wahana, kapasitas in kapasitas_tersedia.items():
                    if kapasitas > 0:
                        wahana = self.wahana_df[self.wahana_df['Nama Wahana'] == nama_wahana].iloc[0]
                        skor = self.hitung_skor_kecocokan_baru(peserta, wahana.to_dict())
                        skor_kecocokan.append((peserta_id, nama_wahana, skor))
            
            # Urutkan berdasarkan skor
            skor_kecocokan.sort(key=lambda x: x[2], reverse=True)
            
            # Tempatkan berdasarkan skor tertinggi dengan batasan stabilitas
            for peserta_id, nama_wahana, _ in skor_kecocokan:
                # Skip jika peserta sudah ditempatkan
                if peserta_id in penempatan:
                    continue
                    
                # Skip jika wahana sudah mencapai kapasitas optimal
                if kapasitas_tersedia[nama_wahana] <= 0:
                    continue
                
                # Hitung rasio pasien:peserta saat ini untuk wahana ini
                current_count = sum(1 for w in penempatan.values() if w == nama_wahana) + 1  # +1 untuk peserta ini
                wahana_data = self.wahana_df[self.wahana_df['Nama Wahana'] == nama_wahana].iloc[0]
                pasien_count = wahana_data['Pasien Normal']
                
                # Cek apakah penempatan ini menjaga stabilitas rasio
                rasio = pasien_count / current_count if current_count > 0 else 0
                
                # Jika rasio masih dalam range stabil (5-20) atau wahana underutilized, tempatkan peserta
                if 5 <= rasio <= 20 or wahana_data['Status Gangguan'] == 'Underutilized':
                    penempatan[peserta_id] = nama_wahana
                    kapasitas_tersedia[nama_wahana] -= 1
        
        # Simpan hasil dan hitung kualitas
        self.penempatan_awal = penempatan
        self.peserta_tidak_tertempatkan = list(set(self.peserta_df['ID Peserta']) - set(penempatan.keys()))
        
        # Hitung rata-rata skor kecocokan
        self.hitung_rata_rata_skor()
        
        self.hitung_deviasi_kecocokan()
        
        return penempatan


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
        st.session_state.deviasi_history = {}
    
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
    
    # Modifikasi di bagian tab2 untuk melakukan reset dan refresh statistik saat ganti penjadwalan
    with tab2:
        st.header("Penjadwalan Awal")
        
        if not st.session_state.data_loaded:
            st.warning("Silakan input data terlebih dahulu di tab Input Data")
        else:
            # Tambahkan state untuk melacak metode penjadwalan yang terakhir digunakan
            if 'last_scheduling_method' not in st.session_state:
                st.session_state.last_scheduling_method = None
            
            # Tambahkan opsi pemilihan tipe penjadwalan
            col1, col2 = st.columns([2, 3])
            with col1:
                penjadwalan_type = st.radio(
                    "Pilih Tipe Penjadwalan:", 
                    ["Distribusi Merata", "Prioritas Kapasitas", "Prioritas Stabilitas"],
                    help="Distribusi Merata: Skor kecocokan merata antar wahana\n"
                        "Prioritas Kapasitas: Mengutamakan pengisian kapasitas wahana\n"
                        "Prioritas Stabilitas: Mengutamakan kestabilan rasio pasien:peserta"
                )
            
            with col2:
                st.info(
                    "**Distribusi Merata**: Algoritma akan mendistribusikan peserta dengan skor kecocokan yang lebih merata antar wahana.\n\n"
                    "**Prioritas Kapasitas**: Mengutamakan pengisian seluruh kapasitas wahana, meskipun mungkin ada trade-off pada kestabilan.\n\n"
                    "**Prioritas Stabilitas**: Mengutamakan kestabilan rasio pasien:peserta, meskipun mungkin tidak semua peserta ditempatkan."
                )
            
            # Reset jika metode penjadwalan berubah
            if st.session_state.penjadwalan_done and st.session_state.last_scheduling_method != penjadwalan_type:
                if st.button(f"Ubah Penjadwalan ke {penjadwalan_type}"):
                    st.session_state.penjadwalan_done = False
                    st.session_state.gangguan_done = False
                    st.session_state.penyesuaian_done = False
                    st.session_state.last_scheduling_method = penjadwalan_type
                    st.rerun()  # Refresh halaman
            
            if st.button("Lakukan Penjadwalan Awal"):
                with st.spinner(f'Sedang melakukan penjadwalan awal dengan algoritma {penjadwalan_type}...'):
                    try:
                        # Panggil fungsi penjadwalan berdasarkan tipe yang dipilih
                        if penjadwalan_type == "Distribusi Merata":
                            penempatan_hasil = st.session_state.sistem.penjadwalan_distribusi_merata()
                        elif penjadwalan_type == "Prioritas Kapasitas":
                            penempatan_hasil = st.session_state.sistem.penjadwalan_dengan_prioritas(prioritas="kapasitas")
                        else:  # Prioritas Stabilitas
                            penempatan_hasil = st.session_state.sistem.penjadwalan_dengan_prioritas(prioritas="seimbang")
                        
                        st.session_state.penjadwalan_done = True
                        st.session_state.last_scheduling_method = penjadwalan_type
                        st.session_state.gangguan_done = False
                        st.session_state.penyesuaian_done = False
                        
                        # Simpan deviasi ke history jika ada
                        if hasattr(st.session_state.sistem, 'deviasi_kecocokan'):
                            # Pastikan deviasi tidak null sebelum menyimpan
                            if st.session_state.sistem.deviasi_kecocokan and 'std_dev' in st.session_state.sistem.deviasi_kecocokan:
                                st.session_state.deviasi_history[penjadwalan_type] = st.session_state.sistem.deviasi_kecocokan
                        
                        st.success(f"Penjadwalan awal berhasil dilakukan dengan algoritma {penjadwalan_type}!")                        
                        # Perhitungan metrik kualitas dipindahkan ke dalam fungsi penjadwalan masing-masing
                        # Pastikan fungsi-fungsi tersebut melakukan:
                        # 1. self.hitung_rata_rata_skor()
                        # 2. self.hitung_deviasi_kecocokan() (untuk Distribusi Merata)
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
                        lambda x: ['background-color: #2ECC71; color: black' if x['Match'] == '✅ Match' else 
                                'background-color: #E74C3C; color: white' for _ in x],
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
                
                # Grup berdasarkan wahana untuk yang terisi
                wahana_stats = hasil_awal.groupby(['Nama Wahana', 'Kategori Pekerjaan']).agg(
                    Total_Peserta=('ID Peserta', 'count'),
                    Match=('Match', lambda x: (x == '✅ Match').sum()),
                    Tidak_Match=('Match', lambda x: (x == '❌ Tidak Match').sum())
                ).reset_index()
                
                # Pastikan semua wahana ditampilkan (termasuk yang kosong)
                semua_wahana = st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Kapasitas Optimal']].copy()
                wahana_stats = semua_wahana.merge(wahana_stats, on=['Nama Wahana', 'Kategori Pekerjaan'], how='left').fillna(0)
                
                # Convert to integers for the count columns
                wahana_stats['Total_Peserta'] = wahana_stats['Total_Peserta'].astype(int)
                wahana_stats['Match'] = wahana_stats['Match'].astype(int)
                wahana_stats['Tidak_Match'] = wahana_stats['Tidak_Match'].astype(int)
                
                # Tambahkan kolom terisi/kapasitas
                wahana_stats['Terisi/Kapasitas'] = wahana_stats.apply(
                    lambda x: f"{int(x['Total_Peserta'])}/{int(x['Kapasitas Optimal'])}", axis=1)
                
                # Tambahkan kolom persentase terisi
                wahana_stats['Persentase_Terisi'] = (wahana_stats['Total_Peserta'] / wahana_stats['Kapasitas Optimal'] * 100).round(1)
                wahana_stats['Persentase_Terisi'] = wahana_stats['Persentase_Terisi'].map('{:.1f}%'.format)
                
                # Try-catch approach for the percentage calculation
                try:
                    # First ensure numeric types for both columns
                    wahana_stats['Match'] = pd.to_numeric(wahana_stats['Match'], errors='coerce').fillna(0)
                    wahana_stats['Total_Peserta'] = pd.to_numeric(wahana_stats['Total_Peserta'], errors='coerce').fillna(0)
                    
                    # Now calculate the percentage safely using built-in round() function
                    wahana_stats['Persentase_Match'] = wahana_stats.apply(
                        lambda x: round(float(x['Match']) / float(x['Total_Peserta']) * 100, 1) 
                                if float(x['Total_Peserta']) > 0 else 0.0, 
                        axis=1
                    )
                    wahana_stats['Persentase_Match'] = wahana_stats['Persentase_Match'].apply(lambda x: f"{x:.1f}%")
                except Exception as e:
                    st.error(f"Error calculating match percentages: {str(e)}")
                    # Fallback implementation
                    wahana_stats['Persentase_Match'] = wahana_stats.apply(
                        lambda x: '0.0%' if x['Total_Peserta'] == 0 
                                else f"{round(float(x['Match'])/float(x['Total_Peserta'])*100, 1):.1f}%", 
                        axis=1
                    )
                    wahana_stats['Persentase_Match'] = wahana_stats['Persentase_Match'].map('{:.1f}%'.format)
                except Exception as e:
                    st.error(f"Error calculating match percentages: {str(e)}")
                    # Fallback implementation
                    wahana_stats['Persentase_Match'] = wahana_stats.apply(
                        lambda x: '0.0%' if x['Total_Peserta'] == 0 
                                else f"{(x['Match']/x['Total_Peserta']*100):.1f}%", 
                        axis=1
                    )
                
                # Urutkan berdasarkan Total Peserta (descending)
                wahana_stats = wahana_stats.sort_values(by='Total_Peserta', ascending=False)
                
                # Tampilkan tabel statistik dengan formatting yang lebih baik
                st.dataframe(
                    wahana_stats.style
                    .background_gradient(subset=['Total_Peserta'], cmap='Blues')
                    .background_gradient(subset=['Match'], cmap='Greens'),
                    use_container_width=True
                )
                
                # Visualisasi persentase terisi
                st.subheader("Persentase Kapasitas Terisi per Wahana")
                
                # Siapkan data untuk visualisasi
                occupancy_data = wahana_stats.copy()
                occupancy_data['Persentase_Terisi_Numeric'] = (occupancy_data['Total_Peserta'] / occupancy_data['Kapasitas Optimal'] * 100).round(1)
                
                # Urutkan berdasarkan persentase terisi
                occupancy_data = occupancy_data.sort_values('Persentase_Terisi_Numeric', ascending=False)
                
                # Buat warna berdasarkan persentase terisi
                def get_color(pct):
                    if pct >= 90:
                        return '#C0392B'  # Merah untuk hampir/penuh
                    elif pct >= 60:
                        return '#F39C12'  # Oranye untuk cukup terisi
                    elif pct > 0:
                        return '#27AE60'  # Hijau untuk kurang terisi
                    else:
                        return '#7F8C8D'  # Abu-abu untuk kosong
                
                occupancy_data['Color'] = occupancy_data['Persentase_Terisi_Numeric'].apply(get_color)
                
                fig = px.bar(
                    occupancy_data,
                    x='Nama Wahana',
                    y='Persentase_Terisi_Numeric',
                    title='Persentase Kapasitas Terisi per Wahana',
                    text='Terisi/Kapasitas',
                    labels={'Persentase_Terisi_Numeric': 'Persentase Terisi (%)', 'Nama Wahana': 'Nama Wahana'},
                    color='Persentase_Terisi_Numeric',
                    color_continuous_scale='RdYlGn_r'
                )
                
                # Tambahkan garis 100%
                fig.add_shape(
                    type="line",
                    x0=-0.5,
                    y0=100,
                    x1=len(occupancy_data)-0.5,
                    y1=100,
                    line=dict(color="red", width=2, dash="dash"),
                )
                
                fig.update_layout(xaxis_tickangle=-45)
                st.plotly_chart(fig, use_container_width=True)
                
                # Tambahkan download button untuk hasil penjadwalan
                csv = hasil_awal.to_csv(index=False)
                st.download_button(
                    label="📥 Download Hasil Penjadwalan",
                    data=csv,
                    file_name="hasil_penjadwalan_awal.csv",
                    mime="text/csv",
                )
                
                # Tambahkan di bagian hasil penjadwalan awal
                if hasattr(st.session_state.sistem, 'deviasi_kecocokan'):
                    deviasi = st.session_state.sistem.deviasi_kecocokan
                    
                    st.subheader("Analisis Keseimbangan Skor Kecocokan")
                    col1, col2, col3 = st.columns(3)
                    
                    col1.metric("Standar Deviasi", f"{deviasi['std_dev']:.2f}")
                    col2.metric("Range Skor", f"{deviasi['min_skor']:.1f} - {deviasi['max_skor']:.1f}")
                    col3.metric("Selisih Min-Max", f"{deviasi['range_skor']:.1f}")
                    
                    # Visualisasi rata-rata skor kecocokan per wahana
                    if deviasi['rata_rata_per_wahana']:
                        st.subheader("Rata-rata Skor Kecocokan Per Wahana")
                        skor_df = pd.DataFrame({
                            'Wahana': list(deviasi['rata_rata_per_wahana'].keys()),
                            'Rata-rata Skor': list(deviasi['rata_rata_per_wahana'].values())
                        }).sort_values('Rata-rata Skor', ascending=False)
                        
                        fig = px.bar(
                            skor_df,
                            x='Wahana',
                            y='Rata-rata Skor',
                            title='Distribusi Rata-rata Skor Kecocokan per Wahana',
                            color='Rata-rata Skor',
                            color_continuous_scale='Viridis',
                            text='Rata-rata Skor'
                        )
                        
                        # Tambahkan garis rata-rata keseluruhan
                        mean_global = sum(deviasi['rata_rata_per_wahana'].values()) / len(deviasi['rata_rata_per_wahana'])
                        fig.add_shape(
                            type="line",
                            x0=-0.5,
                            y0=mean_global,
                            x1=len(skor_df)-0.5,
                            y1=mean_global,
                            line=dict(color="red", width=2, dash="dash"),
                        )
                        
                        fig.add_annotation(
                            x=0,
                            y=mean_global,
                            text=f"Rata-rata Global ({mean_global:.1f})",
                            showarrow=False,
                            yshift=10
                        )
                        
                        fig.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig, use_container_width=True)
                        
                    if 'deviasi_history' in st.session_state and len(st.session_state.deviasi_history) > 0:
                        st.subheader("Perbandingan Deviasi Antar Metode Penjadwalan")
                        deviasi_df = pd.DataFrame([
                            {"Metode": metode, "Standar Deviasi": data["std_dev"]} 
                            for metode, data in st.session_state.deviasi_history.items()
                        ])
                        
                        fig_compare = px.bar(
                            deviasi_df, 
                            x="Metode", 
                            y="Standar Deviasi",
                            title="Perbandingan Standar Deviasi Antar Metode",
                            color="Standar Deviasi",
                            color_continuous_scale="RdYlBu_r",  # Semakin rendah semakin baik (biru)
                            text="Standar Deviasi"
                        )
                        fig_compare.update_traces(texttemplate='%{text:.2f}', textposition='outside')
                        fig_compare.update_layout(xaxis_tickangle=-45)
                        st.plotly_chart(fig_compare, use_container_width=True)
            
    with tab3:
        st.header("Simulasi Gangguan")
        
        if not st.session_state.penjadwalan_done:
            st.warning("Silakan lakukan penjadwalan awal terlebih dahulu di tab Penjadwalan Awal")
        else:
            # Button untuk simulasi gangguan
            col1, col2 = st.columns([1, 3])
            with col1:
                simulate_button = st.button("Simulasikan Gangguan", use_container_width=True)
            
            if simulate_button:
                with st.spinner('Sedang mensimulasikan gangguan...'):
                    try:
                        st.session_state.sistem.simulasikan_gangguan()
                        st.session_state.gangguan_done = True
                        st.success("Simulasi gangguan berhasil dilakukan!")
                    except Exception as e:
                        st.error(f"Gagal mensimulasikan gangguan: {str(e)}")
                        st.stop()
            
            # Tampilkan hasil simulasi gangguan setelah tombol ditekan atau jika sudah pernah disimulasikan
            if st.session_state.gangguan_done:
                # Data untuk visualisasi
                status_normal = st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Kapasitas Optimal', 'Pasien Normal']]
                status_gangguan = st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Kapasitas Optimal', 'Pasien Gangguan', 'Status Gangguan']]
                
                # Persiapkan data untuk tab
                tabs_gangguan = st.tabs(["Status Wahana", "Perbandingan Pasien", "Rasio Pasien/Peserta"])
                
                # TAB 1: Status Wahana (tampilan pie chart)
                with tabs_gangguan[0]:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.subheader("Status Wahana Normal")
                        
                        # Hitung status normal berdasarkan rasio
                        status_normal_detail = pd.DataFrame()
                        status_normal_detail['Rasio Pasien/Kapasitas'] = status_normal['Pasien Normal'] / status_normal['Kapasitas Optimal']
                        
                        # Tentukan status berdasarkan rasio
                        def tentukan_status(rasio):
                            if rasio == 0:
                                return 'Tutup'
                            elif rasio < 5:
                                return 'Underutilized'
                            elif rasio > 20:
                                return 'Overload'
                            else:
                                return 'Stabil'
                        
                        status_normal_detail['Status'] = status_normal_detail['Rasio Pasien/Kapasitas'].apply(tentukan_status)
                        
                        # Visualisasi distribusi status normal
                        distribusi_normal = status_normal_detail['Status'].value_counts().reset_index()
                        distribusi_normal.columns = ['Status', 'Jumlah']
                        
                        fig_normal = px.pie(
                            distribusi_normal, 
                            values='Jumlah', 
                            names='Status', 
                            title="Status Wahana Kondisi Normal",
                            color='Status',
                            color_discrete_map={
                                'Stabil': '#27AE60',
                                'Underutilized': '#F39C12', 
                                'Overload': '#C0392B',
                                'Tutup': '#7F8C8D'
                            }
                        )
                        st.plotly_chart(fig_normal, use_container_width=True)
                    
                    with col2:
                        st.subheader("Status Wahana Setelah Gangguan")
                        
                        # Visualisasi distribusi status gangguan
                        distribusi_gangguan = status_gangguan['Status Gangguan'].value_counts().reset_index()
                        distribusi_gangguan.columns = ['Status', 'Jumlah']
                        
                        fig_gangguan = px.pie(
                            distribusi_gangguan, 
                            values='Jumlah', 
                            names='Status', 
                            title="Status Wahana Setelah Gangguan",
                            color='Status',
                            color_discrete_map={
                                'Stabil': '#27AE60',
                                'Underutilized': '#F39C12', 
                                'Overload': '#C0392B',
                                'Tutup': '#7F8C8D'
                            }
                        )
                        st.plotly_chart(fig_gangguan, use_container_width=True)
                    
                    # Tampilkan tabel perubahan status
                    st.subheader("Perubahan Status Wahana")
                    perubahan_status = pd.DataFrame()
                    perubahan_status['Nama Wahana'] = status_normal['Nama Wahana']
                    perubahan_status['Kategori'] = status_normal['Kategori Pekerjaan']
                    perubahan_status['Status Normal'] = status_normal_detail['Status']
                    perubahan_status['Status Gangguan'] = status_gangguan['Status Gangguan']
                    perubahan_status['Perubahan'] = perubahan_status.apply(
                        lambda x: '✓ Tetap' if x['Status Normal'] == x['Status Gangguan'] else '⚠️ Berubah',
                        axis=1
                    )
                    
                    st.dataframe(
                        perubahan_status.style.apply(
                            lambda x: ['background-color: #27AE60; color: white' if x['Status Gangguan'] == 'Stabil'
                                    else 'background-color: #F39C12; color: black' if x['Status Gangguan'] == 'Underutilized'
                                    else 'background-color: #C0392B; color: white' if x['Status Gangguan'] == 'Overload'
                                    else 'background-color: #7F8C8D; color: white' for _ in x],
                            axis=1
                        ),
                        use_container_width=True
                    )
                
                # TAB 2: Perbandingan Jumlah Pasien (normal vs gangguan)
                with tabs_gangguan[1]:
                    st.subheader("Perbandingan Jumlah Pasien Normal vs Gangguan")
                    
                    # Buat DataFrame untuk perbandingan
                    perbandingan_df = pd.DataFrame({
                        'Nama Wahana': status_normal['Nama Wahana'],
                        'Pasien Normal': status_normal['Pasien Normal'],
                        'Pasien Gangguan': status_gangguan['Pasien Gangguan']
                    })
                    
                    # Hitung perubahan jumlah pasien
                    perbandingan_df['Perubahan'] = perbandingan_df['Pasien Gangguan'] - perbandingan_df['Pasien Normal']
                    perbandingan_df['Persen Perubahan'] = (perbandingan_df['Perubahan'] / perbandingan_df['Pasien Normal'] * 100).round(1)
                    perbandingan_df['Persen Perubahan'] = perbandingan_df['Persen Perubahan'].replace([float('inf'), float('-inf')], 0)
                    
                    # Visualisasi bar chart perbandingan
                    fig_perbandingan = px.bar(
                        perbandingan_df,
                        x='Nama Wahana',
                        y=['Pasien Normal', 'Pasien Gangguan'],
                        barmode='group',
                        title='Perbandingan Jumlah Pasien Normal vs Gangguan',
                        labels={'value': 'Jumlah Pasien', 'variable': 'Kondisi'},
                        color_discrete_map={
                            'Pasien Normal': '#3498DB',  # Biru
                            'Pasien Gangguan': '#E74C3C'  # Merah
                        }
                    )
                    st.plotly_chart(fig_perbandingan, use_container_width=True)
                    
                    # Tampilkan tabel detail perubahan dengan persentase
                    st.subheader("Detail Perubahan Jumlah Pasien")
                    
                    st.dataframe(
                        perbandingan_df.style.background_gradient(
                            subset=['Perubahan', 'Persen Perubahan'],
                            cmap='RdYlGn_r'
                        ),
                        use_container_width=True
                    )
                
                # TAB 3: Rasio Pasien/Peserta
                with tabs_gangguan[2]:
                    st.subheader("Rasio Pasien per Peserta")
                    
                    # Buat DataFrame untuk visualisasi rasio
                    rasio_df = pd.DataFrame()
                    rasio_df['Nama Wahana'] = status_normal['Nama Wahana']
                    
                    # Hitung jumlah peserta per wahana dari penjadwalan awal
                    jumlah_peserta = {}
                    for wahana in status_normal['Nama Wahana']:
                        jumlah_peserta[wahana] = sum(1 for w in st.session_state.sistem.penempatan_awal.values() if w == wahana)
                    
                    rasio_df['Jumlah Peserta'] = rasio_df['Nama Wahana'].map(jumlah_peserta)
                    rasio_df['Pasien Normal'] = status_normal['Pasien Normal']
                    rasio_df['Pasien Gangguan'] = status_gangguan['Pasien Gangguan']
                    
                    # Hitung rasio
                    rasio_df['Rasio Normal'] = rasio_df.apply(
                        lambda x: x['Pasien Normal'] / x['Jumlah Peserta'] if x['Jumlah Peserta'] > 0 else 0, 
                        axis=1
                    )
                    rasio_df['Rasio Gangguan'] = rasio_df.apply(
                        lambda x: x['Pasien Gangguan'] / x['Jumlah Peserta'] if x['Jumlah Peserta'] > 0 else 0, 
                        axis=1
                    )
                    
                    # Visualisasi rasio
                    fig_rasio = px.bar(
                        rasio_df,
                        x='Nama Wahana',
                        y=['Rasio Normal', 'Rasio Gangguan'],
                        barmode='group',
                        title='Rasio Pasien per Peserta (Normal vs Gangguan)',
                        labels={'value': 'Rasio Pasien/Peserta', 'variable': 'Kondisi'}
                    )
                    
                    # Tambahkan garis threshold Underutilized dan Overload
                    fig_rasio.add_shape(
                        type="line",
                        x0=-0.5,
                        y0=5,
                        x1=len(rasio_df)-0.5,
                        y1=5,
                        line=dict(color="orange", width=2, dash="dash"),
                        name="Threshold Underutilized"
                    )
                    
                    fig_rasio.add_shape(
                        type="line",
                        x0=-0.5,
                        y0=20,
                        x1=len(rasio_df)-0.5,
                        y1=20,
                        line=dict(color="red", width=2, dash="dash"),
                        name="Threshold Overload"
                    )
                    
                    # Menambahkan anotasi untuk threshold
                    fig_rasio.add_annotation(
                        x=0,
                        y=5,
                        text="Underutilized Threshold (5)",
                        showarrow=False,
                        yshift=10
                    )
                    
                    fig_rasio.add_annotation(
                        x=0,
                        y=20,
                        text="Overload Threshold (20)",
                        showarrow=False,
                        yshift=10
                    )
                    
                    st.plotly_chart(fig_rasio, use_container_width=True)
                    
                    # Tampilkan tabel detail rasio
                    st.subheader("Detail Rasio Pasien per Peserta")
                    
                    # Format rasio dengan 2 desimal dan tambahkan status
                    rasio_df['Rasio Normal'] = rasio_df['Rasio Normal'].round(2)
                    rasio_df['Rasio Gangguan'] = rasio_df['Rasio Gangguan'].round(2)
                    
                    rasio_df['Status Normal'] = rasio_df['Rasio Normal'].apply(tentukan_status)
                    rasio_df['Status Gangguan'] = rasio_df['Rasio Gangguan'].apply(tentukan_status)
                    
                    st.dataframe(
                        rasio_df.style.apply(
                            lambda x: ['background-color: #27AE60; color: white' if x['Status Gangguan'] == 'Stabil'
                                    else 'background-color: #F39C12; color: black' if x['Status Gangguan'] == 'Underutilized'
                                    else 'background-color: #C0392B; color: white' if x['Status Gangguan'] == 'Overload'
                                    else 'background-color: #7F8C8D; color: white' for _ in x],
                            axis=1
                        ),
                        use_container_width=True
                    )
                
                # Tampilkan informasi ke pengguna untuk melanjutkan ke tab 4
                st.info("👉 Silakan lanjutkan ke tab **Hasil Akhir** untuk melakukan penyesuaian penempatan berdasarkan simulasi gangguan ini.")
            else:
                # Tampilkan informasi status awal
                st.subheader("📊 Status Wahana Awal (Kondisi Normal)")
                
                # Buat DataFrame untuk status awal (normal)
                status_normal = st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Kapasitas Optimal', 'Pasien Normal']]
                
                # Buat tabel yang lebih informatif
                status_normal_detail = pd.DataFrame()
                status_normal_detail['Nama Wahana'] = status_normal['Nama Wahana']
                status_normal_detail['Kategori Pekerjaan'] = status_normal['Kategori Pekerjaan']
                status_normal_detail['Kapasitas'] = status_normal['Kapasitas Optimal']
                status_normal_detail['Pasien'] = status_normal['Pasien Normal']
                
                # Tambahkan kolom Rasio dan Status
                status_normal_detail['Rasio Pasien/Kapasitas'] = status_normal['Pasien Normal'] / status_normal['Kapasitas Optimal']
                
                # Tentukan status berdasarkan rasio
                def tentukan_status(rasio):
                    if rasio == 0:
                        return 'Tutup'
                    elif rasio < 5:
                        return 'Underutilized'
                    elif rasio > 20:
                        return 'Overload'
                    else:
                        return 'Stabil'
                
                status_normal_detail['Status'] = status_normal_detail['Rasio Pasien/Kapasitas'].apply(tentukan_status)
                
                # Tampilkan tabel dengan conditional formatting
                st.dataframe(
                    status_normal_detail.style.apply(
                        lambda x: ['background-color: #27AE60; color: white' if x['Status'] == 'Stabil' 
                                else 'background-color: #F39C12; color: black' if x['Status'] == 'Underutilized'
                                else 'background-color: #C0392B; color: white' if x['Status'] == 'Overload'
                                else 'background-color: #7F8C8D; color: white' for _ in x],
                        axis=1
                    ),
                    use_container_width=True
                )
                
                st.info("⚠️ Klik tombol **Simulasikan Gangguan** untuk melihat perubahan status wahana.")
    
    with tab4:
        st.header("Hasil Akhir")
        
        if not st.session_state.gangguan_done:
            st.warning("Silakan lakukan simulasi gangguan terlebih dahulu di tab Simulasi Gangguan")
        else:
            # Tombol untuk melakukan penyesuaian (hanya tampilkan jika belum dilakukan penyesuaian)
            if not st.session_state.penyesuaian_done:
                col1, col2 = st.columns([1, 3])
                with col1:
                    redistribution_button = st.button("Lakukan Penyesuaian Penempatan", 
                                                    use_container_width=True, 
                                                    type="primary")
                
                if redistribution_button:
                    with st.spinner('Sedang menyesuaikan penempatan berdasarkan kondisi gangguan...'):
                        try:
                            penempatan_akhir = st.session_state.sistem.redistribusi_adaptif()
                            st.session_state.penyesuaian_done = True
                            st.success("✅ Penyesuaian penempatan berhasil dilakukan!")
                        except Exception as e:
                            st.error(f"❌ Gagal melakukan penyesuaian: {str(e)}")
                            import traceback
                            st.code(traceback.format_exc())
                            st.stop()
            
            # Tampilkan hasil jika sudah dilakukan penyesuaian
            if st.session_state.penyesuaian_done:
                try:
                    # Tampilkan statistik penjadwalan dengan card styling
                    st.subheader("📊 Statistik Penjadwalan")
                    
                    # Buat baris metrik untuk perbandingan
                    col1, col2, col3 = st.columns(3)
                    
                    # Hitung statistik awal dan akhir
                    peserta_awal = len(st.session_state.sistem.penempatan_awal)
                    peserta_akhir = len(st.session_state.sistem.penempatan_akhir)
                    
                    # Hitung match preferensi awal
                    match_awal = 0
                    for peserta_id, wahana in st.session_state.sistem.penempatan_awal.items():
                        peserta = st.session_state.sistem.peserta_df[st.session_state.sistem.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                        wahana_data = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Nama Wahana'] == wahana].iloc[0]
                        if peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan']:
                            match_awal += 1
                    
                    # Hitung match preferensi akhir
                    match_akhir = 0
                    for peserta_id, wahana in st.session_state.sistem.penempatan_akhir.items():
                        peserta = st.session_state.sistem.peserta_df[st.session_state.sistem.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                        wahana_data = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Nama Wahana'] == wahana].iloc[0]
                        if peserta['Preferensi Pekerjaan'] == wahana_data['Kategori Pekerjaan']:
                            match_akhir += 1
                    
                    # Hitung total peserta yang dipindahkan
                    dipindahkan = 0
                    for peserta_id in st.session_state.sistem.penempatan_awal:
                        if peserta_id in st.session_state.sistem.penempatan_akhir:
                            if st.session_state.sistem.penempatan_awal[peserta_id] != st.session_state.sistem.penempatan_akhir[peserta_id]:
                                dipindahkan += 1
                    
                    # Tampilkan metrik dengan persentase
                    col1.metric(
                        "Total Peserta", 
                        peserta_akhir, 
                        f"{peserta_akhir - peserta_awal:+d}" if peserta_akhir != peserta_awal else "Tidak berubah"
                    )
                    
                    match_pct_awal = (match_awal/peserta_awal*100) if peserta_awal > 0 else 0
                    match_pct_akhir = (match_akhir/peserta_akhir*100) if peserta_akhir > 0 else 0
                    
                    col2.metric(
                        "Match Preferensi", 
                        f"{match_akhir} ({match_pct_akhir:.1f}%)",
                        f"{match_akhir - match_awal:+d} ({match_pct_akhir - match_pct_awal:.1f}%)"
                    )
                    
                    col3.metric(
                        "Peserta Dipindahkan", 
                        dipindahkan,
                        f"{dipindahkan/peserta_awal*100:.1f}% dari total peserta" if peserta_awal > 0 else "0%"
                    )
                    
                    # Tampilkan tabs untuk hasil yang berbeda
                    result_tabs = st.tabs([
                        "Ringkasan Perubahan", 
                        "Detail Perubahan Penempatan",
                        "Hasil Penjadwalan Akhir"
                    ])
                    
                    # Tab 1: Ringkasan perubahan
                    with result_tabs[0]:
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            # Tampilkan perbandingan status wahana
                            st.subheader("Perbandingan Status Wahana")
                            
                            # Buat DataFrame untuk perbandingan status wahana
                            status_sebelum_df = pd.DataFrame()
                            status_sebelum_df['Nama Wahana'] = st.session_state.sistem.wahana_df['Nama Wahana']
                            status_sebelum_df['Kategori'] = st.session_state.sistem.wahana_df['Kategori Pekerjaan']
                            
                            # Definisikan fungsi untuk status
                            def status_dari_rasio(rasio):
                                if rasio == 0:
                                    return 'Tutup'
                                elif rasio < 5:
                                    return 'Underutilized'
                                elif rasio > 20:
                                    return 'Overload'
                                else:
                                    return 'Stabil'
                            
                            # Hitung status berdasarkan rasio
                            status_sebelum_df['Rasio Normal'] = status_sebelum_df.apply(
                                lambda x: st.session_state.sistem.wahana_df[
                                    st.session_state.sistem.wahana_df['Nama Wahana'] == x['Nama Wahana']
                                ]['Pasien Normal'].values[0] / st.session_state.sistem.wahana_df[
                                    st.session_state.sistem.wahana_df['Nama Wahana'] == x['Nama Wahana']
                                ]['Kapasitas Optimal'].values[0],
                                axis=1
                            )
                            status_sebelum_df['Status Sebelum Gangguan'] = status_sebelum_df['Rasio Normal'].apply(status_dari_rasio)
                            status_sebelum_df['Status Setelah Gangguan'] = st.session_state.sistem.wahana_df['Status Gangguan'].values
                            
                            # Tampilkan perubahan status dalam tabel
                            status_sebelum_df['Perubahan Status'] = status_sebelum_df.apply(
                                lambda x: '✓ Tetap' if x['Status Sebelum Gangguan'] == x['Status Setelah Gangguan'] 
                                else '⚠️ Berubah', axis=1
                            )
                            
                            # Visualisasikan perubahan status
                            perubahan_count = status_sebelum_df['Perubahan Status'].value_counts()
                            
                            fig_perubahan = px.pie(
                                values=perubahan_count.values,
                                names=perubahan_count.index,
                                title="Proporsi Wahana Yang Mengalami Perubahan Status",
                                color=perubahan_count.index,
                                color_discrete_map={
                                    '✓ Tetap': '#4CAF50',
                                    '⚠️ Berubah': '#F44336'
                                },
                                hole=0.4
                            )
                            fig_perubahan.update_layout(margin=dict(t=50, b=30))
                            st.plotly_chart(fig_perubahan, use_container_width=True)
                        
                        with col2:
                            # Perbandingan distribusi peserta per wahana
                            st.subheader("Distribusi Peserta per Wahana")
                            
                            # Hitung distribusi peserta per wahana sebelum
                            distribusi_awal = pd.DataFrame(
                                pd.Series(st.session_state.sistem.penempatan_awal).value_counts()
                            ).reset_index()
                            distribusi_awal.columns = ['Nama Wahana', 'Jumlah Peserta Awal']
                            
                            # Hitung distribusi peserta per wahana sesudah
                            distribusi_akhir = pd.DataFrame(
                                pd.Series(st.session_state.sistem.penempatan_akhir).value_counts()
                            ).reset_index()
                            distribusi_akhir.columns = ['Nama Wahana', 'Jumlah Peserta Akhir']
                            
                            # Gabungkan keduanya
                            distribusi_gabungan = pd.merge(
                                distribusi_awal, distribusi_akhir, 
                                on='Nama Wahana', how='outer'
                            ).fillna(0)
                            
                            # Tambahkan kolom perubahan
                            distribusi_gabungan['Perubahan'] = distribusi_gabungan['Jumlah Peserta Akhir'] - distribusi_gabungan['Jumlah Peserta Awal']
                            
                            # Buat grafik batang perbandingan
                            fig_distribusi = px.bar(
                                distribusi_gabungan,
                                x='Nama Wahana',
                                y=['Jumlah Peserta Awal', 'Jumlah Peserta Akhir'],
                                barmode='group',
                                title='Perbandingan Distribusi Peserta',
                                color_discrete_sequence=['#1f77b4', '#ff7f0e'],
                                labels={
                                    'value': 'Jumlah Peserta',
                                    'variable': 'Kondisi'
                                }
                            )
                            fig_distribusi.update_layout(margin=dict(t=50, b=30))
                            st.plotly_chart(fig_distribusi, use_container_width=True)
                        
                        # Tampilkan tabel perbandingan
                        st.subheader("Detail Perubahan Distribusi")
                        st.dataframe(
                            distribusi_gabungan.style.background_gradient(
                                subset=['Perubahan'], cmap='RdYlGn'
                            ),
                            use_container_width=True
                        )
                    
                    # Tab 2: Detail perubahan penempatan
                    with result_tabs[1]:
                        st.subheader("🔄 Detail Pemindahan Peserta")
                        
                        # Buat DataFrame untuk peserta yang dipindahkan
                        perubahan_df = pd.DataFrame(columns=[
                            'ID Peserta', 'Nama Peserta', 'Preferensi', 
                            'Wahana Awal', 'Status Awal', 'Match Awal',
                            'Wahana Akhir', 'Status Akhir', 'Match Akhir',
                            'Peningkatan Match'
                        ])
                        
                        # Isi data perubahan penempatan
                        for peserta_id in st.session_state.sistem.penempatan_awal:
                            if peserta_id not in st.session_state.sistem.penempatan_akhir:
                                continue
                            
                            wahana_awal = st.session_state.sistem.penempatan_awal[peserta_id]
                            wahana_akhir = st.session_state.sistem.penempatan_akhir[peserta_id]
                            
                            if wahana_awal != wahana_akhir:
                                # Ada perubahan penempatan, tambahkan ke DataFrame
                                peserta = st.session_state.sistem.peserta_df[st.session_state.sistem.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                                wahana_awal_data = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Nama Wahana'] == wahana_awal].iloc[0]
                                wahana_akhir_data = st.session_state.sistem.wahana_df[st.session_state.sistem.wahana_df['Nama Wahana'] == wahana_akhir].iloc[0]
                                
                                # Tentukan match sebelum dan sesudah
                                match_awal = peserta['Preferensi Pekerjaan'] == wahana_awal_data['Kategori Pekerjaan']
                                match_akhir = peserta['Preferensi Pekerjaan'] == wahana_akhir_data['Kategori Pekerjaan']
                                
                                # Tambahkan ke DataFrame
                                perubahan_df = perubahan_df._append({
                                    'ID Peserta': peserta_id,
                                    'Nama Peserta': peserta['Nama Peserta'],
                                    'Preferensi': peserta['Preferensi Pekerjaan'],
                                    'Wahana Awal': wahana_awal,
                                    'Status Awal': wahana_awal_data['Status Gangguan'],
                                    'Match Awal': '✅' if match_awal else '❌',
                                    'Wahana Akhir': wahana_akhir,
                                    'Status Akhir': wahana_akhir_data['Status Gangguan'],
                                    'Match Akhir': '✅' if match_akhir else '❌',
                                    'Peningkatan Match': '✅' if match_akhir and not match_awal else 
                                                    '❌' if not match_akhir and match_awal else
                                                    '➖'
                                }, ignore_index=True)
                        
                        # Tampilkan tabel perubahan
                        if not perubahan_df.empty:
                            # Tambahkan pengurutan & pewarnaan
                            perubahan_df = perubahan_df.sort_values(by=['Peningkatan Match', 'Match Akhir'], ascending=[False, False])
                            
                            # Tampilkan metrik perubahan penempatan
                            col1, col2, col3 = st.columns(3)
                            
                            peningkatan_match = sum(1 for _, row in perubahan_df.iterrows() if row['Peningkatan Match'] == '✅')
                            penurunan_match = sum(1 for _, row in perubahan_df.iterrows() if row['Peningkatan Match'] == '❌')
                            tetap_match = sum(1 for _, row in perubahan_df.iterrows() if row['Peningkatan Match'] == '➖')
                            
                            col1.metric("Peningkatan Match", peningkatan_match)
                            col2.metric("Penurunan Match", penurunan_match)
                            col3.metric("Tetap", tetap_match)
                            
                            # Tampilkan tabel dengan styling yang lebih baik
                            st.dataframe(
                                perubahan_df.style.apply(
                                    lambda x: ['background-color: #2ECC71; color: black' if x['Match Akhir'] == '✅' else 
                                            'background-color: #E74C3C; color: white' for _ in x],
                                    axis=1
                                ),
                                use_container_width=True
                            )
                            
                            # Buat grafik aliran dari wahana asal ke wahana tujuan
                            st.subheader("🔄 Aliran Pemindahan Peserta")
                            
                            # Buat diagram Sunburst yang lebih informatif
                            fig = px.sunburst(
                                perubahan_df,
                                path=['Status Awal', 'Wahana Awal', 'Wahana Akhir'],
                                color='Match Akhir',
                                color_discrete_map={
                                    '✅': '#2ECC71',
                                    '❌': '#E74C3C'
                                },
                                title='Aliran Pemindahan Peserta (Status Awal → Wahana Awal → Wahana Akhir)'
                            )
                            fig.update_layout(margin=dict(t=50, b=30))
                            st.plotly_chart(fig, use_container_width=True)
                            
                            # Tambahkan download button
                            st.download_button(
                                label="📥 Download Detail Perubahan Penempatan",
                                data=perubahan_df.to_csv(index=False),
                                file_name="detail_perubahan_penempatan.csv",
                                mime="text/csv",
                            )
                        else:
                            st.info("Tidak ada perubahan penempatan peserta yang terdeteksi.")
                    
                    # Tab 3: Hasil penjadwalan akhir
                    with result_tabs[2]:
                        st.subheader("📋 Jadwal Penempatan Akhir")
                        
                        # Buat dataframe untuk jadwal penempatan
                        if st.session_state.sistem.penempatan_akhir:
                            # Buat dictionary untuk mengelompokkan peserta per wahana
                            peserta_per_wahana = defaultdict(list)
                            
                            # Susun data peserta berdasarkan wahana penempatan
                            for peserta_id, wahana in st.session_state.sistem.penempatan_akhir.items():
                                # Ambil data peserta
                                peserta = st.session_state.sistem.peserta_df[st.session_state.sistem.peserta_df['ID Peserta'] == peserta_id].iloc[0]
                                
                                # Tambahkan ke grup wahana yang sesuai
                                peserta_per_wahana[wahana].append({
                                    'ID Peserta': peserta_id,
                                    'Nama Peserta': peserta['Nama Peserta'],
                                    'Preferensi': peserta['Preferensi Pekerjaan']
                                })
                            
                            # Ambil data semua wahana
                            wahana_data = st.session_state.sistem.wahana_df.set_index('Nama Wahana').to_dict('index')
                            
                            # Buat DataFrame untuk hasil lengkap
                            hasil_lengkap = pd.DataFrame({
                                'ID Peserta': list(st.session_state.sistem.penempatan_akhir.keys()),
                                'Nama Wahana': list(st.session_state.sistem.penempatan_akhir.values())
                            })
                            
                            # Gabungkan dengan data peserta
                            hasil_lengkap = hasil_lengkap.merge(
                                st.session_state.sistem.peserta_df,
                                on='ID Peserta'
                            )
                            
                            # Gabungkan dengan data wahana
                            hasil_lengkap = hasil_lengkap.merge(
                                st.session_state.sistem.wahana_df[['Nama Wahana', 'Kategori Pekerjaan', 'Status Gangguan']],
                                on='Nama Wahana',
                                how='left'
                            )
                            
                            # Tambahkan kolom match
                            hasil_lengkap['Match'] = hasil_lengkap['Preferensi Pekerjaan'] == hasil_lengkap['Kategori Pekerjaan']
                            hasil_lengkap['Match'] = hasil_lengkap['Match'].map({True: '✅ Match', False: '❌ Tidak Match'})
                            
                            # Urutkan berdasarkan wahana dan nama peserta
                            hasil_lengkap = hasil_lengkap.sort_values(['Nama Wahana', 'Nama Peserta'])
                            
                            # Tampilkan tabel dengan informasi lengkap
                            st.dataframe(
                                hasil_lengkap.style.apply(
                                    lambda x: ['background-color: #2ECC71; color: black' if x['Match'] == '✅ Match' else 
                                            'background-color: #E74C3C; color: white' for _ in x],
                                    axis=1
                                ),
                                use_container_width=True
                            )
                            
                            # Tampilkan tabulasi jadwal untuk setiap wahana
                            st.subheader("Detail Peserta per Wahana")
                            st.write("Pilih wahana untuk melihat daftar peserta:")
                            
                            # Urutkan nama wahana 
                            nama_wahana_list = sorted(peserta_per_wahana.keys())
                            
                            # Buat tabs untuk setiap wahana
                            wahana_tabs = st.tabs(nama_wahana_list)
                            
                            for i, nama_wahana in enumerate(nama_wahana_list):
                                with wahana_tabs[i]:
                                    # Tampilkan informasi wahana
                                    wahana_info = wahana_data.get(nama_wahana, {})
                                    
                                    col1, col2, col3 = st.columns(3)
                                    col1.metric("Kategori", wahana_info.get('Kategori Pekerjaan', 'N/A'))
                                    col2.metric("Status", wahana_info.get('Status Gangguan', 'N/A'))
                                    col3.metric("Kapasitas", wahana_info.get('Kapasitas Optimal', 0))
                                    
                                    # Tampilkan daftar peserta
                                    st.write(f"**Daftar Peserta di {nama_wahana}**")
                                    
                                    # Buat DataFrame dari daftar peserta
                                    peserta_df = pd.DataFrame(peserta_per_wahana[nama_wahana])
                                    
                                    # Tambahkan kolom match
                                    peserta_df['Match'] = peserta_df['Preferensi'] == wahana_info.get('Kategori Pekerjaan', '')
                                    peserta_df['Match'] = peserta_df['Match'].map({True: '✅ Match', False: '❌ Tidak Match'})
                                    
                                    # Tampilkan tabel dengan pewarnaan yang lebih baik
                                    st.dataframe(
                                        peserta_df.style.apply(
                                            lambda x: ['background-color: #2ECC71; color: black' if x['Match'] == '✅ Match' else 
                                                    'background-color: #E74C3C; color: white' for _ in x],
                                            axis=1
                                        ),
                                        use_container_width=True
                                    )
                                    
                                    # Tampilkan statistik match
                                    total_peserta = len(peserta_df)
                                    match_count = (peserta_df['Match'] == '✅ Match').sum()
                                    match_percent = (match_count / total_peserta * 100) if total_peserta > 0 else 0
                                    
                                    st.metric("Persentase Kesesuaian", f"{match_percent:.1f}%", f"{match_count}/{total_peserta} peserta")
                            
                            # Download jadwal lengkap
                            st.download_button(
                                label="📥 Download Jadwal Lengkap",
                                data=hasil_lengkap.to_csv(index=False),
                                file_name="jadwal_lengkap_penempatan.csv",
                                mime="text/csv",
                            )
                    
                    # Tampilkan kualitas penjadwalan akhir
                    st.subheader("⭐ Kualitas Penjadwalan Akhir")
                    
                    if hasattr(st.session_state.sistem, 'kualitas_penjadwalan'):
                        kualitas = st.session_state.sistem.kualitas_penjadwalan
                        
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.metric("Rata-rata Skor Kecocokan", f"{kualitas['rata_rata_skor']:.1f}/100")
                            st.info(f"**Interpretasi**: {kualitas['interpretasi']}")
                        
                        with col2:
                            # Visualisasi skor per wahana
                            if kualitas['per_wahana']:
                                skor_wahana_df = pd.DataFrame({
                                    'Wahana': list(kualitas['per_wahana'].keys()),
                                    'Rata-rata Skor': list(kualitas['per_wahana'].values())
                                }).sort_values('Rata-rata Skor', ascending=False)
                                
                                fig = px.bar(skor_wahana_df, 
                                            x='Wahana', 
                                            y='Rata-rata Skor',
                                            title='Rata-rata Skor Kecocokan per Wahana',
                                            color='Rata-rata Skor',
                                            color_continuous_scale='RdYlGn')
                                fig.update_layout(margin=dict(t=50, b=30))
                                st.plotly_chart(fig, use_container_width=True)
                            else:
                                st.info("Data kualitas per wahana tidak tersedia")
                    else:
                        st.info("Data kualitas penjadwalan tidak tersedia")
                        
                except Exception as e:
                    st.error(f"Gagal menampilkan hasil akhir: {str(e)}")
                    import traceback
                    st.code(traceback.format_exc())
            else:
                # Jika sudah ada simulasi tapi belum penyesuaian, tampilkan visualisasi status wahana
                st.info("⚠️ Silakan klik tombol 'Lakukan Penyesuaian Penempatan' di atas untuk melakukan redistribusi peserta berdasarkan kondisi gangguan.")
                
                # Tampilkan rangkuman status wahana
                st.subheader("📊 Ringkasan Status Wahana Setelah Gangguan")
                
                # Hitung jumlah wahana per status
                status_counts = st.session_state.sistem.wahana_df['Status Gangguan'].value_counts()
                
                # Tampilkan metrik
                cols = st.columns(4)
                metrics = {
                    'Stabil': {'color': '#27AE60', 'icon': '✅'},
                    'Underutilized': {'color': '#F39C12', 'icon': '⚠️'},
                    'Overload': {'color': '#C0392B', 'icon': '🚨'},
                    'Tutup': {'color': '#7F8C8D', 'icon': '❌'}
                }
                
                for i, (status, count) in enumerate(status_counts.items()):
                    if i < len(cols):
                        color = metrics.get(status, {}).get('color', '#7F8C8D')
                        icon = metrics.get(status, {}).get('icon', '')
                        cols[i].markdown(f"<div style='background-color: {color}; color: white; padding: 10px; border-radius: 5px; text-align: center;'><h3>{icon} {status}</h3><h2>{count}</h2></div>", unsafe_allow_html=True)

if __name__ == "__main__":
    main()