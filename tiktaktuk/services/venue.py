from django.db import connection
from .utils import dictfetchall


def _get_user_roles(cursor, session_id):
    cursor.execute("""
        SELECT us.user_id, r.role_name
        FROM USER_SESSION us
        JOIN ACCOUNT_ROLE ar ON us.user_id = ar.user_id
        JOIN ROLE r ON ar.role_id = r.role_id
        WHERE us.session_id = %s AND us.is_active = TRUE;
    """, [session_id])

    rows = cursor.fetchall()
    if not rows:
        return None, []

    user_id = rows[0][0]
    roles = [r[1] for r in rows]

    return user_id, roles


def create_venue(session_id, venue_name, capacity, address, city):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return None

        cursor.execute("""
            INSERT INTO VENUE (venue_name, capacity, address, city)
            VALUES (%s, %s, %s, %s)
            RETURNING venue_id;
        """, [venue_name, capacity, address, city])

        return cursor.fetchone()[0]


def update_venue(session_id, venue_id, venue_name, capacity, address, city):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        cursor.execute("""
            UPDATE VENUE
            SET venue_name = %s,
                capacity = %s,
                address = %s,
                city = %s
            WHERE venue_id = %s;
        """, [venue_name, capacity, address, city, venue_id])

    return True


def delete_venue(session_id, venue_id):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id or ("administrator" not in roles and "organizer" not in roles):
            return False

        cursor.execute("""
            DELETE FROM VENUE
            WHERE venue_id = %s;
        """, [venue_id])

    return True


def get_all_venues():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT venue_id, venue_name, capacity, address, city
            FROM VENUE;
        """)

        return dictfetchall(cursor)


def get_venue_by_id(venue_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT venue_id, venue_name, capacity, address, city
            FROM VENUE
            WHERE venue_id = %s;
        """, [venue_id])

        result = dictfetchall(cursor)

    return result[0] if result else None
