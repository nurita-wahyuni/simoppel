
from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from datetime import datetime, date
from app.core.database import get_db_connection
from app.core.security import get_current_user
from app.schemas.schemas import ShipEntry, EntryUpdate, SubmitRequest
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# --- OPERATOR ENDPOINTS ---

@router.get("/entries")
def get_all_entries(
    operator_id: Optional[str] = None, 
    year: Optional[int] = None,
    month: Optional[int] = None,
    status: Optional[str] = None,
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
        
    cursor = conn.cursor(dictionary=True)
    try:
        # Build query dengan filter dinamis
        conditions = []
        params = []
        
        # operator_id might be None (not filtered), or an integer
        # Frontend might pass 'undefined' string if not careful, so let's validate
        if user['role'] == 'OPERATOR':
            operator_id = str(user['id'])

        if operator_id and operator_id.lower() != 'undefined':
            conditions.append("operator_id = %s")
            params.append(operator_id)
            
        if year is not None:
            conditions.append("YEAR(tanggal_laporan) = %s")
            params.append(year)
            
        if month is not None:
            conditions.append("MONTH(tanggal_laporan) = %s")
            params.append(month)
            
        if status is not None and status.lower() != 'undefined':
            if ',' in status:
                statuses = status.split(',')
                placeholders = ', '.join(['%s'] * len(statuses))
                conditions.append(f"status IN ({placeholders})")
                params.extend(statuses)
            else:
                conditions.append("status = %s")
                params.append(status)

        where_clause = ""
        if conditions:
            where_clause = "WHERE " + " AND ".join(conditions)
            
        sql = f"SELECT * FROM ship_entries {where_clause} ORDER BY tanggal_laporan DESC, id DESC"
        cursor.execute(sql, tuple(params))
        return cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

@router.get("/entries/periods")
def get_entry_periods(
    operator_id: Optional[int] = None,
    user: dict = Depends(get_current_user)
):
    if user["role"] == "OPERATOR":
        operator_id = user["id"]
    if operator_id is None:
        raise HTTPException(status_code=400, detail="Operator ID required")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """
            SELECT DISTINCT
                YEAR(tanggal_laporan) AS tahun,
                MONTH(tanggal_laporan) AS bulan
            FROM ship_entries
            WHERE operator_id = %s
              AND status IN ('SUBMITTED', 'APPROVED')
            ORDER BY tahun DESC, bulan DESC
            """,
            (operator_id,),
        )
        rows = cursor.fetchall()
        months_by_year = {}
        for r in rows:
            y = int(r["tahun"])
            m = int(r["bulan"])
            months_by_year.setdefault(str(y), set()).add(m)

        for y in list(months_by_year.keys()):
            months_by_year[y] = sorted(list(months_by_year[y]))

        years = sorted([int(y) for y in months_by_year.keys()], reverse=True)

        return {"years": years, "months_by_year": months_by_year}
    finally:
        cursor.close()
        conn.close()

@router.post("/entries/report")
def submit_batch_entries(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    if user.get("role") != "OPERATOR":
        raise HTTPException(status_code=403, detail="Hanya operator yang dapat melakukan submit")

    CATEGORY_MAP = {
        "luar_negeri": "Luar Negeri",
        "dalam_negeri": "Dalam Negeri",
        "perintis": "Perintis",
        "rakyat": "Rakyat",
    }

    def has_row_data(row: dict) -> bool:
        if not isinstance(row, dict):
            return False
        loa = float(row.get("loa") or 0)
        grt = float(row.get("grt") or 0)
        activity = str(row.get("activity") or "").strip()
        commodity = str(row.get("commodity") or "").strip()
        description = str(row.get("description") or "").strip()
        amount = float(row.get("amount") or 0)
        unit = str(row.get("unit") or "").strip()
        packaging = str(row.get("packaging") or "").strip()
        return any([
            loa != 0,
            grt != 0,
            bool(activity),
            bool(commodity),
            bool(description),
            amount != 0,
            bool(unit),
            bool(packaging),
        ])

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")

    cursor = conn.cursor()
    insert_sql = """
        INSERT INTO ship_entries (
            operator_id,
            kategori_pelayaran,
            loa,
            grt,
            jenis_kegiatan,
            komoditas,
            nama_muatan,
            jumlah_muatan,
            satuan_muatan,
            jenis_kemasan,
            tanggal_laporan,
            status,
            submitted_at,
            submit_method
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURDATE(), 'SUBMITTED', NOW(), 'MANUAL')
    """

    total_rows = 0
    try:
        for cat_key, rows in (payload or {}).items():
            kategori = CATEGORY_MAP.get(cat_key)
            if not kategori:
                continue
            if not isinstance(rows, list):
                continue
            for row in rows:
                if not has_row_data(row):
                    continue
                values = (
                    user["id"],
                    kategori,
                    float(row.get("loa") or 0),
                    float(row.get("grt") or 0),
                    (row.get("activity") or "Bongkar"),
                    (row.get("commodity") or None),
                    (row.get("description") or None),
                    float(row.get("amount") or 0),
                    (row.get("unit") or None),
                    (row.get("packaging") or None),
                )
                cursor.execute(insert_sql, values)
                total_rows += 1

        conn.commit()
        return {"message": "Entries submitted successfully", "rows_inserted": total_rows}
    except Exception as e:
        conn.rollback()
        logger.exception("Error submitting batch entries")
        raise HTTPException(status_code=500, detail="Gagal menyimpan data") from e
    finally:
        try:
            cursor.close()
        finally:
            conn.close()

@router.get("/entries/{entry_id}")
def get_entry_detail(
    entry_id: int,
    user: dict = Depends(get_current_user)
):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT 
                se.*, 
                u.nama as operator_name 
            FROM ship_entries se
            LEFT JOIN users u ON se.operator_id = u.id
            WHERE se.id = %s
        """
        cursor.execute(query, (entry_id,))
        entry = cursor.fetchone()
        
        if not entry:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
            
        # Security check: 
        # - Admin can view all
        # - Operator can only view their own
        # - Viewer can view all (assuming read-only access)
        
        is_admin = user['role'] == 'ADMIN'
        is_viewer = user['role'] == 'VIEWER'
        is_owner = str(entry['operator_id']) == str(user['id'])
        
        if not is_admin and not is_viewer and not is_owner:
             raise HTTPException(status_code=403, detail="Anda tidak memiliki akses ke data ini")
             
        return entry
    finally:
        cursor.close()
        conn.close()

@router.post("/entri")
def save_entries(entry: ShipEntry, user: dict = Depends(get_current_user)):
    # SECURITY CHECK
    if user['role'] != 'OPERATOR':
        raise HTTPException(status_code=403, detail="Hanya operator yang dapat melakukan entri")
        
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
    
    cursor = conn.cursor()
    try:
        # Override operator_id
        entry.operator_id = user['id']

        # Query untuk menyimpan data ke tabel ship_entries
        # MODIFIED: Default status changed from 'DRAFT' to 'SUBMITTED'
        sql = """INSERT INTO ship_entries (
            nama_kapal, kategori_pelayaran, loa, grt, 
            jenis_kegiatan, berat_ton, jumlah_penumpang,
            tanggal_kedatangan, tanggal_keberangkatan, tanggal_laporan,
            operator_id, status,
            jenis_muatan, nama_muatan, jumlah_muatan, satuan_muatan, jenis_kemasan,
            bendera, pemilik_agen, pelabuhan_asal, pelabuhan_tujuan, tanggal_tambat, dermaga, keterangan,
            submitted_at, submit_method
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'SUBMITTED', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), 'MANUAL')"""
        
        # Mapping data dari request body ke format tuple untuk MySQL
        values = (
            entry.nama_kapal, entry.kategori_pelayaran, entry.loa, entry.grt,
            entry.jenis_kegiatan, entry.berat_ton, entry.jumlah_penumpang,
            entry.tanggal_kedatangan, entry.tanggal_keberangkatan, entry.tanggal_laporan,
            entry.operator_id,
            entry.jenis_muatan, entry.nama_muatan, entry.jumlah_muatan, entry.satuan_muatan, entry.jenis_kemasan,
            entry.bendera, entry.pemilik_agen, entry.pelabuhan_asal, entry.pelabuhan_tujuan, entry.tanggal_tambat, entry.dermaga, entry.keterangan
        )
        
        cursor.execute(sql, values)
        conn.commit()
        
        return {"message": "Data berhasil disimpan"}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.put("/entries/{id}")
def update_entry(id: int, entry: ShipEntry, user: dict = Depends(get_current_user)):
    # SECURITY CHECK
    if user['role'] != 'OPERATOR':
        raise HTTPException(status_code=403, detail="Hanya operator yang dapat melakukan update")
        
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Cek Data Existing (Status & Ownership)
        cursor.execute("SELECT operator_id, status FROM ship_entries WHERE id = %s", (id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
        
        # Validasi Ownership (Operator ID harus sama dengan user login)
        if existing['operator_id'] != user['id']:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk mengedit data ini")
            
        # Validasi Status (Boleh edit jika SUBMITTED atau DRAFT, tapi tidak APPROVED)
        if existing['status'] == 'APPROVED':
            raise HTTPException(status_code=400, detail="Data sudah disetujui (APPROVED) dan tidak bisa diedit")
            
        # 2. Update Data
        sql = """UPDATE ship_entries SET
            nama_kapal = %s,
            kategori_pelayaran = %s,
            loa = %s,
            grt = %s,
            jenis_kegiatan = %s,
            berat_ton = %s,
            jumlah_penumpang = %s,
            tanggal_kedatangan = %s,
            tanggal_keberangkatan = %s,
            tanggal_laporan = %s,
            jenis_muatan = %s,
            nama_muatan = %s,
            jumlah_muatan = %s,
            satuan_muatan = %s,
            jenis_kemasan = %s,
            bendera = %s,
            pemilik_agen = %s,
            pelabuhan_asal = %s,
            pelabuhan_tujuan = %s,
            tanggal_tambat = %s,
            dermaga = %s,
            keterangan = %s
            WHERE id = %s
        """
        
        values = (
            entry.nama_kapal, entry.kategori_pelayaran, entry.loa, entry.grt,
            entry.jenis_kegiatan, entry.berat_ton, entry.jumlah_penumpang,
            entry.tanggal_kedatangan, entry.tanggal_keberangkatan, entry.tanggal_laporan,
            entry.jenis_muatan, entry.nama_muatan, entry.jumlah_muatan, entry.satuan_muatan, entry.jenis_kemasan,
            entry.bendera, entry.pemilik_agen, entry.pelabuhan_asal, entry.pelabuhan_tujuan, entry.tanggal_tambat, entry.dermaga, entry.keterangan,
            id
        )
        
        cursor.execute(sql, values)
        conn.commit()
        
        return {"message": "Data berhasil diperbarui"}
        
    except HTTPException as http_ex:
        conn.rollback()
        raise http_ex
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.delete("/entri/{id}")
def delete_entry(id: int, user: dict = Depends(get_current_user)):
    # SECURITY CHECK
    if user['role'] != 'OPERATOR':
        raise HTTPException(status_code=403, detail="Hanya operator yang dapat menghapus data")
        
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
    
    cursor = conn.cursor(dictionary=True)
    try:
        # 1. Cek Data Existing
        cursor.execute("SELECT operator_id, status FROM ship_entries WHERE id = %s", (id,))
        existing = cursor.fetchone()
        
        if not existing:
            raise HTTPException(status_code=404, detail="Data tidak ditemukan")
            
        # Validasi Ownership
        if existing['operator_id'] != user['id']:
            raise HTTPException(status_code=403, detail="Anda tidak memiliki akses untuk menghapus data ini")
            
        # Validasi Status (Boleh hapus jika SUBMITTED atau DRAFT)
        if existing['status'] == 'APPROVED':
            raise HTTPException(status_code=400, detail="Data sudah disetujui (APPROVED) dan tidak bisa dihapus")
            
        cursor.execute("DELETE FROM ship_entries WHERE id = %s", (id,))
        conn.commit()
        
        return {"message": "Data berhasil dihapus"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.post("/entries/manual-submit")
async def manual_submit_entries(
    payload: dict = Body(...),
    user: dict = Depends(get_current_user)
):
    if user['role'] != 'OPERATOR':
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    target_ids = payload.get("entry_ids") 
    
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now = datetime.now()
        
        if target_ids:
            # Submit specific IDs (if provided)
            format_strings = ','.join(['%s'] * len(target_ids))
            sql = f"""
                UPDATE ship_entries
                SET status = 'SUBMITTED',
                    submitted_at = %s,
                    submit_method = 'MANUAL'
                WHERE id IN ({format_strings})
                  AND operator_id = %s
            """
            params = [now] + target_ids + [user['id']]
            cursor.execute(sql, tuple(params))
            rows = cursor.rowcount
            
        else:
             raise HTTPException(status_code=400, detail="Invalid submit request")

        conn.commit()
        return {"message": f"Berhasil mensubmit {rows} data secara manual.", "rows": rows}
        
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

# --- ADMIN ENTRY ENDPOINTS ---

@router.put("/admin/entries/{entry_id}")
def update_entry_admin(entry_id: int, entry: EntryUpdate, user: dict = Depends(get_current_user)):
    if user['role'] != 'ADMIN':
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        # Check existence
        cursor.execute("SELECT id FROM ship_entries WHERE id = %s", (entry_id,))
        if not cursor.fetchone():
            raise HTTPException(status_code=404, detail="Entry not found")
            
        # Build update query dynamically
        update_fields = []
        params = []
        
        # entry.dict(exclude_unset=True) is deprecated in Pydantic v2, use model_dump
        # But we need to check if user has pydantic v2 or v1.
        # Requirements didn't specify version. Assuming v2.
        # But to be safe with v1/v2 compatibility:
        entry_data = entry.model_dump(exclude_unset=True) if hasattr(entry, 'model_dump') else entry.dict(exclude_unset=True)

        for field, value in entry_data.items():
            update_fields.append(f"{field} = %s")
            params.append(value)
            
        if not update_fields:
            return {"message": "No fields to update"}
            
        params.append(entry_id)
        sql = f"UPDATE ship_entries SET {', '.join(update_fields)} WHERE id = %s"
        
        cursor.execute(sql, tuple(params))
        conn.commit()
        
        return {"message": "Entry updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.delete("/admin/entries/{id}")
def delete_entry_admin(id: int, user: dict = Depends(get_current_user)):
    if user['role'] != 'ADMIN':
        raise HTTPException(status_code=403, detail="Unauthorized")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM ship_entries WHERE id = %s", (id,))
        conn.commit()
        return {"message": "Entry deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()

@router.get("/entries/draft-count")
def get_my_draft_count(operator_id: Optional[int] = None, user: dict = Depends(get_current_user)):
    # SECURITY LOGIC
    target_operator_id = operator_id
    if user['role'] == 'OPERATOR':
        target_operator_id = user['id'] # Force own ID
        
    if target_operator_id is None:
        raise HTTPException(status_code=400, detail="Operator ID required")

    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Database tidak terhubung")
    
    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT COUNT(*) as draft_count 
        FROM ship_entries 
        WHERE operator_id = %s AND status = 'DRAFT'
        """
        cursor.execute(query, (target_operator_id,))
        result = cursor.fetchone()
        
        return result 
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        cursor.close()
        conn.close()
