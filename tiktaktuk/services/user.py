from django.db import connection
from .utils import dictfetchall
import bcrypt


def create_user_account(username, password):
    hashed_password = bcrypt.hashpw(
        password.encode(), bcrypt.gensalt()).decode()

    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO USER_ACCOUNT (username, password)
            VALUES (%s, %s)
            RETURNING user_id;
        """, [username, hashed_password])

        return cursor.fetchone()[0]


def assign_role_to_user(user_id, role_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ACCOUNT_ROLE (user_id, role_id)
            VALUES (%s, %s);
        """, [user_id, role_id])


def create_customer_profile(user_id, full_name, phone_number):
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO CUSTOMER (full_name, phone_number, user_id)
            VALUES (%s, %s, %s)
            RETURNING customer_id;
        """, [full_name, phone_number, user_id])

        return cursor.fetchone()[0]


def create_organizer_profile(user_id, organizer_name, contact_email):
    with connection.cursor() as cursor:
        cursor.execute("""
            INSERT INTO ORGANIZER (organizer_name, contact_email, user_id)
            VALUES (%s, %s, %s)
            RETURNING organizer_id;
        """, [organizer_name, contact_email, user_id])

        return cursor.fetchone()[0]


def login_user(username, password):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id, password
            FROM USER_ACCOUNT
            WHERE username = %s;
        """, [username])

        user = cursor.fetchone()

        if not user:
            return None

        user_id, hashed_password = user

        if not bcrypt.checkpw(password.encode(), hashed_password.encode()):
            return None

        cursor.execute("""
            INSERT INTO USER_SESSION (user_id)
            VALUES (%s)
            RETURNING session_id;
        """, [user_id])

        session_id = cursor.fetchone()[0]

        cursor.execute("""
            SELECT r.role_name
            FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id
            WHERE ar.user_id = %s;
        """, [user_id])

        roles = [row[0] for row in cursor.fetchall()]

    return {
        "session_id": session_id,
        "user_id": user_id,
        "username": username,
        "roles": roles
    }


def logout_user(session_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE USER_SESSION
            SET is_active = FALSE
            WHERE session_id = %s;
        """, [session_id])

    return True


def get_user_by_id(user_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id, username
            FROM USER_ACCOUNT
            WHERE user_id = %s;
        """, [user_id])

        result = dictfetchall(cursor)

    return result[0] if result else None


def get_all_users():
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id, username
            FROM USER_ACCOUNT;
        """)

        return dictfetchall(cursor)


def get_user_roles(user_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.role_name
            FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id
            WHERE ar.user_id = %s;
        """, [user_id])

        return [row[0] for row in cursor.fetchall()]


def validate_session(session_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id
            FROM USER_SESSION
            WHERE session_id = %s AND is_active = TRUE;
        """, [session_id])

        result = cursor.fetchone()

    return result[0] if result else None


def get_user_dashboard(session_id):
    with connection.cursor() as cursor:
        # validasi session
        cursor.execute("""
            SELECT user_id
            FROM USER_SESSION
            WHERE session_id = %s AND is_active = TRUE;
        """, [session_id])

        result = cursor.fetchone()
        if not result:
            return None

        user_id = result[0]

        # ambil role
        cursor.execute("""
            SELECT r.role_name
            FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id
            WHERE ar.user_id = %s;
        """, [user_id])

        roles = [row[0] for row in cursor.fetchall()]

        dashboard = {
            "user_id": user_id,
            "roles": roles
        }

        # customer dashboard
        if "customer" in roles:
            cursor.execute("""
                SELECT c.customer_id
                FROM CUSTOMER c
                WHERE c.user_id = %s;
            """, [user_id])

            customer = cursor.fetchone()

            if customer:
                customer_id = customer[0]

                cursor.execute("""
                    SELECT 
                        COUNT(o.order_id) AS total_orders,
                        COALESCE(SUM(o.total_amount), 0) AS total_spent
                    FROM "ORDER" o
                    WHERE o.customer_id = %s;
                """, [customer_id])

                data = dictfetchall(cursor)[0]
                dashboard["customer"] = data

        # organizer dashboard
        if "organizer" in roles:
            cursor.execute("""
                SELECT organizer_id
                FROM ORGANIZER
                WHERE user_id = %s;
            """, [user_id])

            organizer = cursor.fetchone()

            if organizer:
                organizer_id = organizer[0]

                cursor.execute("""
                    SELECT COUNT(event_id) AS total_events
                    FROM EVENT
                    WHERE organizer_id = %s;
                """, [organizer_id])

                total_events = dictfetchall(cursor)[0]["total_events"]

                cursor.execute("""
                    SELECT COUNT(t.ticket_id) AS total_tickets_sold
                    FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN CUSTOMER c ON o.customer_id = c.customer_id
                    JOIN ORGANIZER org ON org.user_id = %s
                    JOIN EVENT e ON e.organizer_id = org.organizer_id
                    JOIN TICKET_CATEGORY tc ON tc.category_id = t.tcategory_id
                    WHERE e.event_id = tc.tevent_id;
                """, [user_id])

                tickets = dictfetchall(cursor)[0]["total_tickets_sold"]

                dashboard["organizer"] = {
                    "total_events": total_events,
                    "total_tickets_sold": tickets
                }

        # admin dashboard
        if "administrator" in roles:
            cursor.execute("""
                SELECT COUNT(*) AS total_users
                FROM USER_ACCOUNT;
            """)
            total_users = dictfetchall(cursor)[0]["total_users"]

            cursor.execute("""
                SELECT COUNT(*) AS total_events
                FROM EVENT;
            """)
            total_events = dictfetchall(cursor)[0]["total_events"]

            cursor.execute("""
                SELECT COUNT(*) AS total_orders
                FROM "ORDER";
            """)
            total_orders = dictfetchall(cursor)[0]["total_orders"]

            dashboard["admin"] = {
                "total_users": total_users,
                "total_events": total_events,
                "total_orders": total_orders
            }

    return dashboard
