from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session


def create_promotion(session_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit):
    """
    note: hanya admin yang bisa membuat promosi.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False, "Sesi tidak valid atau Anda bukan Admin."

        try:
            cursor.execute("""
                INSERT INTO PROMOTION (promo_code, discount_type, discount_value, start_date, end_date, usage_limit)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING promotion_id;
            """, [promo_code, discount_type, discount_value, start_date, end_date, usage_limit])

            # Sukses
            return True, "Promosi berhasil dibuat!"
            
        except Exception as e:
            # Menangkap RAISE EXCEPTION dari Trigger PostgreSQL
            error_message = str(e).split('\n')[0]
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[1].strip()
            
            print(f"error create promotion: {error_message}")
            return False, error_message


def update_promotion(session_id, promotion_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit):
    """
    note: hanya admin yang bisa update promosi.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False, "Sesi tidak valid atau Anda bukan Admin."

        try:
            cursor.execute("""
                UPDATE PROMOTION
                SET promo_code = %s, 
                    discount_type = %s, 
                    discount_value = %s, 
                    start_date = %s, 
                    end_date = %s, 
                    usage_limit = %s
                WHERE promotion_id = %s;
            """, [promo_code, discount_type, discount_value, start_date, end_date, usage_limit, promotion_id])
            
            return True, "Promosi berhasil diperbarui!"
            
        except Exception as e:
            # Menangkap RAISE EXCEPTION dari Trigger PostgreSQL
            error_message = str(e).split('\n')[0]
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[1].strip()
                
            print(f"error update promotion: {error_message}")
            return False, error_message


def delete_promotion(session_id, promotion_id):
    """
    note: hanya admin yang bisa hapus promosi. 
    akan gagal (restrict) jika promo sudah pernah dipakai di order_promotion.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False, "Sesi tidak valid atau Anda bukan Admin."

        try:
            cursor.execute(
                "DELETE FROM PROMOTION WHERE promotion_id = %s;", [promotion_id])
            return True, "Promosi berhasil dihapus!"
            
        except IntegrityError:
            # error karena constraint on delete restrict (promo udah kepake)
            return False, "Gagal hapus: Promo sudah pernah digunakan oleh pengguna!"
            
        except Exception as e:
            error_message = str(e).split('\n')[0]
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[1].strip()
                
            print(f"error delete promotion: {error_message}")
            return False, error_message


def get_all_promotions(search='', discount_type=''):
    """
    Menampilkan list promo beserta rangkuman dashboard.
    Bisa diakses semua pengguna (termasuk Guest).
    """
    with connection.cursor() as cursor:
        # query summary (total promo, total pemakaian, dan tipe persentase)
        cursor.execute("""
            SELECT 
                (SELECT COUNT(*) FROM PROMOTION) as total_promo,
                (SELECT COUNT(*) FROM ORDER_PROMOTION) as total_penggunaan,
                (SELECT COUNT(*) FROM PROMOTION WHERE discount_type = 'PERCENTAGE') as tipe_persentase;
        """)
        summary_result = dictfetchall(cursor)
        summary = summary_result[0] if summary_result else {}

        # query list promotion (dengan fitur search, filter, dan perhitungan usage)
        query = """
            SELECT 
                p.promotion_id, p.promo_code, p.discount_type, p.discount_value, 
                p.start_date, p.end_date, p.usage_limit,
                (SELECT COUNT(*) FROM ORDER_PROMOTION op WHERE op.promotion_id = p.promotion_id) as used_count
            FROM PROMOTION p
            WHERE 1=1
        """
        params = []
        if search:
            query += " AND p.promo_code ILIKE %s"
            params.append(f"%{search}%")
        
        if discount_type:
            query += " AND p.discount_type = %s"
            params.append(discount_type)

        query += " ORDER BY p.start_date DESC;"
        
        cursor.execute(query, params)
        list_promotion = dictfetchall(cursor)

        return {
            "summary": summary,
            "list_promotion": list_promotion
        }

def get_promotion_by_id(promotion_id):
    """ 
    note: ambil detail spesifik 1 promo buat form edit 
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                promotion_id, promo_code, discount_type, discount_value, 
                start_date, end_date, usage_limit 
            FROM PROMOTION 
            WHERE promotion_id = %s;
        """, [promotion_id])

        result = dictfetchall(cursor)
        return result[0] if result else None