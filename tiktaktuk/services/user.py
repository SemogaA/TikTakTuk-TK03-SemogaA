from django.db import connection, transaction
from datetime import datetime, timedelta
from .utils import dictfetchall
import bcrypt
import re


def register_user_atomic(username, email, password, role_name, profile_data):
    """
    ngehandle pendaftaran user sekaligus profile dalam satu transaksi.
    profile_data: dict berisi {full_name, phone_number} atau {organizer_name}
    contact_email otomatis ngambil dari input email utama.
    """
    hashed_password = bcrypt.hashpw(
        password.encode(), bcrypt.gensalt()).decode()

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                # Create User Account
                cursor.execute("""
                    INSERT INTO USER_ACCOUNT (username, email, password)
                    VALUES (%s, %s, %s) RETURNING user_id;
                """, [username, email, hashed_password])
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
                    """, [profile_data['full_name'], profile_data.get('phone_number'), user_id])
                elif role_name == 'organizer':
                    cursor.execute("""
                        INSERT INTO ORGANIZER (organizer_name, contact_email, user_id)
                        VALUES (%s, %s, %s);
                    """, [profile_data['organizer_name'], email, user_id])

                return user_id
    except Exception as e:
        print(f"Error during registration: {e}")
        return None


def login_user(identifier, password):
    """
    pengguna memasukkan EMAIL atau USERNAME beserta password.
    identifier bisa berupa string email atau username.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT user_id, password 
            FROM USER_ACCOUNT 
            WHERE email = %s OR username = %s;
        """, [identifier, identifier])
        user = cursor.fetchone()

        if not user or not bcrypt.checkpw(password.encode(), user[1].encode()):
            return None

        user_id = user[0]

        cursor.execute("""
            DELETE FROM USER_SESSION 
            WHERE user_id = %s AND (expires_at <= CURRENT_TIMESTAMP OR is_active = FALSE);
        """, [user_id])

        expires_at = datetime.now() + timedelta(hours=24)

        cursor.execute("""
            INSERT INTO USER_SESSION (user_id, expires_at)
            VALUES (%s, %s) RETURNING session_id;
        """, [user_id, expires_at])
        session_id = cursor.fetchone()[0]

        cursor.execute("""
            SELECT r.role_name FROM ACCOUNT_ROLE ar
            JOIN ROLE r ON ar.role_id = r.role_id WHERE ar.user_id = %s LIMIT 1;
        """, [user_id])
        role_data = cursor.fetchone()
        role = role_data[0] if role_data else None

    return {"session_id": str(session_id), "user_id": str(user_id), "role": role}


def get_dashboard_data(session_id):
    """
    menarik data dashboard sesuai dengan role tunggal user (Admin, Organizer, atau Customer).
    """
    with connection.cursor() as cursor:
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
            JOIN ROLE r ON ar.role_id = r.role_id WHERE ar.user_id = %s LIMIT 1;
        """, [user_id])
        role_data = cursor.fetchone()

        if not role_data:
            return None

        role = role_data[0]

        dashboard = {
            "username": username,
            "role": role,
        }

        if role == 'administrator':
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

        elif role == 'organizer':
            cursor.execute(
                "SELECT organizer_id, organizer_name FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_data = cursor.fetchone()
            if org_data:
                org_id, org_name = org_data

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

                cursor.execute("""
                    SELECT 
                        e.event_id,
                        e.event_title,
                        v.venue_name AS lokasi,
                        CASE 
                            WHEN e.event_datetime::date = CURRENT_DATE THEN 'LIVE'
                            WHEN e.event_datetime > CURRENT_TIMESTAMP THEN 'UPCOMING'
                            ELSE 'PAST'
                        END as status_label,
                        COALESCE(
                            CEILING(
                                (SELECT COUNT(t.ticket_id) FROM TICKET t JOIN TICKET_CATEGORY tc2 ON t.tcategory_id = tc2.category_id JOIN "ORDER" o2 ON t.torder_id = o2.order_id WHERE tc2.tevent_id = e.event_id AND o2.payment_status = 'Paid') * 100.0 / 
                                NULLIF((SELECT SUM(quota) FROM TICKET_CATEGORY tc3 WHERE tc3.tevent_id = e.event_id), 0)
                            )
                        , 0) AS persentase_penjualan
                    FROM EVENT e
                    JOIN VENUE v ON e.venue_id = v.venue_id
                    WHERE e.organizer_id = %s
                    ORDER BY e.event_datetime DESC;
                """, [org_id])
                performa_acara = dictfetchall(cursor)

                dashboard['organizer'] = {
                    "organizer_name": org_name,
                    "acara_aktif": acara_aktif,
                    "tiket_terjual": tiket_terjual,
                    "revenue": float(revenue),
                    "venue_mitra": venue_mitra,
                    "performa_acara": performa_acara
                }

        elif role == 'customer':
            cursor.execute(
                "SELECT customer_id, full_name FROM CUSTOMER WHERE user_id = %s;", [user_id])
            cust_data = cursor.fetchone()
            if cust_data:
                cust_id, full_name = cust_data

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

                cursor.execute("""
                    SELECT 
                        e.event_title AS nama_pertunjukan,
                        e.event_datetime AS tanggal,
                        v.venue_name AS lokasi,
                        tc.category_name AS tiket_label,
                        COUNT(t.ticket_id) as jumlah_tiket,
                        array_agg(t.ticket_id::text) as list_ticket_id,
                        array_agg(t.ticket_code) as list_ticket_code
                    FROM TICKET t
                    JOIN "ORDER" o ON t.torder_id = o.order_id
                    JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                    JOIN EVENT e ON tc.tevent_id = e.event_id
                    JOIN VENUE v ON e.venue_id = v.venue_id
                    WHERE o.customer_id = %s AND o.payment_status = 'Paid' AND e.event_datetime > NOW()
                    GROUP BY e.event_title, e.event_datetime, v.venue_name, tc.category_name
                    ORDER BY e.event_datetime ASC;
                """, [cust_id])

                tiket_mendatang_raw = dictfetchall(cursor)
                tiket_mendatang = []
                for row in tiket_mendatang_raw:
                    detail_tiket = []
                    for i in range(row['jumlah_tiket']):
                        detail_tiket.append({
                            'id': row['list_ticket_id'][i],
                            'code': row['list_ticket_code'][i]
                        })
                    row['detail_tiket'] = detail_tiket
                    tiket_mendatang.append(row)

                dashboard['customer'] = {
                    "full_name": full_name,
                    "tiket_aktif": tiket_aktif,
                    "acara_diikuti": acara_diikuti,
                    "kode_promo_tersedia": promo_tersedia,
                    "total_belanja": float(total_belanja),
                    "tiket_mendatang": tiket_mendatang
                }

    return dashboard


def get_user_role_by_session(session_id):
    """
    helper buat ngambil string role langsung pakai session_id.
    """
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT r.role_name 
            FROM USER_SESSION s
            JOIN ACCOUNT_ROLE ar ON s.user_id = ar.user_id
            JOIN ROLE r ON ar.role_id = r.role_id 
            WHERE s.session_id = %s 
              AND s.is_active = TRUE 
              AND s.expires_at > CURRENT_TIMESTAMP
            LIMIT 1;
        """, [session_id])
        result = cursor.fetchone()
    return result[0] if result else None


def logout_user(session_id):
    with connection.cursor() as cursor:
        cursor.execute("""
            UPDATE USER_SESSION
            SET is_active = FALSE
            WHERE session_id = %s;
        """, [session_id])
    return True


def validate_session(session_id):
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

# ==============================================================
# FUNGSI PROFILE BARU (READ & UPDATE)
# ==============================================================


def get_profile_data(session_id):
    """Mengambil data profil lengkap berdasarkan role tunggal user."""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.user_id, u.username, u.email, r.role_name
            FROM USER_SESSION s
            JOIN USER_ACCOUNT u ON s.user_id = u.user_id
            JOIN ACCOUNT_ROLE ar ON u.user_id = ar.user_id
            JOIN ROLE r ON ar.role_id = r.role_id
            WHERE s.session_id = %s AND s.is_active = TRUE AND s.expires_at > CURRENT_TIMESTAMP
            LIMIT 1;
        """, [session_id])
        user = cursor.fetchone()

        if not user:
            return None

        user_id, username, email, role = user
        profile = {
            'username': username,
            'email': email,
            'role': role
        }

        # Tarik data ekstra sesuai role
        if role == 'customer':
            cursor.execute(
                "SELECT full_name, phone_number FROM CUSTOMER WHERE user_id = %s;", [user_id])
            cust = cursor.fetchone()
            if cust:
                profile['full_name'], profile['phone_number'] = cust
        elif role == 'organizer':
            cursor.execute(
                "SELECT organizer_name, contact_email FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org = cursor.fetchone()
            if org:
                profile['organizer_name'], profile['contact_email'] = org

        return profile


def update_profile_info(session_id, data):
    """menyimpan perubahan informasi profil (tanpa password)"""
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT u.user_id, r.role_name
            FROM USER_SESSION s
            JOIN USER_ACCOUNT u ON s.user_id = u.user_id
            JOIN ACCOUNT_ROLE ar ON u.user_id = ar.user_id
            JOIN ROLE r ON ar.role_id = r.role_id
            WHERE s.session_id = %s AND s.is_active = TRUE
        """, [session_id])
        user = cursor.fetchone()
        if not user:
            return False, "Session tidak valid."

        user_id, role = user
        email = data.get('email')

        try:
            # update Email di USER_ACCOUNT
            cursor.execute("UPDATE USER_ACCOUNT SET email = %s WHERE user_id = %s", [
                           email, user_id])

            # update Data Spesifik Role
            if role == 'customer':
                cursor.execute("UPDATE CUSTOMER SET full_name = %s, phone_number = %s WHERE user_id = %s",
                               [data.get('full_name'), data.get('phone_number'), user_id])
            elif role == 'organizer':
                cursor.execute("UPDATE ORGANIZER SET organizer_name = %s, contact_email = %s WHERE user_id = %s",
                               [data.get('organizer_name'), data.get('contact_email'), user_id])

            connection.commit()
            return True, "Informasi profil berhasil diperbarui."

        except Exception as e:
            connection.rollback()
            return False, f"Gagal update profil: Email mungkin sudah digunakan."


def change_user_password(session_id, old_password, new_password):
    """cek password lama dan mengupdate password baru."""
    with connection.cursor() as cursor:
        # ambil user_id dan password lama dari database
        cursor.execute("""
            SELECT u.user_id, u.password
            FROM USER_SESSION s
            JOIN USER_ACCOUNT u ON s.user_id = u.user_id
            WHERE s.session_id = %s AND s.is_active = TRUE
        """, [session_id])
        user = cursor.fetchone()

        if not user:
            return False, "Session tidak valid."
        user_id, hashed_old_password_db = user

        # cek apakah password lama yang dimasukkan cocok dengan di database
        if not bcrypt.checkpw(old_password.encode('utf-8'), hashed_old_password_db.encode('utf-8')):
            return False, "Password lama yang Anda masukkan salah!"

        # hash password baru dan Update
        try:
            hashed_new_pw = bcrypt.hashpw(new_password.encode(
                'utf-8'), bcrypt.gensalt()).decode('utf-8')
            cursor.execute("UPDATE USER_ACCOUNT SET password = %s WHERE user_id = %s", [
                           hashed_new_pw, user_id])
            connection.commit()
            return True, "Password berhasil diubah!"
        except Exception as e:
            connection.rollback()
            return False, "Terjadi kesalahan saat mengubah password."
