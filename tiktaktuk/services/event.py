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


def create_event(session_id, event_title, event_datetime, venue_id, organizer_id=None):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id:
            return None

        if "organizer" in roles:
            cursor.execute("""
                SELECT organizer_id
                FROM ORGANIZER
                WHERE user_id = %s;
            """, [user_id])

            result = cursor.fetchone()
            if not result:
                return None

            organizer_id = result[0]

        elif "administrator" in roles:
            if not organizer_id:
                return None
        else:
            return None

        cursor.execute("""
            INSERT INTO EVENT (event_title, event_datetime, venue_id, organizer_id)
            VALUES (%s, %s, %s, %s)
            RETURNING event_id;
        """, [event_title, event_datetime, venue_id, organizer_id])

        return cursor.fetchone()[0]


def update_event(session_id, event_id, event_title, event_datetime, venue_id):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id:
            return False

        if "administrator" in roles:
            cursor.execute("""
                UPDATE EVENT
                SET event_title = %s,
                    event_datetime = %s,
                    venue_id = %s
                WHERE event_id = %s;
            """, [event_title, event_datetime, venue_id, event_id])

        elif "organizer" in roles:
            cursor.execute("""
                SELECT organizer_id
                FROM ORGANIZER
                WHERE user_id = %s;
            """, [user_id])

            result = cursor.fetchone()
            if not result:
                return False

            organizer_id = result[0]

            cursor.execute("""
                UPDATE EVENT
                SET event_title = %s,
                    event_datetime = %s,
                    venue_id = %s
                WHERE event_id = %s
                  AND organizer_id = %s;
            """, [event_title, event_datetime, venue_id, event_id, organizer_id])

        else:
            return False

    return True


def get_all_events():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                e.event_id,
                e.event_title,
                e.event_datetime,
                v.venue_name,
                o.organizer_name
            FROM EVENT e
            JOIN VENUE v ON e.venue_id = v.venue_id
            JOIN ORGANIZER o ON e.organizer_id = o.organizer_id;
        """)

        return dictfetchall(cursor)


def get_event_by_id(event_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                e.event_id,
                e.event_title,
                e.event_datetime,
                v.venue_name,
                o.organizer_name
            FROM EVENT e
            JOIN VENUE v ON e.venue_id = v.venue_id
            JOIN ORGANIZER o ON e.organizer_id = o.organizer_id
            WHERE e.event_id = %s;
        """, [event_id])

        result = dictfetchall(cursor)

    return result[0] if result else None


def get_events_by_organizer(session_id):
    with connection.cursor() as cursor:
        user_id, roles = _get_user_roles(cursor, session_id)

        if not user_id or "organizer" not in roles:
            return []

        cursor.execute("""
            SELECT organizer_id
            FROM ORGANIZER
            WHERE user_id = %s;
        """, [user_id])

        result = cursor.fetchone()
        if not result:
            return []

        organizer_id = result[0]

        cursor.execute("""
            SELECT event_id, event_title, event_datetime, venue_id
            FROM EVENT
            WHERE organizer_id = %s;
        """, [organizer_id])

        return dictfetchall(cursor)
