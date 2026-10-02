"""
Clinic Queue Analyzer - Versi Web (Streamlit)

Install:
    pip install streamlit pandas matplotlib

Jalankan (hanya di laptop sendiri):
    streamlit run app.py

Jalankan supaya bisa dibuka HP lain di Wi-Fi yang sama:
    streamlit run app.py --server.address 0.0.0.0
    lalu buka  http://IP-LAPTOP:8501  dari HP (cek IP dengan perintah: ipconfig)

Catatan: data disimpan di memori server dan DIPAKAI BERSAMA semua pengunjung,
jadi pasien yang ditambah dari HP A langsung terlihat di HP B (klik "Segarkan").
Data hilang kalau server dimatikan / restart.
"""

import io
import random
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

# Zona waktu klinik. Server online biasanya memakai UTC, jadi ini penting
# supaya jam check-in dan "jam paling sibuk" sesuai waktu setempat.
# WIB = "Asia/Jakarta" | WITA = "Asia/Makassar" | WIT = "Asia/Jayapura"
TZ = ZoneInfo("Asia/Jakarta")

LAYANAN = ["Umum", "Gigi", "Spesialis", "Vaksinasi"]
LOKET = ["Loket 1", "Loket 2", "Loket 3"]
TIME_COLS = ["waktu_checkin", "waktu_dipanggil", "waktu_selesai"]
COLUMNS = ["no_antrean", "nama", "layanan", "loket"] + TIME_COLS

NAVY = "#123B5D"
BLUE = "#1976D2"
TEAL = "#009688"


# =========================================================
# DATA (dipakai bersama semua pengunjung)
# =========================================================

def empty_df():
    return pd.DataFrame({
        "no_antrean": pd.Series(dtype="int64"),
        "nama": pd.Series(dtype="object"),
        "layanan": pd.Series(dtype="object"),
        "loket": pd.Series(dtype="object"),
        "waktu_checkin": pd.Series(dtype="datetime64[ns]"),
        "waktu_dipanggil": pd.Series(dtype="datetime64[ns]"),
        "waktu_selesai": pd.Series(dtype="datetime64[ns]"),
    })


@st.cache_resource
def get_store():
    """Satu objek yang sama untuk semua sesi/pengunjung."""
    return {"df": empty_df(), "lock": threading.Lock(), "label": "Belum ada data"}


def now():
    """Waktu sekarang di zona klinik (tanpa info tz, satuan nanodetik)."""
    return pd.Timestamp(datetime.now(TZ).replace(tzinfo=None)).as_unit("ns")


def normalize(df):
    df = df.copy()
    df["no_antrean"] = pd.to_numeric(df["no_antrean"], errors="coerce").astype("int64")
    for tc in TIME_COLS:
        df[tc] = pd.to_datetime(df[tc], errors="coerce").astype("datetime64[ns]")
    return df.reset_index(drop=True)


def add_patient(store, nama, layanan, loket):
    with store["lock"]:
        df = store["df"]
        no = 1 if df.empty else int(df["no_antrean"].max()) + 1
        row = pd.DataFrame([{
            "no_antrean": no,
            "nama": nama,
            "layanan": layanan,
            "loket": loket,
            "waktu_checkin": now(),
            "waktu_dipanggil": pd.NaT,
            "waktu_selesai": pd.NaT,
        }])
        store["df"] = normalize(pd.concat([df, row], ignore_index=True))
        store["label"] = f"Data manual • {len(store['df'])} pasien"
    return no


def mark_time(store, no, col):
    """Isi waktu_dipanggil / waktu_selesai. Return (ok, pesan)."""
    with store["lock"]:
        df = normalize(store["df"])
        mask = df["no_antrean"] == no
        if not mask.any():
            return False, "Pasien tidak ditemukan."
        if col == "waktu_dipanggil" and df.loc[mask, "waktu_dipanggil"].notna().any():
            return False, "Pasien ini sudah dipanggil."
        if col == "waktu_selesai":
            if df.loc[mask, "waktu_dipanggil"].isna().any():
                return False, "Pasien ini belum dipanggil. Tekan Panggil dulu."
            if df.loc[mask, "waktu_selesai"].notna().any():
                return False, "Pasien ini sudah selesai."
        df.loc[mask, col] = now()
        store["df"] = df
    return True, "OK"


def set_data(store, df, label):
    with store["lock"]:
        store["df"] = normalize(df)
        store["label"] = label


def sample_data():
    random.seed(42)
    base = datetime.now(TZ).replace(hour=8, minute=0, second=0, microsecond=0, tzinfo=None)
    names = [
        "Andi Pratama", "Budi Santoso", "Citra Dewi", "Deni Kurniawan",
        "Eka Rahmawati", "Fajar Hidayat", "Gita Gutawa", "Hadi Wijaya",
        "Indah Permata", "Joko Widodo", "Kurnia Fitri", "Lestari Putri",
        "Muhammad Rizky", "Nadia Safira", "Oktavia Nur", "Putra Agung",
        "Qori Rahmah", "Rian Hidayat", "Siti Nurhaliza", "Taufik Hidayat",
    ]
    rows, t = [], base
    for i, nm in enumerate(names, start=1):
        t += timedelta(minutes=random.randint(20, 40))
        checkin = t
        dipanggil = checkin + timedelta(minutes=random.randint(5, 30))
        selesai = dipanggil + timedelta(minutes=random.randint(20, 30))
        rows.append({
            "no_antrean": i, "nama": nm,
            "layanan": random.choice(LAYANAN), "loket": random.choice(LOKET),
            "waktu_checkin": checkin, "waktu_dipanggil": dipanggil,
            "waktu_selesai": selesai,
        })
    return pd.DataFrame(rows)


# =========================================================
# ANALISIS
# =========================================================

def compute(df):
    d = normalize(df)
    d["tunggu_menit"] = (d["waktu_dipanggil"] - d["waktu_checkin"]).dt.total_seconds() / 60
    d["layanan_menit"] = (d["waktu_selesai"] - d["waktu_dipanggil"]).dt.total_seconds() / 60
    d.loc[d["tunggu_menit"] < 0, "tunggu_menit"] = float("nan")
    d.loc[d["layanan_menit"] < 0, "layanan_menit"] = float("nan")

    def status(r):
        if pd.notna(r["waktu_selesai"]):
            return "Selesai"
        if pd.notna(r["waktu_dipanggil"]):
            return "Dipanggil"
        return "Menunggu"

    d["status"] = d.apply(status, axis=1) if not d.empty else pd.Series(dtype="object")
    return d


def fmt_durasi(menit):
    if menit is None or pd.isna(menit):
        return "-"
    if menit < 1:
        return f"{int(round(menit * 60))} detik"
    return f"{menit:.1f} menit"


def hourly_counts(d):
    hours = d["waktu_checkin"].dt.hour.dropna().astype(int)
    counts = hours.value_counts().sort_index()
    if counts.empty:
        return counts
    return counts.reindex(range(int(counts.index.min()), int(counts.index.max()) + 1), fill_value=0)


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


def peak_chart(counts):
    fig, ax = plt.subplots(figsize=(5.2, 3.6), dpi=110)
    ax.set_title("Jumlah Pasien per Jam", fontsize=12, fontweight="bold", pad=10)
    if counts.empty:
        ax.text(0.5, 0.5, "Belum ada data", ha="center", va="center")
        ax.set_xticks([])
        ax.set_yticks([])
        fig.tight_layout()
        return fig

    counts = pad_hours(counts)
    peak = counts.idxmax()
    colors = [TEAL if h == peak else BLUE for h in counts.index]
    bars = ax.bar([f"{h:02d}" for h in counts.index], counts.values, color=colors, width=0.6)
    for b, v in zip(bars, counts.values):
        if v > 0:
            ax.text(b.get_x() + b.get_width() / 2, b.get_height(), str(int(v)),
                    ha="center", va="bottom", fontsize=8)
    ax.set_xlabel("Jam Check-in")
    ax.set_ylabel("Jumlah Pasien")
    ax.set_ylim(0, counts.max() + 1)
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return fig


def loket_performance(d):
    if d.empty:
        return pd.DataFrame()
    g = d.groupby("loket").agg(
        Pasien=("no_antrean", "count"),
        Tunggu=("tunggu_menit", "mean"),
        Layanan=("layanan_menit", "mean"),
    )
    g["Rata-rata Tunggu"] = g["Tunggu"].map(fmt_durasi)
    g["Rata-rata Layanan"] = g["Layanan"].map(fmt_durasi)
    return g[["Pasien", "Rata-rata Tunggu", "Rata-rata Layanan"]].reset_index().rename(columns={"loket": "Loket"})


# =========================================================
# UI
# =========================================================

st.set_page_config(page_title="Clinic Queue Analyzer", page_icon="🏥", layout="wide")

st.markdown(
    f"""
    <style>
      .hero {{background:{NAVY}; padding:22px 28px; border-radius:12px; margin-bottom:18px;}}
      .hero h1 {{color:#fff; margin:0; font-size:1.9rem;}}
      .hero p {{color:#D9EAF5; margin:4px 0 0 0;}}
      div[data-testid="stMetric"] {{
        background:#fff; border:1px solid #D9E5EC; border-radius:10px; padding:12px 16px;
      }}
    </style>
    <div class="hero">
      <h1>🏥 CLINIC QUEUE ANALYZER</h1>
      <p>Smart Dashboard untuk Analisis Antrean dan Pelayanan Klinik</p>
    </div>
    """,
    unsafe_allow_html=True,
)

store = get_store()

# ---------- pesan hasil aksi sebelumnya ----------
flash = st.session_state.pop("flash", None)
if flash:
    kind, text = flash
    {"ok": st.success, "warn": st.warning}.get(kind, st.info)(text)

# ---------- SIDEBAR: data ----------
with st.sidebar:
    st.header("Data Antrean")
    st.caption(store["label"])

    up = st.file_uploader("📂 Buka CSV", type=["csv"])
    if up is not None and st.button("Muat file CSV", use_container_width=True):
        try:
            raw = pd.read_csv(up)
            raw.columns = raw.columns.str.strip()
            missing = set(COLUMNS) - set(raw.columns)
            if missing:
                raise ValueError("Kolom CSV kurang: " + ", ".join(sorted(missing)))
            if raw.empty:
                raise ValueError("File CSV tidak memiliki data.")
            set_data(store, raw[COLUMNS], f"File: {up.name} • {len(raw)} pasien")
            st.session_state["flash"] = ("ok", f"CSV dimuat: {len(raw)} pasien.")
            st.rerun()
        except Exception as e:
            st.error(f"Gagal membuka file: {e}")

    if st.button("🧪 Data Contoh 20 Pasien", use_container_width=True):
        set_data(store, sample_data(), "Data contoh • 20 pasien")
        st.session_state["flash"] = ("ok", "Data contoh 20 pasien dimuat.")
        st.rerun()

    if not store["df"].empty:
        buf = io.StringIO()
        store["df"].to_csv(buf, index=False)
        st.download_button(
            "💾 Unduh data (CSV)", buf.getvalue(),
            file_name="data_antrean_klinik.csv", mime="text/csv",
            use_container_width=True,
        )

    st.divider()
    confirm = st.checkbox("Saya yakin ingin menghapus semua data")
    if st.button("🗑️ Kosongkan data", use_container_width=True, disabled=not confirm):
        set_data(store, empty_df(), "Belum ada data")
        st.session_state["flash"] = ("ok", "Semua data dikosongkan.")
        st.rerun()

    st.divider()
    st.caption("Data dipakai bersama semua pengunjung. Klik Segarkan untuk melihat perubahan dari perangkat lain.")

# ---------- INPUT: tambah pasien ----------
with st.container(border=True):
    st.subheader("➕ Tambah Pasien Baru")
    with st.form("form_tambah", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([3, 2, 2, 1.5])
        nama = c1.text_input("Nama")
        layanan = c2.selectbox("Layanan", LAYANAN)
        loket = c3.selectbox("Loket", LOKET)
        c4.write("")
        c4.write("")
        submit = c4.form_submit_button("Tambah Pasien", type="primary", use_container_width=True)

    if submit:
        if not nama.strip():
            st.session_state["flash"] = ("warn", "Silakan masukkan nama pasien terlebih dahulu.")
        else:
            no = add_patient(store, nama.strip(), layanan, loket)
            st.session_state["flash"] = ("ok", f"Pasien '{nama.strip()}' ditambahkan dengan nomor antrean {no}.")
        st.rerun()

# ---------- AKSI: panggil / selesai ----------
d = compute(store["df"])

with st.container(border=True):
    st.subheader("📣 Panggil & Selesaikan Pasien")
    if d.empty:
        st.info("Belum ada pasien. Tambahkan pasien dulu.")
    else:
        opsi = d["no_antrean"].tolist()
        info = {int(r.no_antrean): f"{int(r.no_antrean)}. {r.nama}  —  {r.status}" for r in d.itertuples()}
        a1, a2, a3, a4 = st.columns([4, 1.5, 1.5, 1.5])
        pilih = a1.selectbox("Pilih pasien", opsi, format_func=lambda n: info[int(n)], index=len(opsi) - 1)
        status = d.loc[d["no_antrean"] == pilih, "status"].iloc[0]
        a2.write("")
        a2.write("")
        a3.write("")
        a3.write("")
        a4.write("")
        a4.write("")
        if a2.button("Panggil", use_container_width=True, disabled=(status != "Menunggu")):
            ok, msg = mark_time(store, int(pilih), "waktu_dipanggil")
            st.session_state["flash"] = ("ok" if ok else "warn", "Pasien dipanggil." if ok else msg)
            st.rerun()
        if a3.button("Selesai", use_container_width=True, disabled=(status != "Dipanggil")):
            ok, msg = mark_time(store, int(pilih), "waktu_selesai")
            st.session_state["flash"] = ("ok" if ok else "warn", "Layanan pasien selesai." if ok else msg)
            st.rerun()
        if a4.button("🔄 Segarkan", use_container_width=True):
            st.rerun()

# ---------- STATISTIK ----------
counts = hourly_counts(d) if not d.empty else pd.Series(dtype="int64")
m1, m2, m3, m4 = st.columns(4)
m1.metric("👥 TOTAL PASIEN", len(d))
m2.metric("⏱ RATA-RATA WAKTU TUNGGU", fmt_durasi(d["tunggu_menit"].mean()) if not d.empty else "-")
m3.metric("🩺 RATA-RATA WAKTU LAYANAN", fmt_durasi(d["layanan_menit"].mean()) if not d.empty else "-")
m4.metric("📊 JAM PALING SIBUK", f"{int(counts.idxmax()):02d}:00" if not counts.empty else "-")

# ---------- TABEL + GRAFIK ----------
left, right = st.columns([3, 2])

with left:
    st.subheader("📋 Data Antrean Pasien")
    if d.empty:
        st.info("Belum ada data.")
    else:
        view = pd.DataFrame({
            "No": d["no_antrean"],
            "Nama Pasien": d["nama"],
            "Layanan": d["layanan"],
            "Loket": d["loket"],
            "Status": d["status"],
            "Check-in": d["waktu_checkin"].dt.strftime("%H:%M:%S").fillna("-"),
            "Tunggu (menit)": d["tunggu_menit"].map(
                lambda v: "-" if pd.isna(v) else f"{v:.2f}"),
            "Layanan (menit)": d["layanan_menit"].map(
                lambda v: "-" if pd.isna(v) else f"{v:.2f}"),
        })
        st.dataframe(view, hide_index=True, use_container_width=True, height=380)

with right:
    st.subheader("📈 Analisis Jam Sibuk")
    fig = peak_chart(counts)
    st.pyplot(fig)
    plt.close(fig)

st.subheader("🏢 Performa Loket")
perf = loket_performance(d)
if perf.empty:
    st.caption("Belum ada data.")
else:
    st.dataframe(perf, hide_index=True, use_container_width=True)
