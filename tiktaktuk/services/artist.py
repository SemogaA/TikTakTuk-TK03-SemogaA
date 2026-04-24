from django.db import connection, IntegrityError
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session


def create_artist(session_id, name, genre=None):
    """
    note: hanya Admin yang bisa nambah data artist.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        # Cek apakah user valid dan punya role 'administrator'
        if not user_id or role != "administrator":
            return None

        # Nama tidak boleh kosong (validasi ganda di backend)
        if not name or name.strip() == "":
            return None

        cursor.execute("""
            INSERT INTO ARTIST (name, genre)
            VALUES (%s, %s)
            RETURNING artist_id;
        """, [name, genre])

        return cursor.fetchone()[0]


def update_artist(session_id, artist_id, name, genre=None):
    """
    note: hanya Admin yang bisa ngedit data artist.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != "administrator":
            return False

        if not name or name.strip() == "":
            return False

        cursor.execute("""
            UPDATE ARTIST
            SET name = %s,
                genre = %s
            WHERE artist_id = %s;
        """, [name, genre, artist_id])

    return True


def delete_artist(session_id, artist_id):
    """
    note: hanya Admin yang bisa ngapus data artist.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != "administrator":
            return False

        try:
            cursor.execute("""
                DELETE FROM ARTIST
                WHERE artist_id = %s;
            """, [artist_id])
            return True
        except IntegrityError:
            return False


def get_all_artists():
    """
    note: bisa diakses Guest (tidak butuh session_id).
    table harus diurutkan berdasarkan Name secara ascending sesuai dokumen.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT artist_id, name, genre
            FROM ARTIST
            ORDER BY name ASC;
        """)

        return dictfetchall(cursor)


def get_artist_by_id(artist_id):
    """
    helper function buat narik spesifik 1 artist.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT artist_id, name, genre
            FROM ARTIST
            WHERE artist_id = %s;
        """, [artist_id])

        result = dictfetchall(cursor)

    return result[0] if result else None
