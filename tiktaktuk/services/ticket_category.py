from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session


def check_organizer_ownership(cursor, user_id, event_id):
    """ helper buat mastiin Organizer cuma bisa ngedit tiket event dia sendiri """
    cursor.execute(
        "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
    org_res = cursor.fetchone()
    if not org_res:
        return False

    cursor.execute(
        "SELECT organizer_id FROM EVENT WHERE event_id = %s;", [event_id])
    ev_res = cursor.fetchone()
    if not ev_res or ev_res[0] != org_res[0]:
        return False
    return True


def validate_venue_capacity(cursor, event_id, new_quota, exclude_category_id=None):
    """ Helper buat ngecek supaya kuota tiket nggak melebihi kapasitas venue """
    # ambil kapasitas venue dari event ini
    cursor.execute("""
        SELECT v.capacity 
        FROM EVENT e JOIN VENUE v ON e.venue_id = v.venue_id 
        WHERE e.event_id = %s;
    """, [event_id])
    cap_res = cursor.fetchone()
    if not cap_res:
        return False
    venue_capacity = cap_res[0]

    # hitung total kuota yang udah ada di event ini
    query = "SELECT COALESCE(SUM(quota), 0) FROM TICKET_CATEGORY WHERE tevent_id = %s"
    params = [event_id]

    if exclude_category_id:
        query += " AND category_id != %s"
        params.append(exclude_category_id)

    cursor.execute(query, params)
    current_total_quota = cursor.fetchone()[0]

    return (current_total_quota + new_quota) <= venue_capacity


def create_ticket_category(session_id, category_name, quota, price, tevent_id):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or (role != 'administrator' and role != 'organizer'):
            return None

        if role == 'organizer':
            if not check_organizer_ownership(cursor, user_id, tevent_id):
                return None

       # 1. Tambahkan int() pada quota
        if not validate_venue_capacity(cursor, tevent_id, int(quota)):
            print("Error: Penambahan kuota ini melebihi sisa kapasitas venue!")
            return None

        # 2. Tambahkan ::INTEGER dan ::NUMERIC pada query SQL
        cursor.execute("""
            INSERT INTO TICKET_CATEGORY (category_name, quota, price, tevent_id)
            VALUES (%s, %s::INTEGER, %s::NUMERIC, %s)
            RETURNING category_id;
        """, [category_name, quota, price, tevent_id])

        return cursor.fetchone()[0]


def update_ticket_category(session_id, category_id, category_name, quota, price):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or (role != 'administrator' and role != 'organizer'):
            return False

        # cari event_id dari category_id ini dulu
        cursor.execute(
            "SELECT tevent_id FROM TICKET_CATEGORY WHERE category_id = %s;", [category_id])
        res = cursor.fetchone()
        if not res:
            return False
        tevent_id = res[0]

        # validasi kepemilikan organizer
        if role == 'organizer':
            if not check_organizer_ownership(cursor, user_id, tevent_id):
                return False

        # validasi kapasitas
        # 1. Tambahkan int() pada quota
        if not validate_venue_capacity(cursor, tevent_id, int(quota), exclude_category_id=category_id):
            print("Error: Update kuota ini melebihi sisa kapasitas venue!")
            return False

        # 2. Tambahkan ::INTEGER dan ::NUMERIC pada query SQL
        cursor.execute("""
            UPDATE TICKET_CATEGORY
            SET category_name = %s, quota = %s::INTEGER, price = %s::NUMERIC
            WHERE category_id = %s;
        """, [category_name, quota, price, category_id])

    return True


def delete_ticket_category(session_id, category_id):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or (role != 'administrator' and role != 'organizer'):
            return False

        # cari event_id untuk cek hak akses Organizer
        cursor.execute(
            "SELECT tevent_id FROM TICKET_CATEGORY WHERE category_id = %s;", [category_id])
        res = cursor.fetchone()
        if not res:
            return False

        if role == 'organizer':
            if not check_organizer_ownership(cursor, user_id, res[0]):
                return False

        try:
            cursor.execute(
                "DELETE FROM TICKET_CATEGORY WHERE category_id = %s;", [category_id])
            return True
        except IntegrityError:
            # bakal ke-trigger karena relasi TICKET ke TICKET_CATEGORY pake ON DELETE RESTRICT
            # ini dibikin supaya gabisa hapus kategori yg tiketnya udah dibeli orang.
            # TODO: kalau mau pake CASCADE, harus handle logic kayak refund dkk.
            print(
                "Gagal hapus: Sudah ada tiket yang diterbitkan/dibeli untuk kategori ini!")
            return False


def get_all_ticket_categories(tevent_id=None):
    """
    note: bisa diakses Guest. Ditambahkan JOIN ke EVENT untuk ambil judul.
    """
    # Gunakan alias 'tc' untuk TICKET_CATEGORY dan 'e' untuk EVENT
    query = """
        SELECT tc.category_id, tc.category_name, tc.quota, tc.price, tc.tevent_id, e.event_title 
        FROM TICKET_CATEGORY tc
        JOIN EVENT e ON tc.tevent_id = e.event_id
    """
    params = []

    if tevent_id:
        query += " WHERE tc.tevent_id = %s"
        params.append(tevent_id)

    # Urutkan berdasarkan nama event, lalu nama kategori (sesuai skenario soal)
    query += " ORDER BY e.event_title ASC, tc.category_name ASC;"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return dictfetchall(cursor)


def get_ticket_category_by_id(category_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT tc.category_id, tc.category_name, tc.quota, tc.price, tc.tevent_id, e.event_title 
            FROM TICKET_CATEGORY tc
            JOIN EVENT e ON tc.tevent_id = e.event_id
            WHERE tc.category_id = %s;
        """, [category_id])
        result = dictfetchall(cursor)

    return result[0] if result else None
