from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_roles_by_session


def create_promotion(session_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit):
    """
    note: hanya admin yang bisa membuat promosi.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or 'administrator' not in roles:
            return None

        try:
            cursor.execute("""
                INSERT INTO PROMOTION (promo_code, discount_type, discount_value, start_date, end_date, usage_limit)
                VALUES (%s, %s, %s, %s, %s, %s) RETURNING promotion_id;
            """, [promo_code, discount_type, discount_value, start_date, end_date, usage_limit])

            return cursor.fetchone()[0]
        except Exception as e:
            print(f"error create promotion: {e}")
            return None


def update_promotion(session_id, promotion_id, promo_code, discount_type, discount_value, start_date, end_date, usage_limit):
    """
    note: hanya admin yang bisa update promosi.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or 'administrator' not in roles:
            return False

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
            return True
        except Exception as e:
            print(f"error update promotion: {e}")
            return False


def delete_promotion(session_id, promotion_id):
    """
    note: hanya admin yang bisa hapus promosi. 
    akan gagal (restrict) jika promo sudah pernah dipakai di order_promotion.
    TODO: kalau mau pake cascade, harus handle logic kayak refund dkk.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or 'administrator' not in roles:
            return False

        try:
            cursor.execute(
                "DELETE FROM PROMOTION WHERE promotion_id = %s;", [promotion_id])
            return True
        except IntegrityError:
            # error karena constraint on delete restrict (promo udah kepake)
            print("gagal hapus: promo sudah pernah digunakan oleh pengguna!")
            return False
        except Exception as e:
            print(f"error delete promotion: {e}")
            return False


def get_all_promotions(session_id=None):
    """
    note: menampilkan list promo beserta rangkuman dashboard.
    bisa diakses semua pengguna (termasuk yang belum login, tapi data summary butuh logic terpisah jika diinginkan).
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

        # query list promotion (diurutkan berdasarkan promo terbaru / start_date terdekat)
        cursor.execute("""
            SELECT 
                promotion_id, promo_code, discount_type, discount_value, 
                start_date, end_date, usage_limit 
            FROM PROMOTION
            ORDER BY start_date DESC;
        """)
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
