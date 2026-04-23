from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_roles_by_session


def create_venue(session_id, venue_name, capacity, address, city, seating_type):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return None

        cursor.execute("""
            INSERT INTO VENUE (venue_name, capacity, address, city, seating_type)
            VALUES (%s, %s, %s, %s, %s) RETURNING venue_id;
        """, [venue_name, capacity, address, city, seating_type])
        return cursor.fetchone()[0]


def update_venue(session_id, venue_id, venue_name, capacity, address, city, seating_type):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        cursor.execute("""
            UPDATE VENUE
            SET venue_name=%s, capacity=%s, address=%s, city=%s, seating_type=%s
            WHERE venue_id=%s;
        """, [venue_name, capacity, address, city, seating_type, venue_id])
    return True


def delete_venue(session_id, venue_id):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        try:
            cursor.execute(
                "DELETE FROM VENUE WHERE venue_id = %s;", [venue_id])
            return True
        except IntegrityError:
            return False


def get_all_venues(search_query=None):
    """
    R - Venue: Ditambah logika search berdasarkan nama/kota sesuai skenario.
    """
    query = "SELECT venue_id, venue_name, capacity, address, city, seating_type FROM VENUE"
    params = []

    if search_query:
        query += " WHERE venue_name ILIKE %s OR city ILIKE %s"
        params.extend([f"%{search_query}%", f"%{search_query}%"])

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return dictfetchall(cursor)


def get_venue_by_id(venue_id):
    with connection.cursor() as cursor:
        cursor.execute("SELECT * FROM VENUE WHERE venue_id = %s;", [venue_id])
        result = dictfetchall(cursor)
    return result[0] if result else None
