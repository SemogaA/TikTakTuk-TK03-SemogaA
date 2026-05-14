from django.db import connection, transaction, DatabaseError
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session
import uuid


def check_seat_availability(cursor, seat_id, event_id):
    """ helper buat ngecek apakah sebuah kursi beneran kosong di event tertentu """
    cursor.execute("""
        SELECT hr.seat_id
        FROM HAS_RELATIONSHIP hr
        JOIN TICKET t ON hr.ticket_id = t.ticket_id
        JOIN "ORDER" o ON t.torder_id = o.order_id
        JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
        WHERE tc.tevent_id = %s AND hr.seat_id = %s AND o.payment_status != 'Cancelled';
    """, [event_id, seat_id])

    # kalau ada hasil, berarti kursi terisi
    return cursor.fetchone() is None


def check_seat_belongs_to_event(cursor, seat_id, event_id):
    cursor.execute("""
        SELECT 1
        FROM SEAT s
        JOIN EVENT e ON s.venue_id = e.venue_id
        WHERE s.seat_id = %s AND e.event_id = %s;
    """, [seat_id, event_id])
    return cursor.fetchone() is not None


def create_ticket(session_id, tcategory_id, torder_id, seat_id=None):
    """
    note: admin & organizer bisa bikin tiket manual.
    harus nempel ke sebuah order_id yang valid.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or (role != 'administrator' and role != 'organizer'):
            return None, 'Anda tidak memiliki akses.'

        # ambil data event & tipe venue dari kategori tiket
        cursor.execute("""
            SELECT e.event_id, e.organizer_id, v.seating_type
            FROM TICKET_CATEGORY tc
            JOIN EVENT e ON tc.tevent_id = e.event_id
            JOIN VENUE v ON e.venue_id = v.venue_id
            WHERE tc.category_id = %s;
        """, [tcategory_id])
        ev_data = cursor.fetchone()

        if not ev_data:
            return None, 'Kategori tiket tidak ditemukan.'
        event_id, event_org_id, seating_type = ev_data

        cursor.execute("""
            SELECT DISTINCT tc.tevent_id
            FROM TICKET t
            JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
            WHERE t.torder_id = %s;
        """, [torder_id])
        order_event_ids = {row[0] for row in cursor.fetchall()}
        if event_id not in order_event_ids:
            return None, 'Kategori tiket tidak sesuai dengan event dari order.'

        # validasi kepemilikan organizer
        if role == 'organizer':
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_res = cursor.fetchone()
            if not org_res or org_res[0] != event_org_id:
                return None, 'Anda tidak berwenang membuat tiket untuk event ini.'

        # validasi rule kursi
        if seating_type == 'reserved':
            if not seat_id:
                return None, 'Venue reserved seating wajib mengisi seat_id.'
            if not check_seat_belongs_to_event(cursor, seat_id, event_id):
                return None, 'Kursi tidak sesuai dengan venue event.'
            if not check_seat_availability(cursor, seat_id, event_id):
                return None, 'Kursi sudah terisi oleh orang lain.'
        else:
            # venue free seating, abaikan seat_id walaupun dikirim dari frontend
            seat_id = None

        try:
            with transaction.atomic():
                ticket_code = f"TKT-{str(uuid.uuid4())[:8].upper()}"

                cursor.execute("""
                    INSERT INTO TICKET (ticket_code, tcategory_id, torder_id, status)
                    VALUES (%s, %s, %s, 'Valid') RETURNING ticket_id;
                """, [ticket_code, tcategory_id, torder_id])
                ticket_id = cursor.fetchone()[0]

                if seat_id:
                    cursor.execute("""
                        INSERT INTO HAS_RELATIONSHIP (seat_id, ticket_id)
                        VALUES (%s, %s);
                    """, [seat_id, ticket_id])

                return ticket_id, None
        except DatabaseError as e:
            return None, str(e)
        except Exception as e:
            return None, str(e)


def get_all_tickets(session_id):
    """
    menampilkan summary dan list tiket yang dibedakan per role.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)
        if not user_id:
            return None

        base_query = ""
        summary_query = ""
        params = []
        summary = {}

        if role == 'administrator':
            # admin liat semua tiket di platform
            summary_query = """
                SELECT 
                    COUNT(*) as total_ticket,
                    SUM(CASE WHEN status = 'Valid' THEN 1 ELSE 0 END) as jumlah_valid,
                    SUM(CASE WHEN status = 'Terpakai' THEN 1 ELSE 0 END) as terpakai
                FROM TICKET;
            """
            base_query = """
                SELECT t.ticket_id, t.ticket_code, t.status, 
                       tc.category_name, tc.price, e.event_id, e.event_title, e.event_datetime,
                       v.venue_name, v.seating_type, o.order_id AS torder_id,
                       s.seat_id,
                       c.full_name as customer_name,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' ' || s.row_number || '-' || s.seat_number
                       END AS seat,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' - Baris ' || s.row_number || ', No. ' || s.seat_number
                       END AS seat_label
                FROM TICKET t
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                JOIN "ORDER" o ON t.torder_id = o.order_id
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                LEFT JOIN HAS_RELATIONSHIP hr ON t.ticket_id = hr.ticket_id
                LEFT JOIN SEAT s ON hr.seat_id = s.seat_id
                ORDER BY e.event_datetime DESC;
            """

        elif role == 'organizer':
            # organizer cuma liat tiket untuk event mereka
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_res = cursor.fetchone()
            if not org_res:
                return None
            params = [org_res[0]]

            summary_query = """
                SELECT 
                    COUNT(t.ticket_id) as total_ticket,
                    SUM(CASE WHEN t.status = 'Valid' THEN 1 ELSE 0 END) as jumlah_valid,
                    SUM(CASE WHEN t.status = 'Terpakai' THEN 1 ELSE 0 END) as terpakai
                FROM TICKET t
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                WHERE e.organizer_id = %s;
            """
            base_query = """
                SELECT t.ticket_id, t.ticket_code, t.status, 
                       tc.category_name, tc.price, e.event_id, e.event_title, e.event_datetime,
                       v.venue_name, v.seating_type, o.order_id AS torder_id,
                       s.seat_id,
                       c.full_name as customer_name,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' ' || s.row_number || '-' || s.seat_number
                       END AS seat,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' - Baris ' || s.row_number || ', No. ' || s.seat_number
                       END AS seat_label
                FROM TICKET t
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                JOIN "ORDER" o ON t.torder_id = o.order_id
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                LEFT JOIN HAS_RELATIONSHIP hr ON t.ticket_id = hr.ticket_id
                LEFT JOIN SEAT s ON hr.seat_id = s.seat_id
                WHERE e.organizer_id = %s
                ORDER BY e.event_datetime DESC;
            """

        elif role == 'customer':
            # customer cuma liat tiket punya dia sendiri
            cursor.execute(
                "SELECT customer_id FROM CUSTOMER WHERE user_id = %s;", [user_id])
            cust_res = cursor.fetchone()
            if not cust_res:
                return None
            params = [cust_res[0]]

            summary_query = """
                SELECT 
                    COUNT(t.ticket_id) as total_ticket,
                    SUM(CASE WHEN t.status = 'Valid' THEN 1 ELSE 0 END) as jumlah_valid,
                    SUM(CASE WHEN t.status = 'Terpakai' THEN 1 ELSE 0 END) as terpakai
                FROM TICKET t
                JOIN "ORDER" o ON t.torder_id = o.order_id
                WHERE o.customer_id = %s;
            """
            base_query = """
                SELECT t.ticket_id, t.ticket_code, t.status, 
                       tc.category_name, tc.price, e.event_id, e.event_title, e.event_datetime,
                       v.venue_name, v.seating_type, o.order_id AS torder_id,
                       s.seat_id,
                       c.full_name AS customer_name,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' ' || s.row_number || '-' || s.seat_number
                       END AS seat,
                       CASE
                           WHEN s.seat_id IS NULL THEN NULL
                           ELSE s.section || ' - Baris ' || s.row_number || ', No. ' || s.seat_number
                       END AS seat_label
                FROM TICKET t
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                JOIN "ORDER" o ON t.torder_id = o.order_id
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                LEFT JOIN HAS_RELATIONSHIP hr ON t.ticket_id = hr.ticket_id
                LEFT JOIN SEAT s ON hr.seat_id = s.seat_id
                WHERE o.customer_id = %s
                ORDER BY e.event_datetime ASC;
            """
        else:
            return None

        # eksekusi query
        cursor.execute(summary_query, params)
        summary_res = dictfetchall(cursor)
        if summary_res:
            summary = summary_res[0]

        cursor.execute(base_query, params)
        list_ticket = dictfetchall(cursor)

        return {
            "summary": summary,
            "list_ticket": list_ticket
        }


def get_ticket_by_id(session_id, ticket_id):
    """
    ambil detail 1 tiket spesifik
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        if not user_id:
            return None

        cursor.execute("""
            SELECT t.*, tc.category_name, e.event_title, o.payment_status 
            FROM TICKET t
            JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
            JOIN EVENT e ON tc.tevent_id = e.event_id
            JOIN "ORDER" o ON t.torder_id = o.order_id
            WHERE t.ticket_id = %s;
        """, [ticket_id])
        result = dictfetchall(cursor)
        return result[0] if result else None


def update_ticket(session_id, ticket_id, status, seat_id=None):
    """
    note: hanya admin yang bisa ngubah data tiket (contoh ngubah status jadi terpakai)
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False

        if status not in ('Valid', 'Terpakai', 'Cancelled'):
            return False

        # ambil event_id, tipe seating, dan kursi saat ini buat validasi kursi
        cursor.execute("""
            SELECT tc.tevent_id, v.seating_type, hr.seat_id
            FROM TICKET t
            JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
            JOIN EVENT e ON tc.tevent_id = e.event_id
            JOIN VENUE v ON e.venue_id = v.venue_id
            LEFT JOIN HAS_RELATIONSHIP hr ON t.ticket_id = hr.ticket_id
            WHERE t.ticket_id = %s;
        """, [ticket_id])
        ticket_res = cursor.fetchone()
        if not ticket_res:
            return False
        event_id, seating_type, current_seat_id = ticket_res

        try:
            with transaction.atomic():
                cursor.execute("""
                    UPDATE TICKET SET status = %s WHERE ticket_id = %s;
                """, [status, ticket_id])

                # Opsi "Tanpa Kursi" melepas relasi kursi dari tiket.
                cursor.execute(
                    "DELETE FROM HAS_RELATIONSHIP WHERE ticket_id = %s;", [ticket_id])

                if seat_id and seating_type == 'reserved':
                    if not check_seat_belongs_to_event(cursor, seat_id, event_id):
                        print("error: kursi pengganti tidak sesuai dengan venue event!")
                        raise Exception("kursi tidak sesuai event")
                    if seat_id != str(current_seat_id) and not check_seat_availability(cursor, seat_id, event_id):
                        print("error: kursi pengganti sudah terisi!")
                        raise Exception("kursi tidak tersedia")

                    cursor.execute("""
                        INSERT INTO HAS_RELATIONSHIP (seat_id, ticket_id)
                        VALUES (%s, %s);
                    """, [seat_id, ticket_id])
            return True
        except Exception as e:
            print(f"error update ticket: {e}")
            return False


def delete_ticket(session_id, ticket_id):
    """
    note: hanya admin yang bisa ngapus tiket.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False

        with transaction.atomic():
            cursor.execute("DELETE FROM HAS_RELATIONSHIP WHERE ticket_id = %s;", [ticket_id])
            cursor.execute("DELETE FROM TICKET WHERE ticket_id = %s;", [ticket_id])
    return True
