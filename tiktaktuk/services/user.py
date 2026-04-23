from django.db import connection, transaction
from datetime import datetime, timedelta
from .utils import dictfetchall
import bcrypt


def register_user_atomic(username, password, role_name, profile_data):
    """
    ngehandle pendaftaran user sekaligus profile dalam satu transaksi.
    """
    hashed_password = bcrypt.hashpw(
        password.encode(), bcrypt.gensalt()).decode()

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Create User Account
                cursor.execute("""
                    INSERT INTO USER_ACCOUNT (username, password)
                    VALUES (%s, %s) RETURNING user_id;
                """, [username, hashed_password])
                user_id = cursor.fetchone()[0]

                # Get Role ID & Assign Role
                cursor.execute(
                    "SELECT role_id FROM ROLE WHERE role_name = %s;", [role_name])
                role_id = cursor.fetchone()[0]

                cursor.execute("""
                    INSERT INTO ACCOUNT_ROLE (user_id, role_id)
                    VALUES (%s, %s);
                """, [user_id, role_id])

                # Create Profile berdasarkan Role
                if role_name == 'customer':
                    cursor.execute("""
                        INSERT INTO CUSTOMER (full_name, phone_number, user_id)
                        VALUES (%s, %s, %s);
                    """, [profile_data['full_name'], profile_data['phone_number'], user_id])
                elif role_name == 'organizer':
                    cursor.execute("""
                        INSERT INTO ORGANIZER (organizer_name, contact_email, user_id)
                        VALUES (%s, %s, %s);
                    """, [profile_data['organizer_name'], profile_data['contact_email'], user_id])

                return user_id
    except Exception as e:
        print(f"Error during registration: {e}")
        return None


def login_user(username, password):
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT user_id, password FROM USER_ACCOUNT WHERE username = %s;", [username])
        user = cursor.fetchone()

        if not user or not bcrypt.checkpw(password.encode(), user[1].encode()):
            return None

        user_id = user[0]

        # hapus session si user ini yang udah expired atau udah dilogout (bersihin session lama)
        cursor.execute("""
            DELETE FROM USER_SESSION 
            WHERE user_id = %s AND (expires_at <= CURRENT_TIMESTAMP OR is_active = FALSE);
        """, [user_id])

        # Set expiry 24 jam ke depan
        expires_at = datetime.now() + timedelta(hours=24)

        cursor.execute("""
            INSERT INTO USER_SESSION (user_id, expires_at)
            VALUES (%s, %s) RETURNING session_id;
        """, [user_id, expires_at])
        session_id = cursor.fetchone()[0]

        # Ambil semua role user
        cursor.execute("""
            SELECT r.role_name FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id WHERE ar.user_id = %s;
        """, [user_id])
        roles = [row[0] for row in cursor.fetchall()]

    return {"session_id": str(session_id), "user_id": str(user_id), "roles": roles}


def get_dashboard_data(session_id):
    """
    menarik data dashboard sesuai dengan spesifikasi tiap role (Admin, Organizer, Customer).
    """
    with connection.cursor() as cursor:
        # Validasi Session & Ambil Username
        cursor.execute("""
            SELECT u.user_id, u.username 
            FROM USER_SESSION s
            JOIN USER_ACCOUNT u ON s.user_id = u.user_id
            WHERE s.session_id = %s AND s.is_active = TRUE AND s.expires_at > CURRENT_TIMESTAMP;
        """, [session_id])
        session = cursor.fetchone()

        if not session:
            return None

        user_id, username = session

        cursor.execute("""
            SELECT r.role_name FROM ACCOUNT_ROLE ar 
            JOIN ROLE r ON ar.role_id = r.role_id WHERE ar.user_id = %s;
        """, [user_id])
        roles = [row[0] for row in cursor.fetchall()]

        dashboard = {
            "username": username,
            "roles": roles
        }

        # dashboard administrator
        if 'administrator' in roles:
            cursor.execute("SELECT COUNT(*) FROM USER_ACCOUNT;")
            tot_pengguna = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM EVENT;")
            tot_acara = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COALESCE(SUM(total_amount), 0) FROM \"ORDER\" WHERE payment_status = 'Paid';")
            omset = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM PROMOTION WHERE CURRENT_DATE BETWEEN start_date AND end_date;")
            promo_aktif = cursor.fetchone()[0]

            cursor.execute("""
                SELECT 
                    COUNT(*) AS total_venue,
                    SUM(CASE WHEN seating_type = 'reserved' THEN 1 ELSE 0 END) AS reserved_seating,
                    COALESCE(MAX(capacity), 0) AS kapasitas_terbesar
                FROM VENUE;
            """)
            infrastruktur = dictfetchall(cursor)[0]

            cursor.execute("""
                SELECT 
                    SUM(CASE WHEN discount_type = 'PERCENTAGE' THEN 1 ELSE 0 END) AS promo_persentase,
                    SUM(CASE WHEN discount_type = 'NOMINAL' THEN 1 ELSE 0 END) AS promo_nominal
                FROM PROMOTION;
            """)
            marketing_tipe = dictfetchall(cursor)[0]

            cursor.execute("SELECT COUNT(*) FROM ORDER_PROMOTION;")
            penggunaan_promo = cursor.fetchone()[0]

            dashboard['admin'] = {
                "statistik_utama": {
                    "total_pengguna": tot_pengguna,
                    "total_acara": tot_acara,
                    "omset_platform": float(omset),
                    "promosi_aktif": promo_aktif
                },
                "infrastruktur_venue": infrastruktur,
                "marketing_promosi": {
                    "promo_persentase": marketing_tipe['promo_persentase'],
                    "promo_potongan_nominal": marketing_tipe['promo_nominal'],
                    "total_penggunaan": penggunaan_promo
                }
            }

        # dashboard organizer
        if 'organizer' in roles:
            # Cari Organizer ID dulu
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_data = cursor.fetchone()
            if org_data:
                org_id = org_data[0]

                # Rangkuman Organizer
                cursor.execute(
                    "SELECT COUNT(*) FROM EVENT WHERE organizer_id = %s AND event_datetime >= NOW();", [org_id])
                acara_aktif = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(t.ticket_id) FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                    JOIN EVENT e ON tc.tevent_id = e.event_id
                    WHERE e.organizer_id = %s AND o.payment_status = 'Paid';
                """, [org_id])
                tiket_terjual = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COALESCE(SUM(total_amount), 0) FROM "ORDER" 
                    WHERE payment_status = 'Paid' AND order_id IN (
                        SELECT DISTINCT torder_id FROM TICKET t
                        JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                        JOIN EVENT e ON tc.tevent_id = e.event_id
                        WHERE e.organizer_id = %s
                    );
                """, [org_id])
                revenue = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(DISTINCT venue_id) FROM EVENT WHERE organizer_id = %s;", [org_id])
                venue_mitra = cursor.fetchone()[0]

                # List Performa Acara (Nama, % Penjualan, Lokasi, Label LIVE)
                cursor.execute("""
                    SELECT 
                        e.event_title,
                        v.venue_name AS lokasi,
                        CASE 
                            WHEN e.event_datetime::date = CURRENT_DATE THEN 'LIVE'
                            WHEN e.event_datetime > CURRENT_TIMESTAMP THEN 'UPCOMING'
                            ELSE 'PAST'
                        END as status_label,
                        COALESCE(
                            ROUND(
                                (SELECT COUNT(t.ticket_id) FROM TICKET t JOIN TICKET_CATEGORY tc2 ON t.tcategory_id = tc2.category_id JOIN "ORDER" o2 ON t.torder_id = o2.order_id WHERE tc2.tevent_id = e.event_id AND o2.payment_status = 'Paid') * 100.0 / 
                                NULLIF((SELECT SUM(quota) FROM TICKET_CATEGORY tc3 WHERE tc3.tevent_id = e.event_id), 0)
                            , 1)
                        , 0) AS persentase_penjualan
                    FROM EVENT e
                    JOIN VENUE v ON e.venue_id = v.venue_id
                    WHERE e.organizer_id = %s
                    ORDER BY e.event_datetime DESC;
                """, [org_id])
                performa_acara = dictfetchall(cursor)

                dashboard['organizer'] = {
                    "acara_aktif": acara_aktif,
                    "tiket_terjual": tiket_terjual,
                    "revenue": float(revenue),
                    "venue_mitra": venue_mitra,
                    "performa_acara": performa_acara
                }

        # dashboard customer
        if 'customer' in roles:
            # Cari Customer ID dulu
            cursor.execute(
                "SELECT customer_id FROM CUSTOMER WHERE user_id = %s;", [user_id])
            cust_data = cursor.fetchone()
            if cust_data:
                cust_id = cust_data[0]

                # Rangkuman Customer
                cursor.execute("""
                    SELECT COUNT(t.ticket_id) FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                    JOIN EVENT e ON tc.tevent_id = e.event_id
                    WHERE o.customer_id = %s AND o.payment_status = 'Paid' AND e.event_datetime > NOW();
                """, [cust_id])
                tiket_aktif = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(DISTINCT e.event_id) FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                    JOIN EVENT e ON tc.tevent_id = e.event_id
                    WHERE o.customer_id = %s AND o.payment_status = 'Paid';
                """, [cust_id])
                acara_diikuti = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COUNT(*) FROM PROMOTION WHERE CURRENT_DATE BETWEEN start_date AND end_date;")
                promo_tersedia = cursor.fetchone()[0]

                cursor.execute(
                    "SELECT COALESCE(SUM(total_amount), 0) FROM \"ORDER\" WHERE customer_id = %s AND payment_status = 'Paid';", [cust_id])
                total_belanja = cursor.fetchone()[0]

                # List Tiket Mendatang (Nama Pertunjukan, Tanggal, Lokasi, Label WVIP/General)
                cursor.execute("""
                    SELECT 
                        e.event_title AS nama_pertunjukan,
                        e.event_datetime AS tanggal,
                        v.venue_name AS lokasi,
                        tc.category_name AS tiket_label
                    FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                    JOIN EVENT e ON tc.tevent_id = e.event_id
                    JOIN VENUE v ON e.venue_id = v.venue_id
                    WHERE o.customer_id = %s AND o.payment_status = 'Paid' AND e.event_datetime > NOW()
                    ORDER BY e.event_datetime ASC;
                """, [cust_id])
                tiket_mendatang = dictfetchall(cursor)

                dashboard['customer'] = {
                    "tiket_aktif": tiket_aktif,
                    "acara_diikuti": acara_diikuti,
                    "kode_promo_tersedia": promo_tersedia,
                    "total_belanja": float(total_belanja),
                    "tiket_mendatang": tiket_mendatang
                }

    return dashboard


def get_user_roles(user_id):
    """
    helper buat ngambil list role dari user_id tertentu.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.role_name 
            FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id 
            WHERE ar.user_id = %s;
        """, [user_id])

        roles = [row[0] for row in cursor.fetchall()]

    return roles


def get_user_roles_by_session(session_id):
    """
    helper buat ngambil list role langsung pakai session_id.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.role_name 
            FROM USER_SESSION s
            JOIN ACCOUNT_ROLE ar ON s.user_id = ar.user_id
            JOIN ROLE r ON ar.role_id = r.role_id 
            WHERE s.session_id = %s 
              AND s.is_active = TRUE 
              AND s.expires_at > CURRENT_TIMESTAMP;
        """, [session_id])

        roles = [row[0] for row in cursor.fetchall()]

    return roles


def logout_user(session_id):
    """
    ngehandle flow logout.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE USER_SESSION
            SET is_active = FALSE
            WHERE session_id = %s;
        """, [session_id])

    return True


def validate_session(session_id):
    """
    helper untuk check apakah session valid & belum expired.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id
            FROM USER_SESSION
            WHERE session_id = %s 
              AND is_active = TRUE 
              AND expires_at > CURRENT_TIMESTAMP;
        """, [session_id])
        result = cursor.fetchone()

    return result[0] if result else None


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
