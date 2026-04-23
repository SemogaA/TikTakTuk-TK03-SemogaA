from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_roles_by_session


def create_seat(session_id, venue_id, section, row_number, seat_number):
    """
    note: admin dan organizer nambahin layout kursi ke venue tertentu.
    hanya bisa ditambahin ke venue yang seating_type nya 'reserved'.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return None

        # validasi: pastikan venue-nya tipe reserved
        cursor.execute(
            "SELECT seating_type FROM VENUE WHERE venue_id = %s;", [venue_id])
        venue_data = cursor.fetchone()
        if not venue_data or venue_data[0] != 'reserved':
            print("error: kursi hanya bisa ditambahkan ke venue dengan reserved seating!")
            return None

        try:
            cursor.execute("""
                INSERT INTO SEAT (section, seat_number, row_number, venue_id)
                VALUES (%s, %s, %s, %s) RETURNING seat_id;
            """, [section, seat_number, row_number, venue_id])

            return cursor.fetchone()[0]
        except Exception as e:
            print(f"error create seat: {e}")
            return None


def update_seat(session_id, seat_id, section, row_number, seat_number):
    """
    note: admin/organizer update detail kursi.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        try:
            cursor.execute("""
                UPDATE SEAT 
                SET section = %s, row_number = %s, seat_number = %s
                WHERE seat_id = %s;
            """, [section, row_number, seat_number, seat_id])
            return True
        except Exception as e:
            print(f"error update seat: {e}")
            return False


def delete_seat(session_id, seat_id):
    """
    note: admin/organizer hapus kursi. 
    akan restrict (gagal) kalau kursi udah keburu di-booking di event apapun.
    TODO: kalau mau pake cascade, harus handle logic kayak refund dkk.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        try:
            cursor.execute("DELETE FROM SEAT WHERE seat_id = %s;", [seat_id])
            return True
        except IntegrityError:
            print(
                "gagal hapus: kursi ini sudah pernah dipesan (terdapat di histori has_relationship)!")
            return False


def get_event_seats(session_id, event_id):
    """
    kita harus narik kursi berdasarkan event_id biar tau dia terisi atau tersedia.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        if not user_id:
            return None

        # pastikan event valid dan ambil venue_id nya
        cursor.execute(
            "SELECT venue_id FROM EVENT WHERE event_id = %s;", [event_id])
        ev_data = cursor.fetchone()
        if not ev_data:
            return None
        venue_id = ev_data[0]

        # query list kursi + status ketersediaannya untuk event ini
        # kalau id kursi ini ada di tabel has_relationship yang nempel ke tiket untuk event ini (dan order ga dicancel), berarti terisi.
        query_list = """
            SELECT 
                s.seat_id, s.section, s.row_number, s.seat_number,
                CASE 
                    WHEN booked.seat_id IS NOT NULL THEN 'Terisi' 
                    ELSE 'Tersedia' 
                END as status
            FROM SEAT s
            LEFT JOIN (
                SELECT hr.seat_id
                FROM HAS_RELATIONSHIP hr
                JOIN TICKET t ON hr.ticket_id = t.ticket_id
                JOIN "ORDER" o ON t.torder_id = o.order_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                WHERE tc.tevent_id = %s AND o.payment_status != 'Cancelled'
            ) booked ON s.seat_id = booked.seat_id
            WHERE s.venue_id = %s
            ORDER BY s.section ASC, s.row_number ASC, s.seat_number ASC;
        """
        cursor.execute(query_list, [event_id, venue_id])
        seats = dictfetchall(cursor)

        # hitung rangkuman (total, tersedia, terisi)
        total_kursi = len(seats)
        terisi = sum(1 for seat in seats if seat['status'] == 'Terisi')
        tersedia = total_kursi - terisi

        summary = {
            "total_kursi": total_kursi,
            "tersedia": tersedia,
            "terisi": terisi
        }

        return {
            "summary": summary,
            "list_seat": seats
        }
