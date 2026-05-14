import datetime
from django.db import IntegrityError, connection, transaction
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session

def create_event(session_id, event_title, event_datetime, venue_id, description, image_url, artists, ticket_categories, organizer_id=None):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id:
            return False, "Sesi tidak valid, silakan login kembali.", None

        # validasi Organizer
        if role == "organizer":
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            res = cursor.fetchone()
            if not res:
                return False, "Akun Anda tidak terdaftar sebagai Organizer.", None
            org_id_to_use = res[0]
        elif role == "administrator":
            if not organizer_id:
                return False, "Admin harus menentukan Organizer untuk event ini.", None
            org_id_to_use = organizer_id
        else:
            return False, "Anda tidak memiliki akses untuk membuat event.", None

        # validasi Kapasitas Venue
        cursor.execute(
            "SELECT capacity FROM VENUE WHERE venue_id = %s;", [venue_id])
        venue_cap = cursor.fetchone()
        if not venue_cap:
            return False, "Venue yang dipilih tidak ditemukan.", None

        total_quota_requested = sum(
            int(tc['quota']) for tc in ticket_categories) if ticket_categories else 0
        if total_quota_requested > venue_cap[0]:
            return False, f"Gagal: Total kuota tiket ({total_quota_requested}) melebihi kapasitas maksimal venue ({venue_cap[0]}).", None

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

                return True, f"Event '{event_title}' berhasil dibuat!", event_id
        except Exception as e:
            # catch error dari trigger POSTGRESQL
            error_msg = str(e).split('\n')[0]
            return False, error_msg, None

def update_event(session_id, event_id, event_title, event_datetime, venue_id, description, image_url, artists=None, ticket_categories=None):
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id:
            return False, "Sesi tidak valid, silakan login kembali."

        try:
            with transaction.atomic():
                if role == "administrator":
                    cursor.execute("""
                        UPDATE EVENT SET event_title=%s, event_datetime=%s, venue_id=%s, description=%s, image_url=%s
                        WHERE event_id=%s;
                    """, [event_title, event_datetime, venue_id, description, image_url, event_id])
                elif role == "organizer":
                    cursor.execute(
                        "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
                    res = cursor.fetchone()
                    if not res:
                        return False, "Akun Anda tidak terdaftar sebagai Organizer."

                    cursor.execute("""
                        UPDATE EVENT SET event_title=%s, event_datetime=%s, venue_id=%s, description=%s, image_url=%s
                        WHERE event_id=%s AND organizer_id=%s;
                    """, [event_title, event_datetime, venue_id, description, image_url, event_id, res[0]])
                else:
                    return False, "Anda tidak memiliki izin untuk mengedit event ini."

                if artists is not None:
                    cursor.execute(
                        "DELETE FROM EVENT_ARTIST WHERE event_id = %s;", [event_id])
                    for artist in artists:
                        cursor.execute("""
                            INSERT INTO EVENT_ARTIST (event_id, artist_id, role)
                            VALUES (%s, %s, %s);
                        """, [event_id, artist['artist_id'], artist.get('role', 'Supporting')])

                if ticket_categories is not None:
                    try:
                        cursor.execute(
                            "DELETE FROM TICKET_CATEGORY WHERE tevent_id = %s;", [event_id])
                        for tc in ticket_categories:
                            cursor.execute("""
                                INSERT INTO TICKET_CATEGORY (category_name, quota, price, tevent_id)
                                VALUES (%s, %s, %s, %s);
                            """, [tc['category_name'], tc['quota'], tc['price'], event_id])
                    except IntegrityError:
                        return False, "Gagal mengedit kategori: Sudah ada tiket yang terjual untuk acara ini. Kategori tiket tidak dapat diubah."

                return True, "Perubahan event berhasil disimpan!"
        except Exception as e:
            # catch error dari trigger POSTGRESQL
            error_msg = str(e).split('\n')[0]
            return False, error_msg

def get_events(search_query=None, venue_id=None, artist_id=None, status='upcoming'):
    query = """
        SELECT e.event_id, e.event_title, e.event_datetime, e.image_url, e.description, e.venue_id,
               v.venue_name, v.city, o.organizer_name,
               COALESCE(MIN(tc.price), 0) AS harga_tiket_mulai,
               STRING_AGG(DISTINCT a.name, ', ') AS daftar_artis,
               STRING_AGG(DISTINCT a.artist_id::text, ',') AS daftar_artist_ids,
               STRING_AGG(DISTINCT tc.category_name, ', ') AS daftar_kategori_tiket,
               STRING_AGG(DISTINCT tc.category_name || '|' || tc.price || '|' || tc.quota, ';;') AS ticket_data
        FROM EVENT e
        JOIN VENUE v ON e.venue_id = v.venue_id
        JOIN ORGANIZER o ON e.organizer_id = o.organizer_id
        LEFT JOIN TICKET_CATEGORY tc ON e.event_id = tc.tevent_id
        LEFT JOIN EVENT_ARTIST ea ON e.event_id = ea.event_id
        LEFT JOIN ARTIST a ON ea.artist_id = a.artist_id
    """

    filters = []
    params = []

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    now_wib = now_utc + datetime.timedelta(hours=7)
    now_str = now_wib.strftime('%Y-%m-%d %H:%M:%S')

    sort_order = "ASC"

    if status == 'past':
        filters.append("e.event_datetime < %s")
        params.append(now_str)
        sort_order = "DESC"
    else:
        filters.append("e.event_datetime >= %s")
        params.append(now_str)
        sort_order = "ASC"

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

    query += f" GROUP BY e.event_id, v.venue_name, v.city, o.organizer_name ORDER BY e.event_datetime {sort_order};"

    with connection.cursor() as cursor:
        cursor.execute(query, params)
        events = dictfetchall(cursor)

        for event in events:
            event['artis_list'] = [a.strip() for a in event['daftar_artis'].split(
                ',')] if event['daftar_artis'] else []
            event['artist_ids'] = [a.strip() for a in event['daftar_artist_ids'].split(
                ',')] if event['daftar_artist_ids'] else []
            event['kategori_list'] = [k.strip() for k in event['daftar_kategori_tiket'].split(
                ',')] if event['daftar_kategori_tiket'] else []

            event['ticket_list_full'] = []
            if event['ticket_data']:
                for t in event['ticket_data'].split(';;'):
                    parts = t.split('|')
                    if len(parts) == 3:
                        event['ticket_list_full'].append(
                            {'name': parts[0], 'price': parts[1], 'quota': parts[2]})

        return events

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