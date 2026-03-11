# 🛠️ Panduan Instalasi & Setup Lengkap

Dokumen ini berisi langkah-langkah detail untuk menginstal dan menjalankan project **Web Entries** dari awal hingga siap digunakan.

---

## 📋 Prasyarat Sistem

Sebelum memulai, pastikan perangkat Anda telah terinstal software berikut:

1.  **Python** (Versi 3.10 atau lebih baru) - [Download](https://www.python.org/downloads/)
    - _Pastikan mencentang "Add Python to PATH" saat instalasi._
2.  **Node.js** (Versi 18 atau lebih baru) - [Download](https://nodejs.org/)
3.  **MySQL Server** (Versi 8.0 atau MariaDB 10.4+) - Bisa menggunakan XAMPP atau MySQL Installer.
4.  **Git** (Opsional, untuk clone repository) - [Download](https://git-scm.com/)

---

## 🗄️ 1. Setup Database

1.  Aktifkan MySQL Server Anda.
2.  Buka terminal atau MySQL Client (seperti phpMyAdmin/DBeaver).
3.  Buat database baru bernama `db_entries`:
    ```sql
    CREATE DATABASE db_entries;
    ```
4.  Pastikan user database memiliki hak akses penuh. Default XAMPP biasanya:
    - **Host**: `localhost`
    - **User**: `root`
    - **Password**: (kosong)

---

## 🐍 2. Setup Backend (API)

Backend dibangun menggunakan **FastAPI (Python)**.

1.  Buka terminal dan masuk ke folder `backend`:

    ```bash
    cd backend
    ```

2.  **Buat Virtual Environment** (agar library python terisolasi):

    ```bash
    python -m venv venv
    ```

3.  **Aktifkan Virtual Environment**:

    - **Windows (Command Prompt)**:
      ```bash
      venv\Scripts\activate
      ```
    - **Windows (Git Bash)**:
      ```bash
      source venv/Scripts/activate
      ```
    - **Windows (PowerShell)**:
      ```powershell
      .\venv\Scripts\Activate.ps1
      ```
    - **Mac/Linux**:
      ```bash
      source venv/bin/activate
      ```
      _(Tanda berhasil: akan muncul `(venv)` di awal baris terminal)_

4.  **Install Dependencies**:

    ```bash
    pip install -r requirements.txt
    ```

5.  **Konfigurasi Environment Variables**:

    - Buat file baru bernama `.env` di dalam folder `backend`.
    - Salin isi berikut (sesuaikan dengan database Anda):
      ```env
      DB_HOST=localhost
      DB_USER=root
      DB_PASSWORD=
      DB_NAME=db_entries
      SECRET_KEY=rahasia_super_aman_12345
      ACCESS_TOKEN_EXPIRE_MINUTES=4320
      ```

6.  **Inisialisasi Database & Seeding Data**:

    - Jalankan script setup untuk membuat tabel:
      ```bash
      python setup_db.py
      ```
    - Jalankan script seeding untuk mengisi data awal (Akun Admin & Operator):
      ```bash
      python seed_direct.py
      ```
      _Note: Script ini akan membuat akun admin default dan beberapa data dummy._

7.  **Jalankan Server Backend**:

    ```bash
    python main.py
    ```

    Atau menggunakan Uvicorn langsung:

    ```bash
    uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
    ```

    ✅ **Backend Berjalan**: Akses di `http://localhost:8001`.
    📄 **Dokumentasi API (Swagger UI)**: `http://localhost:8001/docs`.

---

## ⚛️ 3. Setup Frontend (Web App)

Frontend dibangun menggunakan **React 19 + Vite**.

1.  Buka terminal baru (biarkan terminal backend tetap jalan).
2.  Masuk ke folder `frontend`:

    ```bash
    cd frontend
    ```

3.  **Install Dependencies**:

    ```bash
    npm install
    ```

4.  **Konfigurasi Environment Variables**:

    - Buat file baru bernama `.env` di dalam folder `frontend`.
    - Isi dengan konfigurasi berikut:
      ```env
      VITE_API_URL=http://localhost:8001
      ```

5.  **Jalankan Development Server**:

    ```bash
    npm run dev
    ```

    ✅ **Frontend Berjalan**: Akses di `http://localhost:5173`.

---

## 👤 4. Akun Pengguna Default

Setelah menjalankan script `seed_direct.py`, Anda dapat login menggunakan akun berikut:

| Role              | Email               | Password      | Keterangan                                                      |
| :---------------- | :------------------ | :------------ | :-------------------------------------------------------------- |
| **Administrator** | `admin@example.com` | `password123` | Akses penuh ke dashboard admin, rekap data, dan manajemen user. |
| **Operator**      | `andi@example.com`  | `password123` | Akses untuk input data kapal dan melihat laporan sendiri.       |
| **Operator**      | `budi@example.com`  | `password123` | Akun operator tambahan untuk simulasi.                          |

---

## 🔧 5. Troubleshooting (Masalah Umum)

### ❌ Backend Error: "Module not found"

- **Solusi**: Pastikan virtual environment (`venv`) sudah aktif sebelum menjalankan `pip install` atau `python main.py`. Cek apakah ada prefix `(venv)` di terminal.

### ❌ Database Error: "Access denied for user 'root'@'localhost'"

- **Solusi**: Cek file `.env` di folder backend. Pastikan `DB_PASSWORD` sesuai dengan password MySQL Anda. Jika menggunakan XAMPP default, kosongkan password.

### ❌ Frontend Error: "Network Error" / API tidak terpanggil

- **Solusi**:
  1. Pastikan backend server sudah jalan di port 8001.
  2. Cek file `.env` di frontend, pastikan `VITE_API_URL` mengarah ke `http://localhost:8001` (tanpa slash di akhir).
  3. Restart frontend server (`Ctrl+C` lalu `npm run dev`) agar perubahan `.env` terbaca.

### ❌ Error 500 saat Cetak PDF Rekap

- **Solusi**: Pastikan Anda telah melakukan _pull_ terbaru atau update kode backend `admin.py`. Masalah ini biasanya terkait data kontainer kosong yang tidak terinisialisasi dengan benar, namun sudah diperbaiki di versi terbaru.

---

## 🔄 Reset Data

Jika ingin menghapus semua data transaksi dan memulai dari nol (tanpa menghapus akun):

1. Masuk ke folder backend.
2. Jalankan:
   ```bash
   python clear_data.py
   ```
   _Script ini akan menghapus semua laporan kapal dan log, namun mempertahankan data user (Admin & Operator)._
