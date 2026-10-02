"""
Clinic Queue Analyzer - GUI Desktop App
Analisis data antrean klinik:
- Waktu tunggu
- Waktu layanan
- Jam sibuk
- Performa loket

Install:
    pip install pandas matplotlib

Jalankan:
    python clinic_queue_analyzer.py
"""

import os
import random
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from datetime import datetime, timedelta

import pandas as pd

import matplotlib
matplotlib.use("TkAgg")

from matplotlib.figure import Figure
from matplotlib.ticker import MaxNLocator
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


TIME_COLS = ("waktu_checkin", "waktu_dipanggil", "waktu_selesai")


def pad_hours(counts, min_bins=7):
    """Lebarkan rentang jam supaya grafik tidak hanya 1 batang raksasa.
    Jam kosong ditampilkan sebagai 0 pasien (batas 00-23)."""
    lo, hi = int(counts.index.min()), int(counts.index.max())
    kiri = True
    while hi - lo + 1 < min_bins and (lo > 0 or hi < 23):
        if kiri and lo > 0:
            lo -= 1
        elif hi < 23:
            hi += 1
        else:
            lo -= 1
        kiri = not kiri
    return counts.reindex(range(lo, hi + 1), fill_value=0)


class ClinicQueueAnalyzer(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Clinic Queue Analyzer | Smart Clinic Dashboard")
        self.geometry("1250x760")
        self.minsize(1000, 650)

        # =========================
        # THEME UI/UX KLINIK
        # =========================
        self.colors = {
            "navy": "#123B5D",
            "blue": "#1976D2",
            "teal": "#009688",
            "light": "#F4F8FB",
            "white": "#FFFFFF",
            "text": "#243746",
            "muted": "#6B7C8C",
            "border": "#D9E5EC",
            "success": "#2E8B70",
        }

        self.configure(bg=self.colors["light"])
        self._setup_styles()

        self.df = None

        self._build_layout()

    # =========================================================
    # USER INTERFACE
    # =========================================================

    def _setup_styles(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass

        c = self.colors

        style.configure("App.TFrame", background=c["light"])
        style.configure("Header.TFrame", background=c["navy"])
        style.configure("Card.TFrame", background=c["white"], relief="flat")
        style.configure(
            "Title.TLabel",
            background=c["navy"],
            foreground=c["white"],
            font=("Segoe UI", 22, "bold")
        )
        style.configure(
            "Subtitle.TLabel",
            background=c["navy"],
            foreground="#D9EAF5",
            font=("Segoe UI", 10)
        )
        style.configure(
            "Section.TLabel",
            background=c["light"],
            foreground=c["text"],
            font=("Segoe UI", 12, "bold")
        )
        style.configure(
            "CardTitle.TLabel",
            background=c["white"],
            foreground=c["muted"],
            font=("Segoe UI", 9)
        )
        style.configure(
            "CardValue.TLabel",
            background=c["white"],
            foreground=c["text"],
            font=("Segoe UI", 18, "bold")
        )
        style.configure(
            "Action.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(14, 8),
            foreground=c["navy"]
        )
        style.configure(
            "Primary.TButton",
            font=("Segoe UI", 9, "bold"),
            padding=(14, 8),
            foreground=c["white"],
            background=c["teal"]
        )
        style.map("Primary.TButton", background=[("active", "#00796B")])
        style.configure(
            "Treeview",
            background=c["white"],
            fieldbackground=c["white"],
            foreground=c["text"],
            rowheight=32,
            font=("Segoe UI", 9)
        )
        style.configure(
            "Treeview.Heading",
            background=c["navy"],
            foreground=c["white"],
            font=("Segoe UI", 9, "bold"),
            padding=8
        )
        style.map(
            "Treeview",
            background=[("selected", "#DDEFFC")],
            foreground=[("selected", c["navy"])]
        )
        style.configure("TEntry", padding=7)
        style.configure("TCombobox", padding=6)

    def _build_layout(self):
        c = self.colors

        # ---------- HEADER ----------
        header = ttk.Frame(self, style="Header.TFrame", padding=(24, 18))
        header.pack(side="top", fill="x")

        title_area = ttk.Frame(header, style="Header.TFrame")
        title_area.pack(side="left", fill="x", expand=True)

        ttk.Label(
            title_area,
            text="🏥  CLINIC QUEUE ANALYZER",
            style="Title.TLabel"
        ).pack(anchor="w")

        ttk.Label(
            title_area,
            text="Smart Dashboard untuk Analisis Antrean dan Pelayanan Klinik",
            style="Subtitle.TLabel"
        ).pack(anchor="w", pady=(4, 0))

        self.status_label = ttk.Label(
            header,
            text="●  SISTEM SIAP",
            background=c["navy"],
            foreground="#B9F6CA",
            font=("Segoe UI", 9, "bold")
        )
        self.status_label.pack(side="right", anchor="n", pady=8)

        # ---------- MAIN CONTAINER ----------
        body = ttk.Frame(self, style="App.TFrame", padding=18)
        body.pack(side="top", fill="both", expand=True)

        # ---------- ACTION BAR ----------
        action = ttk.Frame(body, style="App.TFrame")
        action.pack(side="top", fill="x", pady=(0, 14))

        ttk.Label(
            action,
            text="DATA ANTREAN",
            style="Section.TLabel"
        ).pack(side="left", padx=(0, 14))

        ttk.Button(
            action,
            text="📂  Buka CSV",
            command=self.load_csv,
            style="Action.TButton"
        ).pack(side="left", padx=4)

        ttk.Button(
            action,
            text="🧪  Data Contoh 20 Pasien",
            command=self.load_sample_data,
            style="Action.TButton"
        ).pack(side="left", padx=4)

        self.file_label = ttk.Label(
            action,
            text="Belum ada data dimuat",
            background=c["light"],
            foreground=c["muted"],
            font=("Segoe UI", 9)
        )
        self.file_label.pack(side="right")

        # ---------- INPUT CARD ----------
        input_card = ttk.Frame(body, style="Card.TFrame", padding=14)
        input_card.pack(side="top", fill="x", pady=(0, 14))

        ttk.Label(
            input_card,
            text="➕  Tambah Pasien Baru",
            background=c["white"],
            foreground=c["navy"],
            font=("Segoe UI", 11, "bold")
        ).pack(side="left", padx=(0, 18))

        ttk.Label(
            input_card,
            text="Nama",
            background=c["white"],
            foreground=c["muted"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 5))

        self.ent_nama = ttk.Entry(input_card, width=22)
        self.ent_nama.pack(side="left", padx=(0, 14))

        ttk.Label(
            input_card,
            text="Layanan",
            background=c["white"],
            foreground=c["muted"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 5))

        self.combo_layanan = ttk.Combobox(
            input_card,
            values=["Umum", "Gigi", "Spesialis", "Vaksinasi"],
            state="readonly",
            width=14
        )
        self.combo_layanan.set("Umum")
        self.combo_layanan.pack(side="left", padx=(0, 14))

        ttk.Label(
            input_card,
            text="Loket",
            background=c["white"],
            foreground=c["muted"],
            font=("Segoe UI", 9)
        ).pack(side="left", padx=(0, 5))

        self.combo_loket = ttk.Combobox(
            input_card,
            values=["Loket 1", "Loket 2", "Loket 3"],
            state="readonly",
            width=12
        )
        self.combo_loket.set("Loket 1")
        self.combo_loket.pack(side="left", padx=(0, 14))

        ttk.Button(
            input_card,
            text="Tambah Pasien",
            command=self.add_patient,
            style="Primary.TButton"
        ).pack(side="left")

        # Tombol untuk mengisi waktu dipanggil / selesai
        ttk.Button(
            input_card,
            text="Panggil",
            command=self.call_next,
            style="Action.TButton"
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            input_card,
            text="Selesai",
            command=lambda: self._update_selected("waktu_selesai"),
            style="Action.TButton"
        ).pack(side="left", padx=(8, 0))

        # ---------- STATISTICS ----------
        stats = ttk.Frame(body, style="App.TFrame")
        stats.pack(side="top", fill="x", pady=(0, 14))

        self.stat_vars = {
            "total": tk.StringVar(value="-"),
            "avg_wait": tk.StringVar(value="-"),
            "avg_service": tk.StringVar(value="-"),
            "peak_hour": tk.StringVar(value="-")
        }

        cards = [
            ("total", "TOTAL PASIEN", "👥"),
            ("avg_wait", "RATA-RATA WAKTU TUNGGU", "⏱"),
            ("avg_service", "RATA-RATA WAKTU LAYANAN", "🩺"),
            ("peak_hour", "JAM PALING SIBUK", "📊")
        ]

        for key, caption, icon in cards:
            card = ttk.Frame(stats, style="Card.TFrame", padding=13)
            card.pack(side="left", expand=True, fill="both", padx=4)

            ttk.Label(
                card,
                text=f"{icon}  {caption}",
                style="CardTitle.TLabel"
            ).pack(anchor="w")

            ttk.Label(
                card,
                textvariable=self.stat_vars[key],
                style="CardValue.TLabel"
            ).pack(anchor="w", pady=(6, 0))

        # ---------- CONTENT ----------
        content = ttk.Frame(body, style="App.TFrame")
        content.pack(side="top", fill="both", expand=True)

        # Table card
        table_card = ttk.Frame(content, style="Card.TFrame", padding=12)
        table_card.pack(side="left", fill="both", expand=True)

        ttk.Label(
            table_card,
            text="📋  Data Antrean Pasien",
            background=c["white"],
            foreground=c["navy"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        table_area = ttk.Frame(table_card)
        table_area.pack(fill="both", expand=True)

        columns = (
            "no_antrean",
            "nama",
            "layanan",
            "loket",
            "waktu_tunggu_menit"
        )

        self.tree = ttk.Treeview(
            table_area,
            columns=columns,
            show="headings"
        )

        headers = {
            "no_antrean": "No",
            "nama": "Nama Pasien",
            "layanan": "Layanan",
            "loket": "Loket",
            "waktu_tunggu_menit": "Tunggu (menit)"
        }

        widths = {
            "no_antrean": 60,
            "nama": 160,
            "layanan": 110,
            "loket": 90,
            "waktu_tunggu_menit": 120
        }

        for col in columns:
            self.tree.heading(col, text=headers[col])
            self.tree.column(col, width=widths[col], anchor="center")

        self.tree.column("nama", anchor="w")

        vsb = ttk.Scrollbar(
            table_area,
            orient="vertical",
            command=self.tree.yview
        )
        self.tree.configure(yscrollcommand=vsb.set)

        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Chart card
        chart_card = ttk.Frame(content, style="Card.TFrame", padding=12)
        chart_card.pack(side="left", fill="both", padx=(14, 0))

        ttk.Label(
            chart_card,
            text="📈  Analisis Jam Sibuk",
            background=c["white"],
            foreground=c["navy"],
            font=("Segoe UI", 11, "bold")
        ).pack(anchor="w", pady=(0, 8))

        chart_frame = ttk.Frame(chart_card, width=410)
        chart_frame.pack(fill="both", expand=True)
        chart_frame.pack_propagate(False)

        self.figure = Figure(
            figsize=(4.2, 4.5),
            dpi=100,
            facecolor=c["white"]
        )
        self.ax = self.figure.add_subplot(111)
        self.ax.set_facecolor(c["white"])

        self.canvas = FigureCanvasTkAgg(self.figure, master=chart_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        self._draw_empty_chart()

        # ---------- FOOTER ----------
        footer = ttk.Frame(self, style="Header.TFrame", padding=(18, 7))
        footer.pack(side="bottom", fill="x")

        ttk.Label(
            footer,
            text="Clinic Queue Analyzer  •  Sistem Analisis Antrean Klinik",
            background=c["navy"],
            foreground="#D9EAF5",
            font=("Segoe UI", 8)
        ).pack(side="left")

        ttk.Label(
            footer,
            text="Dashboard",
            background=c["navy"],
            foreground="#B9F6CA",
            font=("Segoe UI", 8, "bold")
        ).pack(side="right")

    # =========================================================
    # FITUR TAMBAH PASIEN BARU MANUAL
    # =========================================================

    def add_patient(self):
        nama = self.ent_nama.get().strip()
        layanan = self.combo_layanan.get()
        loket = self.combo_loket.get()

        if not nama:
            messagebox.showwarning(
                "Input Kosong",
                "Silakan masukkan nama pasien terlebih dahulu."
            )
            return

        now = datetime.now()

        if self.df is None or self.df.empty:
            no_antrean = 1
            self.df = pd.DataFrame(columns=[
                "no_antrean", "nama", "layanan", "loket",
                "waktu_checkin", "waktu_dipanggil", "waktu_selesai"
            ])
        else:
            no_antrean = int(self.df["no_antrean"].max()) + 1

        # Waktu dipanggil & selesai dikosongkan (NaT),
        # nanti diisi lewat tombol "Panggil" dan "Selesai".
        new_row = {
            "no_antrean": no_antrean,
            "nama": nama,
            "layanan": layanan,
            "loket": loket,
            "waktu_checkin": now,
            "waktu_dipanggil": pd.NaT,
            "waktu_selesai": pd.NaT
        }

        self.df = pd.concat(
            [self.df, pd.DataFrame([new_row])],
            ignore_index=True
        )
        self.ent_nama.delete(0, tk.END)
        self.file_label.config(text=f"Data manual • {len(self.df)} pasien")
        self.status_label.config(text="●  DATA AKTIF")
        self.analyze()

    def call_next(self):
        """Panggil pasien berikutnya sesuai nomor antrean (terkecil dulu)
        di antara pasien yang belum dipanggil. Tidak perlu memilih baris."""
        if self.df is None or self.df.empty:
            messagebox.showwarning("Data Kosong", "Belum ada data pasien.")
            return

        for tc in TIME_COLS:
            self.df[tc] = pd.to_datetime(
                self.df[tc], errors="coerce"
            ).astype("datetime64[ns]")

        menunggu = self.df[self.df["waktu_dipanggil"].isna()].sort_values("no_antrean")

        if menunggu.empty:
            messagebox.showinfo(
                "Antrean Kosong",
                "Semua pasien sudah dipanggil."
            )
            return

        no = int(menunggu.iloc[0]["no_antrean"])
        nama = menunggu.iloc[0]["nama"]

        mask = self.df["no_antrean"].astype(int) == no
        self.df.loc[mask, "waktu_dipanggil"] = pd.Timestamp.now()

        self.analyze()
        self.status_label.config(text=f"●  MEMANGGIL NO. {no} - {nama}")

        if self.tree.exists(str(no)):
            self.tree.selection_set(str(no))
            self.tree.see(str(no))

    def _update_selected(self, col):
        """Isi waktu_dipanggil / waktu_selesai untuk pasien yang dipilih di tabel."""
        if self.df is None or self.df.empty:
            messagebox.showwarning("Data Kosong", "Belum ada data pasien.")
            return

        sel = self.tree.selection()
        if sel:
            no = int(self.tree.item(sel[0])["values"][0])
        else:
            # Tidak ada baris dipilih: selesaikan pasien yang sedang dipanggil
            # dengan nomor antrean paling kecil.
            for tc in TIME_COLS:
                self.df[tc] = pd.to_datetime(
                    self.df[tc], errors="coerce"
                ).astype("datetime64[ns]")
            aktif = self.df[
                self.df["waktu_dipanggil"].notna()
                & self.df["waktu_selesai"].isna()
            ].sort_values("no_antrean")
            if aktif.empty:
                messagebox.showwarning(
                    "Tidak Ada Pasien",
                    "Tidak ada pasien yang sedang dilayani.\n"
                    "Tekan Panggil dulu, atau klik pasien di tabel."
                )
                return
            no = int(aktif.iloc[0]["no_antrean"])
        mask = self.df["no_antrean"].astype(int) == no

        # Pastikan kolom waktu bertipe datetime agar NaT/isi waktu konsisten
        for tc in TIME_COLS:
            self.df[tc] = pd.to_datetime(
                self.df[tc], errors="coerce"
            ).astype("datetime64[ns]")

        if col == "waktu_selesai" and self.df.loc[mask, "waktu_dipanggil"].isna().any():
            messagebox.showwarning(
                "Belum Dipanggil",
                "Pasien ini belum dipanggil. Tekan tombol Panggil dulu."
            )
            return

        self.df.loc[mask, col] = pd.Timestamp.now()
        self.analyze()

        # Pilih kembali baris yang tadi diklik
        if self.tree.exists(str(no)):
            self.tree.selection_set(str(no))

    # =========================================================
    # CHART KOSONG
    # =========================================================

    def _draw_empty_chart(self):

        self.ax.clear()

        self.ax.set_title(
            "Jumlah Pasien per Jam",
            fontsize=12,
            fontweight="bold",
            pad=12
        )

        self.ax.text(
            0.5, 0.5,
            "Belum ada data",
            ha="center",
            va="center"
        )

        self.ax.set_xticks([])
        self.ax.set_yticks([])

        self.figure.tight_layout()
        self.canvas.draw()

    # =========================================================
    # LOAD CSV
    # =========================================================

    def load_csv(self):

        path = filedialog.askopenfilename(
            title="Pilih File CSV",
            filetypes=[
                ("CSV Files", "*.csv"),
                ("All Files", "*.*")
            ]
        )

        if not path:
            return

        try:
            df = pd.read_csv(path)
            df.columns = df.columns.str.strip()
            self._validate_columns(df)

            if df.empty:
                raise ValueError("File CSV tidak memiliki data.")

            self.df = df

            filename = os.path.basename(path)

            self.file_label.config(
                text=f"File: {filename}  •  {len(df)} pasien"
            )
            self.status_label.config(text="●  DATA AKTIF")

            self.analyze()

        except Exception as e:
            messagebox.showerror(
                "Gagal Membuka File",
                f"Terjadi kesalahan:\n\n{e}"
            )

    # =========================================================
    # DATA CONTOH 20 PASIEN (NAMA RANDOM)
    # =========================================================

    def load_sample_data(self):

        random.seed(42)

        base_day = datetime(2026, 9, 23, 8, 0)

        nama_pasien_list = [
            "Andi Pratama", "Budi Santoso", "Citra Dewi", "Deni Kurniawan",
            "Eka Rahmawati", "Fajar Hidayat", "Gita Gutawa", "Hadi Wijaya",
            "Indah Permata", "Joko Widodo", "Kurnia Fitri", "Lestari Putri",
            "Muhammad Rizky", "Nadia Safira", "Oktavia Nur", "Putra Agung",
            "Qori Rahmah", "Rian Hidayat", "Siti Nurhaliza", "Taufik Hidayat"
        ]

        services = ["Umum", "Gigi", "Spesialis", "Vaksinasi"]
        loket_list = ["Loket 1", "Loket 2", "Loket 3"]

        rows = []
        t = base_day

        for i, nama in enumerate(nama_pasien_list, start=1):

            t += timedelta(minutes=random.randint(20, 40))
            wait_min = random.randint(5, 30)
            service_min = random.randint(20, 30)

            checkin = t
            dipanggil = checkin + timedelta(minutes=wait_min)
            selesai = dipanggil + timedelta(minutes=service_min)

            rows.append({
                "no_antrean": i,
                "nama": nama,
                "layanan": random.choice(services),
                "loket": random.choice(loket_list),
                "waktu_checkin": checkin,
                "waktu_dipanggil": dipanggil,
                "waktu_selesai": selesai
            })

        self.df = pd.DataFrame(rows)

        self.file_label.config(text="Data contoh • 20 pasien")
        self.status_label.config(text="●  DATA AKTIF")

        self.analyze()

    # =========================================================
    # VALIDASI KOLOM
    # =========================================================

    def _validate_columns(self, df):

        required = {
            "no_antrean",
            "nama",
            "layanan",
            "loket",
            "waktu_checkin",
            "waktu_dipanggil",
            "waktu_selesai"
        }

        missing = required - set(df.columns)

        if missing:
            raise ValueError(
                "Kolom CSV kurang:\n"
                + "\n".join(sorted(missing))
            )

    # =========================================================
    # ANALISIS DATA
    # =========================================================

    @staticmethod
    def _format_durasi(menit):
        """Ubah menit (float) jadi teks yang enak dibaca.
        Kalau di bawah 1 menit ditampilkan dalam detik, supaya
        hasil tes manual tidak tampil sebagai 0.0 menit."""
        if menit is None or pd.isna(menit):
            return "-"
        if menit < 1:
            return f"{int(round(menit * 60))} detik"
        return f"{menit:.1f} menit"

    def analyze(self):

        if self.df is None or self.df.empty:
            messagebox.showwarning(
                "Data Kosong",
                "Tidak ada data untuk dianalisis."
            )
            return

        # 1) Pastikan semua kolom waktu bertipe datetime
        for tc in TIME_COLS:
            self.df[tc] = pd.to_datetime(
                self.df[tc], errors="coerce"
            ).astype("datetime64[ns]")

        # 2) Hitung durasi pada salinan (NaN kalau salah satu waktu kosong)
        df = self.df.copy()

        df["tunggu_menit"] = (
            df["waktu_dipanggil"] - df["waktu_checkin"]
        ).dt.total_seconds() / 60

        df["layanan_menit"] = (
            df["waktu_selesai"] - df["waktu_dipanggil"]
        ).dt.total_seconds() / 60

        # Durasi negatif = data tidak valid, abaikan
        df.loc[df["tunggu_menit"] < 0, "tunggu_menit"] = pd.NA
        df.loc[df["layanan_menit"] < 0, "layanan_menit"] = pd.NA

        df["tunggu_menit"] = pd.to_numeric(df["tunggu_menit"], errors="coerce")
        df["layanan_menit"] = pd.to_numeric(df["layanan_menit"], errors="coerce")

        # 3) Statistik (hanya dari pasien yang datanya sudah lengkap)
        avg_wait = df["tunggu_menit"].mean()       # NaN jika belum ada
        avg_service = df["layanan_menit"].mean()   # NaN jika belum ada

        hours = df["waktu_checkin"].dt.hour.dropna().astype(int)
        counts = hours.value_counts().sort_index()

        self.stat_vars["total"].set(str(len(df)))
        self.stat_vars["avg_wait"].set(self._format_durasi(avg_wait))
        self.stat_vars["avg_service"].set(self._format_durasi(avg_service))

        if counts.empty:
            self.stat_vars["peak_hour"].set("-")
        else:
            self.stat_vars["peak_hour"].set(f"{int(counts.idxmax()):02d}:00")

        # 4) Isi ulang tabel
        selected = self.tree.selection()
        selected_id = selected[0] if selected else None

        self.tree.delete(*self.tree.get_children())

        for _, row in df.iterrows():
            no = int(row["no_antrean"])
            tunggu = row["tunggu_menit"]

            # Selalu 2 angka desimal supaya format seragam (0.53, 0.51, 1.40)
            tunggu_txt = "-" if pd.isna(tunggu) else f"{tunggu:.2f}"

            self.tree.insert(
                "",
                "end",
                iid=str(no),
                values=(no, row["nama"], row["layanan"], row["loket"], tunggu_txt)
            )

        if selected_id and self.tree.exists(selected_id):
            self.tree.selection_set(selected_id)

        # 5) Gambar grafik jam sibuk
        self._draw_peak_chart(counts)

    def _draw_peak_chart(self, counts):

        c = self.colors
        self.ax.clear()

        self.ax.set_title(
            "Jumlah Pasien per Jam",
            fontsize=12,
            fontweight="bold",
            pad=12
        )

        if counts.empty:
            self.ax.text(
                0.5, 0.5, "Belum ada data",
                ha="center", va="center"
            )
            self.ax.set_xticks([])
            self.ax.set_yticks([])
            self.figure.tight_layout()
            self.canvas.draw()
            return

        # Sertakan jam yang kosong (0 pasien) di antara jam terkecil dan terbesar
        counts = pad_hours(counts)

        peak_hour = counts.idxmax()
        bar_colors = [
            c["teal"] if h == peak_hour else c["blue"]
            for h in counts.index
        ]

        bars = self.ax.bar(
            [str(h) for h in counts.index],
            counts.values,
            color=bar_colors,
            width=0.6
        )

        # Angka di atas setiap batang
        for bar, val in zip(bars, counts.values):
            if val > 0:
                self.ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    str(int(val)),
                    ha="center",
                    va="bottom",
                    fontsize=8
                )

        self.ax.set_xlabel("Jam Check-in")
        self.ax.set_ylabel("Jumlah Pasien")
        self.ax.set_ylim(0, counts.max() + 1)
        self.ax.yaxis.set_major_locator(MaxNLocator(integer=True))
        self.ax.spines["top"].set_visible(False)
        self.ax.spines["right"].set_visible(False)

        self.figure.tight_layout()
        self.canvas.draw()


# =========================================================
# MAIN
# =========================================================

if __name__ == "__main__":
    app = ClinicQueueAnalyzer()
    app.mainloop()
