import pandas as pd
import numpy as np
from collections import defaultdict
import random
import time
import math

class PenjadwalanAdaptif:
    def __init__(self, data_wahana_path, data_peserta_path):
        self.wahana_df = pd.read_excel(data_wahana_path, sheet_name='Data Wahana')
        self.peserta_df = pd.read_excel(data_wahana_path, sheet_name='Data Peserta')
        
        # Konversi data ke format yang lebih mudah diproses
        self.preprocess_data()
        
        self._skor_cache = {}
        
    def preprocess_data(self):
        # Membersihkan dan memformat data
        self.wahana_df['Bidang Penyakit'] = self.wahana_df['Bidang Penyakit'].str.split(', ')
        self.wahana_df['Kategori Pekerjaan'] = self.wahana_df['Kategori Pekerjaan'].str.split(', ')
        
        self.peserta_df['Minat Penyakit'] = self.peserta_df['Minat Penyakit'].str.split(', ')
        self.peserta_df['Preferensi Pekerjaan'] = self.peserta_df['Preferensi Pekerjaan'].str.split(', ')
        
    def hitung_skor_kecocokan(self, peserta, wahana):
        """Menghitung skor kecocokan antara peserta dan wahana dengan caching"""
        # Gunakan ID sebagai key untuk cache
        cache_key = (peserta['ID Peserta'], wahana['Wahana'])
        
        # Cek apakah skor sudah dihitung sebelumnya
        if cache_key in self._skor_cache:
            return self._skor_cache[cache_key]
        
        # Hitung skor seperti sebelumnya
        skor = 0
        
        # Kesesuaian bidang penyakit
        penyakit_match = len(set(peserta['Minat Penyakit']) & set(wahana['Bidang Penyakit']))
        skor += penyakit_match * 10
        
        # Kesesuaian preferensi pekerjaan
        pekerjaan_match = len(set(peserta['Preferensi Pekerjaan']) & set(wahana['Kategori Pekerjaan']))
        skor += pekerjaan_match * 5
        
        # Simpan ke cache untuk penggunaan berikutnya
        self._skor_cache[cache_key] = skor
        
        return skor
    
    def penjadwalan_awal(self):
        """Membuat penjadwalan awal berdasarkan skor kecocokan"""
        # Inisialisasi penjadwalan
        penjadwalan = defaultdict(list)
        kapasitas_terisi = {wahana['Wahana']: 0 for _, wahana in self.wahana_df.iterrows()}
        
        # Buat daftar peserta dan wahana
        peserta_list = [row for _, row in self.peserta_df.iterrows()]
        wahana_list = [row for _, row in self.wahana_df.iterrows()]
        
        # Hitung skor untuk semua kombinasi peserta-wahana
        skor_matrix = []
        for peserta in peserta_list:
            skor_peserta = []
            for wahana in wahana_list:
                skor_peserta.append(self.hitung_skor_kecocokan(peserta, wahana))
            skor_matrix.append(skor_peserta)
        
        # Lakukan penjadwalan dengan algoritma greedy
        for i, peserta in enumerate(peserta_list):
            # Dapatkan indeks wahana dengan skor tertinggi yang masih memiliki kapasitas
            skor_peserta = skor_matrix[i]
            wahana_terurut = sorted(
                [(skor, j) for j, skor in enumerate(skor_peserta)],
                key=lambda x: (-x[0], x[1])
            )
            
            for skor, j in wahana_terurut:
                wahana = wahana_list[j]
                if kapasitas_terisi[wahana['Wahana']] < wahana['Kapasitas']:
                    penjadwalan[wahana['Wahana']].append({
                        'ID Peserta': peserta['ID Peserta'],
                        'Nama': peserta['Nama'],
                        'Skor Kecocokan': skor
                    })
                    kapasitas_terisi[wahana['Wahana']] += 1
                    break
        
        self.penjadwalan_awal = penjadwalan
        self.kapasitas_terisi = kapasitas_terisi
        return penjadwalan
    
    def identifikasi_gangguan(self, skenario='normal'):
        """Mengidentifikasi wahana yang mengalami overload atau underutilized"""
        gangguan = {'overload': [], 'underutilized': []}
        
        for _, wahana in self.wahana_df.iterrows():
            nama_wahana = wahana['Wahana']
            jumlah_peserta = len(self.penjadwalan_awal[nama_wahana])
            
            if jumlah_peserta == 0:
                continue
                
            if skenario == 'normal':
                pasien = wahana['Pasien Normal']
            else:
                pasien = wahana['Pasien Gangguan']
            
            rasio = pasien / jumlah_peserta
            
            # Kriteria gangguan
            if rasio > 20:  # Overload
                gangguan['overload'].append({
                    'wahana': nama_wahana,
                    'rasio': rasio,
                    'pasien': pasien,
                    'peserta': jumlah_peserta
                })
            elif rasio < 5:  # Underutilized
                gangguan['underutilized'].append({
                    'wahana': nama_wahana,
                    'rasio': rasio,
                    'pasien': pasien,
                    'peserta': jumlah_peserta
                })
        
        return gangguan
    
    def redistribusi_adaptif(self, gangguan):
        """Melakukan penyesuaian penjadwalan berdasarkan identifikasi gangguan"""
        penjadwalan_baru = defaultdict(list)
        
        # Salin penjadwalan awal ke penjadwalan baru
        for wahana, peserta_list in self.penjadwalan_awal.items():
            penjadwalan_baru[wahana] = peserta_list.copy()
        
        # Proses redistribusi dari wahana overload ke underutilized
        for overload in gangguan['overload']:
            wahana_overload = overload['wahana']
            peserta_overload = penjadwalan_baru[wahana_overload].copy()
            
            # Cari wahana underutilized yang cocok
            for underutilized in gangguan['underutilized']:
                wahana_under = underutilized['wahana']
                
                # Dapatkan data wahana underutilized
                wahana_data = self.wahana_df[self.wahana_df['Wahana'] == wahana_under].iloc[0]
                kapasitas = wahana_data['Kapasitas']
                terisi = len(penjadwalan_baru[wahana_under])
                
                if terisi >= kapasitas:
                    continue
                
                # Cari peserta yang lebih cocok di wahana underutilized
                for i, peserta in enumerate(peserta_overload):
                    peserta_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta['ID Peserta']].iloc[0]
                    skor_sekarang = self.hitung_skor_kecocokan(peserta_data, wahana_data)
                    
                    # Jika lebih cocok di wahana underutilized, pindahkan
                    if skor_sekarang > peserta['Skor Kecocokan']:
                        # Pindahkan peserta
                        penjadwalan_baru[wahana_under].append({
                            'ID Peserta': peserta['ID Peserta'],
                            'Nama': peserta['Nama'],
                            'Skor Kecocokan': skor_sekarang
                        })
                        penjadwalan_baru[wahana_overload].remove(peserta)
                        
                        # Update kapasitas terisi
                        underutilized['peserta'] += 1
                        overload['peserta'] -= 1
                        
                        # Update rasio overload
                        if overload['peserta'] > 0:
                            overload['rasio'] = overload['pasien'] / overload['peserta']
                        else:
                            overload['rasio'] = float('inf')
                            
                        # Update rasio underutilized
                        underutilized['rasio'] = underutilized['pasien'] / underutilized['peserta']
                        
                        # Hentikan jika wahana underutilized sudah penuh
                        if len(penjadwalan_baru[wahana_under]) >= kapasitas:
                            break
                
                # Hentikan jika sudah cukup mengurangi overload
                if overload['rasio'] <= 20:
                    break
        
        self.penjadwalan_adaptif = penjadwalan_baru
        return penjadwalan_baru
    
    def evaluasi_penjadwalan(self, penjadwalan):
        """Mengevaluasi kualitas penjadwalan"""
        total_peserta = 0
        total_skor = 0
        match_sempurna = 0
        
        for wahana, peserta_list in penjadwalan.items():
            wahana_data = self.wahana_df[self.wahana_df['Wahana'] == wahana].iloc[0]
            
            for peserta in peserta_list:
                peserta_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta['ID Peserta']].iloc[0]
                skor = self.hitung_skor_kecocokan(peserta_data, wahana_data)
                
                total_skor += skor
                total_peserta += 1
                
                # Hitung match sempurna (skor maksimum)
                max_skor = (len(peserta_data['Minat Penyakit']) * 10 + 
                           len(peserta_data['Preferensi Pekerjaan']) * 5)
                if skor == max_skor:
                    match_sempurna += 1
        
        return {
            'rata_rata_skor': total_skor / total_peserta if total_peserta > 0 else 0,
            'persentase_match_sempurna': (match_sempurna / total_peserta) * 100 if total_peserta > 0 else 0,
            'total_peserta_terjadwal': total_peserta
        }
    
    def visualisasi_hasil(self):
        """Menghasilkan visualisasi sederhana dari hasil penjadwalan"""
        print("\n=== HASIL PENJADWALAN AWAL ===")
        for wahana, peserta_list in self.penjadwalan_awal.items():
            print(f"\nWahana: {wahana} ({len(peserta_list)} peserta)")
            for peserta in peserta_list:
                print(f"  - {peserta['ID Peserta']}: {peserta['Nama']} (Skor: {peserta['Skor Kecocokan']})")
        
        print("\n=== EVALUASI PENJADWALAN AWAL ===")
        eval_awal = self.evaluasi_penjadwalan(self.penjadwalan_awal)
        print(f"Rata-rata skor kecocokan: {eval_awal['rata_rata_skor']:.2f}")
        print(f"Persentase match sempurna: {eval_awal['persentase_match_sempurna']:.2f}%")
        print(f"Total peserta terjadwal: {eval_awal['total_peserta_terjadwal']}")
        
        # Identifikasi gangguan
        gangguan = self.identifikasi_gangguan(skenario='gangguan')
        
        print("\n=== IDENTIFIKASI GANGGUAN ===")
        print("\nWahana Overload:")
        for item in gangguan['overload']:
            print(f"{item['wahana']}: {item['rasio']:.1f} pasien/peserta (Pasien: {item['pasien']}, Peserta: {item['peserta']})")
        
        print("\nWahana Underutilized:")
        for item in gangguan['underutilized']:
            print(f"{item['wahana']}: {item['rasio']:.1f} pasien/peserta (Pasien: {item['pasien']}, Peserta: {item['peserta']})")
        
        # Redistribusi adaptif
        penjadwalan_baru = self.redistribusi_adaptif(gangguan)
        
        print("\n=== HASIL PENJADWALAN ADAPTIF ===")
        for wahana, peserta_list in penjadwalan_baru.items():
            print(f"\nWahana: {wahana} ({len(peserta_list)} peserta)")
            for peserta in peserta_list:
                print(f"  - {peserta['ID Peserta']}: {peserta['Nama']} (Skor: {peserta['Skor Kecocokan']})")
        
        print("\n=== EVALUASI PENJADWALAN ADAPTIF ===")
        eval_adaptif = self.evaluasi_penjadwalan(penjadwalan_baru)
        print(f"Rata-rata skor kecocokan: {eval_adaptif['rata_rata_skor']:.2f}")
        print(f"Persentase match sempurna: {eval_adaptif['persentase_match_sempurna']:.2f}%")
        print(f"Total peserta terjadwal: {eval_adaptif['total_peserta_terjadwal']}")
    
    # === NEW METHODS FOR GLOBAL OPTIMIZATION ===
    
    def optimasi_dengan_ilp(self):
        """Mengoptimalkan penjadwalan menggunakan Integer Linear Programming"""
        try:
            import pulp as pl
        except ImportError:
            print("PuLP library tidak tersedia. Silakan install dengan: pip install pulp")
            return self.penjadwalan_awal()
        
        # Inisialisasi problem
        problem = pl.LpProblem("OptimalAssignment", pl.LpMaximize)
        
        # Buat daftar peserta dan wahana
        peserta_ids = [row['ID Peserta'] for _, row in self.peserta_df.iterrows()]
        wahana_ids = [row['Wahana'] for _, row in self.wahana_df.iterrows()]
        
        # Variabel keputusan: x[p,w] = 1 jika peserta p ditempatkan di wahana w
        x = {}
        for p in peserta_ids:
            for w in wahana_ids:
                x[p,w] = pl.LpVariable(f"x_{p}_{w}", cat='Binary')
        
        # Hitung skor untuk semua kombinasi peserta-wahana
        skor = {}
        for _, peserta in self.peserta_df.iterrows():
            p_id = peserta['ID Peserta']
            for _, wahana in self.wahana_df.iterrows():
                w_id = wahana['Wahana']
                skor[p_id, w_id] = self.hitung_skor_kecocokan(peserta, wahana)
        
        # Fungsi tujuan: maksimumkan total skor kecocokan
        problem += pl.lpSum([skor[p,w] * x[p,w] for p in peserta_ids for w in wahana_ids])
        
        # Batasan 1: Setiap peserta ditempatkan maksimal di satu wahana
        for p in peserta_ids:
            problem += pl.lpSum([x[p,w] for w in wahana_ids]) <= 1  # Boleh tidak ditempatkan
        
        # Batasan 2: Kapasitas wahana tidak terlampaui
        for _, wahana in self.wahana_df.iterrows():
            w_id = wahana['Wahana']
            problem += pl.lpSum([x[p,w_id] for p in peserta_ids]) <= wahana['Kapasitas']
        
        # Selesaikan model
        solver = pl.PULP_CBC_CMD(msg=False)
        problem.solve(solver)
        
        # Jika solusi ditemukan
        if problem.status == 1:  # Status 1 = Optimal
            penjadwalan_optimal = defaultdict(list)
            
            # Ekstrak hasil
            for p in peserta_ids:
                for w in wahana_ids:
                    if pl.value(x[p,w]) == 1:
                        peserta_data = self.peserta_df[self.peserta_df['ID Peserta'] == p].iloc[0]
                        
                        penjadwalan_optimal[w].append({
                            'ID Peserta': p,
                            'Nama': peserta_data['Nama'],
                            'Skor Kecocokan': skor[p,w]
                        })
            
            return penjadwalan_optimal
        else:
            print("Tidak dapat menemukan solusi optimal")
            return self.penjadwalan_awal()  # Fallback ke algoritma greedy
    
    def optimasi_dengan_genetik(self, populasi_size=100, generasi=50):
        """Menggunakan algoritma genetik untuk optimasi global"""
        # Gunakan cache yang sudah di-precompute
        self.precompute_skor_matrix()
        
        # Buat data referensi untuk akses cepat
        peserta_list = [row for _, row in self.peserta_df.iterrows()]
        wahana_list = [row for _, row in self.wahana_df.iterrows()]
        n_peserta = len(peserta_list)
        n_wahana = len(wahana_list)
        
        # Gunakan skor matrix yang sudah di-precompute
        skor_matrix = np.zeros((n_peserta, n_wahana))
        for p_idx, peserta in enumerate(peserta_list):
            for w_idx, wahana in enumerate(wahana_list):
                # Ambil dari cache daripada hitung ulang
                skor_matrix[p_idx, w_idx] = self._skor_cache.get(
                    (peserta['ID Peserta'], wahana['Wahana']), 
                    self.hitung_skor_kecocokan(peserta, wahana)
                )
        
        # Batasan kapasitas
        kapasitas = {w_idx: wahana['Kapasitas'] for w_idx, wahana in enumerate(wahana_list)}
        
        # 1. Representasi: Kromosom adalah array di mana indeks = peserta, nilai = wahana
        # Nilai -1 berarti peserta tidak ditempatkan
        
        # 2. Inisialisasi populasi awal
        def create_chromosom():
            chromosom = np.full(n_peserta, -1)  # Default: tidak ada penempatan
            
            # Assign wahana secara acak dengan mempertimbangkan kapasitas
            kapasitas_terisi = {w_idx: 0 for w_idx in range(n_wahana)}
            
            # Shuffle peserta untuk penempatan random
            peserta_indices = list(range(n_peserta))
            random.shuffle(peserta_indices)
            
            for p_idx in peserta_indices:
                # Cari wahana dengan skor tertinggi yang masih punya kapasitas
                w_options = [(skor_matrix[p_idx, w_idx], w_idx) for w_idx in range(n_wahana) 
                            if kapasitas_terisi[w_idx] < kapasitas[w_idx]]
                
                if w_options:
                    w_options.sort(reverse=True)
                    _, best_w_idx = w_options[0]
                    chromosom[p_idx] = best_w_idx
                    kapasitas_terisi[best_w_idx] += 1
            
            return chromosom
        
        # Inisialisasi populasi
        populasi = [create_chromosom() for _ in range(populasi_size)]
        
        # 3. Fungsi evaluasi fitness
        def calculate_fitness(chromosom):
            # Total skor
            total_skor = 0
            for p_idx, w_idx in enumerate(chromosom):
                if w_idx >= 0:  # Jika peserta ditempatkan
                    total_skor += skor_matrix[p_idx, w_idx]
            
            # Penalti untuk pelanggaran kapasitas
            kapasitas_terisi = {w_idx: 0 for w_idx in range(n_wahana)}
            for w_idx in chromosom:
                if w_idx >= 0:
                    kapasitas_terisi[w_idx] += 1
            
            penalti = 0
            for w_idx, terisi in kapasitas_terisi.items():
                if terisi > kapasitas[w_idx]:
                    penalti += 1000 * (terisi - kapasitas[w_idx])
            
            return total_skor - penalti
        
        # 4. Seleksi orang tua (Tournament selection)
        def select_parent(populasi, fitness_scores, tournament_size=3):
            # Pilih kandidat secara acak
            candidates_idx = random.sample(range(len(populasi)), tournament_size)
            # Pilih yang terbaik dari kandidat
            best_idx = max(candidates_idx, key=lambda idx: fitness_scores[idx])
            return populasi[best_idx]
        
        # 5. Crossover (One-point crossover)
        def crossover(parent1, parent2):
            if random.random() > 0.7:  # 70% chance of crossover
                return parent1, parent2
            
            point = random.randint(1, len(parent1) - 1)
            child1 = np.concatenate([parent1[:point], parent2[point:]])
            child2 = np.concatenate([parent2[:point], parent1[point:]])
            return child1, child2
        
        # 6. Mutasi (Random reassignment)
        def mutate(chromosom, mutation_rate=0.05):
            mutated = chromosom.copy()
            
            for p_idx in range(len(mutated)):
                if random.random() < mutation_rate:
                    # 80% chance: set to -1 (tidak ditempatkan)
                    # 20% chance: tempatkan di wahana random
                    if random.random() < 0.8:
                        mutated[p_idx] = -1
                    else:
                        mutated[p_idx] = random.randint(0, n_wahana - 1)
            
            return mutated
        
        # 7. Evolusi
        best_fitness = -float('inf')
        best_chromosom = None
        
        for gen in range(generasi):
            # Calculate fitness for all chromosomes
            fitness_scores = [calculate_fitness(chromosom) for chromosom in populasi]
            
            # Track best solution
            gen_best_idx = fitness_scores.index(max(fitness_scores))
            if fitness_scores[gen_best_idx] > best_fitness:
                best_fitness = fitness_scores[gen_best_idx]
                best_chromosom = populasi[gen_best_idx].copy()
            
            # Create new population
            new_populasi = []
            
            # Elitism: simpan chromosom terbaik
            new_populasi.append(populasi[gen_best_idx])
            
            while len(new_populasi) < populasi_size:
                # Seleksi orang tua
                parent1 = select_parent(populasi, fitness_scores)
                parent2 = select_parent(populasi, fitness_scores)
                
                # Crossover
                child1, child2 = crossover(parent1, parent2)
                
                # Mutasi
                child1 = mutate(child1)
                child2 = mutate(child2)
                
                # Tambahkan ke populasi baru
                new_populasi.append(child1)
                if len(new_populasi) < populasi_size:
                    new_populasi.append(child2)
            
            populasi = new_populasi
        
        # 8. Konversi chromosom terbaik ke penjadwalan
        penjadwalan_optimal = defaultdict(list)
        
        for p_idx, w_idx in enumerate(best_chromosom):
            if w_idx >= 0:  # Jika peserta ditempatkan
                peserta = peserta_list[p_idx]
                wahana = wahana_list[w_idx]
                skor = skor_matrix[p_idx, w_idx]
                
                penjadwalan_optimal[wahana['Wahana']].append({
                    'ID Peserta': peserta['ID Peserta'],
                    'Nama': peserta['Nama'],
                    'Skor Kecocokan': skor
                })
        
        return penjadwalan_optimal
    
    def optimasi_dengan_simulated_annealing(self, temp_awal=100.0, temp_akhir=0.1, alpha=0.95, iterasi_per_temp=100):
        """Optimasi penjadwalan dengan simulated annealing"""
        import math
        import copy
        import random
        
        # Mulai dengan penjadwalan awal
        if not hasattr(self, 'penjadwalan_awal'):
            penjadwalan_awal = self.penjadwalan_awal()
        else:
            penjadwalan_awal = self.penjadwalan_awal
            
        current = copy.deepcopy(penjadwalan_awal)
        best = copy.deepcopy(current)
        
        # Definisikan fungsi untuk mengevaluasi solusi
        def evaluate_solution(penjadwalan):
            eval_res = self.evaluasi_penjadwalan(penjadwalan)
            return eval_res['rata_rata_skor'] * eval_res['total_peserta_terjadwal'] / 100
        
        # Fungsi untuk menghasilkan solusi tetangga
        def generate_neighbor(penjadwalan):
            neighbor = copy.deepcopy(penjadwalan)
            
            # Pilih secara acak: swap atau move
            if random.random() < 0.5:
                # Operasi swap: tukar 2 peserta antar wahana
                wahana_list = list(penjadwalan.keys())
                if len(wahana_list) < 2:
                    return neighbor
                
                wahana1, wahana2 = random.sample(wahana_list, 2)
                
                # Periksa apakah kedua wahana memiliki peserta
                if not neighbor[wahana1] or not neighbor[wahana2]:
                    return neighbor
                
                # Pilih peserta secara acak
                idx1 = random.randint(0, len(neighbor[wahana1]) - 1)
                idx2 = random.randint(0, len(neighbor[wahana2]) - 1)
                
                # Tukar peserta
                peserta1 = neighbor[wahana1][idx1]
                peserta2 = neighbor[wahana2][idx2]
                
                # Hitung skor untuk wahana tujuan
                peserta1_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta1['ID Peserta']].iloc[0]
                peserta2_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta2['ID Peserta']].iloc[0]
                
                wahana1_data = self.wahana_df[self.wahana_df['Wahana'] == wahana1].iloc[0]
                wahana2_data = self.wahana_df[self.wahana_df['Wahana'] == wahana2].iloc[0]
                
                skor1_baru = self.hitung_skor_kecocokan(peserta1_data, wahana2_data)
                skor2_baru = self.hitung_skor_kecocokan(peserta2_data, wahana1_data)
                
                # Lakukan penukaran
                neighbor[wahana1][idx1] = {
                    'ID Peserta': peserta2['ID Peserta'],
                    'Nama': peserta2['Nama'],
                    'Skor Kecocokan': skor2_baru
                }
                
                neighbor[wahana2][idx2] = {
                    'ID Peserta': peserta1['ID Peserta'],
                    'Nama': peserta1['Nama'],
                    'Skor Kecocokan': skor1_baru
                }
                
            else:
                # Operasi move: pindahkan peserta ke wahana lain
                wahana_list = list(penjadwalan.keys())
                if not wahana_list:
                    return neighbor
                    
                # Pilih wahana sumber dan tujuan
                wahana_source = random.choice(wahana_list)
                if not neighbor[wahana_source]:
                    return neighbor
                    
                wahana_target = random.choice(wahana_list)
                
                # Periksa kapasitas wahana tujuan
                wahana_target_data = self.wahana_df[self.wahana_df['Wahana'] == wahana_target].iloc[0]
                if len(neighbor[wahana_target]) >= wahana_target_data['Kapasitas']:
                    return neighbor
                
                # Pilih peserta untuk dipindahkan
                idx = random.randint(0, len(neighbor[wahana_source]) - 1)
                peserta = neighbor[wahana_source][idx]
                
                # Hitung skor untuk wahana tujuan
                peserta_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta['ID Peserta']].iloc[0]
                skor_baru = self.hitung_skor_kecocokan(peserta_data, wahana_target_data)
                
                # Pindahkan peserta
                neighbor[wahana_source].pop(idx)
                neighbor[wahana_target].append({
                    'ID Peserta': peserta['ID Peserta'],
                    'Nama': peserta['Nama'],
                    'Skor Kecocokan': skor_baru
                })
            
            return neighbor
        
        # Algoritma simulated annealing
        current_eval = evaluate_solution(current)
        best_eval = current_eval
        
        temp = temp_awal
        
        iterations_without_improvement = 0
        max_iterations_without_improvement = iterasi_per_temp * 5
        
        while temp > temp_akhir and iterations_without_improvement < max_iterations_without_improvement:
            for i in range(iterasi_per_temp):
                # Buat solusi tetangga
                neighbor = generate_neighbor(current)
                neighbor_eval = evaluate_solution(neighbor)
                
                # Hitung delta
                delta = neighbor_eval - current_eval
                
                # Keputusan penerimaan
                accept = False
                if delta > 0:  # Selalu terima solusi yang lebih baik
                    accept = True
                    iterations_without_improvement = 0
                else:
                    # Terima solusi yang lebih buruk dengan probabilitas tertentu
                    p = math.exp(delta / temp)
                    if random.random() < p:
                        accept = True
                        iterations_without_improvement += 1
                    else:
                        iterations_without_improvement += 1
                
                if accept:
                    current = neighbor
                    current_eval = neighbor_eval
                    
                    if current_eval > best_eval:
                        best = current.copy()
                        best_eval = current_eval
                        iterations_without_improvement = 0
            
            # Turunkan suhu
            temp *= alpha
        
        print(f"Simulated Annealing selesai pada temperatur {temp:.4f}")
        return best

    def redistribusi_global(self, gangguan):
            """
            Redistribusi dengan pendekatan global, mencoba semua kemungkinan perpindahan
            untuk mencapai solusi optimal
            """
            import copy
            
            # Salin jadwal awal
            penjadwalan_baru = defaultdict(list)
            for wahana, peserta_list in self.penjadwalan_awal.items():
                penjadwalan_baru[wahana] = copy.deepcopy(peserta_list)
            
            # Dapatkan data kapasitas wahana
            kapasitas = {}
            for _, wahana in self.wahana_df.iterrows():
                kapasitas[wahana['Wahana']] = wahana['Kapasitas']
            
            # Pertama, evaluasi semua kemungkinan perpindahan peserta
            perpindahan_kandidat = []
            
            # Dari wahana overload ke underutilized
            for overload in gangguan['overload']:
                wahana_overload = overload['wahana']
                
                for underutilized in gangguan['underutilized']:
                    wahana_under = underutilized['wahana']
                    
                    # Periksa kapasitas
                    if len(penjadwalan_baru[wahana_under]) >= kapasitas[wahana_under]:
                        continue
                    
                    # Cek setiap peserta di wahana overload
                    for peserta in penjadwalan_baru[wahana_overload]:
                        peserta_data = self.peserta_df[self.peserta_df['ID Peserta'] == peserta['ID Peserta']].iloc[0]
                        wahana_under_data = self.wahana_df[self.wahana_df['Wahana'] == wahana_under].iloc[0]
                        
                        skor_sekarang = peserta['Skor Kecocokan']
                        skor_baru = self.hitung_skor_kecocokan(peserta_data, wahana_under_data)
                        
                        # Evaluasi perubahan skor
                        delta_skor = skor_baru - skor_sekarang
                        
                        # Tambahkan ke kandidat perpindahan
                        perpindahan_kandidat.append({
                            'peserta': peserta,
                            'wahana_asal': wahana_overload,
                            'wahana_tujuan': wahana_under,
                            'skor_awal': skor_sekarang,
                            'skor_baru': skor_baru,
                            'delta': delta_skor
                        })
            
            # Urutkan kandidat perpindahan berdasarkan peningkatan skor
            perpindahan_kandidat.sort(key=lambda x: x['delta'], reverse=True)
            
            # Lakukan perpindahan optimal
            for perpindahan in perpindahan_kandidat:
                # Periksa kapasitas terkini
                if len(penjadwalan_baru[perpindahan['wahana_tujuan']]) >= kapasitas[perpindahan['wahana_tujuan']]:
                    continue
                
                # Perpindahan valid - pindahkan peserta
                try:
                    # Cari indeks peserta di wahana asal
                    peserta_idx = next(i for i, p in enumerate(penjadwalan_baru[perpindahan['wahana_asal']]) 
                                    if p['ID Peserta'] == perpindahan['peserta']['ID Peserta'])
                    
                    # Hapus dari wahana asal
                    peserta = penjadwalan_baru[perpindahan['wahana_asal']].pop(peserta_idx)
                    
                    # Tambahkan ke wahana tujuan dengan skor baru
                    penjadwalan_baru[perpindahan['wahana_tujuan']].append({
                        'ID Peserta': peserta['ID Peserta'],
                        'Nama': peserta['Nama'],
                        'Skor Kecocokan': perpindahan['skor_baru']
                    })
                    
                    # Update status gangguan
                    for overload in gangguan['overload']:
                        if overload['wahana'] == perpindahan['wahana_asal']:
                            overload['peserta'] -= 1
                            overload['rasio'] = overload['pasien'] / overload['peserta'] if overload['peserta'] > 0 else float('inf')
                    
                    for underutilized in gangguan['underutilized']:
                        if underutilized['wahana'] == perpindahan['wahana_tujuan']:
                            underutilized['peserta'] += 1
                            underutilized['rasio'] = underutilized['pasien'] / underutilized['peserta']
                    
                except (StopIteration, ValueError):
                    # Peserta mungkin telah dipindahkan oleh perpindahan sebelumnya
                    continue
                
                # Hentikan jika sudah cukup mengurangi overload
                # atau wahana underutilized sudah seimbang
                overload_resolved = all(o['rasio'] <= 20 for o in gangguan['overload'])
                underutilized_resolved = all(u['rasio'] >= 5 for u in gangguan['underutilized'])
                
                if overload_resolved and underutilized_resolved:
                    break
            
            return penjadwalan_baru

    def optimasi_dua_fase(self, gangguan=None, genetik_params=None):
            """Optimasi dua fase: optimasi global diikuti penyesuaian adaptif"""
            
            # Default parameter untuk genetik
            if genetik_params is None:
                genetik_params = {'populasi_size': 50, 'generasi': 20}
            
            # Fase 1: Optimasi global untuk penjadwalan awal yang lebih baik
            try:
                # Coba gunakan ILP jika tersedia dan dataset tidak terlalu besar
                if len(self.peserta_df) * len(self.wahana_df) <= 1000:
                    penjadwalan_global = self.optimasi_dengan_ilp()
                else:
                    # Dataset besar, skip ILP
                    raise ImportError("Skip ILP for large dataset")
            except:
                # Fallback ke algoritma genetik
                penjadwalan_global = self.optimasi_dengan_genetik(
                    populasi_size=genetik_params['populasi_size'], 
                    generasi=genetik_params['generasi']
                )
            
            # Simpan sebagai penjadwalan awal baru
            self.penjadwalan_awal = penjadwalan_global
            
            # Fase 2: Jika ada gangguan, lakukan redistribusi adaptif
            if gangguan:
                penjadwalan_final = self.redistribusi_adaptif(gangguan)
            else:
                # Jika tidak ada gangguan, identifikasi terlebih dahulu
                gangguan_terdeteksi = self.identifikasi_gangguan(skenario='normal')
                if gangguan_terdeteksi['overload'] or gangguan_terdeteksi['underutilized']:
                    penjadwalan_final = self.redistribusi_adaptif(gangguan_terdeteksi)
                else:
                    penjadwalan_final = penjadwalan_global
            
            return penjadwalan_final
        
    def penjadwalan_adaptif_optimal(self, strategi='two-phase', skenario='normal', genetik_params=None, sa_params=None):
            """
            Method utama untuk penjadwalan adaptif dengan optimasi global
            
            Parameters:
            -----------
            strategi : str
                Pilihan strategi optimasi: 'ilp', 'genetik', 'simulated_annealing', 'two-phase', 'greedy'
            skenario : str
                Skenario gangguan: 'normal' atau 'gangguan'
            genetik_params : dict
                Parameter untuk algoritma genetik: {'populasi_size': int, 'generasi': int}
            sa_params : dict
                Parameter untuk simulated annealing: {'temp_awal': float, 'iterasi_per_temp': int}
                
            Returns:
            --------
            dict
                Hasil penjadwalan optimal
            """
            
            # Default parameter
            if genetik_params is None:
                genetik_params = {'populasi_size': 100, 'generasi': 50}
            
            if sa_params is None:
                sa_params = {'temp_awal': 100.0, 'iterasi_per_temp': 100}
            
            # Langkah 1: Pilih strategi penjadwalan awal
            if strategi == 'ilp':
                try:
                    self.penjadwalan_awal = self.optimasi_dengan_ilp()
                except Exception as e:
                    print(f"Optimasi ILP gagal: {e}")
                    self.penjadwalan_awal = self.penjadwalan_awal()  # Gunakan greedy sebagai fallback
            
            elif strategi == 'genetik':
                self.penjadwalan_awal = self.optimasi_dengan_genetik(
                    populasi_size=genetik_params['populasi_size'], 
                    generasi=genetik_params['generasi']
                )
            
            elif strategi == 'simulated_annealing':
                # Mulai dengan greedy solution
                if not hasattr(self, 'penjadwalan_awal'):
                    self.penjadwalan_awal = self.penjadwalan_awal()
                # Kemudian optimalkan dengan simulated annealing
                self.penjadwalan_awal = self.optimasi_dengan_simulated_annealing(
                    temp_awal=sa_params['temp_awal'],
                    iterasi_per_temp=sa_params['iterasi_per_temp']
                )
            
            elif strategi == 'two-phase':
                return self.optimasi_dua_fase(gangguan=None, genetik_params=genetik_params)
            
            else:  # default to greedy
                self.penjadwalan_awal = self.penjadwalan_awal()
            
            # Langkah 2: Identifikasi gangguan
            gangguan = self.identifikasi_gangguan(skenario=skenario)
            
            # Langkah 3: Jika ada gangguan, lakukan redistribusi adaptif
            if gangguan['overload'] or gangguan['underutilized']:
                penjadwalan_final = self.redistribusi_adaptif(gangguan)
            else:
                penjadwalan_final = self.penjadwalan_awal
            
            return penjadwalan_final
        
    def bandingkan_strategi(self, skenario='normal', max_time_per_strategy=300, reduce_parameters=True, exclude_slow=False):
        """
        Membandingkan berbagai strategi optimasi dengan parameter tambahan untuk optimasi
        
        Parameters:
        -----------
        skenario : str
            Skenario gangguan: 'normal' atau 'gangguan'
        max_time_per_strategy : int
            Batas waktu maksimum per strategi (detik)
        reduce_parameters : bool
            Jika True, akan mengurangi parameter untuk algoritma yang berat
        exclude_slow : bool
            Jika True, akan melewati algoritma yang sangat lambat (seperti ILP) untuk dataset besar
        """
        import time
        import threading
        import platform
        
        # Pre-compute skor untuk mengoptimalkan pemrosesan
        self.precompute_skor_matrix()
        
        hasil = {}
        
        # Definisikan strategi yang akan dibandingkan
        strategi_list = ['greedy', 'genetik', 'simulated_annealing', 'two-phase']
        
        # Cek ukuran dataset untuk menentukan apakah akan menyertakan ILP
        dataset_size = len(self.peserta_df) * len(self.wahana_df)
        large_dataset = dataset_size > 1000  # Batas untuk dataset besar
        
        # Tambahkan ILP jika tersedia dan dataset tidak terlalu besar
        if not (large_dataset and exclude_slow):
            try:
                import pulp
                strategi_list.insert(1, 'ilp')
            except ImportError:
                pass
        
        # Konfigurasi parameter untuk algoritma berdasarkan ukuran dataset
        genetik_params = {'populasi_size': 20, 'generasi': 10} if reduce_parameters else {'populasi_size': 100, 'generasi': 50}
        sa_params = {'temp_awal': 50, 'iterasi_per_temp': 20} if reduce_parameters else {'temp_awal': 100, 'iterasi_per_temp': 100}
        
        # Helper function untuk menjalankan strategi dengan batas waktu
        def run_strategy_with_timeout(strategi):
            print(f"Menjalankan strategi: {strategi}")
            result_container = {}  # Container untuk menyimpan hasil dari thread
            error_container = {}   # Container untuk menyimpan error
            
            def target_function():
                try:
                    start_time = time.time()
                    
                    # Jalankan strategi berdasarkan jenis
                    if strategi == 'genetik':
                        penjadwalan = self.penjadwalan_adaptif_optimal(
                            strategi=strategi, 
                            skenario=skenario, 
                            genetik_params=genetik_params
                        )
                    elif strategi == 'simulated_annealing':
                        penjadwalan = self.penjadwalan_adaptif_optimal(
                            strategi=strategi, 
                            skenario=skenario, 
                            sa_params=sa_params
                        )
                    else:
                        penjadwalan = self.penjadwalan_adaptif_optimal(
                            strategi=strategi, 
                            skenario=skenario
                        )
                    
                    # Evaluasi hasil
                    evaluasi = self.evaluasi_penjadwalan(penjadwalan)
                    waktu_eksekusi = time.time() - start_time
                    
                    result_container['result'] = {
                        'evaluasi': evaluasi,
                        'waktu': waktu_eksekusi,
                        'penjadwalan': penjadwalan
                    }
                    
                    print(f"Selesai: {strategi} - Skor: {evaluasi['rata_rata_skor']:.2f}, Waktu: {waktu_eksekusi:.2f}s")
                
                except Exception as e:
                    error_container['error'] = str(e)
                    error_container['waktu'] = time.time() - start_time
            
            # Buat thread untuk strategi
            thread = threading.Thread(target=target_function)
            thread.daemon = True  # Daemon thread akan berhenti saat program utama selesai
            
            # Mulai dan tunggu thread
            start_time = time.time()
            thread.start()
            thread.join(timeout=max_time_per_strategy)  # Tunggu dengan timeout
            
            # Cek apakah thread selesai
            if thread.is_alive():
                # Thread timeout, belum selesai
                print(f"Timeout: {strategi} melebihi batas waktu {max_time_per_strategy} detik")
                return {'error': f"Timeout: melebihi batas waktu {max_time_per_strategy} detik", 'waktu': max_time_per_strategy}
            elif 'error' in error_container:
                # Thread selesai tapi terjadi error
                print(f"Error: {strategi} - {error_container['error']}")
                return {'error': error_container['error'], 'waktu': error_container.get('waktu', time.time() - start_time)}
            elif 'result' in result_container:
                # Thread berhasil
                return result_container['result']
            else:
                # Tidak ada hasil, kemungkinan thread selesai tanpa mengisi result_container
                return {'error': "Terjadi kesalahan yang tidak diketahui", 'waktu': time.time() - start_time}
        
        # Jalankan perbandingan secara serial
        for strategi in strategi_list:
            hasil[strategi] = run_strategy_with_timeout(strategi)
        
        # Tampilkan perbandingan
        print("\n=== PERBANDINGAN STRATEGI ===")
        print(f"{'Strategi':<20} {'Rata-rata Skor':<15} {'Match Sempurna':<15} {'Peserta':<10} {'Waktu (s)':<10}")
        print("-" * 70)
        
        for strategi, data in hasil.items():
            if 'error' in data:
                print(f"{strategi:<20} ERROR: {data['error']}")
            else:
                print(f"{strategi:<20} {data['evaluasi']['rata_rata_skor']:>14.2f} {data['evaluasi']['persentase_match_sempurna']:>14.2f}% {data['evaluasi']['total_peserta_terjadwal']:>9} {data['waktu']:>9.2f}")
        
        return hasil
        
    def visualisasi_perbandingan(self, hasil_perbandingan):
            """Visualisasi hasil perbandingan berbagai strategi"""
            try:
                import matplotlib.pyplot as plt
                
                strategi = list(hasil_perbandingan.keys())
                strategi_valid = [s for s in strategi if 'error' not in hasil_perbandingan[s]]
                
                if not strategi_valid:
                    print("Tidak ada data valid untuk divisualisasikan")
                    return None
                
                skor_rata = [hasil_perbandingan[s]['evaluasi']['rata_rata_skor'] for s in strategi_valid]
                match_sempurna = [hasil_perbandingan[s]['evaluasi']['persentase_match_sempurna'] for s in strategi_valid]
                peserta = [hasil_perbandingan[s]['evaluasi']['total_peserta_terjadwal'] for s in strategi_valid]
                waktu = [hasil_perbandingan[s]['waktu'] for s in strategi_valid]
                
                # Siapkan figure dengan 2x2 subplot
                fig, axes = plt.subplots(2, 2, figsize=(12, 10))
                fig.suptitle('Perbandingan Strategi Optimasi', fontsize=16)
                
                # Plot 1: Skor rata-rata
                axes[0, 0].bar(strategi_valid, skor_rata)
                axes[0, 0].set_title('Rata-rata Skor Kecocokan')
                axes[0, 0].set_ylabel('Skor')
                for i, v in enumerate(skor_rata):
                    axes[0, 0].text(i, v + 0.5, f'{v:.2f}', ha='center')
                
                # Plot 2: Persentase match sempurna
                axes[0, 1].bar(strategi_valid, match_sempurna)
                axes[0, 1].set_title('Persentase Match Sempurna')
                axes[0, 1].set_ylabel('%')
                for i, v in enumerate(match_sempurna):
                    axes[0, 1].text(i, v + 1, f'{v:.2f}%', ha='center')
                
                # Plot 3: Jumlah peserta terjadwal
                axes[1, 0].bar(strategi_valid, peserta)
                axes[1, 0].set_title('Total Peserta Terjadwal')
                axes[1, 0].set_ylabel('Jumlah')
                for i, v in enumerate(peserta):
                    axes[1, 0].text(i, v + 0.5, str(v), ha='center')
                
                # Plot 4: Waktu eksekusi
                axes[1, 1].bar(strategi_valid, waktu)
                axes[1, 1].set_title('Waktu Eksekusi')
                axes[1, 1].set_ylabel('Detik')
                axes[1, 1].set_yscale('log')
                for i, v in enumerate(waktu):
                    axes[1, 1].text(i, v * 1.1, f'{v:.2f}s', ha='center')
                
                # Adjust layout
                plt.tight_layout(rect=[0, 0, 1, 0.95])
                plt.show()
                
                return fig
            except ImportError:
                print("Matplotlib tidak tersedia. Silakan install dengan: pip install matplotlib")
                return None
            
    def precompute_skor_matrix(self):
            """Pre-compute semua skor kecocokan antara peserta dan wahana"""
            if hasattr(self, '_skor_matrix_df'):
                return self._skor_matrix_df
            
            # Buat dataframe kosong untuk menyimpan skor
            peserta_ids = self.peserta_df['ID Peserta'].tolist()
            wahana_ids = self.wahana_df['Wahana'].tolist()
            
            skor_matrix = {}
            
            # Hitung semua skor
            for _, peserta in self.peserta_df.iterrows():
                for _, wahana in self.wahana_df.iterrows():
                    skor = self.hitung_skor_kecocokan(peserta, wahana)
                    skor_matrix[(peserta['ID Peserta'], wahana['Wahana'])] = skor
            
            self._skor_matrix_df = skor_matrix
            return skor_matrix

    def check_optimization_effectiveness(self):
        """Memeriksa efektivitas optimasi cache"""
        # Hitung berapa banyak cache hit vs miss
        cache_size = len(self._skor_cache) if hasattr(self, '_skor_cache') else 0
        total_combinations = len(self.peserta_df) * len(self.wahana_df)
        
        print("\n=== OPTIMASI CACHE ===")
        print(f"Total kombinasi peserta-wahana: {total_combinations}")
        print(f"Cache size: {cache_size}")
        print(f"Coverage: {cache_size/total_combinations*100:.2f}%")
        
        # Tes kecepatan dengan dan tanpa cache
        import time
        
        # Reset cache untuk tes
        old_cache = self._skor_cache.copy() if hasattr(self, '_skor_cache') else {}
        self._skor_cache = {}
        
        # Tes tanpa cache
        start = time.time()
        for _, peserta in self.peserta_df.iterrows():
            for _, wahana in self.wahana_df.iterrows():
                self._skor_cache = {}  # Pastikan cache kosong
                self.hitung_skor_kecocokan(peserta, wahana)
        no_cache_time = time.time() - start
        
        # Tes dengan cache
        self._skor_cache = {}  # Reset cache
        start = time.time()
        for _, peserta in self.peserta_df.iterrows():
            for _, wahana in self.wahana_df.iterrows():
                self.hitung_skor_kecocokan(peserta, wahana)
        with_cache_time = time.time() - start
        
        # Restore original cache
        self._skor_cache = old_cache
        
        print(f"Waktu tanpa cache: {no_cache_time:.4f}s")
        print(f"Waktu dengan cache: {with_cache_time:.4f}s")
        print(f"Speedup: {no_cache_time/with_cache_time:.2f}x")
        
        return {
            'cache_size': cache_size,
            'total_combinations': total_combinations,
            'coverage': cache_size/total_combinations*100,
            'no_cache_time': no_cache_time,
            'with_cache_time': with_cache_time,
            'speedup': no_cache_time/with_cache_time
        }
# Contoh penggunaan
if __name__ == "__main__":
    # Inisialisasi sistem
    sistem = PenjadwalanAdaptif('DataDummy_PenjadwalanDokter_Maksimal.xlsx', 'DataDummy_PenjadwalanDokter_Maksimal.xlsx')
    
    # Buat penjadwalan awal
    penjadwalan_awal = sistem.penjadwalan_awal()
    
    # Visualisasi hasil
    sistem.visualisasi_hasil()
    
    # Bandingkan berbagai strategi
    hasil = sistem.bandingkan_strategi()
    
    # Visualisasikan perbandingan
    sistem.visualisasi_perbandingan(hasil)