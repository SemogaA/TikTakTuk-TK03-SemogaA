from django.db import connection, transaction
from .utils import dictfetchall
from .user import validate_session, get_user_role_by_session
import uuid


def create_order(session_id, items, promo_code=None):
    """
    note: hanya customer yang bisa bikin pesanan.
    items format: [{'category_id': 'uuid', 'quantity': 2, 'seat_ids': ['uuid1', 'uuid2']}]
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'customer':
            return False, "Sesi tidak valid atau Anda bukan customer."

        cursor.execute(
            "SELECT customer_id FROM CUSTOMER WHERE user_id = %s;", [user_id])
        res = cursor.fetchone()
        if not res:
            return False, "Customer tidak ditemukan."
        customer_id = res[0]

        total_price = 0

        try:
            with transaction.atomic():
                # 1. validasi kuota dan kursi per item
                for item in items:
                    cat_id = item['category_id']
                    qty = item['quantity']
                    seat_ids = item.get('seat_ids', [])

                    cursor.execute(
                        "SELECT quota, price, tevent_id FROM TICKET_CATEGORY WHERE category_id = %s;", [cat_id])
                    cat_data = cursor.fetchone()
                    if not cat_data:
                        raise Exception("Kategori tiket tidak ditemukan")
                    quota, price, event_id = cat_data

                    # cek tipe seating venue
                    cursor.execute("""
                        SELECT v.seating_type FROM EVENT e 
                        JOIN VENUE v ON e.venue_id = v.venue_id 
                        WHERE e.event_id = %s;
                    """, [event_id])
                    seating_type = cursor.fetchone()[0]

                    if seating_type == 'reserved' and len(seat_ids) != qty:
                        raise Exception("Jumlah kursi yang dipilih harus sama dengan jumlah tiket untuk venue reserved seating!")

                    # cek ketersediaan kuota berjalan (abaikan yang dicancel)
                    cursor.execute("""
                        SELECT COUNT(*) FROM TICKET t
                        JOIN "ORDER" o ON t.torder_id = o.order_id
                        WHERE t.tcategory_id = %s AND o.payment_status != 'Cancelled';
                    """, [cat_id])
                    sold_tickets = cursor.fetchone()[0]

                    if (sold_tickets + qty) > quota:
                        raise Exception("Sisa kuota tiket tidak mencukupi")

                    total_price += float(price) * qty

                # 2. Kalkulasi promo (HANYA MENGAMBIL DATA, VALIDASI DILAKUKAN OLEH TRIGGER POSTGRESQL NANTI)
                discount = 0
                promotion_id = None

                if promo_code:
                    cursor.execute("""
                        SELECT promotion_id, discount_type, discount_value 
                        FROM PROMOTION 
                        WHERE promo_code = %s;
                    """, [promo_code])
                    promo_data = cursor.fetchone()

                    if not promo_data:
                        raise Exception("Kode promo tidak ditemukan.")
                    
                    promo_id, d_type, d_value = promo_data
                    promotion_id = promo_id

                    if d_type == 'NOMINAL':
                        discount = float(d_value)
                    elif d_type == 'PERCENTAGE':
                        discount = total_price * (float(d_value) / 100.0)

                total_amount = max(0, total_price - discount)

                # 3. insert tabel order (default status pending)
                cursor.execute("""
                    INSERT INTO "ORDER" (payment_status, total_amount, customer_id)
                    VALUES ('Pending', %s, %s) RETURNING order_id;
                """, [total_amount, customer_id])
                order_id = cursor.fetchone()[0]

                # 4. generate tiket dan insert kursi (HARUS DILAKUKAN SEBELUM PROMO AGAR TRIGGER BISA MENCARI TANGGAL EVENT)
                for item in items:
                    cat_id = item['category_id']
                    qty = item['quantity']
                    seat_ids = item.get('seat_ids', [])

                    for i in range(qty):
                        ticket_code = f"TKT-{str(uuid.uuid4())[:8].upper()}"

                        cursor.execute("""
                            INSERT INTO TICKET (ticket_code, tcategory_id, torder_id)
                            VALUES (%s, %s, %s) RETURNING ticket_id;
                        """, [ticket_code, cat_id, order_id])
                        ticket_id = cursor.fetchone()[0]

                        # mapping kursi untuk venue reserved
                        if seat_ids:
                            cursor.execute("""
                                INSERT INTO HAS_RELATIONSHIP (seat_id, ticket_id)
                                VALUES (%s, %s);
                            """, [seat_ids[i], ticket_id])

                # 5. Insert relasi promo jika ada (INI AKAN MEMICU TRIGGER POSTGRESQL!)
                if promotion_id:
                    cursor.execute("""
                        INSERT INTO ORDER_PROMOTION (order_promotion_id, promotion_id, order_id)
                        VALUES (%s, %s, %s);
                    """, [str(uuid.uuid4()), promotion_id, order_id])

                return True, order_id
                
        except Exception as e:
            # 6. Menangkap RAISE EXCEPTION dari PostgreSQL
            error_message = str(e).split('\n')[0]
            
            # Menghapus prefix "ERROR:" bawaan Postgres agar rapi di UI
            if "ERROR:" in error_message:
                error_message = error_message.split("ERROR:")[1].strip()
                
            print(f"Error order creation: {error_message}")
            return False, error_message


def get_all_orders(session_id):
    """
    note: view order list & rangkuman sesuai role dan requirements tambahan.
    """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)
        if not user_id:
            return None

        # inisialisasi default variable
        base_query = ""
        summary_query = ""
        params = []
        summary = {}

        if role == 'administrator':
            # query summary admin (semua order)
            summary_query = """
                SELECT 
                    COUNT(*) as total_order,
                    SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as lunas,
                    SUM(CASE WHEN payment_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                    COALESCE(SUM(CASE WHEN payment_status = 'Paid' THEN total_amount ELSE 0 END), 0) as total_revenue
                FROM "ORDER";
            """

            # query list order admin
            base_query = """
                SELECT DISTINCT
                    o.order_id, o.order_date, o.payment_status, o.total_amount,
                    c.full_name AS customer_name,
                    e.event_title, v.venue_name
                FROM "ORDER" o
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                ORDER BY o.order_date DESC;
            """

        elif role == 'organizer':
            cursor.execute(
                "SELECT organizer_id FROM ORGANIZER WHERE user_id = %s;", [user_id])
            org_res = cursor.fetchone()
            if not org_res:
                return None
            org_id = org_res[0]
            params = [org_id]

            # query summary organizer (hanya event miliknya, revenue hanya dihitung dari order Paid)
            summary_query = """
                SELECT 
                    COUNT(DISTINCT o.order_id) as total_order,
                    SUM(CASE WHEN o.payment_status = 'Paid' THEN 1 ELSE 0 END) as lunas,
                    SUM(CASE WHEN o.payment_status = 'Pending' THEN 1 ELSE 0 END) as pending,
                    COALESCE(SUM(CASE WHEN o.payment_status = 'Paid' THEN o.total_amount ELSE 0 END), 0) as total_revenue
                FROM "ORDER" o
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                WHERE e.organizer_id = %s;
            """

            # query list order organizer
            base_query = """
                SELECT DISTINCT
                    o.order_id, o.order_date, o.payment_status, o.total_amount,
                    c.full_name AS customer_name,
                    e.event_title, v.venue_name
                FROM "ORDER" o
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                WHERE e.organizer_id = %s
                ORDER BY o.order_date DESC;
            """

        elif role == 'customer':
            cursor.execute(
                "SELECT customer_id FROM CUSTOMER WHERE user_id = %s;", [user_id])
            cust_res = cursor.fetchone()
            if not cust_res:
                return None
            cust_id = cust_res[0]
            params = [cust_id]

            # query summary customer (tanpa revenue)
            summary_query = """
                SELECT 
                    COUNT(*) as total_order,
                    SUM(CASE WHEN payment_status = 'Paid' THEN 1 ELSE 0 END) as lunas,
                    SUM(CASE WHEN payment_status = 'Pending' THEN 1 ELSE 0 END) as pending
                FROM "ORDER"
                WHERE customer_id = %s;
            """

            # query list order customer
            base_query = """
                SELECT DISTINCT
                    o.order_id, o.order_date, o.payment_status, o.total_amount,
                    c.full_name AS customer_name,
                    e.event_title, v.venue_name
                FROM "ORDER" o
                JOIN CUSTOMER c ON o.customer_id = c.customer_id
                JOIN TICKET t ON o.order_id = t.torder_id
                JOIN TICKET_CATEGORY tc ON t.tcategory_id = tc.category_id
                JOIN EVENT e ON tc.tevent_id = e.event_id
                JOIN VENUE v ON e.venue_id = v.venue_id
                WHERE o.customer_id = %s
                ORDER BY o.order_date DESC;
            """
        else:
            return None

        # eksekusi query summary
        cursor.execute(summary_query, params)
        summary_result = dictfetchall(cursor)
        if summary_result:
            summary = summary_result[0]

            # format revenue khusus untuk role yg punya revenue
            if 'total_revenue' in summary:
                summary['total_revenue'] = float(summary['total_revenue'])

        # eksekusi query list
        cursor.execute(base_query, params)
        order_list = dictfetchall(cursor)

        return {
            "summary": summary,
            "list_order": order_list
        }


def get_order_by_id(session_id, order_id):
    """ read detail 1 order """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        if not user_id:
            return None

        cursor.execute("""
            SELECT o.order_id, o.order_date, o.payment_status, o.total_amount, c.full_name
            FROM "ORDER" o JOIN CUSTOMER c ON o.customer_id = c.customer_id
            WHERE o.order_id = %s;
        """, [order_id])
        result = dictfetchall(cursor)
        return result[0] if result else None


def update_order(session_id, order_id, payment_status):
    """ note: hanya admin yang bisa ubah status """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False

        cursor.execute("""
            UPDATE "ORDER" SET payment_status = %s WHERE order_id = %s;
        """, [payment_status, order_id])
    return True


def delete_order(session_id, order_id):
    """ note: hanya admin yang bisa hapus """
    with connection.cursor() as cursor:
        user_id = validate_session(session_id)
        role = get_user_role_by_session(session_id)

        if not user_id or role != 'administrator':
            return False

        cursor.execute(
            "DELETE FROM \"ORDER\" WHERE order_id = %s;", [order_id])
    return True

def get_checkout_data(event_id):
    """
    Ambil semua data untuk halaman checkout.
    Return dict berisi event, categories, seats — atau None jika event tidak ada.
    """
    with connection.cursor() as cursor:
        # Info event + venue
        cursor.execute("""
            SELECT e.event_id, e.event_title, e.event_datetime,
                   v.venue_id, v.venue_name, v.city, v.seating_type,
                   STRING_AGG(DISTINCT a.name, ', ') AS daftar_artis
            FROM EVENT e
            JOIN VENUE v ON e.venue_id = v.venue_id
            LEFT JOIN EVENT_ARTIST ea ON e.event_id = ea.event_id
            LEFT JOIN ARTIST a ON ea.artist_id = a.artist_id
            WHERE e.event_id = %s
            GROUP BY e.event_id, v.venue_id, v.venue_name, v.city, v.seating_type;
        """, [event_id])
        event = dictfetchall(cursor)
        if not event:
            return None
        event = event[0]

        # Kategori tiket + sisa kuota (abaikan order cancelled)
        cursor.execute("""
            SELECT tc.category_id, tc.category_name, tc.price, tc.quota,
                   COALESCE((
                       SELECT COUNT(*) FROM TICKET t
                       JOIN "ORDER" o ON t.torder_id = o.order_id
                       WHERE t.tcategory_id = tc.category_id
                         AND o.payment_status != 'Cancelled'
                   ), 0) AS sold
            FROM TICKET_CATEGORY tc
            WHERE tc.tevent_id = %s
            ORDER BY tc.price DESC;
        """, [event_id])
        categories = dictfetchall(cursor)

        for cat in categories:
            cat['remaining'] = int(cat['quota']) - int(cat['sold'])
            cat['price']     = int(cat['price'])

        # Seat list (hanya jika reserved seating)
        seats = []
        if event['seating_type'] == 'reserved':
            cursor.execute("""
                SELECT s.seat_id, s.section, s.row_number, s.seat_number,
                       CASE WHEN hr.seat_id IS NOT NULL THEN true ELSE false END AS is_taken
                FROM SEAT s
                LEFT JOIN HAS_RELATIONSHIP hr ON s.seat_id = hr.seat_id
                WHERE s.venue_id = %s
                ORDER BY s.section, s.row_number, s.seat_number::int;
            """, [event['venue_id']])
            seats = dictfetchall(cursor)

        return {
            'event':      event,
            'categories': categories,
            'seats':      seats,
        }


def validate_promo_only(promo_code, total_price):
    """
    Validasi kode promo sederhana untuk AJAX.
    Validasi limit dan tanggal sengaja dihapus di sini agar 
    Trigger PostgreSQL bisa mengambil alih saat tombol 'Bayar Sekarang' ditekan.
    """
    with connection.cursor() as cursor:
        # Kita hapus filter 'BETWEEN start_date AND end_date' agar Python meloloskan promo expired
        cursor.execute("""
            SELECT promotion_id, promo_code, discount_type, discount_value 
            FROM PROMOTION
            WHERE UPPER(promo_code) = UPPER(%s);
        """, [promo_code])
        row = cursor.fetchone()

        if not row:
            return 0, None, 'Kode promo tidak ditemukan.'

        promo_id, code, d_type, d_value = row

        d_value = float(d_value)
        if d_type == 'NOMINAL':
            diskon = d_value
        else:  # PERCENTAGE
            diskon = total_price * (d_value / 100.0)

        promo_data = {
            'promotion_id':  promo_id,
            'promo_code':    code,
            'discount_type': d_type,
            'discount_value': d_value,
        }
        return diskon, promo_data, None