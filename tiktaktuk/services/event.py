from django.db import connection, transaction
from .utils import dictfetchall
from .user import validate_session, get_user_roles_by_session


def create_event(session_id, event_title, event_datetime, venue_id, description, image_url, artists, ticket_categories, organizer_id=None):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)
        if not user_id:
            return None

        # validasi Organizer
        if "organizer" in roles:
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            res = cursor.fetchone()
            if not res:
                return None
            org_id_to_use = res[0]
        elif "administrator" in roles:
            if not organizer_id:
                return None
            org_id_to_use = organizer_id
        else:
            return None

        # cek Kuota Tiket vs Kapasitas Venue
        cursor.execute(
            "SELECT capacity FROM VENUE WHERE venue_id = %s;", [venue_id])
        venue_cap = cursor.fetchone()
        if not venue_cap:
            return None

        total_quota_requested = sum(
            tc['quota'] for tc in ticket_categories) if ticket_categories else 0
        if total_quota_requested > venue_cap[0]:
            print(
                f"Error: Kuota tiket ({total_quota_requested}) melebihi kapasitas venue ({venue_cap[0]})!")
            return None

        try:
            with transaction.atomic():
                cursor.execute("""
                    INSERT INTO EVENT (event_title, event_datetime, venue_id, organizer_id, description, image_url)
                    VALUES (%s, %s, %s, %s, %s, %s) RETURNING event_id;
                """, [event_title, event_datetime, venue_id, org_id_to_use, description, image_url])
                event_id = cursor.fetchone()[0]

                # insert artists
                if artists:
                    for artist in artists:
                        cursor.execute("""
                            INSERT INTO EVENT_ARTIST (event_id, artist_id, role)
                            VALUES (%s, %s, %s);
                        """, [event_id, artist['artist_id'], artist.get('role', 'Supporting')])

                # insert ticket categories
                if ticket_categories:
                    for tc in ticket_categories:
                        cursor.execute("""
                            INSERT INTO TICKET_CATEGORY (category_name, quota, price, tevent_id)
                            VALUES (%s, %s, %s, %s);
                        """, [tc['category_name'], tc['quota'], tc['price'], event_id])

                return event_id
        except Exception as e:
            print(f"Error creating event: {e}")
            return None


def update_event(session_id, event_id, event_title, event_datetime, venue_id, description, image_url, artists=None):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        roles = get_user_roles_by_session(session_id)
        if not user_id:
            return False

        try:
            with transaction.atomic():
                if "administrator" in roles:
                    cursor.execute("""
                        UPDATE EVENT SET event_title=%s, event_datetime=%s, venue_id=%s, description=%s, image_url=%s
                        WHERE event_id=%s;
                    """, [event_title, event_datetime, venue_id, description, image_url, event_id])
                elif "organizer" in roles:
                    cursor.execute(
                        "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
                    res = cursor.fetchone()
                    if not res:
                        return False

                    cursor.execute("""
                        UPDATE EVENT SET event_title=%s, event_datetime=%s, venue_id=%s, description=%s, image_url=%s
                        WHERE event_id=%s AND organizer_id=%s;
                    """, [event_title, event_datetime, venue_id, description, image_url, event_id, res[0]])
                else:
                    return False

                if artists is not None:
                    cursor.execute(
                        "DELETE FROM EVENT_ARTIST WHERE event_id = %s;", [event_id])
                    for artist in artists:
                        cursor.execute("""
                            INSERT INTO EVENT_ARTIST (event_id, artist_id, role)
                            VALUES (%s, %s, %s);
                        """, [event_id, artist['artist_id'], artist.get('role', 'Supporting')])
                return True
        except Exception as e:
            print(e)
            return False


def get_events(search_query=None, venue_id=None, artist_id=None):
    query = """
        SELECT e.event_id, e.event_title, e.event_datetime, e.image_url,
               v.venue_name, o.organizer_name,
               COALESCE(MIN(tc.price), 0) AS harga_tiket_mulai,
               STRING_AGG(DISTINCT a.name, ', ') AS daftar_artis
        FROM EVENT e
        JOIN VENUE v ON e.venue_id = v.venue_id
        JOIN ORGANIZER o ON e.organizer_id = o.organizer_id
        LEFT JOIN TICKET_CATEGORY tc ON e.event_id = tc.tevent_id
        LEFT JOIN EVENT_ARTIST ea ON e.event_id = ea.event_id
        LEFT JOIN ARTIST a ON ea.artist_id = a.artist_id
    """
    filters, params = [], []

    if search_query:
        filters.append("(e.event_title ILIKE %s OR a.name ILIKE %s)")
        params.extend([f"%{search_query}%", f"%{search_query}%"])
    if venue_id:
        filters.append("e.venue_id = %s")
        params.append(venue_id)
    if artist_id:
        filters.append("ea.artist_id = %s")
        params.append(artist_id)

    if filters:
        query += " WHERE " + " AND ".join(filters)
    query += " GROUP BY e.event_id, v.venue_name, o.organizer_name ORDER BY e.event_datetime DESC;"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        return dictfetchall(cursor)


def get_event_by_id(event_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT e.*, v.venue_name, v.seating_type, o.organizer_name
            FROM EVENT e
            JOIN VENUE v ON e.venue_id = v.venue_id
            JOIN ORGANIZER o ON e.organizer_id = o.organizer_id
            WHERE e.event_id = %s;
        """, [event_id])
        event_result = dictfetchall(cursor)
        if not event_result:
            return None

        event_data = event_result[0]

        cursor.execute("""
            SELECT a.artist_id, a.name, ea.role
            FROM EVENT_ARTIST ea JOIN ARTIST a ON ea.artist_id = a.artist_id
            WHERE ea.event_id = %s;
        """, [event_id])
        event_data['artists'] = dictfetchall(cursor)

        cursor.execute(
            "SELECT * FROM TICKET_CATEGORY WHERE tevent_id = %s;", [event_id])
        event_data['ticket_categories'] = dictfetchall(cursor)

        return event_data
