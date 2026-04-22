from django.db import connection
from .utils import dictfetchall


def create_venue(venue_name, capacity, address, city):
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO VENUE (venue_name, capacity, address, city)
            VALUES (%s, %s, %s, %s)
            RETURNING venue_id;
        """, [venue_name, capacity, address, city])

        return cursor.fetchone()[0]


def update_venue(venue_id, venue_name, capacity, address, city):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE VENUE
            SET venue_name = %s,
                capacity = %s,
                address = %s,
                city = %s
            WHERE venue_id = %s;
        """, [venue_name, capacity, address, city, venue_id])

    return True


def delete_venue(venue_id):
    with connection.cursor() as cursor:
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
