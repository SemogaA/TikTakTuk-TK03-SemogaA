from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session


def create_venue(session_id, venue_name, capacity, address, city, seating_type):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role not in ['administrator', 'organizer']:
            return None

        # --- DIBUNGKUS TRY-EXCEPT DAN RAISE ---
        try:
            cursor.execute("""
                INSERT INTO VENUE (venue_name, capacity, address, city, seating_type)
                VALUES (%s, %s, %s, %s, %s) RETURNING venue_id;
            """, [venue_name, capacity, address, city, seating_type])

            venue_id = cursor.fetchone()[0]
            connection.commit()
            return venue_id
        except Exception as e:
            raise e


def update_venue(session_id, venue_id, venue_name, capacity, address, city, seating_type):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role not in ['administrator', 'organizer']:
            return False

        # --- DIBUNGKUS TRY-EXCEPT DAN RAISE ---
        try:
            cursor.execute("""
                UPDATE VENUE
                SET venue_name=%s, capacity=%s, address=%s, city=%s, seating_type=%s
                WHERE venue_id=%s;
            """, [venue_name, capacity, address, city, seating_type, venue_id])

            connection.commit()
            return True
        except Exception as e:
            raise e


def delete_venue(session_id, venue_id):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role not in ['administrator', 'organizer']:
            return False

        # --- UBAH INTEGRITYERROR MENJADI RAISE ---
        try:
            cursor.execute(
                "DELETE FROM VENUE WHERE venue_id = %s;", [venue_id])
            connection.commit()

            return True
        except Exception as e:
            raise e


def get_all_venues(search_query=None, city=None, seating_type=None):
    # butuh helper WHERE
    query = "SELECT venue_id, venue_name, capacity, address, city, seating_type FROM VENUE WHERE 1=1"
    params = []

    if search_query:
        query += " AND (venue_name ILIKE %s OR address ILIKE %s)"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    if city:
        query += " AND city = %s"
        params.append(city)

    if seating_type:
        query += " AND seating_type = %s"
        params.append(seating_type)

    query += " ORDER BY venue_name ASC"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return dictfetchall(cursor)


def get_distinct_cities():
    """ambil daftar kota unik untuk dropdown filter"""
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT city FROM VENUE ORDER BY city ASC;")
        return [row[0] for row in cursor.fetchall()]


def get_venue_by_id(venue_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM VENUE WHERE venue_id = %s;", [venue_id])
        result = dictfetchall(cursor)
    return result[0] if result else None
